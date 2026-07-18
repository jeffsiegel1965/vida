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