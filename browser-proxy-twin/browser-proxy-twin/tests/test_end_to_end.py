import threading
import unittest

from proxytwin.demo import OwnerSimulator
from proxytwin.server import Hub, make_server
from proxytwin.user_agent import Client, UserAgent, parse_request

SALON = {"category": "salon", "area": "Gandhipuram", "hours": {"open": "10:00", "close": "20:00"}}


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.server = make_server("127.0.0.1", 0, Hub(hold_ttl=30))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = Client(self.base)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def register(self, name, price):
        card = {**SALON, "name": name, "services": [{"name": "Haircut", "price_inr": price}]}
        reply = self.client.call("POST", "/cards", card)
        self.assertEqual(reply["card"]["name"], name)
        return reply["id"]

    def test_discovery_filters_by_category(self):
        self.register("A Salon", 100)
        self.client.call("POST", "/cards", {"name": "Doc", "category": "clinic", "area": "X",
                                            "services": [{"name": "Visit", "price_inr": 1}],
                                            "hours": {"open": "09:00", "close": "10:00"}})
        found = self.client.call("GET", "/cards?category=salon")["cards"]
        self.assertEqual([c["name"] for c in found], ["A Salon"])

    def test_invalid_card_is_rejected_over_http(self):
        reply = self.client.call("POST", "/cards", {"name": "Broken"})
        self.assertEqual(reply["code"], "BAD_REQUEST")

    def test_unknown_route_and_shop(self):
        self.assertEqual(self.client.call("GET", "/nope")["code"], "NOT_FOUND")
        reply = self.client.call("POST", "/agents/missing/message", {"type": "query"})
        self.assertEqual(reply["code"], "NOT_FOUND")

    def test_agent_falls_back_when_first_owner_declines(self):
        self.register("Cheap Salon", 100)
        self.register("Pricey Salon", 300)
        owner = OwnerSimulator(self.base, "decline-first", lambda s: None)
        owner.start()
        agent = UserAgent(self.base, log=lambda s: None, owner_timeout=10, poll=0.1)
        result = agent.book("Book a haircut on 2026-11-25 evening")
        owner.stop.set()
        self.assertEqual(result["status"], "booked")
        self.assertEqual(result["booking"]["shop"], "Pricey Salon")
        self.assertEqual(result["pages_loaded"], 0)

    def test_user_can_cancel_at_approval(self):
        self.register("Only Salon", 100)
        owner = OwnerSimulator(self.base, "accept", lambda s: None)
        owner.start()
        agent = UserAgent(self.base, log=lambda s: None, approve=lambda summary: False,
                          owner_timeout=10, poll=0.1)
        result = agent.book("Book a haircut on 2026-11-25")
        owner.stop.set()
        self.assertEqual(result["status"], "cancelled")

    def test_parse_request(self):
        intent = parse_request("Book a dentist tomorrow evening")
        self.assertEqual((intent["category"], intent["pref"]), ("dentist", "evening"))
        self.assertEqual(parse_request("தையல் on 2026-12-02")["category"], "tailor")


if __name__ == "__main__":
    unittest.main()
