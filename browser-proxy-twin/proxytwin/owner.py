"""Owner console: stands in for the WhatsApp message the shopkeeper receives."""
import argparse
import time

from .user_agent import Client


def main():
    ap = argparse.ArgumentParser(description="Answer booking requests for one shop.")
    ap.add_argument("--shop", required=True, help="the shop's card id")
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    args = ap.parse_args()
    client = Client(args.server)
    print(f"Waiting for requests for {args.shop} (Ctrl+C to stop)")
    try:
        while True:
            for hold in client.call("GET", f"/owner/{args.shop}/pending").get("pending", []):
                print(f"\nWhatsApp: new request, {hold['service']} on {hold['date']} at {hold['time']}.")
                accept = input("Confirm? [y/N] ").strip().lower() == "y"
                client.call("POST", f"/owner/{args.shop}/decision",
                            {"hold_id": hold["hold_id"], "accept": accept})
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
