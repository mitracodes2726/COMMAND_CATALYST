import unittest

from proxytwin.demo import TAMIL_SAMPLE
from proxytwin.onboard import parse_description


class OnboardTests(unittest.TestCase):
    def test_english_description(self):
        card = parse_description("Tailor shop called Meena Boutique in Saibaba Colony. "
                                 "Blouse stitching ₹280, alteration ₹90. Open 10 am to 6 pm. "
                                 "Documents: none. We speak Tamil and English.")
        self.assertEqual(card["name"], "Meena Boutique")
        self.assertEqual(card["category"], "tailor")
        self.assertEqual(card["area"], "Saibaba Colony")
        self.assertEqual([(s["name"], s["price_inr"]) for s in card["services"]],
                         [("Blouse stitching", 280), ("Alteration", 90)])
        self.assertEqual(card["hours"], {"open": "10:00", "close": "18:00"})
        self.assertEqual(card["languages"], ["Tamil", "English"])
        self.assertEqual(card["required_documents"], [])

    def test_tamil_and_english_description(self):
        card = parse_description(TAMIL_SAMPLE)
        self.assertEqual(card["name"], "Meena Beauty Parlour")
        self.assertEqual(card["category"], "salon")
        self.assertEqual(card["hours"], {"open": "10:00", "close": "20:00"})
        self.assertEqual(card["closed_days"], ["Sunday"])

    def test_documents_and_closed_days(self):
        card = parse_description("Taluk office called Ward Desk in Ward 4. Application help ₹0. "
                                 "Open 10 am to 5 pm. Closed on Saturday. "
                                 "Documents: Aadhaar, Ration card and Address proof.")
        self.assertEqual(card["category"], "office")
        self.assertEqual(card["required_documents"], ["Aadhaar", "Ration card", "Address proof"])
        self.assertEqual(card["closed_days"], ["Saturday"])


if __name__ == "__main__":
    unittest.main()
