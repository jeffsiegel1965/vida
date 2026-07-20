#!/usr/bin/env python3
"""T1.2 owner derivation + encrypted provision — offline unit tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Known BIP39 test vector (NOT for funds)
TEST_MNEMONIC = (
    "abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon about"
)
# Expected cold SS58 prefix 42 from substrate-interface (captured in this env)
EXPECTED_COLD = "5EPCUjPxiHAcNooYipQFWr9NmmXJKpNG5RhcntXwbtUySrgH"
EXPECTED_HOT = "5DUfE6odm5zHq9GqArraUFKDny34ormTU5FPLAhgKnSWUd8y"


class TestDerive(unittest.TestCase):
    def test_deterministic_addresses(self):
        from vida.plugins.tao.derive import derive_tao_keys, wipe_secrets

        k1 = derive_tao_keys(TEST_MNEMONIC, ss58_prefix=42)
        k2 = derive_tao_keys(TEST_MNEMONIC, ss58_prefix=42)
        self.assertEqual(k1.ss58_address, EXPECTED_COLD)
        self.assertEqual(k1.hotkey_ss58, EXPECTED_HOT)
        self.assertEqual(k1.ss58_address, k2.ss58_address)
        self.assertEqual(k1.hotkey_ss58, k2.hotkey_ss58)
        self.assertNotEqual(k1.ss58_address, k1.hotkey_ss58)
        pub = k1.public_dict()
        self.assertNotIn("cold_private_hex", pub)
        wipe_secrets(k1)
        self.assertEqual(k1.cold_private_hex, "")

    def test_invalid_mnemonic(self):
        from vida.plugins.tao.derive import derive_tao_keys

        with self.assertRaises(ValueError):
            derive_tao_keys("not a real mnemonic phrase at all here")


class TestProvision(unittest.TestCase):
    def test_provision_encrypt_unlock(self):
        from vida.plugins.tao.accounts import TaoAccountStore
        from vida.plugins.tao.provision import provision_tao_account, unlock_tao_secrets

        with tempfile.TemporaryDirectory() as td:
            store = TaoAccountStore(td)
            r = provision_tao_account(
                wallet_id="w-test",
                mnemonic=TEST_MNEMONIC,
                password="test-password-not-for-prod",
                network="mock",
                store=store,
                ss58_prefix=42,
            )
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["ss58_address"], EXPECTED_COLD)
            self.assertNotIn("cold_private_hex", str(r))
            rec = store.load("w-test")
            self.assertIsNotNone(rec)
            assert rec is not None
            self.assertTrue(rec.provisioned)
            pub = rec.to_public_dict()
            self.assertTrue(pub["has_enc_cold_material"])
            # wrong password fails
            bad = unlock_tao_secrets(rec, "wrong")
            self.assertFalse(bad["ok"])
            good = unlock_tao_secrets(rec, "test-password-not-for-prod")
            self.assertTrue(good["ok"])
            self.assertIn("cold_private_hex", good["secrets"])
            self.assertEqual(good["secrets"]["hotkey_ss58"], EXPECTED_HOT)

    def test_no_overwrite(self):
        from vida.plugins.tao.accounts import TaoAccountStore
        from vida.plugins.tao.provision import provision_tao_account

        with tempfile.TemporaryDirectory() as td:
            store = TaoAccountStore(td)
            r1 = provision_tao_account(
                wallet_id="w1",
                mnemonic=TEST_MNEMONIC,
                password="pw",
                network="mock",
                store=store,
            )
            self.assertTrue(r1["ok"])
            r2 = provision_tao_account(
                wallet_id="w1",
                mnemonic=TEST_MNEMONIC,
                password="pw",
                network="mock",
                store=store,
            )
            self.assertFalse(r2["ok"])


class TestPluginOwnerProvision(unittest.TestCase):
    def test_agent_path_blocked_owner_path_works(self):
        from vida.plugins import VidaPluginContext
        from vida.plugins.tao import TaoAccountStore, TaoConfig, TaoNetwork, TaoPlugin

        with tempfile.TemporaryDirectory() as td:
            store = TaoAccountStore(td)
            plugin = TaoPlugin(
                config=TaoConfig(network=TaoNetwork.MOCK),
                account_store=store,
            )
            blocked = plugin.provision_from_seed(TEST_MNEMONIC)
            self.assertFalse(blocked["ok"])
            r = plugin.owner_provision(
                wallet_id="w1",
                mnemonic=TEST_MNEMONIC,
                password="pw",
            )
            self.assertTrue(r["ok"], r)
            st = plugin.status(VidaPluginContext(wallet_id="w1", mode="COMMAND"))
            self.assertTrue(st["provisioned"])
            self.assertEqual(st["ss58_address"], EXPECTED_COLD)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
