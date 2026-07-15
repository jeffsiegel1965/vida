#!/usr/bin/env python3
"""T1.3 balance-on-status tests (mock client; no network)."""

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
    TaoAccountRecord,
    TaoAccountStore,
    TaoConfig,
    TaoNetwork,
    TaoPlugin,
)
from vida.plugins.tao.tools import vida_tao_balance, vida_tao_status  # noqa: E402


class TestBalanceStatus(unittest.TestCase):
    def test_status_balance_when_provisioned(self):
        with tempfile.TemporaryDirectory() as td:
            store = TaoAccountStore(td)
            addr = "5BalanceTestAddress000000000000000000000000"
            store.save(
                TaoAccountRecord(
                    wallet_id="w1",
                    network="mock",
                    ss58_address=addr,
                    provisioned=True,
                    meta={"hotkey_ss58": "5HotkeyTest"},
                )
            )
            client = MockTaoClient(balances={addr: Decimal("7.5")})
            plugin = TaoPlugin(
                config=TaoConfig(network=TaoNetwork.MOCK),
                client=client,
                account_store=store,
            )
            st = plugin.status(VidaPluginContext(wallet_id="w1", mode="FULL"))
            self.assertTrue(st["provisioned"])
            self.assertEqual(st["ss58_address"], addr)
            self.assertEqual(st["hotkey_ss58"], "5HotkeyTest")
            self.assertTrue(st["balance"]["ok"])
            self.assertEqual(st["balance"]["free_tao"], "7.5")
            self.assertIn("balance", st["capabilities"])

            b = plugin.balance(VidaPluginContext(wallet_id="w1"))
            self.assertTrue(b["ok"])
            self.assertEqual(b["balance"]["free_tao"], "7.5")

    def test_status_not_provisioned_balance_error(self):
        with tempfile.TemporaryDirectory() as td:
            store = TaoAccountStore(td)
            plugin = TaoPlugin(
                config=TaoConfig(network=TaoNetwork.MOCK),
                client=MockTaoClient(),
                account_store=store,
            )
            st = plugin.status(VidaPluginContext(wallet_id="missing"))
            self.assertFalse(st["provisioned"])
            self.assertEqual(st["balance"]["error"], "not_provisioned")

    def test_tools_read_store(self):
        with tempfile.TemporaryDirectory() as td:
            store = TaoAccountStore(td)
            addr = "5ToolTestAddress00000000000000000000000000"
            store.save(
                TaoAccountRecord(
                    wallet_id="tool1",
                    network="mock",
                    ss58_address=addr,
                    provisioned=True,
                )
            )
            # tools construct their own plugin — force mock via network + inject by
            # calling plugin path through store only works with mock factory when network=mock
            st = vida_tao_status("tool1", network="mock", store_dir=td)
            # mock client has 0 balance for unknown addresses unless we can't inject —
            # for mock network tools use MockTaoClient with empty balances → free 0
            self.assertTrue(st.get("provisioned"))
            self.assertEqual(st.get("ss58_address"), addr)
            self.assertIsNotNone(st.get("balance"))
            bal = vida_tao_balance("tool1", network="mock", store_dir=td)
            self.assertEqual(bal.get("ss58_address"), addr)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
