"""Tests for the escrow covenant module."""

from __future__ import annotations

import os
import tempfile
import unittest

from vida.plugins.covenant.escrow import (
    EscrowRecord,
    EscrowStore,
    escrow_covenant_id,
    deploy_escrow,
    release_escrow,
    refund_escrow,
    resolve_escrow,
    vida_escrow_create,
    vida_escrow_status,
    vida_escrow_list,
)


class TestEscrowRecord(unittest.TestCase):
    def test_to_dict(self):
        r = EscrowRecord(
            id="escrow_test",
            buyer_address="kaspa:buyer1",
            seller_address="kaspa:seller1",
            arbiter_address="kaspa:arbiter1",
            amount_sompi=100_000_000,
            timeout_block=10080,
            covenant_id="abc123",
            fund_txid="0xfund",
        )
        d = r.to_dict()
        self.assertEqual(d["id"], "escrow_test")
        self.assertEqual(d["amount_kas"], 1.0)
        self.assertEqual(d["status"], "funded")


class TestEscrowStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = EscrowStore(storage_dir=self.tmp.name)
    
    def tearDown(self):
        self.tmp.cleanup()
    
    def test_empty_store(self):
        self.assertEqual(len(self.store.list_all()), 0)
    
    def test_save_and_get(self):
        r = EscrowRecord(
            id="escrow_1", buyer_address="b", seller_address="s",
            arbiter_address="a", amount_sompi=100_000_000,
            timeout_block=10080, covenant_id="cid",
        )
        self.store.save(r)
        self.assertIsNotNone(self.store.get("escrow_1"))
        self.assertEqual(len(self.store.list_active()), 1)
    
    def test_update_status(self):
        r = EscrowRecord(
            id="escrow_2", buyer_address="b", seller_address="s",
            arbiter_address="a", amount_sompi=100_000_000,
            timeout_block=10080, covenant_id="cid",
        )
        self.store.save(r)
        self.store.update_status("escrow_2", "released", "0xrelease")
        updated = self.store.get("escrow_2")
        self.assertEqual(updated.status, "released")
        self.assertEqual(updated.release_txid, "0xrelease")
        self.assertEqual(len(self.store.list_active()), 0)
    
    def test_persistence(self):
        r = EscrowRecord(
            id="escrow_3", buyer_address="b", seller_address="s",
            arbiter_address="a", amount_sompi=50_000_000,
            timeout_block=10080, covenant_id="cid",
        )
        self.store.save(r)
        store2 = EscrowStore(storage_dir=self.tmp.name)
        self.assertIsNotNone(store2.get("escrow_3"))


class TestEscrowDeploy(unittest.TestCase):
    def test_deploy_creates_escrow(self):
        result = deploy_escrow(
            buyer_address="kaspa:buyer",
            seller_address="kaspa:seller",
            arbiter_address="kaspa:arbiter",
            amount_kas=1.0,
        )
        self.assertTrue(result["ok"])
        self.assertIn("escrow_id", result)
        self.assertIn("covenant_id", result)
        self.assertEqual(result["amount_kas"], 1.0)
    
    def test_deploy_with_zero_amount(self):
        result = deploy_escrow(
            buyer_address="kaspa:b", seller_address="kaspa:s",
            arbiter_address="kaspa:a", amount_kas=0,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["amount_sompi"], 0)
    
    def test_escrow_covenant_id_deterministic(self):
        cid1 = escrow_covenant_id()
        cid2 = escrow_covenant_id()
        self.assertEqual(cid1, cid2)
        self.assertEqual(len(cid1), 64)


class TestEscrowRelease(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = EscrowStore(storage_dir=self.tmp.name)
        r = EscrowRecord(
            id="escrow_release", buyer_address="b", seller_address="s",
            arbiter_address="a", amount_sompi=100_000_000,
            timeout_block=10080, covenant_id="cid",
        )
        self.store.save(r)
    
    def tearDown(self):
        self.tmp.cleanup()
    
    def test_release(self):
        result = release_escrow("escrow_release", "seller_sig", "arbiter_sig", store=self.store)
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "release")
    
    def test_release_nonexistent(self):
        result = release_escrow("no_such_escrow", "sig", "sig")
        self.assertFalse(result["ok"])


class TestEscrowRefund(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = EscrowStore(storage_dir=self.tmp.name)
        r = EscrowRecord(
            id="escrow_refund", buyer_address="b", seller_address="s",
            arbiter_address="a", amount_sompi=100_000_000,
            timeout_block=10080, covenant_id="cid",
        )
        self.store.save(r)
    
    def tearDown(self):
        self.tmp.cleanup()
    
    def test_refund(self):
        result = refund_escrow("escrow_refund", "buyer_sig", store=self.store)
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "refund")


class TestEscrowResolve(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = EscrowStore(storage_dir=self.tmp.name)
        self.escrow = EscrowRecord(
            id="escrow_resolve", buyer_address="kaspa:buyer",
            seller_address="kaspa:seller",
            arbiter_address="kaspa:arbiter",
            amount_sompi=100_000_000, timeout_block=10080,
            covenant_id="cid",
        )
        self.store.save(self.escrow)
    
    def tearDown(self):
        self.tmp.cleanup()
    
    def test_resolve_to_buyer(self):
        result = resolve_escrow("escrow_resolve", "arbiter_sig", "kaspa:buyer", store=self.store)
        self.assertTrue(result["ok"])
        self.assertEqual(result["recipient"], "kaspa:buyer")
    
    def test_resolve_to_seller(self):
        result = resolve_escrow("escrow_resolve", "arbiter_sig", "kaspa:seller", store=self.store)
        self.assertTrue(result["ok"])
    
    def test_resolve_invalid_recipient(self):
        result = resolve_escrow("escrow_resolve", "arbiter_sig", "kaspa:thief")
        self.assertFalse(result["ok"])


class TestEscrowTools(unittest.TestCase):
    def test_escrow_create_tool(self):
        result = vida_escrow_create(
            buyer_address="kaspa:b",
            seller_address="kaspa:s",
            amount_kas=5.0,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["amount_kas"], 5.0)
    
    def test_escrow_status_tool(self):
        # Create first, then check status
        result = vida_escrow_create(
            buyer_address="kaspa:b",
            seller_address="kaspa:s",
            amount_kas=1.0,
        )
        escrow_id = result["escrow_id"]
        status = vida_escrow_status(escrow_id)
        self.assertTrue(status["ok"])
    
    def test_escrow_list_tool(self):
        result = vida_escrow_list()
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()