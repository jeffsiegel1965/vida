"""Tests for Vida AgentMemory."""

from __future__ import annotations

import os
import tempfile
import unittest

from vida.agents.memory import AgentMemory, DealRecord


class TestAgentMemory(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.mem = AgentMemory(wallet_id="test_wallet", storage_dir=self.tmp_dir.name)
    
    def tearDown(self):
        self.tmp_dir.cleanup()
    
    def test_empty_stats(self):
        stats = self.mem.stats()
        self.assertEqual(stats["total_deals"], 0)
        self.assertEqual(stats["unique_counterparties"], 0)
    
    def test_record_deal(self):
        deal = DealRecord(
            id="deal_1", deal_type="tao_stake",
            counterparty_id="agent_netuid1",
            amount_tao=5.0, netuid=1,
            txid="0xabc123", success=True,
            rounds_to_deal=3,
        )
        self.mem.record_deal(deal)
        self.assertEqual(self.mem.stats()["total_deals"], 1)
    
    def test_counterparty_profile_updated(self):
        deal = DealRecord(
            id="deal_1", deal_type="covenant_pot",
            counterparty_id="agent_2",
            amount_kas=10.0, success=True,
        )
        self.mem.record_deal(deal)
        cp = self.mem.get_counterparty("agent_2")
        self.assertIsNotNone(cp)
        self.assertEqual(cp["total_deals"], 1)
        self.assertEqual(cp["total_kas_volume"], 10.0)
    
    def test_get_deals_filtered(self):
        self.mem.record_deal(DealRecord(id="d1", deal_type="tao_stake", counterparty_id="a1", amount_tao=1.0, success=True))
        self.mem.record_deal(DealRecord(id="d2", deal_type="subnet_purchase", counterparty_id="a2", amount_tao=0.5, success=True))
        self.mem.record_deal(DealRecord(id="d3", deal_type="tao_stake", counterparty_id="a3", amount_tao=2.0, success=True))
        
        stakes = self.mem.get_deals(deal_type="tao_stake")
        self.assertEqual(len(stakes), 2)
    
    def test_kv_store(self):
        self.mem.put("last_goal", "stake 50 TAO")
        self.assertEqual(self.mem.get("last_goal"), "stake 50 TAO")
        self.assertEqual(self.mem.get("nonexistent", "fallback"), "fallback")
        self.mem.delete("last_goal")
        self.assertIsNone(self.mem.get("last_goal"))
    
    def test_context_persistence(self):
        self.mem.set_context(current_goal="Deploy covenant pot")
        ctx = self.mem.get_context()
        self.assertEqual(ctx["current_goal"], "Deploy covenant pot")
        
        self.mem.clear_context()
        ctx = self.mem.get_context()
        self.assertEqual(ctx["current_goal"], "")
    
    def test_subnet_usage(self):
        deal = DealRecord(
            id="d_sn1", deal_type="llm_inference",
            counterparty_id="agent_sn19",
            amount_tao=0.05, netuid=19,
            success=True,
        )
        self.mem.record_deal(deal)
        sn = self.mem.get_subnet_record(19)
        self.assertIsNotNone(sn)
        self.assertEqual(sn["requests_made"], 1)
        
        self.mem.mark_subnet_favorite(19)
        faves = self.mem.list_favorite_subnets()
        self.assertEqual(len(faves), 1)
    
    def test_failed_deal_updates_success_rate(self):
        self.mem.record_deal(DealRecord(id="d1", deal_type="tao_stake", counterparty_id="a1", amount_tao=1.0, success=True))
        self.mem.record_deal(DealRecord(id="d2", deal_type="tao_stake", counterparty_id="a1", amount_tao=1.0, success=False))
        cp = self.mem.get_counterparty("a1")
        self.assertEqual(cp["failed_deals"], 1)
        self.assertEqual(cp["success_rate"], 0.5)
    
    def test_volume_discount(self):
        self.mem.record_deal(DealRecord(id="d1", deal_type="tao_stake", counterparty_id="big", amount_tao=500.0, success=True))
        self.mem.record_deal(DealRecord(id="d2", deal_type="tao_stake", counterparty_id="big", amount_tao=500.0, success=True))
        rate = self.mem.volume_discount_rate("big")
        self.assertEqual(rate, 0.20)  # 1000+ TAO = 20%


if __name__ == "__main__":
    unittest.main()