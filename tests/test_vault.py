"""Tests for self-custody vault covenant."""

from __future__ import annotations

import tempfile
import unittest

from vida.plugins.covenant.vault import (
    DEFAULT_DELAY_DAA,
    VaultState,
    VaultStore,
    cancel_withdrawal,
    create_vault,
    destination_hash,
    finalize_withdrawal,
    initiate_withdrawal,
    vida_vault_cancel,
    vida_vault_create,
    vida_vault_finalize,
    vida_vault_initiate,
    vida_vault_list,
    vida_vault_status,
)


class TestDestinationHash(unittest.TestCase):
    def test_hash_length(self):
        h = destination_hash("kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k")
        self.assertEqual(len(h), 64)  # 32 bytes hex

    def test_deterministic(self):
        addr = "kaspa:test123"
        self.assertEqual(destination_hash(addr), destination_hash(addr))

    def test_different_addresses(self):
        self.assertNotEqual(destination_hash("addr1"), destination_hash("addr2"))


class TestVaultState(unittest.TestCase):
    def setUp(self):
        self.vault = VaultState(
            vault_id="vault_test",
            hot_pubkey="ab" * 32,
            cold_pubkey="cd" * 32,
            whitelist_dest="ef" * 32,
            balance_sompi=100_000_000,
        )

    def test_not_pending_by_default(self):
        self.assertFalse(self.vault.is_pending)

    def test_pending_when_set(self):
        self.vault.pending_dest = "ff" * 32
        self.vault.pending_since = 1000000
        self.assertTrue(self.vault.is_pending)

    def test_balance_kas(self):
        self.assertEqual(self.vault.balance_kas, 1.0)

    def test_to_dict(self):
        d = self.vault.to_dict()
        self.assertEqual(d["balance_kas"], 1.0)
        self.assertEqual(d["status"], "active")
        self.assertIn("...", d["hot_pubkey"])


class TestVaultStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = VaultStore(storage_dir=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_store(self):
        self.assertEqual(len(self.store.list_all()), 0)

    def test_save_and_get(self):
        v = VaultState(
            vault_id="v_1",
            hot_pubkey="ab" * 32,
            cold_pubkey="cd" * 32,
            whitelist_dest="ef" * 32,
            balance_sompi=100_000_000,
        )
        self.store.save(v)
        self.assertIsNotNone(self.store.get("v_1"))
        self.assertEqual(len(self.store.list_active()), 1)

    def test_persistence(self):
        v = VaultState(
            vault_id="v_2",
            hot_pubkey="ab" * 32,
            cold_pubkey="cd" * 32,
            whitelist_dest="ef" * 32,
            balance_sompi=100_000_000,
        )
        self.store.save(v)
        store2 = VaultStore(storage_dir=self.tmp.name)
        self.assertIsNotNone(store2.get("v_2"))


class TestVaultLifecycle(unittest.TestCase):
    """Full vault lifecycle: create → initiate → cancel → initiate → finalize."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = VaultStore(storage_dir=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _make_vault(self) -> str:
        whitelist = "kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k"
        result = create_vault(
            hot_pubkey="ab" * 32,
            cold_pubkey="cd" * 32,
            whitelist_address=whitelist,
            balance_kas=10.0,
            delay_daa=1000,
        )
        self.assertTrue(result["ok"])
        vid = result["vault_id"]
        # Move vault from default store to test store
        default_store = __import__("vida.plugins.covenant.vault", fromlist=["VaultStore"]).VaultStore()
        v = default_store.get(vid)
        if v:
            self.store.save(v)
        return vid

    def test_create_vault(self):
        vid = self._make_vault()
        vault = self.store.get(vid)
        self.assertIsNotNone(vault)

    def test_initiate_withdrawal(self):
        vid = self._make_vault()
        whitelist = "kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k"

        result = initiate_withdrawal(vid, "ab" * 64, whitelist, 1000000, store=self.store)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "initiated")

    def test_initiate_bad_destination(self):
        vid = self._make_vault()
        result = initiate_withdrawal(vid, "ab" * 64, "kaspa:badaddress", 1000000, store=self.store)
        self.assertFalse(result["ok"])

    def test_cancel_withdrawal(self):
        vid = self._make_vault()
        whitelist = "kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k"

        # Initiate
        initiate_withdrawal(vid, "ab" * 64, whitelist, 1000000, store=self.store)

        # Cancel
        result = cancel_withdrawal(vid, "cd" * 64, store=self.store)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "active")

    def test_cancel_no_pending(self):
        vid = self._make_vault()
        result = cancel_withdrawal(vid, "cd" * 64, store=self.store)
        self.assertFalse(result["ok"])

    def test_finalize_before_delay(self):
        vid = self._make_vault()
        whitelist = "kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k"

        initiate_withdrawal(vid, "ab" * 64, whitelist, 1000000, store=self.store)

        # Try to finalize before delay expires
        result = finalize_withdrawal(vid, 1000500, store=self.store)  # Only 500 DAA later
        self.assertFalse(result["ok"])
        self.assertIn("delay not expired", result.get("error", ""))

    def test_finalize_after_delay(self):
        vid = self._make_vault()
        whitelist = "kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k"

        initiate_withdrawal(vid, "ab" * 64, whitelist, 1000000, store=self.store)

        # Finalize after delay (1000 DAA delay, so 1002000 is after)
        result = finalize_withdrawal(vid, 1002000, store=self.store)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "finalized")

    def test_full_cycle_initiate_cancel_initiate_finalize(self):
        vid = self._make_vault()
        whitelist = "kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k"

        # Round 1: initiate then cancel
        self.assertTrue(initiate_withdrawal(vid, "ab" * 64, whitelist, 1000000, store=self.store)["ok"])
        self.assertTrue(cancel_withdrawal(vid, "cd" * 64, store=self.store)["ok"])

        # Round 2: initiate again, wait, finalize
        self.assertTrue(initiate_withdrawal(vid, "ab" * 64, whitelist, 2000000, store=self.store)["ok"])
        self.assertTrue(finalize_withdrawal(vid, 2002000, store=self.store)["ok"])

        # Verify final state
        vault = self.store.get(vid)
        self.assertEqual(vault.status, "finalized")


class TestVaultHermesTools(unittest.TestCase):
    def test_vida_vault_create(self):
        result = vida_vault_create(
            hot_pubkey="ab" * 32,
            cold_pubkey="cd" * 32,
            whitelist_address="kaspa:test",
            balance_kas=5.0,
        )
        self.assertTrue(result["ok"])
        self.assertIn("vault_id", result)

    def test_vida_vault_list(self):
        result = vida_vault_list()
        self.assertTrue(result["ok"])

    def test_vida_vault_status_not_found(self):
        result = vida_vault_status("nonexistent")
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
