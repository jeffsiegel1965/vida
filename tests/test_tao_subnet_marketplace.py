"""Tests for the TAO subnet marketplace module."""

from __future__ import annotations

import unittest

from vida.plugins.tao.subnet_marketplace import (
    ServiceType,
    SubnetRegistry,
)


class TestSubnetRegistry(unittest.TestCase):
    def test_list_all(self):
        results = SubnetRegistry.list_all()
        self.assertGreater(len(results), 0)
        self.assertIn("netuid", results[0])
        self.assertIn("name", results[0])

    def test_get_by_netuid(self):
        info = SubnetRegistry.get_by_netuid(19)
        self.assertIsNotNone(info)
        self.assertEqual(info.name, "Inference (LLM)")

    def test_get_nonexistent(self):
        info = SubnetRegistry.get_by_netuid(9999)
        self.assertIsNone(info)

    def test_search_by_service_type(self):
        results = SubnetRegistry.search(service_type=ServiceType.LLM_INFERENCE)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r["service_type"], "llm_inference")

    def test_search_by_tags(self):
        results = SubnetRegistry.search(tags=["compute"])
        self.assertGreater(len(results), 0)

    def test_search_by_query(self):
        results = SubnetRegistry.search(query="storage")
        self.assertGreater(len(results), 0)

    def test_find_by_capability_llm(self):
        results = SubnetRegistry.find_by_capability("llm")
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r["service_type"], "llm_inference")

    def test_find_by_capability_compute(self):
        results = SubnetRegistry.find_by_capability("gpu")
        self.assertGreater(len(results), 0)

    def test_find_by_capability_unknown(self):
        results = SubnetRegistry.find_by_capability("nonexistent")
        self.assertEqual(len(results), 0)

    def test_stats(self):
        stats = SubnetRegistry.stats()
        self.assertGreater(stats["total_subnets"], 0)
        self.assertIn("by_service_type", stats)


if __name__ == "__main__":
    unittest.main()
