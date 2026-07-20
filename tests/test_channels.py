"""Tests for covenant payment channels."""

from __future__ import annotations

import os
import tempfile
import unittest

from vida.plugins.covenant.channels import (
    ChannelStore,
    PaymentChannel,
    open_channel,
    update_channel,
    close_channel,
    vida_channel_open,
    vida_channel_status,
    vida_channel_list,
)


class TestPaymentChannel(unittest.TestCase):
    def test_to_dict(self):
        c = PaymentChannel(
            id="ch_test", party_a="party_a_long_address...", party_b="party_b",
            capacity_sompi=100_000_000, balance_a=100_000_000, balance_b=0,
        )
        d = c.to_dict()
        self.assertEqual(d["capacity_kas"], 1.0)
        self.assertEqual(d["balance_a_kas"], 1.0)
        self.assertEqual(d["status"], "open")
        self.assertIn("...", d["party_a"])


class TestChannelStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ChannelStore(storage_dir=self.tmp.name)
    
    def tearDown(self):
        self.tmp.cleanup()
    
    def test_empty_store(self):
        self.assertEqual(len(self.store.list_all()), 0)
    
    def test_save_and_get(self):
        c = PaymentChannel(id="ch_1", party_a="a", party_b="b", capacity_sompi=100_000_000, balance_a=100_000_000, balance_b=0)
        self.store.save(c)
        self.assertIsNotNone(self.store.get("ch_1"))
        self.assertEqual(len(self.store.list_open()), 1)
    
    def test_update(self):
        c = PaymentChannel(id="ch_2", party_a="a", party_b="b", capacity_sompi=100_000_000, balance_a=100_000_000, balance_b=0)
        self.store.save(c)
        self.store.update("ch_2", balance_a=50_000_000, balance_b=50_000_000, sequence=1)
        updated = self.store.get("ch_2")
        self.assertEqual(updated.balance_a, 50_000_000)
        self.assertEqual(updated.sequence, 1)
    
    def test_close(self):
        c = PaymentChannel(id="ch_3", party_a="a", party_b="b", capacity_sompi=100_000_000, balance_a=100_000_000, balance_b=0)
        self.store.save(c)
        self.store.update("ch_3", status="closed")
        self.assertEqual(len(self.store.list_open()), 0)
    
    def test_persistence(self):
        c = PaymentChannel(id="ch_4", party_a="a", party_b="b", capacity_sompi=100_000_000, balance_a=100_000_000, balance_b=0)
        self.store.save(c)
        store2 = ChannelStore(storage_dir=self.tmp.name)
        self.assertIsNotNone(store2.get("ch_4"))


class TestOpenChannel(unittest.TestCase):
    def test_open_channel(self):
        result = open_channel("party_a_address", "party_b_address", 1.0)
        self.assertTrue(result["ok"])
        self.assertIn("channel_id", result)
        self.assertEqual(result["capacity_kas"], 1.0)
        self.assertIn("fee_kas", result)
    
    def test_open_channel_with_fee(self):
        result = open_channel("a", "b", 100.0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["fee_kas"], 0.1)  # 0.1% of 100 = 0.1


class TestUpdateChannel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ChannelStore(storage_dir=self.tmp.name)
        c = PaymentChannel(id="ch_update", party_a="a", party_b="b", capacity_sompi=100_000_000, balance_a=100_000_000, balance_b=0)
        self.store.save(c)
    
    def tearDown(self):
        self.tmp.cleanup()
    
    def test_update_balance(self):
        result = update_channel("ch_update", "sig_a", "sig_b", 60_000_000, 40_000_000, store=self.store)
        self.assertTrue(result["ok"])
        self.assertEqual(result["balance_a_kas"], 0.6)
        self.assertEqual(result["balance_b_kas"], 0.4)
        self.assertEqual(result["sequence"], 1)
    
    def test_update_overflow(self):
        result = update_channel("ch_update", "sig_a", "sig_b", 200_000_000, 0)
        self.assertFalse(result["ok"])
    
    def test_update_negative(self):
        result = update_channel("ch_update", "sig_a", "sig_b", -1, 100_000_001)
        self.assertFalse(result["ok"])
    
    def test_update_unopened(self):
        result = update_channel("nonexistent", "sig_a", "sig_b", 50_000_000, 50_000_000)
        self.assertFalse(result["ok"])


class TestCloseChannel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ChannelStore(storage_dir=self.tmp.name)
        c = PaymentChannel(id="ch_close", party_a="a", party_b="b", capacity_sompi=100_000_000, balance_a=60_000_000, balance_b=40_000_000)
        self.store.save(c)
    
    def tearDown(self):
        self.tmp.cleanup()
    
    def test_close_channel(self):
        result = close_channel("ch_close", store=self.store)
        self.assertTrue(result["ok"])
        self.assertEqual(result["final_a_kas"], 0.6)
        self.assertEqual(result["final_b_kas"], 0.4)
    
    def test_close_already_closed(self):
        close_channel("ch_close")
        result = close_channel("ch_close")
        self.assertFalse(result["ok"])


class TestChannelTools(unittest.TestCase):
    def test_open_tool(self):
        result = vida_channel_open("a", "b", 5.0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["capacity_kas"], 5.0)
    
    def test_status_tool(self):
        result = vida_channel_open("a", "b", 1.0)
        cid = result["channel_id"]
        status = vida_channel_status(cid)
        self.assertTrue(status["ok"])
    
    def test_list_tool(self):
        result = vida_channel_list()
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()