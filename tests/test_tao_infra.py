#!/usr/bin/env python3
"""Phase 1 TAO infrastructure tests — offline only, no derivation, no RPC."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vida.plugins import PluginRegistry, VidaPluginContext  # noqa: E402
from vida.plugins.tao import (  # noqa: E402
    MockTaoClient,
    TaoAccountRecord,
    TaoAccountStore,
    TaoConfig,
    TaoNetwork,
    TaoPlugin,
    load_tao_config,
)
from vida.plugins.tao.client import UnimplementedLiveTaoClient  # noqa: E402


class TestTaoConfig(unittest.TestCase):
    def test_default_mock(self):
        cfg = load_tao_config(network="mock")
        self.assertEqual(cfg.network, TaoNetwork.MOCK)
        self.assertEqual(cfg.resolved_endpoints(), [])

    def test_finney_endpoints(self):
        cfg = load_tao_config(network="finney")
        self.assertEqual(cfg.network, TaoNetwork.FINNEY)
        self.assertTrue(len(cfg.resolved_endpoints()) >= 1)

    def test_endpoint_override(self):
        cfg = load_tao_config(network="finney", endpoint="wss://example.test")
        self.assertEqual(cfg.resolved_endpoints(), ["wss://example.test"])

    def test_bad_network(self):
        with self.assertRaises(ValueError):
            load_tao_config(network="ethereum")


class TestMockClient(unittest.TestCase):
    def test_health_requires_connect(self):
        c = MockTaoClient()
        h = c.health()
        self.assertFalse(h.ok)
        c.connect()
        h = c.health()
        self.assertTrue(h.ok)
        self.assertEqual(h.chain_name, "mock-bittensor")
        c.close()

    def test_balance(self):
        addr = "5FakeAddressForTestsOnly000000000000000000000"
        c = MockTaoClient(balances={addr: Decimal("12.5")})
        c.connect()
        b = c.get_balance(addr)
        self.assertTrue(b.ok)
        self.assertEqual(b.free_tao, Decimal("12.5"))
        b2 = c.get_balance("5Unknown")
        self.assertTrue(b2.ok)
        self.assertEqual(b2.free_tao, Decimal("0"))

    def test_live_placeholder_raises(self):
        c = UnimplementedLiveTaoClient()
        with self.assertRaises(NotImplementedError):
            c.connect()


class TestAccountStore(unittest.TestCase):
    def test_save_load_public(self):
        with tempfile.TemporaryDirectory() as td:
            store = TaoAccountStore(td)
            rec = TaoAccountRecord(
                wallet_id="w1",
                network="mock",
                ss58_address="",
                provisioned=False,
            )
            store.save(rec)
            loaded = store.load("w1")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.wallet_id, "w1")
            self.assertFalse(loaded.provisioned)
            pub = loaded.to_public_dict()
            self.assertNotIn("enc_cold_material", pub)
            self.assertFalse(pub["has_enc_cold_material"])
            # file mode 0600
            mode = store.path_for("w1").stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)

    def test_public_dict_hides_secrets(self):
        rec = TaoAccountRecord(
            wallet_id="w1",
            network="finney",
            ss58_address="5ABC",
            provisioned=True,
            enc_cold_material={"nonce": "x", "ct": "y"},
        )
        pub = rec.to_public_dict()
        self.assertTrue(pub["has_enc_cold_material"])
        dumped = json.dumps(pub)
        self.assertNotIn("nonce", dumped)


class TestTaoPlugin(unittest.TestCase):
    def test_register(self):
        reg = PluginRegistry()
        reg.register(TaoPlugin(config=TaoConfig(network=TaoNetwork.MOCK)))
        self.assertEqual(reg.names(), ["tao"])
        meta = reg.list_plugins()[0]
        self.assertEqual(meta["chain"], "bittensor")
        self.assertIn("status", meta["capabilities"])

    def test_status_not_provisioned(self):
        with tempfile.TemporaryDirectory() as td:
            store = TaoAccountStore(td)
            client = MockTaoClient()
            plugin = TaoPlugin(
                config=TaoConfig(network=TaoNetwork.MOCK),
                client=client,
                account_store=store,
            )
            ctx = VidaPluginContext(wallet_id="w1", mode="COMMAND")
            st = plugin.status(ctx)
            self.assertTrue(st["ok"])
            self.assertFalse(st["provisioned"])
            self.assertIsNone(st["ss58_address"])
            self.assertTrue(st["client"]["ok"])

    def test_status_provisioned_with_balance(self):
        with tempfile.TemporaryDirectory() as td:
            store = TaoAccountStore(td)
            addr = "5ProvTestAddress000000000000000000000000000"
            store.save(
                TaoAccountRecord(
                    wallet_id="w1",
                    network="mock",
                    ss58_address=addr,
                    provisioned=True,
                )
            )
            client = MockTaoClient(balances={addr: Decimal("3.25")})
            plugin = TaoPlugin(
                config=TaoConfig(network=TaoNetwork.MOCK),
                client=client,
                account_store=store,
            )
            st = plugin.status(VidaPluginContext(wallet_id="w1", mode="FULL"))
            self.assertTrue(st["provisioned"])
            self.assertEqual(st["ss58_address"], addr)
            self.assertEqual(st["balance"]["free_tao"], "3.25")

    def test_derivation_blocked(self):
        plugin = TaoPlugin(config=TaoConfig(network=TaoNetwork.MOCK))
        r = plugin.provision_from_seed(mnemonic="abandon " * 11 + "about")
        self.assertFalse(r["ok"])
        err = r["error"].lower()
        self.assertTrue("blocked" in err or "owner" in err)

    def test_policy_preflight_command(self):
        plugin = TaoPlugin(config=TaoConfig(network=TaoNetwork.MOCK))
        ctx = VidaPluginContext(wallet_id="w1", mode="COMMAND")
        r = plugin.check_action(ctx, "delegate", 1.0)
        self.assertFalse(r["allowed"])
        self.assertTrue(r["needs_approval"])

    def test_policy_preflight_full(self):
        plugin = TaoPlugin(config=TaoConfig(network=TaoNetwork.MOCK))
        ctx = VidaPluginContext(
            wallet_id="w1",
            mode="FULL",
            max_per_tx=10.0,
            daily_limit=10.0,
            allowed_actions=["delegate"],
        )
        r = plugin.check_action(ctx, "delegate", 1.0)
        self.assertTrue(r["allowed"])


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
