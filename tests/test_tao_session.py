#!/usr/bin/env python3
"""TAO agent session tests (mock stake; no password on agent path)."""

from __future__ import annotations

import json
import sys
import tempfile
import time
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
from vida.plugins.tao.session import (  # noqa: E402
    grant_tao_agent_session,
    load_tao_session_secrets,
    revoke_tao_agent_session,
)

TEST_MNEMONIC = (
    "abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon about"
)


class TestTaoSession(unittest.TestCase):
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
        self.session_path = str(Path(self.td.name) / "sess.json")

    def tearDown(self):
        self.td.cleanup()

    def test_grant_load_stake_without_password(self):
        g = grant_tao_agent_session(
            store=self.store,
            wallet_id="w1",
            password="pw",
            session_path=self.session_path,
            hours=1,
            mode="FULL",
            max_tao_per_tx=1.0,
            max_tao_per_day=2.0,
            allowed_subnets=[1],
            scope="STAKE_ONLY",
        )
        self.assertTrue(g["ok"], g)
        # session file must not contain raw private hex in plaintext fields
        raw = Path(self.session_path).read_text()
        self.assertNotIn("cold_private_hex", raw)

        loaded = load_tao_session_secrets(self.session_path)
        self.assertTrue(loaded["ok"])
        self.assertIn("cold_private_hex", loaded["secrets"])

        ctx = VidaPluginContext(wallet_id="w1", mode="COMMAND")  # session overrides mode
        r = self.plugin.delegate(
            ctx,
            amount_tao=0.1,
            netuid=1,
            confirm=True,
            session_path=self.session_path,
            # no password
        )
        self.assertTrue(r["ok"], r)
        self.assertEqual(r.get("unlock_via"), "session")
        self.assertTrue(str(r.get("extrinsic_hash", "")).startswith("mock_delegate"))

    def test_session_respects_subnet_limit(self):
        grant_tao_agent_session(
            store=self.store,
            wallet_id="w1",
            password="pw",
            session_path=self.session_path,
            hours=1,
            mode="FULL",
            max_tao_per_tx=1.0,
            max_tao_per_day=5.0,
            allowed_subnets=[1],
            scope="STAKE_ONLY",
        )
        r = self.plugin.delegate(
            VidaPluginContext(wallet_id="w1", mode="FULL"),
            amount_tao=0.1,
            netuid=9,
            confirm=True,
            session_path=self.session_path,
        )
        self.assertFalse(r["ok"])

    def test_revoke_blocks(self):
        grant_tao_agent_session(
            store=self.store,
            wallet_id="w1",
            password="pw",
            session_path=self.session_path,
            hours=1,
            mode="FULL",
            max_tao_per_tx=1.0,
            max_tao_per_day=5.0,
            scope="STAKE_ONLY",
        )
        self.assertTrue(revoke_tao_agent_session(self.session_path))
        r = self.plugin.delegate(
            VidaPluginContext(wallet_id="w1", mode="FULL"),
            amount_tao=0.1,
            netuid=1,
            confirm=True,
            session_path=self.session_path,
        )
        self.assertFalse(r["ok"])

    def test_expired_burns(self):
        g = grant_tao_agent_session(
            store=self.store,
            wallet_id="w1",
            password="pw",
            session_path=self.session_path,
            hours=0.00001,  # ~0.036 seconds
            mode="FULL",
            max_tao_per_tx=1.0,
            max_tao_per_day=5.0,
            scope="STAKE_ONLY",
        )
        self.assertTrue(g["ok"])
        time.sleep(0.1)
        loaded = load_tao_session_secrets(self.session_path)
        self.assertFalse(loaded["ok"])
        self.assertTrue(loaded.get("session_revoked"))
        self.assertFalse(Path(self.session_path).exists())

    def test_tamper_limits_fails_decrypt(self):
        grant_tao_agent_session(
            store=self.store,
            wallet_id="w1",
            password="pw",
            session_path=self.session_path,
            hours=1,
            mode="FULL",
            max_tao_per_tx=0.1,
            max_tao_per_day=5.0,
            scope="STAKE_ONLY",
        )
        data = json.loads(Path(self.session_path).read_text())
        data["limits"]["max_tao_per_tx"] = 999.0  # raise cap
        Path(self.session_path).write_text(json.dumps(data))
        loaded = load_tao_session_secrets(self.session_path)
        self.assertFalse(loaded["ok"])


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
