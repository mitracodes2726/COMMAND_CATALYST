"""The user's agent: understands a request, finds shops, negotiates, books.

It never loads a web page. Every step is a small JSON message.
"""
import argparse
import datetime
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .vocab import detect_category


class Client:
    def __init__(self, base_url):
        self.base = base_url.rstrip("/")

    def call(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return json.loads(e.read().decode("utf-8"))


def parse_request(text, today=None):
    """Turn 'Book a haircut tomorrow evening' into a structured intent."""
    today = today or datetime.date.today()
    iso = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if iso:
        date = iso.group(0)
    elif re.search(r"\btoday\b", text, re.I):
        date = today.isoformat()
    else:
        date = (today + datetime.timedelta(days=1)).isoformat()
    pref = next((p for p, w in (("evening", r"evening|night"), ("morning", r"morning"),
                                ("afternoon", r"afternoon")) if re.search(w, text, re.I)), "any")
    return {"category": detect_category(text), "date": date, "pref": pref}


def fits(slot, pref):
    return (pref == "any" or (pref == "evening" and slot >= "16:00")
            or (pref == "morning" and slot < "12:00")
            or (pref == "afternoon" and "12:00" <= slot < "16:00"))


def choose_slot(slots, pref):
    """Best free slot: one inside the preferred window if possible."""
    for s in slots:
        if fits(s, pref):
            return s, True
    return (slots[0], False) if slots else (None, False)


def pick_service(card, text):
    for s in card["services"]:
        if s["name"].lower() in text.lower():
            return s["name"]
    return None


class UserAgent:
    def __init__(self, base_url, log=print, approve=None, owner_timeout=30.0, poll=0.25):
        self.client = Client(base_url)
        self.log = log
        self.approve = approve or (lambda summary: True)
        self.owner_timeout, self.poll = owner_timeout, poll
        self.messages = 0

    def _say(self, who, text):
        self.log(f"[{who}] {text}")

    def _send(self, shop_id, msg):
        self.messages += 2                       # one request and one reply
        return self.client.call("POST", f"/agents/{shop_id}/message", msg)

    def _result(self, status, **extra):
        return {"status": status, "messages": self.messages, "pages_loaded": 0, **extra}

    def book(self, text):
        intent = parse_request(text)
        self._say("user agent", f"understood: {intent['category']}, {intent['date']}, {intent['pref']}")
        if not intent["category"]:
            self._say("user agent", "I could not tell what kind of business you need.")
            return self._result("failed", reason="unknown category")

        found = self.client.call("GET", "/cards?category=" + urllib.parse.quote(intent["category"]))["cards"]
        self.messages += 2
        self._say("directory", f"{len(found)} {intent['category']} card(s) found")

        options = []
        for card in found:
            msg = {"type": "query", "date": intent["date"]}
            service = pick_service(card, text)
            if service:
                msg["service"] = service
            offer = self._send(card["id"], msg)
            if offer["type"] == "error":
                self._say(f"shop: {card['name']}", f"error {offer['code']}: {offer['message']}")
                continue
            slot, ok = choose_slot(offer["slots"], intent["pref"])
            if slot is None:
                self._say(f"shop: {card['name']}", "no free slots that day")
                continue
            note = "" if ok else f" (nothing free in the {intent['pref']})"
            self._say(f"shop: {card['name']}", f"{offer['service']} Rs {offer['price_inr']}, "
                      f"free {slot}{note}")
            options.append({"card": card, "offer": offer, "slot": slot, "fits": ok})

        options.sort(key=lambda o: (not o["fits"], o["offer"]["price_inr"], o["card"]["name"]))
        if options:
            self._say("user agent", f"best match: {options[0]['card']['name']}")

        for opt in options:
            card, offer, slot = opt["card"], opt["offer"], opt["slot"]
            hold = self._send(card["id"], {"type": "hold", "date": intent["date"], "time": slot,
                                           "service": offer["service"], "customer_ref": "user-1"})
            if hold["type"] == "error":
                self._say(f"shop: {card['name']}", f"{hold['code']}: {hold['message']}")
                continue
            self._say(f"shop: {card['name']}", "holding the slot, asking the owner to confirm")
            deadline = time.time() + self.owner_timeout
            while hold["status"] == "pending_owner" and time.time() < deadline:
                time.sleep(self.poll)
                hold = self._send(card["id"], {"type": "status", "hold_id": hold["hold_id"]})
            if hold["status"] == "pending_owner":
                self._send(card["id"], {"type": "cancel", "hold_id": hold["hold_id"]})
                self._say("user agent", "the owner did not reply in time, trying the next shop")
                continue
            if hold["status"] != "held":
                self._say("owner", f"{card['name']}: {hold['status']}, trying the next shop")
                continue
            self._say("owner", f"{card['name']}: confirmed {slot}")
            summary = {"shop": card["name"], "area": card["area"], "date": intent["date"],
                       "time": slot, "service": offer["service"], "price_inr": offer["price_inr"],
                       "bring": offer["required_documents"]}
            if not self.approve(summary):
                self._send(card["id"], {"type": "cancel", "hold_id": hold["hold_id"]})
                self._say("user", "cancelled, nothing was booked")
                return self._result("cancelled")
            booked = self._send(card["id"], {"type": "book", "hold_id": hold["hold_id"]})
            if booked["type"] == "booked":
                self._say("user agent", f"BOOKED {booked['booking_id']}: {booked['shop']}, "
                          f"{booked['date']} {booked['time']}, Rs {booked['price_inr']}")
                return self._result("booked", booking=booked)
            self._say("shop", f"{booked['code']}: {booked['message']}")
        self._say("user agent", "no shop could confirm. Try another time.")
        return self._result("failed", reason="no shop confirmed")


def console_approve(summary):
    print("\n  Approve this booking?")
    for k, v in summary.items():
        print(f"    {k}: {v}")
    return input("  [y/N] ").strip().lower() == "y"


def main():
    ap = argparse.ArgumentParser(description="Ask your agent to book something.")
    ap.add_argument("request", help='e.g. "Book a haircut tomorrow evening"')
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    ap.add_argument("--yes", action="store_true", help="approve automatically")
    ap.add_argument("--owner-timeout", type=float, default=60.0)
    args = ap.parse_args()
    agent = UserAgent(args.server, approve=None if args.yes else console_approve,
                      owner_timeout=args.owner_timeout)
    result = agent.book(args.request)
    print(f"\nresult: {result['status']} | messages: {result['messages']} | pages loaded: 0")


if __name__ == "__main__":
    main()
