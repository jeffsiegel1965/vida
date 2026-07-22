import unittest
from unittest.mock import patch
from vida.plugins.covenant.coamm import (
    CoAMMClient,
    PoolState,
    vida_coamm_pools,
    vida_coamm_swap,
    vida_coamm_estimate,
    vida_coamm_liquidity,
)


class TestCoAMMClient(unittest.TestCase):
    def setUp(self):
        self.client = CoAMMClient(kaspa_sdk=None)
        self.client.pools["test_pool"] = PoolState(
            pool_id="test_pool",
            kas_reserve=1000000,
            token_reserve=500000,
            lp_supply=1000,
            protocol_fee_kas=100,
            protocol_fee_tkn=50,
            token_covid="test_token",
        )

    def test_get_pool_success(self):
        result = self.client.get_pool("test_pool")
        self.assertTrue(result["ok"])
        self.assertEqual(result["pool"].pool_id, "test_pool")

    def test_get_pool_not_found(self):
        result = self.client.get_pool("nonexistent_pool")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Pool not found")

    def test_estimate_swap_kas_to_token(self):
        result = self.client.estimate_swap("test_pool", "KAS", "test_token", 1000)
        self.assertTrue(result["ok"])
        self.assertGreater(result["output_amount"], 0)

    def test_estimate_swap_token_to_kas(self):
        result = self.client.estimate_swap("test_pool", "test_token", "KAS", 100)
        self.assertTrue(result["ok"])
        self.assertGreater(result["output_amount"], 0)

    def test_swap_tokens_success(self):
        result = self.client.swap_tokens(
            "test_wallet", "test_pool", "KAS", "test_token", 1000, 0.01
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["txid"], "simulated_txid_for_testnet")

    def test_add_liquidity_success(self):
        result = self.client.add_liquidity(
            "test_wallet", "test_pool", {"KAS": 1000, "test_token": 500}
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["txid"], "simulated_txid_for_testnet")


class TestVidaCoAMMTools(unittest.TestCase):
    @patch("vida.plugins.covenant.coamm.CoAMMClient")
    def test_vida_coamm_pools(self, mock_client):
        mock_client.return_value.pools = {"test_pool": "mock_pool"}
        result = vida_coamm_pools()
        self.assertTrue(result["ok"])
        self.assertEqual(result["pools"], ["mock_pool"])

    @patch("vida.plugins.covenant.coamm.CoAMMClient")
    def test_vida_coamm_swap(self, mock_client):
        mock_client.return_value.swap_tokens.return_value = "mock_result"
        result = vida_coamm_swap("test_wallet", "test_pool", "KAS", "test_token", 1000, 0.01)
        self.assertEqual(result, "mock_result")

    @patch("vida.plugins.covenant.coamm.CoAMMClient")
    def test_vida_coamm_estimate(self, mock_client):
        mock_client.return_value.estimate_swap.return_value = {"ok": True, "output_amount": 500}
        result = vida_coamm_estimate("test_pool", "KAS", "test_token", 1000)
        self.assertTrue(result["ok"])
        self.assertEqual(result["output_amount"], 500)

    @patch("vida.plugins.covenant.coamm.CoAMMClient")
    def test_vida_coamm_liquidity(self, mock_client):
        mock_client.return_value.add_liquidity.return_value = "mock_result"
        result = vida_coamm_liquidity("test_wallet", "test_pool", {"KAS": 1000, "test_token": 500})
        self.assertEqual(result, "mock_result")


if __name__ == "__main__":
    unittest.main()