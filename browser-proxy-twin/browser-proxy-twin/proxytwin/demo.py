"""One-command demo: publish shops, onboard one from Tamil text, then book.

The first owner to be asked declines, so you can watch the agent fall back to
the next shop. Run with:  ./run_demo.sh
"""
import argparse
import datetime
import json
import threading
import time
from pathlib import Path

from .onboard import parse_description, publish
from .server import Hub, make_server
from .user_agent import Client, UserAgent, console_approve

TAMIL_SAMPLE = ("நான் சலூன் நடத்துகிறேன், called Meena Beauty Parlour in Saibaba Colony. "
                "Haircut ₹150, facial ₹400. Open 10 am to 8 pm. Closed on Sunday. "
                "Languages: Tamil and English.")


def next_wednesday(today=None):
    today = today or datetime.date.today()
    return today + datetime.timedelta(days=(2 - today.weekday()) % 7 or 7)


class OwnerSimulator(threading.Thread):
    """Plays every shop owner. mode: decline-first | accept | decline."""

    def __init__(self, base, mode, log):
        super().__init__(daemon=True)
        self.client, self.mode, self.log = Client(base), mode, log
        self.seen, self.stop = 0, threading.Event()

    def run(self):
        while not self.stop.is_set():
            for card in self.client.call("GET", "/cards")["cards"]:
                pending = self.client.call("GET", f"/owner/{card['id']}/pending")["pending"]
                for hold in pending:
                    time.sleep(0.6)
                    self.seen += 1
                    accept = not (self.mode == "decline" or (self.mode == "decline-first" and self.seen == 1))
                    self.log(f"  [WhatsApp to {card['name']}] request for {hold['time']} -> "
                             f"{'CONFIRM' if accept else 'DECLINE'}")
                    self.client.call("POST", f"/owner/{card['id']}/decision",
                                     {"hold_id": hold["hold_id"], "accept": accept})
            time.sleep(0.2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the Browser Proxy Twin demo.")
    ap.add_argument("--date", default=next_wednesday().isoformat(), help="booking date, YYYY-MM-DD")
    ap.add_argument("--owner", default="decline-first", choices=["decline-first", "accept", "decline"])
    ap.add_argument("--interactive", action="store_true", help="ask you to approve the booking")
    args = ap.parse_args(argv)

    server = make_server("127.0.0.1", 0, Hub(hold_ttl=60))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    say = print

    say("== 1. Shops publish agent cards (no website needed) ==")
    for path in sorted((Path(__file__).resolve().parent.parent / "examples").glob("*.json")):
        card = json.loads(path.read_text(encoding="utf-8"))
        say(f"  published {card['name']} ({card['category']})  id={publish(card, base)}")

    say("\n== 2. A shopkeeper describes a shop in Tamil + English ==")
    say("  " + TAMIL_SAMPLE)
    card = parse_description(TAMIL_SAMPLE, "Coimbatore")
    say(f"  -> card: {card['name']} | {card['category']} | {card['area']} | "
        f"{[(s['name'], s['price_inr']) for s in card['services']]} | "
        f"{card['hours']['open']}-{card['hours']['close']} | closed {card['closed_days']}")
    say(f"  owner confirms the card, published with id={publish(card, base)}")

    say(f"\n== 3. The user asks their agent ({args.date}) ==")
    owner = OwnerSimulator(base, args.owner, say)
    owner.start()
    agent = UserAgent(base, log=lambda s: say("  " + s),
                      approve=console_approve if args.interactive else (lambda summary: True))
    result = agent.book(f"Book a haircut on {args.date} evening")
    owner.stop.set()

    say(f"\n== Result: {result['status'].upper()} | agent messages: {result['messages']} | "
        f"pages loaded: {result['pages_loaded']} ==")
    server.shutdown()
    return result


if __name__ == "__main__":
    main()
