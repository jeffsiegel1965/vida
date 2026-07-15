#!/usr/bin/env python3
"""TAO Tier-1 robustness: scopes, dest allowlist, env paths, no password tool surface."""

from __future__ import annotations

import inspect
import os
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
from vida.plugins.tao.paths import actions_for_scope, resolve_store_dir  # noqa: E402
from vida.plugins.tao.session import grant_tao_agent_session  # noqa: E402
from vida.plugins.tao import tools as tao_tools  # noqa: E402

TEST_MNEMONIC = (
    "abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon about"
)


class TestScopeMaps(unittest.TestCase):
    def test_stake_only_no_transfer(self):
        acts = actions_for_scope("STAKE_ONLY")
        self.assertIn("delegate", acts)
        self.assertNotIn("transfer", acts)

    def test_transfer_only_no_delegate(self):
        acts = actions_for_scope("TRANSFER_ONLY")
        self.assertIn("transfer", acts)
        self.assertNotIn("delegate", acts)

    def test_bad_scope(self):
        with self.assertRaises(ValueError):
            actions_for_scope("YEET")


class TestToolsNoPasswordKwarg(unittest.TestCase):
    def test_money_tools_reject_password_param(self):
        for name in (
            "vida_tao_delegate",
            "vida_tao_undelegate",
            "vida_tao_transfer",
            "vida_tao_optimize",
        ):
            fn = getattr(tao_tools, name)
            params = inspect.signature(fn).parameters
            self.assertNotIn("password", params, f"{name} must not accept password=")


class TestPathsEnv(unittest.TestCase):
    def test_vida_tao_store_env(self):
        with tempfile.TemporaryDirectory() as td:
            old = os.environ.get("VIDA_TAO_STORE")
            os.environ["VIDA_TAO_STORE"] = td
            try:
                self.assertEqual(resolve_store_dir(None), td)
            finally:
                if old is None:
                    os.environ.pop("VIDA_TAO_STORE", None)
                else:
                    os.environ["VIDA_TAO_STORE"] = old

    def test_explicit_store_wins(self):
        self.assertEqual(resolve_store_dir("/tmp/explicit_store_x"), "/tmp/explicit_store_x")


class TestGrantAndScopeEnforcement(unittest.TestCase):
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
            wallet_id="w1", mnemonic=TEST_MNEMONIC, password="pw"
        )
        self.assertTrue(r["ok"], r)
        self.session = str(Path(self.td.name) / "sess.json")

    def tearDown(self):
        self.td.cleanup()

    def test_all_scope_requires_dest(self):
        g = grant_tao_agent_session(
            store=self.store,
            wallet_id="w1",
            password="pw",
            session_path=self.session,
            hours=1,
            max_tao_per_tx=1.0,
            max_tao_per_day=2.0,
            scope="ALL",
        )
        self.assertFalse(g["ok"])
        self.assertIn("allowed_destinations", g.get("error", ""))

    def test_long_session_blocked(self):
        g = grant_tao_agent_session(
            store=self.store,
            wallet_id="w1",
            password="pw",
            session_path=self.session,
            hours=48,
            max_tao_per_tx=1.0,
            max_tao_per_day=2.0,
            scope="STAKE_ONLY",
        )
        self.assertFalse(g["ok"])
        self.assertIn("allow_long_session", g.get("error", ""))

    def test_stake_only_blocks_transfer(self):
        g = grant_tao_agent_session(
            store=self.store,
            wallet_id="w1",
            password="pw",
            session_path=self.session,
            hours=1,
            mode="FULL",
            max_tao_per_tx=1.0,
            max_tao_per_day=2.0,
            scope="STAKE_ONLY",
        )
        self.assertTrue(g["ok"], g)
        r = self.plugin.transfer(
            VidaPluginContext(wallet_id="w1", mode="COMMAND"),
            dest_ss58="5SomeoneElseAddress000000000000000000000",
            amount_tao=0.01,
            confirm=True,
            session_path=self.session,
        )
        self.assertFalse(r["ok"])

    def test_dest_allowlist_enforced(self):
        dest = "5AllowedDest000000000000000000000000000"
        g = grant_tao_agent_session(
            store=self.store,
            wallet_id="w1",
            password="pw",
            session_path=self.session,
            hours=1,
            mode="FULL",
            max_tao_per_tx=1.0,
            max_tao_per_day=2.0,
            scope="TRANSFER_ONLY",
            allowed_destinations=[dest],
        )
        self.assertTrue(g["ok"], g)
        bad = self.plugin.transfer(
            VidaPluginContext(wallet_id="w1", mode="COMMAND"),
            dest_ss58="5NotAllowed00000000000000000000000000000",
            amount_tao=0.01,
            confirm=True,
            session_path=self.session,
        )
        self.assertFalse(bad["ok"])
        good = self.plugin.transfer(
            VidaPluginContext(wallet_id="w1", mode="COMMAND"),
            dest_ss58=dest,
            amount_tao=0.01,
            confirm=True,
            session_path=self.session,
        )
        self.assertTrue(good["ok"], good)

    def test_tools_refuse_without_session(self):
        r = tao_tools.vida_tao_delegate(
            "w1", 0.01, 1, confirm=True, store_dir=self.td.name
        )
        self.assertFalse(r["ok"])
        self.assertIn("session", r.get("error", "").lower())

    def test_transfer_updates_enc_spend(self):
        dest = "5AllowedDest000000000000000000000000000"
        g = grant_tao_agent_session(
            store=self.store,
            wallet_id="w1",
            password="pw",
            session_path=self.session,
            hours=1,
            mode="FULL",
            max_tao_per_tx=1.0,
            max_tao_per_day=2.0,
            scope="TRANSFER_ONLY",
            allowed_destinations=[dest],
        )
        self.assertTrue(g["ok"], g)
        r = self.plugin.transfer(
            VidaPluginContext(wallet_id="w1", mode="COMMAND"),
            dest_ss58=dest,
            amount_tao=0.03,
            confirm=True,
            session_path=self.session,
        )
        self.assertTrue(r["ok"], r)
        self.assertTrue((r.get("session_spend") or {}).get("ok"), r)
        from vida.plugins.tao.session import load_tao_session_secrets
        loaded = load_tao_session_secrets(self.session)
        self.assertTrue(loaded["ok"], loaded)
        self.assertGreaterEqual(float(loaded.get("daily_spent") or 0), 0.03 - 1e-9)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
