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