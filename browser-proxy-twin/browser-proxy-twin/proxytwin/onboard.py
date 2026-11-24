"""Shopkeeper onboarding: a description in, a validated agent card out.

Stands in for the WhatsApp voice-note flow. It is rule-based (no LLM yet), so
it understands simple English and Tamil/English descriptions. The owner always
sees the card and must confirm before it is published.
"""
import argparse
import json
import re
import sys

from .schema import WEEKDAYS, to_hhmm, validate_card
from .user_agent import Client
from .vocab import LANGUAGE_WORDS, detect_category


def _to24(hour, ampm):
    hour = int(hour)
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    return hour


def parse_description(text, city=""):
    name = re.search(r"(?:called|named)\s+([^.,]+?)(?=\s+in\s+[A-Z]|[.,]|$)", text, re.I)
    area = re.search(r"\bin\s+([A-Z][\w ]+?)(?:[.,]|$)", text)
    services = []
    for m in re.finditer(r"([A-Za-z][A-Za-z \-]{1,40}?)\s*(?:₹|Rs\.?\s*|rupees\s*)(\d+)", text):
        label = re.sub(r"^(and|then)\s+", "", m.group(1).strip(), flags=re.I)
        if label:
            services.append({"name": label[0].upper() + label[1:], "price_inr": int(m.group(2))})

    hours = {"open": "10:00", "close": "18:00"}
    h = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:to|-|till)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text, re.I)
    if h:
        end_ap = h.group(6).lower()
        start_ap = (h.group(3) or ("am" if int(h.group(1)) > int(h.group(4)) else end_ap)).lower()
        hours = {"open": to_hhmm(_to24(h.group(1), start_ap) * 60 + int(h.group(2) or 0)),
                 "close": to_hhmm(_to24(h.group(4), end_ap) * 60 + int(h.group(5) or 0))}

    closed = [d.capitalize() for d in re.findall(r"closed\s+(?:on\s+)?([A-Za-z]+day)", text, re.I)
              if d.capitalize() in WEEKDAYS]
    docs_match = re.search(r"documents?(?:\s+(?:needed|required))?\s*:\s*([^.]+)", text, re.I)
    docs = []
    if docs_match and not docs_match.group(1).strip().lower().startswith("none"):
        docs = [d.strip() for d in re.split(r",|\band\b", docs_match.group(1)) if d.strip()]
    languages = [n for n, p in LANGUAGE_WORDS if re.search(p, text, re.I)] or ["English"]

    return validate_card({
        "name": name.group(1).strip() if name else "My shop",
        "category": detect_category(text) or "other",
        "area": area.group(1).strip() if area else "Unknown",
        "city": city, "languages": languages, "services": services, "hours": hours,
        "slot_minutes": 60, "closed_days": closed, "required_documents": docs,
    })


def publish(card, server):
    reply = Client(server).call("POST", "/cards", card)
    if reply.get("type") == "error":
        raise RuntimeError(reply["message"])
    return reply["id"]


def main():
    ap = argparse.ArgumentParser(description="Turn a shop description into an agent card.")
    ap.add_argument("--text", help="the description (or use --file)")
    ap.add_argument("--file", help="read the description from a UTF-8 text file")
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    ap.add_argument("--city", default="")
    ap.add_argument("--yes", action="store_true", help="publish without asking")
    ap.add_argument("--dry-run", action="store_true", help="only print the card")
    args = ap.parse_args()
    text = args.text or (open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read())
    card = parse_description(text, args.city)
    print(json.dumps(card, ensure_ascii=False, indent=2))
    if args.dry_run:
        return
    if not args.yes and input("\nOwner: publish this card? [y/N] ").strip().lower() != "y":
        print("Not published.")
        return
    print("Published with id:", publish(card, args.server))


if __name__ == "__main__":
    main()
