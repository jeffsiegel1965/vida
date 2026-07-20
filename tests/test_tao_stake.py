#!/usr/bin/env python3
"""Phase 1B — policy-gated stake tests (mock client; no live funds)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vida.plugins import VidaPluginContext  # noqa: E402
from vida.plugins.tao import (  # noqa: E402
    MockTaoClient,
    TaoAccountStore,
    TaoConfig,
    TaoNetwork,
    TaoPlugin,
)
from vida.plugins.tao.staking import evaluate_stake  # noqa: E402

TEST_MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"


class TestStakePolicy(unittest.TestCase):
    def test_command_denied(self):
        d = evaluate_stake(mode="COMMAND", amount=1.0, action="delegate", netuid=1)
        self.assertFalse(d.allowed)
        self.assertTrue(d.needs_approval)

    def test_full_ok(self):
        d = evaluate_stake(
            mode="FULL",
            amount=1.0,
            action="delegate",
            netuid=1,
            max_per_tx=5.0,
            daily_limit=10.0,
        )
        self.assertTrue(d.allowed)

    def test_subnet_block(self):
        d = evaluate_stake(
            mode="FULL",
            amount=1.0,
            action="delegate",
            netuid=99,
            allowed_subnets=[1, 2],
        )
        self.assertFalse(d.allowed)

    def test_revoked(self):
        d = evaluate_stake(
            mode="FULL",
            amount=1.0,
            action="delegate",
            netuid=1,
            session_revoked=True,
        )
        self.assertFalse(d.allowed)

    def test_negative(self):
        d = evaluate_stake(mode="FULL", amount=-1.0, action="delegate", netuid=1)
        self.assertFalse(d.allowed)

    def test_over_daily(self):
        d = evaluate_stake(
            mode="FULL",
            amount=5.0,
            action="delegate",
            netuid=1,
            daily_limit=10.0,
            daily_spent=6.0,
        )
        self.assertFalse(d.allowed)


class TestStakeMockPath(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.store = TaoAccountStore(self.td.name)
        self.client = MockTaoClient()
        self.plugin = TaoPlugin(
            config=TaoConfig(network=TaoNetwork.MOCK),
            client=self.client,
            account_store=self.store,
        )
        r = self.plugin.owner_provision(
            wallet_id="w1",
            mnemonic=TEST_MNEMONIC,
            password="pw",
        )
        self.assertTrue(r["ok"], r)

    def tearDown(self):
        self.td.cleanup()

    def test_confirm_required(self):
        ctx = VidaPluginContext(wallet_id="w1", mode="FULL", max_per_tx=10.0, daily_limit=10.0)
        r = self.plugin.delegate(ctx, amount_tao=0.1, netuid=1, confirm=False, password="pw")
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("needs_confirm"))

    def test_command_blocked(self):
        ctx = VidaPluginContext(wallet_id="w1", mode="COMMAND")
        r = self.plugin.delegate(ctx, amount_tao=0.1, netuid=1, confirm=True, password="pw")
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("needs_approval"))

    def test_delegate_mock_success(self):
        ctx = VidaPluginContext(
            wallet_id="w1",
            mode="FULL",
            max_per_tx=10.0,
            daily_limit=10.0,
            allowed_subnets=[1],
        )
        r = self.plugin.delegate(ctx, amount_tao=0.5, netuid=1, confirm=True, password="pw")
        self.assertTrue(r["ok"], r)
        self.assertTrue(str(r.get("extrinsic_hash", "")).startswith("mock_delegate"))
        self.assertTrue(r.get("mock"))

    def test_undelegate_mock_success(self):
        ctx = VidaPluginContext(wallet_id="w1", mode="FULL", max_per_tx=10.0, daily_limit=10.0)
        r = self.plugin.undelegate(ctx, amount_tao=0.2, netuid=3, confirm=True, password="pw")
        self.assertTrue(r["ok"], r)
        self.assertIn("mock_undelegate", r.get("extrinsic_hash", ""))

    def test_disallowed_subnet(self):
        ctx = VidaPluginContext(
            wallet_id="w1",
            mode="FULL",
            max_per_tx=10.0,
            allowed_subnets=[1],
        )
        r = self.plugin.delegate(ctx, amount_tao=0.1, netuid=9, confirm=True, password="pw")
        self.assertFalse(r["ok"])

    def test_revoked_session(self):
        ctx = VidaPluginContext(wallet_id="w1", mode="FULL", max_per_tx=10.0, session_revoked=True)
        r = self.plugin.delegate(ctx, amount_tao=0.1, netuid=1, confirm=True, password="pw")
        self.assertFalse(r["ok"])

    def test_wrong_password(self):
        ctx = VidaPluginContext(wallet_id="w1", mode="FULL", max_per_tx=10.0, daily_limit=10.0)
        r = self.plugin.delegate(ctx, amount_tao=0.1, netuid=1, confirm=True, password="nope")
        self.assertFalse(r["ok"])


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
