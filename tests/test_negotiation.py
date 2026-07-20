"""Tests for the negotiation module."""

from __future__ import annotations

import os
import tempfile
import unittest

from vida.agents.negotiation import (
    TEMPLATES,
    ConcessionStrategy,
    CovenantTerms,
    NegotiationMemory,
    NegotiationOutcome,
    NegotiationSession,
    SessionManager,
    Subscription,
    SubscriptionManager,
    apply_template,
)


class TestCovenantTerms(unittest.TestCase):
    def test_defaults(self):
        t = CovenantTerms()
        self.assertEqual(t.max_kas_per_tx, 1.0)
        self.assertEqual(t.max_kas_per_day, 5.0)
        self.assertEqual(t.duration_hours, 720)

    def test_to_dict_roundtrip(self):
        t = CovenantTerms(max_kas_per_tx=5.0, duration_hours=168)
        d = t.to_dict()
        t2 = CovenantTerms.from_dict(d)
        self.assertEqual(t2.max_kas_per_tx, 5.0)
        self.assertEqual(t2.duration_hours, 168)

    def test_from_dict_partial(self):
        t = CovenantTerms.from_dict({"max_kas_per_tx": 2.0})
        self.assertEqual(t.max_kas_per_tx, 2.0)
        self.assertEqual(t.max_kas_per_day, 5.0)  # default


class TestTemplates(unittest.TestCase):
    def test_template_exists(self):
        self.assertIn("standard", TEMPLATES)
        self.assertIn("micro", TEMPLATES)
        self.assertIn("power", TEMPLATES)

    def test_apply_template(self):
        terms = apply_template("micro")
        self.assertEqual(terms.max_kas_per_tx, 0.1)
        self.assertEqual(terms.duration_hours, 168)

    def test_apply_template_with_destinations(self):
        terms = apply_template("standard", ["addr1", "addr2"])
        self.assertEqual(terms.allowed_destinations, ["addr1", "addr2"])

    def test_unknown_template_falls_back(self):
        terms = apply_template("nonexistent")
        self.assertEqual(terms.max_kas_per_tx, 1.0)  # standard defaults


class TestNegotiationMemory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.path = self.tmp.name
        self.tmp.close()
        self.mem = NegotiationMemory(self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_empty_stats(self):
        stats = self.mem.stats()
        self.assertEqual(stats["total_deals"], 0)

    def test_record_outcome(self):
        outcome = NegotiationOutcome(
            counterparty_id="agent_1",
            strategy_used=ConcessionStrategy.BOULWARE,
            rounds_to_deal=3,
            final_terms=CovenantTerms(),
            pot_funded=True,
            pot_sompi=100_000_000,
        )
        self.mem.record(outcome)
        self.assertEqual(self.mem.stats()["total_deals"], 1)

    def test_best_strategy_new(self):
        strategy = self.mem.best_strategy_for("new_agent")
        self.assertEqual(strategy, ConcessionStrategy.BOULWARE)

    def test_best_strategy_after_3_deals(self):
        for i in range(3):
            outcome = NegotiationOutcome(
                counterparty_id="agent_2",
                strategy_used=ConcessionStrategy.CONCEDE,
                rounds_to_deal=i + 1,
                final_terms=CovenantTerms(),
                pot_funded=True,
                pot_sompi=10_000_000,
            )
            self.mem.record(outcome)
        strategy = self.mem.best_strategy_for("agent_2")
        self.assertEqual(strategy, ConcessionStrategy.CONCEDE)

    def test_volume_discount(self):
        outcome = NegotiationOutcome(
            counterparty_id="big_spender",
            strategy_used=ConcessionStrategy.BOULWARE,
            rounds_to_deal=2,
            final_terms=CovenantTerms(),
            pot_funded=True,
            pot_sompi=200_000_000_000,  # 2000 KAS (correct: 200B sompi)
        )
        self.mem.record(outcome)
        discount = self.mem.volume_discount("big_spender")
        self.assertEqual(discount, 0.20)  # 20% for 1000+ KAS

    def test_persistence(self):
        outcome = NegotiationOutcome(
            counterparty_id="persist_test",
            strategy_used=ConcessionStrategy.BOULWARE,
            rounds_to_deal=5,
            final_terms=CovenantTerms(max_kas_per_tx=2.0),
            pot_funded=True,
            pot_sompi=50_000_000,
        )
        self.mem.record(outcome)

        mem2 = NegotiationMemory(self.path)
        self.assertEqual(mem2.stats()["total_deals"], 1)
        profile = mem2.get_profile("persist_test")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.deal_count, 1)


class TestNegotiationSession(unittest.TestCase):
    def setUp(self):
        self.mem = NegotiationMemory()  # in-memory only
        self.session = NegotiationSession(
            counterparty_id="test_agent",
            strategy=ConcessionStrategy.BOULWARE,
            template="standard",
            memory=self.mem,
        )

    def test_initial_offer(self):
        offer = self.session.make_initial_offer()
        self.assertEqual(offer.max_kas_per_tx, 1.0)

    def test_accept_immediately(self):
        """Counterparty offers exactly our template terms — accept."""
        response, accepted = self.session.respond_to_offer(
            apply_template("standard")
        )
        self.assertTrue(accepted)

    def test_reject_then_concede(self):
        """Counterparty offers way more — we should counter, not accept."""
        high_terms = CovenantTerms(max_kas_per_tx=100.0, max_kas_per_day=500.0)
        response, accepted = self.session.respond_to_offer(high_terms)
        self.assertFalse(accepted)
        # BOULWARE holds firm at round 1 (progress 0.1 < 0.3)
        # But we should still counter, not accept
        self.assertFalse(self.session.is_complete)
        # Second round: progress 0.3, should start conceding
        response2, accepted2 = self.session.respond_to_offer(high_terms)
        self.assertFalse(accepted2)
        self.assertGreater(response2.max_kas_per_tx, 1.0)

    def test_walk_away(self):
        result = self.session.reject_and_walk("too expensive")
        self.assertFalse(result["ok"])
        self.assertTrue(self.session.is_complete)

    def test_max_rounds(self):
        """After MAX_ROUNDS, the session should expire."""
        high_terms = CovenantTerms(max_kas_per_tx=100.0, max_kas_per_day=500.0)
        for _ in range(11):  # over max
            response, accepted = self.session.respond_to_offer(high_terms)
            if accepted or self.session.is_complete:
                break
        self.assertTrue(self.session.is_complete)
        self.assertIsNotNone(self.session.error)

    def test_accept_terms_records_outcome(self):
        terms = apply_template("micro")
        import os
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        tmp.close()
        fresh_mem = NegotiationMemory(tmp.name)
        session = NegotiationSession(
            counterparty_id="record_test",
            template="micro",
            memory=fresh_mem,
        )
        result = session.accept_terms(terms)
        os.unlink(tmp.name)
        self.assertTrue(result["ok"])
        self.assertTrue(result["accepted"])
        self.assertEqual(fresh_mem.stats()["total_deals"], 1)


class TestSessionManager(unittest.TestCase):
    def setUp(self):
        self.mgr = SessionManager()

    def test_create_session(self):
        session = self.mgr.create_session("agent_3", template="micro")
        self.assertIsNotNone(session)
        self.assertEqual(session.template, "micro")

    def test_get_session(self):
        self.mgr.create_session("agent_4")
        session = self.mgr.get_session("agent_4")
        self.assertIsNotNone(session)

    def test_nonexistent_session(self):
        session = self.mgr.get_session("no_such_agent")
        self.assertIsNone(session)


class TestSubscriptionManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.path = self.tmp.name
        self.tmp.close()
        self.mgr = SubscriptionManager(self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_create_and_list(self):
        sub = Subscription(
            id="sub_1",
            counterparty_id="agent_5",
            terms=CovenantTerms(),
            amount_kas_per_cycle=1.0,
            interval_hours=168,
        )
        self.mgr.create(sub)
        self.assertEqual(len(self.mgr.list_active()), 1)

    def test_cancel(self):
        sub = Subscription(
            id="sub_2",
            counterparty_id="agent_6",
            terms=CovenantTerms(),
            amount_kas_per_cycle=1.0,
            interval_hours=168,
        )
        self.mgr.create(sub)
        self.assertTrue(self.mgr.cancel("sub_2"))
        self.assertEqual(len(self.mgr.list_active()), 0)

    def test_renew(self):
        sub = Subscription(
            id="sub_3",
            counterparty_id="agent_7",
            terms=CovenantTerms(),
            amount_kas_per_cycle=1.0,
            interval_hours=168,
        )
        self.mgr.create(sub)
        renewed = self.mgr.renew("sub_3")
        self.assertIsNotNone(renewed)
        self.assertEqual(renewed.total_cycles, 1)

    def test_discount(self):
        sub = Subscription(
            id="sub_4",
            counterparty_id="agent_8",
            terms=CovenantTerms(),
            amount_kas_per_cycle=1.0,
            interval_hours=168,
        )
        self.mgr.create(sub)
        self.assertEqual(self.mgr.discount_for("sub_4"), 0.15)

    def test_no_discount_for_nonexistent(self):
        self.assertEqual(self.mgr.discount_for("no_such_sub"), 0.0)


if __name__ == "__main__":
    unittest.main()
