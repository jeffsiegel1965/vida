#!/usr/bin/env python3
"""Offline covenant plugin scaffold tests — no network, no broadcast."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vida.plugins.base import VidaPluginContext  # noqa: E402
from vida.plugins.covenant import (  # noqa: E402
    CovenantPlugin,
    load_covenant_config,
    plan_agent_pot,
    register_covenant_plugin,
    tn10_microproof,
    validate_agent_pot_plan,
)
from vida.plugins.registry import PluginRegistry  # noqa: E402


class TestCovenantScaffold(unittest.TestCase):
    def test_describe_and_status(self):
        p = CovenantPlugin()
        d = p.describe()
        self.assertEqual(d["name"], "covenant")
        self.assertEqual(d["phase"], "tn10_lab_proven_plugin_gated_live")
        self.assertFalse(d["live_enabled"])
        self.assertEqual(d["blocker"], "docs/plugins/COVENANT_BLOCKER_STATUS.md")
        self.assertIn("9fe45342", d["tn10_covenant_id"])
        ctx = VidaPluginContext(wallet_id="test", mode="COMMAND")
        st = p.status(ctx)
        self.assertTrue(st["ok"])
        self.assertFalse(st["live_deploy_available"])
        self.assertTrue(st["soft_policy_available"])
        self.assertTrue(st["tn10_lab_proven"])
        self.assertIn("computeBudget", st["budget_rules"]["field"])

    def test_budget_validate(self):
        p = CovenantPlugin()
        self.assertFalse(p.validate_budget(0)["ok"])
        self.assertTrue(p.validate_budget(10)["ok"])
        w = p.validate_budget(100)
        self.assertTrue(w["ok"])
        self.assertIn("warning", w)

    def test_deploy_and_spend_refuse(self):
        p = CovenantPlugin()
        for method in (p.deploy, p.spend):
            r = method()
            self.assertFalse(r["ok"])
            self.assertTrue(r.get("tn10_lab_proven"))
            self.assertIn("proof", r)
            self.assertNotIn("txid", r)

    def test_soft_policy_check_action(self):
        p = CovenantPlugin()
        ctx = VidaPluginContext(wallet_id="test", mode="COMMAND")
        r = p.check_action(ctx, "deploy", amount=1.0)
        self.assertFalse(r["allowed"])
        self.assertTrue(r["needs_approval"])
        self.assertFalse(r["on_chain_hard_cap"])
        self.assertEqual(r["enforcement"], "soft_policy")

    def test_registry(self):
        reg = PluginRegistry()
        plugin = register_covenant_plugin(reg)
        self.assertIsInstance(plugin, CovenantPlugin)
        names = reg.names()
        self.assertIn("covenant", names)
        listed = reg.list_plugins()
        self.assertTrue(any(x["name"] == "covenant" for x in listed))
        self.assertEqual(listed[0]["chain"], "kaspa")

    def test_timelock_sketch(self):
        p = CovenantPlugin()
        r = p.sketch_timelock(100)
        self.assertTrue(r["ok"])
        self.assertFalse(r["live_ready"])
        self.assertIsNone(r["bytecode_hex"])

    def test_config_defaults(self):
        cfg = load_covenant_config()
        self.assertEqual(cfg.network, "testnet-10")
        self.assertFalse(cfg.live_enabled)

    def test_tn10_proof_embedded(self):
        p = tn10_microproof()
        self.assertEqual(p["network"], "testnet-10")
        self.assertEqual(len(p["covenant_id"]), 64)
        self.assertIn("genesis", p["txs"])
        st = CovenantPlugin().tn10_proof_status()
        self.assertTrue(st["proven"])
        self.assertFalse(st["in_process_live"])

    def test_plan_agent_pot(self):
        plan = plan_agent_pot(
            max_kas_per_tx=1.0,
            max_kas_per_day=5.0,
            allowed_destinations=["kaspatest:qexample"],
        )
        self.assertTrue(plan["ok"])
        self.assertAlmostEqual(plan["fund_pot_kas"], 5.05, places=2)
        self.assertEqual(plan["hard_rules"]["max_kas_per_tx"], 1.0)
        self.assertTrue(plan["hard_rules"]["require_dest_allowlist"])
        bad = plan_agent_pot(max_kas_per_tx=0, max_kas_per_day=1)
        self.assertFalse(bad["ok"])
        via_plugin = CovenantPlugin().plan_agent_pot(
            max_kas_per_tx=2.0, max_kas_per_day=10.0
        )
        via_plan = via_plugin.copy()
        via_plan["live_ready"] = True
        self.assertTrue(via_plugin["ok"])
        self.assertTrue(validate_agent_pot_plan(via_plan)["ok"])


if __name__ == "__main__":
    unittest.main()
