import unittest

from proxytwin.schema import CardError, slots_for, validate_card

BASE = {"name": "Test Shop", "category": "Salon", "area": "RS Puram",
        "services": [{"name": "Haircut", "price_inr": 200}],
        "hours": {"open": "10:00", "close": "13:00"}}


class SchemaTests(unittest.TestCase):
    def test_valid_card_is_normalised(self):
        card = validate_card(BASE)
        self.assertEqual(card["category"], "salon")
        self.assertEqual(card["slot_minutes"], 60)
        self.assertEqual(card["languages"], ["English"])
        self.assertEqual(card["schema"], "proxytwin/0.1")

    def test_rejects_missing_services(self):
        with self.assertRaises(CardError):
            validate_card({**BASE, "services": []})

    def test_rejects_negative_price_and_bad_hours(self):
        with self.assertRaises(CardError):
            validate_card({**BASE, "services": [{"name": "x", "price_inr": -5}]})
        with self.assertRaises(CardError):
            validate_card({**BASE, "hours": {"open": "18:00", "close": "10:00"}})
        with self.assertRaises(CardError):
            validate_card({**BASE, "hours": {"open": "9am", "close": "10:00"}})

    def test_slots_follow_hours_and_closed_days(self):
        card = validate_card({**BASE, "closed_days": ["Monday"]})
        self.assertEqual(slots_for(card, "2026-11-25"), ["10:00", "11:00", "12:00"])  # Wednesday
        self.assertEqual(slots_for(card, "2026-11-23"), [])                           # Monday

    def test_bad_date(self):
        with self.assertRaises(CardError):
            slots_for(validate_card(BASE), "tomorrow")


if __name__ == "__main__":
    unittest.main()
