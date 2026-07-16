#!/usr/bin/env python3
"""Phase 0 plugin seam tests — no network required."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

# Allow `python tests/test_plugins_phase0.py` from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vida.plugins import (  # noqa: E402
    PluginRegistry,
    PolicyRequest,
    VidaPluginContext,
    evaluate_policy,
)
from vida.plugins.dummy import DummyPlugin  # noqa: E402


class TestPolicy(unittest.TestCase):
    def test_read_only_always_allowed(self):
        d = evaluate_policy(mode="COMMAND", amount=0, action="status")
        self.assertTrue(d.allowed)
        self.assertFalse(d.needs_approval)

    def test_negative_denied(self):
        d = evaluate_policy(mode="FULL", amount=-1.0, action="transfer")
        self.assertFalse(d.allowed)

    def test_nan_denied(self):
        d = evaluate_policy(mode="FULL", amount=float("nan"), action="transfer")
        self.assertFalse(d.allowed)

    def test_command_needs_approval(self):
        d = evaluate_policy(mode="COMMAND", amount=1.0, action="transfer")
        self.assertFalse(d.allowed)
        self.assertTrue(d.needs_approval)

    def test_full_within_caps(self):
        d = evaluate_policy(
            mode="FULL",
            amount=2.0,
            max_per_tx=5.0,
            daily_limit=10.0,
            daily_spent=1.0,
            action="transfer",
        )
        self.assertTrue(d.allowed)

    def test_full_over_daily(self):
        d = evaluate_policy(
            mode="FULL",
            amount=5.0,
            daily_limit=10.0,
            daily_spent=6.0,
            action="transfer",
        )
        self.assertFalse(d.allowed)

    def test_hybrid_under_threshold(self):
        d = evaluate_policy(
            mode="HYBRID", amount=3.0, threshold=5.0, action="transfer"
        )
        self.assertTrue(d.allowed)

    def test_hybrid_over_threshold(self):
        d = evaluate_policy(
            mode="HYBRID", amount=6.0, threshold=5.0, action="transfer"
        )
        self.assertFalse(d.allowed)
        self.assertTrue(d.needs_approval)

    def test_action_allowlist(self):
        d = evaluate_policy(
            mode="FULL",
            amount=1.0,
            action="delegate",
            allowed_actions=["transfer"],
        )
        self.assertFalse(d.allowed)


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = PluginRegistry()

    def test_register_and_list(self):
        self.reg.register(DummyPlugin())
        names = self.reg.names()
        self.assertEqual(names, ["dummy"])
        listed = self.reg.list_plugins()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["name"], "dummy")
        self.assertEqual(listed[0]["chain"], "none")
        self.assertIn("status", listed[0]["capabilities"])

    def test_duplicate_rejected(self):
        self.reg.register(DummyPlugin())
        with self.assertRaises(ValueError):
            self.reg.register(DummyPlugin())

    def test_get(self):
        self.reg.register(DummyPlugin())
        p = self.reg.get("dummy")
        self.assertIsNotNone(p)
        self.assertIsNone(self.reg.get("nope"))


class TestDummyPlugin(unittest.TestCase):
    def test_status(self):
        p = DummyPlugin()
        ctx = VidaPluginContext(wallet_id="w1", mode="FULL")
        st = p.status(ctx)
        self.assertTrue(st["ok"])
        self.assertEqual(st["wallet_id"], "w1")

    def test_fake_spend_full(self):
        p = DummyPlugin()
        ctx = VidaPluginContext(
            wallet_id="w1", mode="FULL", max_per_tx=10.0, daily_limit=10.0
        )
        r = p.fake_spend(ctx, 1.5)
        self.assertTrue(r["ok"])

    def test_fake_spend_command(self):
        p = DummyPlugin()
        ctx = VidaPluginContext(wallet_id="w1", mode="COMMAND")
        r = p.fake_spend(ctx, 1.0)
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("needs_approval"))

    def test_context_decide(self):
        ctx = VidaPluginContext(wallet_id="w1", mode="FULL", max_per_tx=1.0)
        d = ctx.decide(PolicyRequest(chain="none", action="transfer", amount=2.0))
        self.assertFalse(d.allowed)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    # sanity: math import used for nan path indirectly
    assert not math.isfinite(float("nan"))
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
