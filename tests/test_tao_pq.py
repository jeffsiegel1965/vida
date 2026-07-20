#!/usr/bin/env python3
"""TAO PQ-ready identity tests (ML-DSA-65), same honesty model as Kaspa."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vida"))

from vida.plugins.tao.accounts import TaoAccountStore
from vida.plugins.tao.pq import PQ_AVAILABLE, generate_pq_identity, verify_message
from vida.plugins.tao.provision import (
    ensure_tao_pq_identity,
    owner_sign_pq,
    provision_tao_account,
    unlock_tao_secrets,
)

TEST_MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"


@unittest.skipUnless(PQ_AVAILABLE, "ml_dsa_65 / pqcrypto not available")
class TestTaoPQ(unittest.TestCase):
    def test_provision_includes_pq(self):
        with tempfile.TemporaryDirectory() as td:
            store = TaoAccountStore(td)
            r = provision_tao_account(
                wallet_id="pq1",
                mnemonic=TEST_MNEMONIC,
                password="test-password-long",
                network="mock",
                store=store,
                overwrite=True,
                with_pq=True,
            )
            self.assertTrue(r["ok"], r)
            self.assertTrue(r.get("pq_ready"), r)
            self.assertEqual(r.get("pq_scheme"), "ML-DSA-65")
            self.assertFalse(r.get("pq_on_chain"))
            rec = store.load("pq1")
            assert rec is not None
            self.assertTrue(rec.pq_public_key)
            self.assertTrue(rec.enc_pq_sk)
            pub = rec.to_public_dict()
            self.assertTrue(pub["pq_ready"])
            self.assertNotIn("enc_pq_sk", pub)
            # secrets not in public
            self.assertNotIn("pq_secret", str(pub).lower())

    def test_unlock_pq_and_sign(self):
        with tempfile.TemporaryDirectory() as td:
            store = TaoAccountStore(td)
            provision_tao_account(
                wallet_id="pq2",
                mnemonic=TEST_MNEMONIC,
                password="pw-for-pq-test-99",
                network="mock",
                store=store,
                overwrite=True,
            )
            rec = store.load("pq2")
            assert rec is not None
            u = unlock_tao_secrets(rec, "pw-for-pq-test-99", include_pq=True)
            self.assertTrue(u["ok"], u)
            self.assertIn("pq_secret_key_bytes", u)
            self.assertIn("cold_private_hex", u["secrets"])
            # agent-style unlock without pq
            u2 = unlock_tao_secrets(rec, "pw-for-pq-test-99", include_pq=False)
            self.assertTrue(u2["ok"])
            self.assertNotIn("pq_secret_key_bytes", u2)

            sig = owner_sign_pq(rec, "pw-for-pq-test-99", b"vida-tao-pq-attestation")
            self.assertTrue(sig["ok"], sig)
            self.assertTrue(sig["verified"])
            self.assertFalse(sig["pq_on_chain"])
            self.assertTrue(
                verify_message(
                    b"vida-tao-pq-attestation",
                    bytes.fromhex(sig["signature_hex"]),
                    sig["pq_public_key"],
                )
            )

    def test_upgrade_existing_without_pq(self):
        with tempfile.TemporaryDirectory() as td:
            store = TaoAccountStore(td)
            r = provision_tao_account(
                wallet_id="pq3",
                mnemonic=TEST_MNEMONIC,
                password="upgrade-pw-12345",
                network="mock",
                store=store,
                overwrite=True,
                with_pq=False,
            )
            self.assertTrue(r["ok"])
            rec = store.load("pq3")
            assert rec is not None
            self.assertFalse(rec.pq_public_key)
            up = ensure_tao_pq_identity(wallet_id="pq3", password="upgrade-pw-12345", store=store)
            self.assertTrue(up["ok"], up)
            self.assertTrue(up.get("upgraded") or up.get("pq_ready"))
            rec2 = store.load("pq3")
            assert rec2 is not None
            self.assertTrue(rec2.pq_public_key and rec2.enc_pq_sk)
            # ss58 unchanged
            self.assertEqual(rec.ss58_address, rec2.ss58_address)

    def test_wrong_password_no_pq(self):
        with tempfile.TemporaryDirectory() as td:
            store = TaoAccountStore(td)
            provision_tao_account(
                wallet_id="pq4",
                mnemonic=TEST_MNEMONIC,
                password="correct-horse-battery",
                network="mock",
                store=store,
                overwrite=True,
            )
            rec = store.load("pq4")
            assert rec is not None
            bad = unlock_tao_secrets(rec, "wrong-password-xxx", include_pq=True)
            self.assertFalse(bad["ok"])


class TestTaoPQAvailability(unittest.TestCase):
    def test_generate_reports_availability(self):
        g = generate_pq_identity()
        if PQ_AVAILABLE:
            self.assertTrue(g["ok"])
            self.assertEqual(len(bytes.fromhex(g["pq_public_key_hex"])), 1952)
        else:
            self.assertFalse(g["ok"])


if __name__ == "__main__":
    unittest.main()
