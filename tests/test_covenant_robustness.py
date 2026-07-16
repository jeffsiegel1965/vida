#!/usr/bin/env python3
"""Covenant robustness tests: fail-safe gates, spend policy, pot records, no secrets."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vida.plugins.covenant import (
    check_spend_allowed,
    check_spend_kas,
    plan_agent_pot,
    build_agent_pot_script_template,
    verify_policy_hash,
    CovenantPlugin,
)
from vida.plugins.covenant.lab_client import (
    live_gates_ok,
    can_run_lab_demo,
    can_fund_agent_pot,
)
from vida.plugins.covenant.pot_spend import (
    save_pot_record,
    load_pot_record,
)


class TestCovenantRobustness(unittest.TestCase):

    def test_spend_zero_denied(self):
        r = check_spend_allowed(
            policy={"max_tx_sompi": 100_000_000, "allowed_destinations": []},
            amount_sompi=0,
            destination="kaspatest:qtest",
        )
        self.assertFalse(r["ok"])

    def test_spend_over_max_tx_denied(self):
        r = check_spend_allowed(
            policy={"max_tx_sompi": 50_000_000, "allowed_destinations": []},
            amount_sompi=100_000_000,
            destination="kaspatest:qtest",
        )
        self.assertFalse(r["ok"])
        self.assertIn("max_tx", r.get("error", ""))

    def test_spend_no_destination_denied(self):
        r = check_spend_allowed(
            policy={"max_tx_sompi": 100_000_000, "allowed_destinations": []},
            amount_sompi=10_000_000,
            destination="",
        )
        self.assertFalse(r["ok"])

    def test_spend_wrong_dest_denied(self):
        r = check_spend_allowed(
            policy={"max_tx_sompi": 100_000_000, "allowed_destinations": ["kaspatest:qallow"]},
            amount_sompi=10_000_000,
            destination="kaspatest:qdeny",
        )
        self.assertFalse(r["ok"])
        self.assertIn("allowlist", r.get("error", ""))

    def test_spend_owner_return_allowed(self):
        r = check_spend_allowed(
            policy={"max_tx_sompi": 100_000_000, "allowed_destinations": []},
            amount_sompi=10_000_000,
            destination="kaspatest:qowner",
            owner_address="kaspatest:qowner",
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["rule"], "owner_return")

    def test_spend_kas_conversion(self):
        r = check_spend_kas(
            policy={"max_tx_sompi": 100_000_000, "allowed_destinations": []},
            amount_kas=0.5,
            destination="kaspatest:qtest",
        )
        self.assertTrue(r["ok"])

    def test_plan_zero_caps_denied(self):
        r = plan_agent_pot(max_kas_per_tx=0, max_kas_per_day=0)
        self.assertFalse(r["ok"])

    def test_plan_negative_fee_denied(self):
        r = plan_agent_pot(max_kas_per_tx=1.0, max_kas_per_day=5.0, fee_buffer_kas=-0.1)
        self.assertFalse(r["ok"])

    def test_policy_template_verify(self):
        t = build_agent_pot_script_template(
            max_kas_per_tx=1.0,
            max_kas_per_day=5.0,
            allowed_destinations=["kaspatest:qtest"],
        )
        self.assertTrue(t["ok"])
        self.assertFalse(t["live_script_ready"])
        self.assertTrue(verify_policy_hash(t))
        t["policy"]["max_tx_sompi"] = 999999999
        self.assertFalse(verify_policy_hash(t))

    def test_kip17_requires_dests(self):
        t = build_agent_pot_script_template(
            max_kas_per_tx=1.0,
            max_kas_per_day=5.0,
            allowed_destinations=[],
            strategy="kip17_max_tx_dest",
        )
        self.assertFalse(t["ok"])

    def test_pot_record_save_load(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            t = build_agent_pot_script_template(
                max_kas_per_tx=1.0, max_kas_per_day=5.0,
                allowed_destinations=["kaspatest:qtest"],
            )
            r = save_pot_record("test-wallet", {"template": t, "pot_sompi": 500_000_000}, base=base)
            self.assertTrue(r["ok"])
            # reload
            r2 = load_pot_record("test-wallet", base=base)
            self.assertTrue(r2["ok"])
            self.assertEqual(r2["record"]["pot_sompi"], 500_000_000)

    def test_pot_record_missing(self):
        with tempfile.TemporaryDirectory() as td:
            r = load_pot_record("nonexistent", base=Path(td))
            self.assertFalse(r["ok"])

    def test_pot_record_bad_template_hash(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            t = build_agent_pot_script_template(
                max_kas_per_tx=1.0, max_kas_per_day=5.0,
                allowed_destinations=[],
            )
            t["policy"]["max_tx_sompi"] = 999999999  # corrupt hash
            r = save_pot_record("test-wallet2", {"template": t}, base=base)
            self.assertFalse(r["ok"])

    def test_live_gates_safe_by_default(self):
        g = live_gates_ok()
        self.assertFalse(g["live_env"])
        self.assertFalse(g["lab_ok"])
        self.assertFalse(g["key_ok"])
        self.assertFalse(can_run_lab_demo())
        self.assertFalse(can_fund_agent_pot())

    def test_plugin_describe_no_secrets(self):
        p = CovenantPlugin()
        d = p.describe()
        raw = json.dumps(d)
        for secret in ("mnemonic", "private_key", "seed", "password"):
            self.assertNotIn(secret.lower(), raw.lower())

    def test_plugin_status_no_secrets(self):
        p = CovenantPlugin()
        from vida.plugins.base import VidaPluginContext
        ctx = VidaPluginContext(
            wallet_id="test"
        )
        s = p.status(ctx)
        raw = json.dumps(s)
        for secret in ("mnemonic", "private_key", "seed", "password"):
            self.assertNotIn(secret.lower(), raw.lower())

    def test_deploy_and_spend_safe_no_env(self):
        p = CovenantPlugin()
        for method in (p.deploy, p.spend):
            r = method()
            self.assertFalse(r["ok"])  # safe by default, no env


if __name__ == "__main__":
    unittest.main()