"""Tests for KCC-0402 aligned payment channels."""
from __future__ import annotations

import os
import tempfile
import unittest

from vida.plugins.covenant.channels import (
    # Legacy
    ChannelStore,
    KCC0402Channel,
    KCC0402ChannelStore,
    PaymentChannel,
    close_channel,
    close_kcc0402,
    create_voucher,
    open_channel,
    open_kcc0402,
    pay_kcc0402,
    update_channel,
    verify_voucher,
    vida_channel_close,
    vida_channel_list,
    vida_channel_offer,
    vida_channel_open,
    vida_channel_pay,
    vida_channel_status,
    vida_channel_voucher,
    voucher_digest,
    voucher_message,
)


class TestVoucherFormat(unittest.TestCase):
    """KCC-0402 voucher message format."""

    def test_message_format(self):
        cid = "ab" * 32
        total = 5000000
        msg = voucher_message(cid, total)
        self.assertEqual(len(msg), 40)  # 32 + 8
        self.assertEqual(msg[:32], bytes.fromhex(cid))
        self.assertEqual(msg[32:], total.to_bytes(8, 'little'))

    def test_message_bad_channel_id(self):
        with self.assertRaises(ValueError):
            voucher_message("abcd", 1000)  # only 2 bytes

    def test_message_negative_total(self):
        with self.assertRaises(ValueError):
            voucher_message("ab" * 32, -1)

    def test_digest(self):
        cid = "ab" * 32
        total = 5000000
        d = voucher_digest(cid, total)
        self.assertEqual(len(d), 64)  # SHA-256 hex
        self.assertTrue(all(c in "0123456789abcdef" for c in d))

    def test_verify_voucher_valid_hex(self):
        result = verify_voucher("ab" * 32, 5000000, "ab" * 64, "cd" * 32)
        self.assertTrue(result)

    def test_verify_voucher_bad_hex(self):
        result = verify_voucher("ab" * 32, 5000000, "nothex", "cd" * 32)
        self.assertFalse(result)

    def test_verify_voucher_wrong_length(self):
        result = verify_voucher("ab" * 32, 5000000, "ab" * 32, "cd" * 32)
        self.assertFalse(result)


class TestKCC0402Channel(unittest.TestCase):
    """KCC-0402 channel state."""

    def setUp(self):
        self.channel = KCC0402Channel(
            payer_pubkey="ab" * 32,
            payee_pubkey="cd" * 32,
            expiry_daa=1000000,
            maxfee_sompi=5000000,
        )
        self.channel.channel_id = "ef" * 32
        self.channel.capacity_sompi = 100_000_000

    def test_to_dict(self):
        d = self.channel.to_dict()
        self.assertEqual(d["capacity_kas"], 1.0)
        self.assertEqual(d["status"], "open")
        self.assertEqual(d["paid_kas"], 0.0)

    def test_payer_remainder_full(self):
        self.assertEqual(self.channel.payer_remainder(), 95_000_000)

    def test_payer_remainder_partial(self):
        self.channel.cumulative_paid_sompi = 30_000_000
        self.assertEqual(self.channel.payer_remainder(), 65_000_000)

    def test_verify_voucher_rejects_old_total(self):
        self.channel.cumulative_paid_sompi = 50_000_000
        result = self.channel.verify_voucher(40_000_000, "ab" * 64)
        self.assertFalse(result)

    def test_verify_voucher_rejects_over_capacity(self):
        result = self.channel.verify_voucher(96_000_000, "ab" * 64)
        self.assertFalse(result)

    def test_offer(self):
        offer = KCC0402Channel.offer(payee_pubkey="ab" * 32)
        self.assertEqual(offer["scheme"], "kaspa-channel")
        self.assertEqual(offer["payee_pubkey"], "ab" * 32)
        self.assertIn("min_channel_sompi", offer)
        self.assertIn("maxfee_sompi", offer)


class TestKCC0402ChannelStore(unittest.TestCase):
    """KCC-0402 channel persistence."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = KCC0402ChannelStore(storage_dir=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_store(self):
        self.assertEqual(len(self.store.list_all()), 0)

    def test_save_and_get(self):
        ch = KCC0402Channel(
            payer_pubkey="ab" * 32,
            payee_pubkey="cd" * 32,
            expiry_daa=1000000,
            maxfee_sompi=5000000,
        )
        ch.channel_id = "ch_1"
        ch.capacity_sompi = 100_000_000
        self.store.save(ch)
        self.assertIsNotNone(self.store.get("ch_1"))
        self.assertEqual(len(self.store.list_open()), 1)

    def test_close(self):
        ch = KCC0402Channel(
            payer_pubkey="ab" * 32,
            payee_pubkey="cd" * 32,
            expiry_daa=1000000,
            maxfee_sompi=5000000,
        )
        ch.channel_id = "ch_2"
        ch.capacity_sompi = 100_000_000
        self.store.save(ch)
        ch.status = "closed"
        self.store.save(ch)
        self.assertEqual(len(self.store.list_open()), 0)

    def test_persistence(self):
        ch = KCC0402Channel(
            payer_pubkey="ab" * 32,
            payee_pubkey="cd" * 32,
            expiry_daa=1000000,
            maxfee_sompi=5000000,
        )
        ch.channel_id = "ch_3"
        ch.capacity_sompi = 100_000_000
        self.store.save(ch)
        store2 = KCC0402ChannelStore(storage_dir=self.tmp.name)
        self.assertIsNotNone(store2.get("ch_3"))


class TestKCC0402Operations(unittest.TestCase):
    """KCC-0402 channel lifecycle."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = KCC0402ChannelStore(storage_dir=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_open_channel(self):
        result = open_kcc0402(
            payer_pubkey="ab" * 32,
            payee_pubkey="cd" * 32,
            capacity_sompi=100_000_000,
            expiry_daa=1000000,
        )
        self.assertTrue(result["ok"])
        self.assertIn("channel_id", result)
        self.assertEqual(result["capacity_kas"], 1.0)

    def test_open_with_voucher(self):
        import secrets

        from kaspa import PrivateKey

        key_hex = secrets.token_hex(32)
        priv = PrivateKey(key_hex)
        pub = priv.to_public_key()
        xonly = pub.to_x_only_public_key()

        result = open_kcc0402(
            payer_pubkey=xonly.to_string(),
            payee_pubkey="cd" * 32,
            capacity_sompi=100_000_000,
            expiry_daa=1000000,
            payer_privkey_hex=key_hex,
        )
        self.assertTrue(result["ok"])
        self.assertIn("genesis_voucher", result)

    def test_pay_and_close(self):
        import secrets

        from kaspa import PrivateKey

        key_hex = secrets.token_hex(32)
        priv = PrivateKey(key_hex)
        pub = priv.to_public_key()
        xonly = pub.to_x_only_public_key()

        # Open
        open_result = open_kcc0402(
            payer_pubkey=xonly.to_string(),
            payee_pubkey="cd" * 32,
            capacity_sompi=100_000_000,
            expiry_daa=1000000,
        )
        cid = open_result["channel_id"]

        # Pay
        pay_result = pay_kcc0402(cid, 30_000_000, key_hex)
        self.assertTrue(pay_result["ok"])
        self.assertEqual(pay_result["cumulative_total_sompi"], 30_000_000)
        self.assertEqual(pay_result["paid_kas"], 0.3)

        # Close
        close_result = close_kcc0402(cid, store=self.store)
        self.assertTrue(close_result["ok"])
        self.assertEqual(close_result["payee_gets_kas"], 0.3)

    def test_pay_nonexistent(self):
        result = pay_kcc0402("nonexistent", 1000, "ab" * 32)
        self.assertFalse(result["ok"])

    def test_pay_closed(self):
        import secrets

        from kaspa import PrivateKey

        key_hex = secrets.token_hex(32)
        priv = PrivateKey(key_hex)
        pub = priv.to_public_key()
        xonly = pub.to_x_only_public_key()

        open_result = open_kcc0402(
            payer_pubkey=xonly.to_string(),
            payee_pubkey="cd" * 32,
            capacity_sompi=100_000_000,
            expiry_daa=1000000,
        )
        cid = open_result["channel_id"]
        close_kcc0402(cid, store=self.store)
        result = pay_kcc0402(cid, 10_000_000, key_hex, store=self.store)
        self.assertFalse(result["ok"])

    def test_close_nonexistent(self):
        result = close_kcc0402("nonexistent")
        self.assertFalse(result["ok"])

    def test_close_already_closed(self):
        import secrets

        from kaspa import PrivateKey

        key_hex = secrets.token_hex(32)
        open_result = open_kcc0402(
            payer_pubkey="ab" * 32,
            payee_pubkey="cd" * 32,
            capacity_sompi=100_000_000,
            expiry_daa=1000000,
        )
        cid = open_result["channel_id"]
        close_kcc0402(cid, store=self.store)
        result = close_kcc0402(cid, store=self.store)
        self.assertFalse(result["ok"])


class TestHermesTools(unittest.TestCase):
    """Hermes tool wrappers for KCC-0402."""

    def test_channel_open_kcc0402(self):
        result = vida_channel_open(
            party_a_or_payer="ab" * 32,
            party_b_or_payee="cd" * 32,
            capacity_kas_or_sompi=100_000_000,
            mode="kcc0402",
            expiry_daa=1000000,
        )
        self.assertTrue(result["ok"])
        self.assertIn("channel_id", result)

    def test_channel_open_bidirectional(self):
        result = vida_channel_open(
            party_a_or_payer="party_a",
            party_b_or_payee="party_b",
            capacity_kas_or_sompi=1.0,
            mode="bidirectional",
        )
        self.assertTrue(result["ok"])

    def test_channel_pay(self):
        import secrets

        from kaspa import PrivateKey

        key_hex = secrets.token_hex(32)
        priv = PrivateKey(key_hex)
        pub = priv.to_public_key()
        xonly = pub.to_x_only_public_key()

        open_result = vida_channel_open(
            party_a_or_payer=xonly.to_string(),
            party_b_or_payee="cd" * 32,
            capacity_kas_or_sompi=100_000_000,
            mode="kcc0402",
            expiry_daa=1000000,
        )
        cid = open_result["channel_id"]
        result = vida_channel_pay(cid, 15_000_000, key_hex)
        self.assertTrue(result["ok"])

    def test_channel_close(self):
        import secrets

        open_result = vida_channel_open(
            party_a_or_payer="ab" * 32,
            party_b_or_payee="cd" * 32,
            capacity_kas_or_sompi=100_000_000,
            mode="kcc0402",
            expiry_daa=1000000,
        )
        cid = open_result["channel_id"]
        result = vida_channel_close(cid, mode="kcc0402")
        self.assertTrue(result["ok"])

    def test_status(self):
        open_result = vida_channel_open(
            party_a_or_payer="ab" * 32,
            party_b_or_payee="cd" * 32,
            capacity_kas_or_sompi=100_000_000,
            mode="kcc0402",
            expiry_daa=1000000,
        )
        cid = open_result["channel_id"]
        status = vida_channel_status(cid)
        self.assertTrue(status["ok"])
        self.assertEqual(status["mode"], "kcc0402")

    def test_list(self):
        result = vida_channel_list()
        self.assertTrue(result["ok"])

    def test_offer(self):
        result = vida_channel_offer(payee_pubkey="ab" * 32)
        self.assertTrue(result["ok"])
        self.assertEqual(result["offer"]["scheme"], "kaspa-channel")

    def test_voucher(self):
        import secrets

        from kaspa import PrivateKey

        key_hex = secrets.token_hex(32)
        result = vida_channel_voucher("ab" * 32, 5000000, key_hex)
        self.assertTrue(result["ok"])
        self.assertIn("voucher", result)
        self.assertEqual(len(result["voucher"]), 128)  # 64 bytes hex


class TestLegacyBidirectional(unittest.TestCase):
    """Legacy bidirectional channel tests (unchanged)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ChannelStore(storage_dir=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_open(self):
        result = open_channel("a", "b", 1.0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["capacity_kas"], 1.0)

    def test_update(self):
        c = PaymentChannel(
            id="ch_test", party_a="a", party_b="b",
            capacity_sompi=100_000_000, balance_a=100_000_000, balance_b=0,
        )
        self.store.save(c)
        result = update_channel("ch_test", "sig_a", "sig_b", 60_000_000, 40_000_000, store=self.store)
        self.assertTrue(result["ok"])
        self.assertEqual(result["balance_a_kas"], 0.6)

    def test_close(self):
        c = PaymentChannel(
            id="ch_test", party_a="a", party_b="b",
            capacity_sompi=100_000_000, balance_a=60_000_000, balance_b=40_000_000,
        )
        self.store.save(c)
        result = close_channel("ch_test", store=self.store)
        self.assertTrue(result["ok"])
        self.assertEqual(result["final_a_kas"], 0.6)

    def test_update_overflow(self):
        c = PaymentChannel(
            id="ch_test", party_a="a", party_b="b",
            capacity_sompi=100_000_000, balance_a=100_000_000, balance_b=0,
        )
        self.store.save(c)
        result = update_channel("ch_test", "sig_a", "sig_b", 200_000_000, 0)
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
