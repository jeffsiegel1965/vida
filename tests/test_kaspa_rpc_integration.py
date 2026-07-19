"""Integration test for Kaspa REST API client.
Hits the real testnet-10 API to verify connectivity and response format.

Run: PYTHONPATH=$PWD python -m pytest tests/test_kaspa_rpc_integration.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_ADDR = "kaspatest:qplmcgy7gvgvsjrcmvphwnasu577y8agpe3crtl0zwna9h34dadeg8f024trj"


class TestKaspaRpcIntegration(unittest.TestCase):
    """Integration tests against the live Kaspa testnet-10 REST API."""

    def test_01_health_endpoint(self):
        """Fetch health endpoint — should return kaspadServers."""
        from vida.plugins.covenant.kaspa_rpc import _api_get
        result = _api_get("/info/health")
        self.assertIn("kaspadServers", result)
        servers = result["kaspadServers"]
        self.assertGreater(len(servers), 0)
        self.assertTrue(servers[0].get("isSynced", False))

    def test_02_balance_known_address(self):
        """Fetch balance from a known address — should be > 0."""
        from vida.plugins.covenant.kaspa_rpc import get_balance
        result = get_balance(TEST_ADDR)
        self.assertTrue(result.get("ok", False))
        balance = result.get("balance_sompi", 0)
        self.assertGreater(balance, 0)

    def test_03_utxos_known_address(self):
        """Fetch UTXOs — should return a list with entries."""
        from vida.plugins.covenant.kaspa_rpc import get_utxos
        result = get_utxos(TEST_ADDR)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        entry = result[0].get("utxoEntry", {})
        self.assertIn("amount", entry)

    def test_04_blue_score(self):
        """Fetch virtual chain blue score."""
        from vida.plugins.covenant.kaspa_rpc import _api_get
        result = _api_get("/info/virtual-chain-blue-score")
        self.assertIn("blueScore", result)
        self.assertGreater(result["blueScore"], 0)


if __name__ == "__main__":
    unittest.main()