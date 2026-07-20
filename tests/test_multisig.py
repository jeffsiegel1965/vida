"""Tests for Bittensor v11 multisig integration."""

from __future__ import annotations

import os
import tempfile
import unittest

from vida.plugins.tao.multisig import (
    MultisigProposal,
    MultisigStore,
    propose,
    approve,
    execute,
    cancel,
    vida_multisig_propose,
    vida_multisig_approve,
    vida_multisig_execute,
    vida_multisig_cancel,
    vida_multisig_status,
    vida_multisig_list,
)


class TestMultisigProposal(unittest.TestCase):
    def test_to_dict(self):
        p = MultisigProposal(
            id="ms_test", network="finney", module="SubtensorModule",
            call="add_stake", params={"amount": 100}, threshold=2,
            signers=["alice", "bob", "charlie"],
        )
        d = p.to_dict()
        self.assertEqual(d["threshold"], 2)
        self.assertEqual(d["approval_count"], 0)
        self.assertEqual(d["needed"], 2)


class TestMultisigStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MultisigStore(storage_dir=self.tmp.name)
    
    def tearDown(self):
        self.tmp.cleanup()
    
    def test_empty_store(self):
        self.assertEqual(len(self.store.list_all()), 0)
    
    def test_save_and_get(self):
        p = MultisigProposal(id="ms_1", network="finney", module="M", call="c", params={}, threshold=2, signers=["a", "b"])
        self.store.save(p)
        self.assertIsNotNone(self.store.get("ms_1"))
        self.assertEqual(len(self.store.list_open()), 1)
    
    def test_persistence(self):
        p = MultisigProposal(id="ms_2", network="finney", module="M", call="c", params={}, threshold=2, signers=["a", "b"])
        self.store.save(p)
        store2 = MultisigStore(storage_dir=self.tmp.name)
        self.assertIsNotNone(store2.get("ms_2"))


class TestPropose(unittest.TestCase):
    def test_propose_valid(self):
        result = propose(["alice", "bob", "charlie"], 2, "SubtensorModule", "add_stake", {"amount": 100})
        self.assertTrue(result["ok"])
        self.assertIn("proposal_id", result)
        self.assertEqual(result["threshold"], 2)
        self.assertEqual(result["signer_count"], 3)
    
    def test_propose_threshold_too_high(self):
        result = propose(["alice", "bob"], 3, "M", "c", {})
        self.assertFalse(result["ok"])
    
    def test_propose_zero_threshold(self):
        result = propose(["alice"], 0, "M", "c", {})
        self.assertFalse(result["ok"])


class TestApprove(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Create a proposal with default store
        import os as _os
        _os.environ["HOME"] = self.tmp.name
        self.result = propose(["alice", "bob", "charlie"], 2, "M", "c", {})
        self.pid = self.result["proposal_id"]
    
    def tearDown(self):
        pass
    
    def test_approve_adds(self):
        result = approve(self.pid, "alice")
        self.assertTrue(result["ok"])
        self.assertEqual(result["approvals"], 1)
        self.assertEqual(result["needed"], 1)
        self.assertEqual(result["status"], "open")
    
    def test_threshold_met(self):
        approve(self.pid, "alice")
        result = approve(self.pid, "bob")
        self.assertTrue(result["ok"])
        self.assertTrue(result["threshold_met"])
        self.assertEqual(result["status"], "approved")
    
    def test_approve_nonexistent(self):
        result = approve("nonexistent", "alice")
        self.assertFalse(result["ok"])
    
    def test_approve_unauthorized(self):
        result = approve(self.pid, "mallory")
        self.assertFalse(result["ok"])
    
    def test_approve_duplicate(self):
        approve(self.pid, "alice")
        result = approve(self.pid, "alice")
        self.assertFalse(result["ok"])


class TestExecute(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        import os as _os
        _os.environ["HOME"] = self.tmp.name
        result = propose(["alice", "bob"], 2, "M", "c", {})
        self.pid = result["proposal_id"]
        approve(self.pid, "alice")
        approve(self.pid, "bob")
    
    def test_execute_approved(self):
        result = execute(self.pid)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "executed")
    
    def test_execute_not_approved(self):
        result = propose(["a", "b"], 2, "M", "c", {})
        pid = result["proposal_id"]
        result = execute(pid)
        self.assertFalse(result["ok"])
    
    def test_execute_nonexistent(self):
        result = execute("nonexistent")
        self.assertFalse(result["ok"])


class TestCancel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        import os as _os
        _os.environ["HOME"] = self.tmp.name
        result = propose(["alice", "bob"], 2, "M", "c", {})
        self.pid = result["proposal_id"]
    
    def test_cancel_open(self):
        result = cancel(self.pid, "alice")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "cancelled")
    
    def test_cancel_unauthorized(self):
        result = cancel(self.pid, "mallory")
        self.assertFalse(result["ok"])
    
    def test_cancel_executed(self):
        approve(self.pid, "alice")
        approve(self.pid, "bob")
        execute(self.pid)
        result = cancel(self.pid, "alice")
        self.assertFalse(result["ok"])


class TestMultisigTools(unittest.TestCase):
    def test_tool_propose(self):
        result = vida_multisig_propose(["a", "b"], 2, call="stake", params={"amount": 5})
        self.assertTrue(result["ok"])
    
    def test_tool_status(self):
        result = vida_multisig_propose(["a", "b"], 2, call="stake")
        pid = result["proposal_id"]
        status = vida_multisig_status(pid)
        self.assertTrue(status["ok"])
    
    def test_tool_list(self):
        result = vida_multisig_list()
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()