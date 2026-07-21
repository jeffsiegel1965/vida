"""
Covenant negotiation tests: terms creation, validation, deal hashing, policy template.
P2P negotiation (counter_offer, accept, reject) is deferred to v2.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vida.plugins.covenant.negotiation import CovenantTerms, create_deal


class TestNegotiationProtocol(unittest.TestCase):

    def test_create_deal(self):
        terms = create_deal(
            max_kas_per_tx=1.0,
            max_kas_per_day=5.0,
            allowed_destinations=["kaspatest:qtest"],
        )
        self.assertEqual(terms.max_kas_per_tx, 1.0)
        self.assertEqual(terms.max_kas_per_day, 5.0)
        self.assertEqual(terms.duration_hours, 24.0)
        self.assertIn("kaspatest:qtest", terms.allowed_destinations)

    def test_deal_hash_deterministic(self):
        t1 = create_deal(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        t2 = create_deal(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        self.assertEqual(t1.deal_hash(), t2.deal_hash())

    def test_deal_hash_changes_with_terms(self):
        t1 = create_deal(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        t2 = create_deal(max_kas_per_tx=2.0, max_kas_per_day=5.0)
        self.assertNotEqual(t1.deal_hash(), t2.deal_hash())

    def test_validate_rejects_zero_tx(self):
        with self.assertRaises(ValueError):
            create_deal(max_kas_per_tx=0, max_kas_per_day=5.0)

    def test_validate_rejects_negative_duration(self):
        with self.assertRaises(ValueError):
            create_deal(max_kas_per_tx=1.0, max_kas_per_day=5.0, duration_hours=-1)

    def test_validate_rejects_excessive_duration(self):
        with self.assertRaises(ValueError):
            create_deal(max_kas_per_tx=1.0, max_kas_per_day=5.0, duration_hours=721)

    def test_validate_rejects_tx_gt_day(self):
        with self.assertRaises(ValueError):
            create_deal(max_kas_per_tx=10.0, max_kas_per_day=5.0)

    def test_to_canonical_json(self):
        terms = create_deal(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        j = terms.to_canonical_json()
        self.assertIn("max_kas_per_tx", j)
        self.assertIn("max_kas_per_day", j)

    def test_to_policy_template(self):
        terms = create_deal(
            max_kas_per_tx=1.0,
            max_kas_per_day=5.0,
            allowed_destinations=["kaspatest:qtest"],
        )
        template = terms.to_policy_template()
        self.assertIn("ok", template)
        self.assertIn("policy_hash", template)

    def test_default_allowed_destinations_empty(self):
        terms = create_deal(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        self.assertEqual(terms.allowed_destinations, [])

    def test_validate_ok(self):
        terms = create_deal(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        self.assertIsNone(terms.validate())


if __name__ == "__main__":
    unittest.main()


# ── Quine strategy integration tests ──


class TestQuineStrategy(unittest.TestCase):
    """Tests for the self-replicating quine pot strategy."""

    def test_quine_template_ok(self):
        from vida.plugins.covenant.agent_pot_script import build_agent_pot_script_template
        t = build_agent_pot_script_template(
            max_kas_per_tx=1.0,
            max_kas_per_day=5.0,
            allowed_destinations=["kaspatest:qtest"],
            strategy="self_replicating_quine_pot",
        )
        self.assertTrue(t["ok"])
        self.assertEqual(t["strategy"], "self_replicating_quine_pot")
        self.assertTrue(t["live_script_ready"])
        self.assertTrue(t["enforcement_now"]["self_replicating"])
        self.assertIn("quine", t["pseudocode"].lower())

    def test_quine_with_owner_address(self):
        from vida.plugins.covenant.agent_pot_script import build_agent_pot_script_template
        t = build_agent_pot_script_template(
            max_kas_per_tx=1.0,
            max_kas_per_day=5.0,
            allowed_destinations=[],
            owner_address="kaspatest:qowner",
            strategy="self_replicating_quine_pot",
        )
        self.assertTrue(t["ok"])  # owner_address satisfies the dest requirement

    def test_quine_generations(self):
        from vida.plugins.covenant.agent_pot_script import build_agent_pot_script_template
        t = build_agent_pot_script_template(
            max_kas_per_tx=1.0,
            max_kas_per_day=5.0,
            allowed_destinations=["kaspatest:qtest"],
            strategy="self_replicating_quine_pot",
            quine_generations=10,
            auto_renew=True,
        )
        self.assertTrue(t["ok"])
        self.assertEqual(t["policy"]["quine_generations"], 10)
        self.assertEqual(t["policy"]["auto_renew"], True)
        self.assertIn("10", str(t["enforcement_now"]["generation_limit"]))

    def test_quine_kii_reference(self):
        """Verify the KII quine covenant ID is referenced in the template."""
        from vida.plugins.covenant.agent_pot_script import build_agent_pot_script_template
        t = build_agent_pot_script_template(
            max_kas_per_tx=1.0,
            max_kas_per_day=5.0,
            allowed_destinations=["kaspatest:qtest"],
            strategy="self_replicating_quine_pot",
        )
        cid = t["on_chain_today"]["kii_quine_covenant_id"]
        self.assertIsNotNone(cid)
        self.assertIn("b802c18b", cid)

    def test_quine_to_policy_template(self):
        """Verify that quine terms can generate a policy template via negotiation."""
        from vida.plugins.covenant.negotiation import create_deal
        terms = create_deal(
            max_kas_per_tx=1.0,
            max_kas_per_day=5.0,
            allowed_destinations=["kaspatest:qtest"],
        )
        template = terms.to_policy_template()
        self.assertIn("ok", template)
        self.assertIn("policy_hash", template)

# ── Phase 1: NegotiationSession multi-round tests ──


class TestNegotiationSession(unittest.TestCase):
    """Tests for the multi-round negotiation session with guardrails."""

    def setUp(self):
        from vida.plugins.covenant.negotiation import (
            NegotiationError,
            NegotiationPhase,
            NegotiationSession,
            Negotiator,
            UserControls,
        )
        self.NegotiationSession = NegotiationSession
        self.Negotiator = Negotiator
        self.NegotiationPhase = NegotiationPhase
        self.UserControls = UserControls
        self.NegotiationError = NegotiationError

    def test_make_offer_sets_phase(self):
        session = self.NegotiationSession(owner_id="owner1", agent_id="agent1")
        r = session.make_offer(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        self.assertEqual(r.phase, self.NegotiationPhase.OFFER)

    def test_counter_offer_requires_offer_first(self):
        session = self.NegotiationSession(owner_id="owner1", agent_id="agent1")
        with self.assertRaises(self.NegotiationError):
            session.counter_offer(max_kas_per_tx=0.5)

    def test_three_round_negotiation(self):
        session = self.NegotiationSession(owner_id="owner1", agent_id="agent1")
        session.make_offer(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        self.assertEqual(len(session.rounds), 1)
        c1 = session.counter_offer(max_kas_per_tx=0.8, party="agent")
        self.assertEqual(c1.phase, self.NegotiationPhase.COUNTER)
        a = session.accept(party="owner")
        self.assertEqual(a.phase, self.NegotiationPhase.ACCEPT)

    def test_round_limit_enforced(self):
        controls = self.UserControls(max_negotiation_rounds=2)
        session = self.NegotiationSession(owner_id="owner1", agent_id="agent1", controls=controls)
        session.make_offer(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        session.counter_offer(max_kas_per_tx=0.8, party="agent")
        with self.assertRaises(self.NegotiationError):
            session.counter_offer(max_kas_per_tx=0.6, party="agent")

    def test_concession_minimum_enforced(self):
        controls = self.UserControls(min_concession_per_round_pct=0.05)
        session = self.NegotiationSession(owner_id="owner1", agent_id="agent1", controls=controls)
        session.make_offer(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        with self.assertRaises(self.NegotiationError):
            session.counter_offer(max_kas_per_tx=0.98, party="agent")

    def test_concession_maximum_enforced(self):
        controls = self.UserControls(max_concession_per_round_pct=0.33)
        session = self.NegotiationSession(owner_id="owner1", agent_id="agent1", controls=controls)
        session.make_offer(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        with self.assertRaises(self.NegotiationError):
            session.counter_offer(max_kas_per_tx=0.5, party="agent")

    def test_accept_on_escalated_fails(self):
        controls = self.UserControls(human_approval_threshold_kas=10.0)
        session = self.NegotiationSession(owner_id="owner1", agent_id="agent1", controls=controls)
        # Daily rate 5 KAS * 480h (20 days) / 24 = 100 KAS pot -> exceeds 10 KAS threshold
        session.make_offer(max_kas_per_tx=1.0, max_kas_per_day=5.0, duration_hours=480.0)
        self.assertEqual(session.phase, self.NegotiationPhase.ESCALATED)
        r = session.accept()
        self.assertEqual(r.phase, self.NegotiationPhase.ESCALATED)

    def test_audit_log_output(self):
        session = self.NegotiationSession(owner_id="owner1", agent_id="agent1")
        session.make_offer(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        log = session.audit_log()
        self.assertIn("owner1", log)
        self.assertIn("agent1", log)


class TestDealBook(unittest.TestCase):
    """Tests for counterparty learning memory."""

    def setUp(self):
        from vida.plugins.covenant.negotiation import DealBook
        self.DealBook = DealBook
        self.CovenantTerms = CovenantTerms

    def test_record_and_history(self):
        book = self.DealBook()
        terms = self.CovenantTerms(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        book.record_deal("agent_abc", terms, "session_1")
        self.assertEqual(len(book.history("agent_abc")), 1)

    def test_history_empty_for_unknown(self):
        book = self.DealBook()
        self.assertEqual(book.history("unknown"), [])

    def test_is_first_deal(self):
        book = self.DealBook()
        self.assertTrue(book.is_first_deal("agent_abc"))
        terms = self.CovenantTerms(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        book.record_deal("agent_abc", terms, "session_1")
        self.assertFalse(book.is_first_deal("agent_abc"))

    def test_last_terms_ignores_rejected(self):
        book = self.DealBook()
        terms = self.CovenantTerms(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        book.record_deal("agent_abc", terms, "s1", outcome="rejected")
        self.assertIsNone(book.last_terms("agent_abc"))

    def test_avg_deal_value(self):
        book = self.DealBook()
        t1 = self.CovenantTerms(max_kas_per_tx=1.0, max_kas_per_day=10.0)
        t2 = self.CovenantTerms(max_kas_per_tx=2.0, max_kas_per_day=20.0)
        book.record_deal("agent_abc", t1, "s1")
        book.record_deal("agent_abc", t2, "s2")
        self.assertAlmostEqual(book.avg_deal_value("agent_abc"), 15.0)


class TestNegotiatorWrapper(unittest.TestCase):
    """Tests for the high-level Negotiator convenience wrapper."""

    def setUp(self):
        from vida.plugins.covenant.negotiation import Negotiator, UserControls
        self.Negotiator = Negotiator
        self.UserControls = UserControls

    def test_template_deal_ok(self):
        neg = self.Negotiator(owner_id="owner1")
        result = neg.template_deal(
            max_kas_per_tx=1.0, max_kas_per_day=5.0, counterparty_id="agent_abc",
        )
        self.assertTrue(result["ok"])
        self.assertIn("deal_hash", result)

    def test_template_deal_escalates_on_high_value(self):
        controls = self.UserControls(human_approval_threshold_kas=10.0)
        neg = self.Negotiator(owner_id="owner1", controls=controls)
        # 10 KAS/day * (480h / 24) = 200 KAS pot -> exceeds 10 KAS threshold
        result = neg.template_deal(
            max_kas_per_tx=5.0, max_kas_per_day=10.0, counterparty_id="agent_abc",
            duration_hours=480.0,
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result.get("escalated"))

    def test_template_deal_escalates_first_time(self):
        controls = self.UserControls(human_approval_threshold_kas=100.0)
        neg = self.Negotiator(owner_id="owner1", controls=controls)
        # 10 KAS/day * (120h / 24) = 50 KAS -> equals half of threshold -> escalates
        result = neg.template_deal(
            max_kas_per_tx=5.0, max_kas_per_day=10.0, counterparty_id="new_agent", duration_hours=120.0,
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result.get("escalated"))

    def test_template_deal_validates_terms(self):
        neg = self.Negotiator(owner_id="owner1")
        result = neg.template_deal(
            max_kas_per_tx=0, max_kas_per_day=5.0, counterparty_id="agent_abc",
        )
        self.assertFalse(result["ok"])
        self.assertIn("Invalid terms", result["error"])

    def test_start_and_get_session(self):
        neg = self.Negotiator(owner_id="owner1")
        s = neg.start_session(agent_id="agent_abc")
        self.assertIs(neg.get_session(s.session_id), s)

    def test_summary(self):
        neg = self.Negotiator(owner_id="owner1")
        s = neg.summary()
        self.assertEqual(s["owner_id"], "owner1")
