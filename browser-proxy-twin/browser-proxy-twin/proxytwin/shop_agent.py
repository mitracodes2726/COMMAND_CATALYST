"""The shop's agent: answers from the card, locks slots, never double-books.

It only ever speaks from the published card. Anything that needs a human
(accepting a booking) is held until the owner decides.
"""
import threading
import time
import uuid

from .schema import CardError, slots_for

ACTIVE = ("pending_owner", "held", "booked")


class AgentError(Exception):
    STATUS = {"BAD_REQUEST": 400, "NOT_FOUND": 404, "SLOT_TAKEN": 409,
              "INVALID_STATE": 409, "HOLD_EXPIRED": 410, "RATE_LIMITED": 429}

    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message, self.status = code, message, self.STATUS[code]

    def payload(self):
        return {"type": "error", "code": self.code, "message": self.message}


class ShopAgent:
    def __init__(self, card, hold_ttl=120, clock=time.time):
        self.card = card
        self.ttl = hold_ttl
        self.clock = clock
        self._holds = {}
        self._lock = threading.Lock()

    # ---- protocol messages (user agent -> shop agent) ----
    def handle(self, msg):
        if not isinstance(msg, dict):
            raise AgentError("BAD_REQUEST", "message must be a JSON object")
        handlers = {"query": self._query, "hold": self._hold, "status": self._status,
                    "book": self._book, "cancel": self._cancel}
        handler = handlers.get(msg.get("type"))
        if handler is None:
            raise AgentError("BAD_REQUEST", f"unknown message type {msg.get('type')!r}")
        with self._lock:
            self._expire()
            return handler(msg)

    # ---- owner channel (stands in for WhatsApp) ----
    def owner_pending(self):
        with self._lock:
            self._expire()
            return [self._view(h) | {"customer_ref": h["customer_ref"]}
                    for h in self._holds.values() if h["status"] == "pending_owner"]

    def owner_decide(self, hold_id, accept):
        with self._lock:
            self._expire()
            hold = self._get(hold_id)
            if hold["status"] == "expired":
                raise AgentError("HOLD_EXPIRED", "the request expired before the owner replied")
            if hold["status"] != "pending_owner":
                raise AgentError("INVALID_STATE", f"hold is already {hold['status']}")
            hold["status"] = "held" if accept else "declined"
            if accept:
                hold["expires_at"] = self.clock() + self.ttl   # time for the user to approve
            return self._view(hold)

    # ---- internals (always called with the lock held) ----
    def _expire(self):
        now = self.clock()
        for h in self._holds.values():
            if h["status"] in ("pending_owner", "held") and now >= h["expires_at"]:
                h["status"] = "expired"

    def _taken(self, date, time_):
        return any(h["date"] == date and h["time"] == time_ and h["status"] in ACTIVE
                   for h in self._holds.values())

    def _day_slots(self, date):
        try:
            return slots_for(self.card, date)
        except CardError as e:
            raise AgentError("BAD_REQUEST", str(e))

    def _service(self, msg):
        wanted = msg.get("service")
        if not wanted:
            return self.card["services"][0]
        for s in self.card["services"]:
            if wanted.lower() in s["name"].lower():
                return s
        raise AgentError("BAD_REQUEST", f"unknown service {wanted!r}")

    def _get(self, hold_id):
        hold = self._holds.get(hold_id)
        if hold is None:
            raise AgentError("NOT_FOUND", f"no such hold {hold_id!r}")
        return hold

    def _view(self, h):
        live = h["status"] in ("pending_owner", "held")
        return {"type": "hold_result", "hold_id": h["hold_id"], "status": h["status"],
                "date": h["date"], "time": h["time"], "service": h["service"],
                "price_inr": h["price_inr"],
                "expires_in": max(0, int(h["expires_at"] - self.clock())) if live else 0}

    def _query(self, msg):
        date = msg.get("date")
        service = self._service(msg)
        free = [s for s in self._day_slots(date) if not self._taken(date, s)]
        return {"type": "offer", "shop": self.card["name"], "date": date,
                "service": service["name"], "price_inr": service["price_inr"],
                "slots": free, "required_documents": self.card["required_documents"],
                "languages": self.card["languages"]}

    def _hold(self, msg):
        date, time_ = msg.get("date"), msg.get("time")
        service = self._service(msg)
        if time_ not in self._day_slots(date):
            raise AgentError("BAD_REQUEST", f"{time_} is not an offered slot on {date}")
        if self._taken(date, time_):
            raise AgentError("SLOT_TAKEN", f"{time_} on {date} is no longer free")
        hold_id = uuid.uuid4().hex[:8]
        self._holds[hold_id] = {
            "hold_id": hold_id, "date": date, "time": time_, "service": service["name"],
            "price_inr": service["price_inr"], "status": "pending_owner",
            "expires_at": self.clock() + self.ttl,
            "customer_ref": str(msg.get("customer_ref", "anonymous"))[:40]}
        return self._view(self._holds[hold_id])

    def _status(self, msg):
        return self._view(self._get(msg.get("hold_id")))

    def _book(self, msg):
        hold = self._get(msg.get("hold_id"))
        if hold["status"] == "expired":
            raise AgentError("HOLD_EXPIRED", "the hold expired; ask for a new one")
        if hold["status"] != "booked":
            if hold["status"] != "held":
                raise AgentError("INVALID_STATE", f"hold is {hold['status']}; the owner has not confirmed")
            hold["status"] = "booked"
        return {"type": "booked", "booking_id": "BK-" + hold["hold_id"].upper(),
                "shop": self.card["name"], "date": hold["date"], "time": hold["time"],
                "service": hold["service"], "price_inr": hold["price_inr"],
                "required_documents": self.card["required_documents"]}

    def _cancel(self, msg):
        hold = self._get(msg.get("hold_id"))
        if hold["status"] in ACTIVE:
            hold["status"] = "cancelled"
        return {"type": "cancelled", "hold_id": hold["hold_id"], "status": hold["status"]}
