#!/usr/bin/env python3
"""Tests: P2P transfer + yield optimizer (mock)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from decimal import Decimal
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
from vida.plugins.tao.session import grant_tao_agent_session  # noqa: E402
from vida.plugins.tao.yield_optimizer import (  # noqa: E402
    ValidatorScore,
    build_yield_plan,
)

TEST_MNEMONIC = (
    "abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon about"
)


class TestYieldPlan(unittest.TestCase):
    def test_plan_stake(self):
        cands = [
            ValidatorScore(1, 2, "5HotA", 100, True, 100.0),
            ValidatorScore(1, 3, "5HotB", 50, True, 50.0),
        ]
        plan = build_yield_plan(
            free_tao="1.0", netuid=1, candidates=cands, reserve_tao="0.1", min_stake="0.05"
        )
        self.assertEqual(plan.action, "stake")
        self.assertEqual(plan.target_hotkey, "5HotA")
        self.assertEqual(plan.stake_amount, Decimal("0.9"))

    def test_plan_hold_if_low(self):
        cands = [ValidatorScore(1, 0, "5X", 1, True, 1.0)]
        plan = build_yield_plan(
            free_tao="0.015", netuid=1, candidates=cands, reserve_tao="0.01", min_stake="0.02"
        )
        self.assertEqual(plan.action, "none")


class TestTransferAndOptimize(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.store = TaoAccountStore(self.td.name)
        self.client = MockTaoClient(balances={"5EPCUjPxiHAcNooYipQFWr9NmmXJKpNG5RhcntXwbtUySrgH": Decimal("1.0")})
        self.client.mock_validators = [
            ValidatorScore(1, 0, "5ValidatorTop", 999, True, 999.0),
            ValidatorScore(1, 1, "5ValidatorTwo", 10, True, 10.0),
        ]
        self.plugin = TaoPlugin(
            config=TaoConfig(network=TaoNetwork.MOCK),
            client=self.client,
            account_store=self.store,
        )
        r = self.plugin.owner_provision(
            wallet_id="w1", mnemonic=TEST_MNEMONIC, password="pw"
        )
        self.assertTrue(r["ok"], r)
        self.session = str(Path(self.td.name) / "sess.json")
        g = grant_tao_agent_session(
            store=self.store,
            wallet_id="w1",
            password="pw",
            session_path=self.session,
            hours=2,
            mode="FULL",
            max_tao_per_tx=1.0,
            max_tao_per_day=2.0,
            allowed_subnets=[1],
            allowed_destinations=["5SomeoneElseAddress000000000000000000000"],
            scope="ALL",
        )
        self.assertTrue(g["ok"], g)

    def tearDown(self):
        self.td.cleanup()

    def test_transfer_via_session(self):
        r = self.plugin.transfer(
            VidaPluginContext(wallet_id="w1", mode="COMMAND"),
            dest_ss58="5SomeoneElseAddress000000000000000000000",
            amount_tao=0.05,
            confirm=True,
            session_path=self.session,
        )
        self.assertTrue(r["ok"], r)
        self.assertEqual(r.get("unlock_via"), "session")
        self.assertTrue(str(r.get("extrinsic_hash", "")).startswith("mock_transfer"))

    def test_optimize_plan_and_execute(self):
        plan = self.plugin.optimize_yield(
            VidaPluginContext(wallet_id="w1", mode="FULL"),
            netuid=1,
            reserve_tao=0.1,
            min_stake=0.05,
            execute=False,
        )
        self.assertTrue(plan.get("ok"), plan)
        self.assertEqual(plan.get("action"), "stake")
        self.assertEqual(plan.get("target_hotkey"), "5ValidatorTop")

        exe = self.plugin.optimize_yield(
            VidaPluginContext(wallet_id="w1", mode="COMMAND"),
            netuid=1,
            reserve_tao=0.1,
            min_stake=0.05,
            execute=True,
            confirm=True,
            session_path=self.session,
        )
        self.assertTrue(exe.get("executed"), exe)
        self.assertTrue((exe.get("stake_result") or {}).get("ok"), exe)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
