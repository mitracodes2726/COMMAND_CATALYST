"""Agent card schema and validation. See PROTOCOL.md for the field list."""
import copy
import datetime
import re

SCHEMA_VERSION = "proxytwin/0.1"
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class CardError(ValueError):
    """Raised when an agent card is invalid."""


def to_minutes(hhmm):
    m = _TIME.match(hhmm if isinstance(hhmm, str) else "")
    if not m:
        raise CardError(f"bad time {hhmm!r}, expected HH:MM (24-hour)")
    return int(m.group(1)) * 60 + int(m.group(2))


def to_hhmm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _str_list(card, key, default):
    value = card.setdefault(key, default)
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise CardError(f"'{key}' must be a list of non-empty strings")
    return value


def validate_card(card):
    """Return a normalised copy of the card, or raise CardError."""
    if not isinstance(card, dict):
        raise CardError("card must be a JSON object")
    out = copy.deepcopy(card)
    for key in ("name", "category", "area"):
        if not isinstance(out.get(key), str) or not out[key].strip():
            raise CardError(f"'{key}' is required")
        out[key] = out[key].strip()
    out["category"] = out["category"].lower()

    services = out.get("services")
    if not isinstance(services, list) or not services:
        raise CardError("'services' must be a non-empty list")
    for s in services:
        if not isinstance(s, dict) or not str(s.get("name", "")).strip():
            raise CardError("every service needs a 'name'")
        price = s.get("price_inr")
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0:
            raise CardError(f"service {s.get('name')!r} needs a non-negative 'price_inr'")
        s["name"] = s["name"].strip()

    hours = out.get("hours")
    if not isinstance(hours, dict):
        raise CardError("'hours' is required, e.g. {\"open\": \"10:00\", \"close\": \"18:00\"}")
    if to_minutes(hours.get("open")) >= to_minutes(hours.get("close")):
        raise CardError("hours.open must be earlier than hours.close")

    step = out.setdefault("slot_minutes", 60)
    if isinstance(step, bool) or not isinstance(step, int) or not 5 <= step <= 240:
        raise CardError("'slot_minutes' must be an integer between 5 and 240")

    closed = out.setdefault("closed_days", [])
    if not isinstance(closed, list) or any(d not in WEEKDAYS for d in closed):
        raise CardError("'closed_days' must be a list of weekday names, e.g. [\"Sunday\"]")

    _str_list(out, "languages", ["English"])
    _str_list(out, "required_documents", [])
    out["schema"] = SCHEMA_VERSION
    return out


def slots_for(card, date):
    """Every slot start time (HH:MM) on an ISO date, before bookings are removed."""
    try:
        day = datetime.date.fromisoformat(date)
    except (TypeError, ValueError):
        raise CardError("date must be YYYY-MM-DD")
    if WEEKDAYS[day.weekday()] in card.get("closed_days", []):
        return []
    start = to_minutes(card["hours"]["open"])
    end = to_minutes(card["hours"]["close"])
    step = card["slot_minutes"]
    return [to_hhmm(t) for t in range(start, end - step + 1, step)]
