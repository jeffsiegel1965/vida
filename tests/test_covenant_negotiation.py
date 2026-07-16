"""
Covenant negotiation tests: offer, counter, accept, reject, deal encoding, on-chain commitment.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vida.plugins.covenant.negotiation import (
    CovenantNegotiator,
    CovenantTerms,
    NegotiationPhase,
    ConcessionStrategy,
)


class TestNegotiationProtocol(unittest.TestCase):

    def test_create_offer(self):
        n = CovenantNegotiator()
        s = n.create_offer(
            agent_id="agent_a",
            agent_a="5A_a".ljust(42, "x"),
            agent_b="5B_b".ljust(42, "x"),
            max_kas_per_tx=1.0,
            max_kas_per_day=5.0,
            allowed_destinations=["kaspatest:qtest"],
        )
        self.assertEqual(s.status, "active")
        self.assertEqual(len(s.rounds), 1)
        self.assertEqual(s.rounds[0].phase, NegotiationPhase.OFFER)
        terms = s.latest_terms()
        self.assertIsNotNone(terms)
        self.assertEqual(terms.max_kas_per_tx, 1.0)
        self.assertEqual(terms.max_kas_per_day, 5.0)

    def test_counter_offer(self):
        n = CovenantNegotiator(strategy=ConcessionStrategy.CONCEDE)
        s = n.create_offer(
            agent_id="a", agent_a="a", agent_b="b",
            max_kas_per_tx=2.0, max_kas_per_day=10.0,
        )
        # Both agents use CONCEDE so B's counter is accepted immediately
        s.strategy_b = ConcessionStrategy.CONCEDE
        s2 = n.counter_offer(s.negotiation_id, "b", max_kas_per_tx=0.5, max_kas_per_day=2.0)
        self.assertIsNotNone(s2)
        self.assertEqual(len(s2.rounds), 2)
        self.assertEqual(s2.latest_terms().max_kas_per_tx, 0.5)
        self.assertEqual(s2.latest_terms().max_kas_per_day, 2.0)

    def test_accept_generates_deal_hash(self):
        n = CovenantNegotiator()
        s = n.create_offer(
            agent_id="a", agent_a="a", agent_b="b",
            max_kas_per_tx=1.0, max_kas_per_day=5.0,
        )
        s2 = n.accept(s.negotiation_id, "b")
        self.assertIsNotNone(s2)
        self.assertEqual(s2.status, "committed")
        self.assertTrue(len(s2.deal_hash) > 0)
        # deal hash should be deterministic from terms
        terms = s2.latest_terms()
        expected_hash = terms.deal_hash()
        self.assertEqual(s2.deal_hash, expected_hash)

    def test_reject(self):
        n = CovenantNegotiator()
        s = n.create_offer(
            agent_id="a", agent_a="a", agent_b="b",
            max_kas_per_tx=1.0, max_kas_per_day=5.0,
        )
        s2 = n.reject(s.negotiation_id, "b", "too expensive")
        self.assertIsNotNone(s2)
        self.assertEqual(s2.status, "rejected")
        self.assertIn("expensive", s2.rounds[-1].message)

    def test_expired_session(self):
        n = CovenantNegotiator()
        s = n.create_offer(
            agent_id="a", agent_a="a", agent_b="b",
            max_kas_per_tx=1.0, max_kas_per_day=5.0,
            deadline_minutes=-1,  # already expired
        )
        s2 = n.accept(s.negotiation_id, "b")
        self.assertIsNotNone(s2)
        # acceptance should not work on expired session
        # (the session was created with negative deadline)
        self.assertEqual(s2.status, "expired")

    def test_encode_deal(self):
        n = CovenantNegotiator()
        s = n.create_offer(
            agent_id="a", agent_a="a", agent_b="b",
            max_kas_per_tx=1.0, max_kas_per_day=5.0,
            allowed_destinations=["kaspatest:qtest"],
            duration_hours=24,
        )
        n.accept(s.negotiation_id, "b")
        encoded = n.encode_deal(s.negotiation_id)
        self.assertTrue(encoded["ok"])
        self.assertEqual(encoded["deal_hash"], s.deal_hash)
        self.assertIn("policy_template", encoded)
        self.assertIn("policy_hash", encoded)
        self.assertIn("commitment", encoded)
        # Commitment should have deal_hash and policy_hash
        self.assertEqual(encoded["commitment"]["deal_hash"], s.deal_hash)
        self.assertEqual(encoded["commitment"]["policy_hash"], encoded["policy_hash"])
        # Should document parties
        self.assertIn("parties", encoded)
        self.assertEqual(len(encoded["parties"]), 2)

    def test_deal_hash_determinism(self):
        """Same terms must produce same deal_hash."""
        t1 = CovenantTerms(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        t2 = CovenantTerms(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        self.assertEqual(t1.deal_hash(), t2.deal_hash())

        t3 = CovenantTerms(max_kas_per_tx=1.5, max_kas_per_day=5.0)
        self.assertNotEqual(t1.deal_hash(), t3.deal_hash())

    def test_list_sessions(self):
        n = CovenantNegotiator()
        n.create_offer(
            agent_id="a", agent_a="agent_a", agent_b="agent_b",
            max_kas_per_tx=1.0, max_kas_per_day=5.0,
        )
        sessions = n.list_sessions()
        self.assertEqual(len(sessions), 1)
        sessions_a = n.list_sessions(agent_id="agent_a")
        self.assertEqual(len(sessions_a), 1)
        sessions_c = n.list_sessions(agent_id="agent_c")
        self.assertEqual(len(sessions_c), 0)


class TestCovenantTerms(unittest.TestCase):

    def test_validate_valid(self):
        t = CovenantTerms(max_kas_per_tx=1.0, max_kas_per_day=5.0)
        self.assertIsNone(t.validate())

    def test_validate_zero_tx(self):
        t = CovenantTerms(max_kas_per_tx=0, max_kas_per_day=5.0)
        self.assertIsNotNone(t.validate())

    def test_validate_zero_day(self):
        t = CovenantTerms(max_kas_per_tx=1.0, max_kas_per_day=0)
        self.assertIsNotNone(t.validate())

    def test_validate_require_dest_no_dests(self):
        t = CovenantTerms(max_kas_per_tx=1.0, max_kas_per_day=5.0,
                          require_dest_allowlist=True, allowed_destinations=[])
        self.assertIsNotNone(t.validate())

    def test_validate_require_dest_with_dests(self):
        t = CovenantTerms(max_kas_per_tx=1.0, max_kas_per_day=5.0,
                          require_dest_allowlist=True,
                          allowed_destinations=["kaspatest:qtest"])
        self.assertIsNone(t.validate())

    def test_bad_voting_threshold(self):
        t = CovenantTerms(max_kas_per_tx=1.0, max_kas_per_day=5.0, voting_threshold=1.5)
        self.assertIsNotNone(t.validate())

    def test_canonical_json_stable(self):
        t1 = CovenantTerms(max_kas_per_tx=1.0, max_kas_per_day=5.0, duration_blocks=100)
        t2 = CovenantTerms(duration_blocks=100, max_kas_per_day=5.0, max_kas_per_tx=1.0)
        self.assertEqual(t1.to_canonical_json(), t2.to_canonical_json())

    def test_to_policy_template(self):
        t = CovenantTerms(max_kas_per_tx=1.0, max_kas_per_day=5.0,
                          allowed_destinations=["kaspatest:qtest"])
        tmpl = t.to_policy_template()
        self.assertTrue(tmpl.get("ok"))
        self.assertIn("policy_hash", tmpl)
        self.assertIn("canonical_json", tmpl)


class TestFullCycle(unittest.TestCase):
    """Full negotiation → deal encoding → policy → covenant commitment."""

    def test_agent_to_agent_full_cycle(self):
        n = CovenantNegotiator()

        # Agent A offers
        s = n.create_offer(
            agent_id="agent_a",
            agent_a="agent_a_ss58",
            agent_b="agent_b_ss58",
            max_kas_per_tx=5.0,
            max_kas_per_day=20.0,
            allowed_destinations=["kaspatest:qmerchant", "kaspatest:qservice"],
            duration_hours=48,
        )

        # Agent B counters with lower caps
        n.counter_offer(
            s.negotiation_id,
            "agent_b_ss58",
            max_kas_per_tx=1.0,
            max_kas_per_day=5.0,
            allowed_destinations=["kaspatest:qmerchant"],
        )

        # Agent A accepts (uses default BOULWARE — 4.6 after round 1)
        s2 = n.accept(s.negotiation_id, "agent_a_ss58")
        self.assertEqual(s2.status, "committed")

        # Encode the deal
        encoded = n.encode_deal(s.negotiation_id)
        self.assertTrue(encoded["ok"])
        self.assertEqual(encoded["parties"], ["agent_a_ss58", "agent_b_ss58"])

        # The deal_hash is deterministic from agreed terms
        # Boulware conceded 10% of the way from 5.0 to 1.0 = 4.6
        final_terms = s2.latest_terms()
        self.assertAlmostEqual(final_terms.max_kas_per_tx, 4.6, places=5)
        # Destinations stay as original (Boulware only concedes numeric values)
        self.assertIn("kaspatest:qmerchant", final_terms.allowed_destinations)

        # The policy template is ready for covenant funding
        self.assertIn("policy_hash", encoded["policy_template"])

        # The commitment can be verified on-chain later
        commitment = encoded["commitment"]
        self.assertEqual(commitment["deal_hash"], s2.deal_hash)

        print(f"Deal hash: {s2.deal_hash[:20]}...")
        print(f"Policy hash: {encoded['policy_hash'][:20]}...")
        print(f"Rounds: {encoded['rounds']}")
        print("Full agent-to-agent covenant negotiation cycle PASS")


if __name__ == "__main__":
    unittest.main()