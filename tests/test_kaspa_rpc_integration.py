"""Integration test for the SDK-based Kaspa RPC client.
Hits the real testnet-10 via PNN (Resolver) to verify connectivity.

Run: source /tmp/kaspa-venv/bin/activate && PYTHONPATH=$PWD python -m pytest tests/test_kaspa_rpc_integration.py -v
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
    """Integration tests against live Kaspa testnet-10 via the SDK."""

    def test_01_network_info(self):
        """Fetch network info — should return testnet-10."""
        from vida.plugins.covenant.kaspa_rpc import get_network_info
        result = get_network_info()
        self.assertTrue(result.get("ok", False), result.get("error", "no error"))
        info = result.get("info", {})
        self.assertIn("network", info)
        self.assertIn("testnet", info["network"])

    def test_02_balance_known_address(self):
        """Fetch balance from a known address — should be > 0."""
        from vida.plugins.covenant.kaspa_rpc import get_balance
        result = get_balance(TEST_ADDR)
        self.assertTrue(result.get("ok", False), result.get("error", "no error"))
        balance = result.get("balance_sompi", 0)
        self.assertGreater(balance, 0, "Expected non-zero balance on deployer address")

    def test_03_balance_format(self):
        """Balance response should include sompi and KAS string."""
        from vida.plugins.covenant.kaspa_rpc import get_balance
        result = get_balance(TEST_ADDR)
        self.assertTrue(result.get("ok", False))
        self.assertIn("balance_sompi", result)
        self.assertIn("balance_kas", result)
        self.assertIsInstance(result["balance_sompi"], int)
        self.assertIsInstance(result["balance_kas"], str)

    def test_04_utxos_known_address(self):
        """Fetch UTXOs — should return a list."""
        from vida.plugins.covenant.kaspa_rpc import get_utxos
        result = get_utxos(TEST_ADDR)
        self.assertTrue(result.get("ok", False), result.get("error", "no error"))
        utxos = result.get("utxos", [])
        self.assertIsInstance(utxos, list)
        self.assertGreater(len(utxos), 0, "Expected UTXOs on deployer address")

    def test_05_blue_score(self):
        """Fetch virtual chain blue score — should be > 0."""
        from vida.plugins.covenant.kaspa_rpc import get_virtual_chain_blue_score
        result = get_virtual_chain_blue_score()
        self.assertTrue(result.get("ok", False), result.get("error", "no error"))
        score = result.get("blue_score", 0)
        self.assertGreater(score, 0)

    def test_06_keypair_generation(self):
        """Generate a keypair — should return valid address and keys."""
        from vida.plugins.covenant.kaspa_rpc import generate_keypair
        result = generate_keypair()
        self.assertTrue(result.get("ok", False), result.get("error", "no error"))
        self.assertIn("private_key_hex", result)
        self.assertIn("public_key_hex", result)
        self.assertIn("address", result)
        self.assertGreater(len(result["private_key_hex"]), 0)
        self.assertGreater(len(result["address"]), 0)


if __name__ == "__main__":
    unittest.main()
