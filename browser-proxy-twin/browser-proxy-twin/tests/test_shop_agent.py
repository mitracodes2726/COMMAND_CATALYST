import threading
import unittest

from proxytwin.schema import validate_card
from proxytwin.shop_agent import AgentError, ShopAgent

CARD = validate_card({"name": "Test Shop", "category": "salon", "area": "RS Puram",
                      "services": [{"name": "Haircut", "price_inr": 200}],
                      "hours": {"open": "10:00", "close": "13:00"}})
DATE = "2026-11-25"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def hold(agent, time_="10:00"):
    return agent.handle({"type": "hold", "date": DATE, "time": time_})


class ShopAgentTests(unittest.TestCase):
    def test_query_answers_from_card(self):
        offer = ShopAgent(CARD).handle({"type": "query", "date": DATE})
        self.assertEqual(offer["price_inr"], 200)
        self.assertEqual(offer["slots"], ["10:00", "11:00", "12:00"])

    def test_held_slot_cannot_be_held_twice(self):
        agent = ShopAgent(CARD)
        hold(agent)
        with self.assertRaises(AgentError) as ctx:
            hold(agent)
        self.assertEqual(ctx.exception.code, "SLOT_TAKEN")
        self.assertNotIn("10:00", agent.handle({"type": "query", "date": DATE})["slots"])

    def test_cannot_book_before_owner_confirms(self):
        agent = ShopAgent(CARD)
        h = hold(agent)
        with self.assertRaises(AgentError) as ctx:
            agent.handle({"type": "book", "hold_id": h["hold_id"]})
        self.assertEqual(ctx.exception.code, "INVALID_STATE")

    def test_full_booking_flow(self):
        agent = ShopAgent(CARD)
        h = hold(agent)
        agent.owner_decide(h["hold_id"], True)
        booked = agent.handle({"type": "book", "hold_id": h["hold_id"]})
        self.assertEqual(booked["type"], "booked")
        self.assertEqual(booked["price_inr"], 200)
        with self.assertRaises(AgentError):
            hold(agent)                                   # still taken after booking

    def test_decline_frees_the_slot(self):
        agent = ShopAgent(CARD)
        h = hold(agent)
        agent.owner_decide(h["hold_id"], False)
        self.assertEqual(hold(agent)["status"], "pending_owner")

    def test_cancel_frees_the_slot(self):
        agent = ShopAgent(CARD)
        h = hold(agent)
        agent.handle({"type": "cancel", "hold_id": h["hold_id"]})
        hold(agent)

    def test_hold_expires_and_slot_returns(self):
        clock = Clock()
        agent = ShopAgent(CARD, hold_ttl=60, clock=clock)
        h = hold(agent)
        clock.now += 61
        self.assertEqual(agent.handle({"type": "status", "hold_id": h["hold_id"]})["status"], "expired")
        hold(agent)                                       # free again
        with self.assertRaises(AgentError) as ctx:
            agent.handle({"type": "book", "hold_id": h["hold_id"]})
        self.assertEqual(ctx.exception.code, "HOLD_EXPIRED")

    def test_bad_requests(self):
        agent = ShopAgent(CARD)
        for msg in ({"type": "nope"}, {"type": "query", "date": "tomorrow"},
                    {"type": "hold", "date": DATE, "time": "03:00"},
                    {"type": "query", "date": DATE, "service": "Massage"}):
            with self.assertRaises(AgentError) as ctx:
                agent.handle(msg)
            self.assertEqual(ctx.exception.code, "BAD_REQUEST")
        with self.assertRaises(AgentError) as ctx:
            agent.handle({"type": "status", "hold_id": "missing"})
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    def test_concurrent_holds_never_double_book(self):
        agent = ShopAgent(CARD)
        results = []

        def attempt():
            try:
                hold(agent, "11:00")
                results.append("ok")
            except AgentError:
                results.append("taken")

        threads = [threading.Thread(target=attempt) for _ in range(40)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count("ok"), 1)
        self.assertEqual(results.count("taken"), 39)


if __name__ == "__main__":
    unittest.main()
