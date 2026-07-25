"""Tests for KIP-16 ZK covenant module."""

import unittest

from vida.plugins.covenant.kip16_zk import (
    TEST_VECTORS,
    CovenantManager,
    ZkProofCovenant,
    ZkProofType,
    ZkScheme,
    verify_benchmark,
    vida_covenant_zk_benchmarks,
    vida_covenant_zk_deploy,
    vida_covenant_zk_status,
    vida_covenant_zk_verify,
)


class TestZkProofCovenant(unittest.TestCase):
    def test_create_proof_covenant(self):
        proof = ZkProofCovenant(
            scheme=ZkScheme.FALCON_512,
            proof_bytes="0x1234",
            public_inputs="0x5678",
            verifier_program_hash="0xabcd",
        )
        self.assertEqual(proof.scheme, ZkScheme.FALCON_512)
        self.assertEqual(proof.proof_type, ZkProofType.STARK)

    def test_all_schemes_construct(self):
        for scheme in ZkScheme:
            proof = ZkProofCovenant(
                scheme=scheme,
                proof_bytes="0x00",
                public_inputs="0x00",
                verifier_program_hash="0x00",
            )
            self.assertEqual(proof.scheme, scheme)


class TestCovenantManager(unittest.TestCase):
    def test_deploy_returns_covenant_id(self):
        proof = ZkProofCovenant(
            scheme=ZkScheme.ML_DSA_44,
            proof_bytes="0xdead",
            public_inputs="0xbeef",
            verifier_program_hash="a" * 64,
        )
        result = CovenantManager.deploy(proof)
        self.assertTrue(result["ok"])
        self.assertIn("covenant_id", result)

    def test_verify_returns_ok(self):
        proof = ZkProofCovenant(
            scheme=ZkScheme.SLH_DSA_128S,
            proof_bytes="0x00",
            public_inputs="0x00",
            verifier_program_hash="0x00",
        )
        result = CovenantManager.verify(proof)
        self.assertTrue(result["ok"])
        self.assertTrue(result["verified"])

    def test_status_returns_active(self):
        result = CovenantManager.status("0x1234")
        self.assertTrue(result["ok"])
        self.assertTrue(result["active"])


class TestBenchmarks(unittest.TestCase):
    def test_benchmark_function(self):
        result = verify_benchmark()
        self.assertTrue(result["ok"])
        bm = result["benchmarks"]
        self.assertAlmostEqual(bm["Falcon-512"], 1.91, places=2)
        self.assertAlmostEqual(bm["ML-DSA-44"], 5.35, places=2)
        self.assertAlmostEqual(bm["SLH-DSA-128s"], 16.3, places=1)
        self.assertEqual(bm["unit"], "seconds")
        self.assertEqual(bm["hardware"], "RTX 4090")


class TestHermesTools(unittest.TestCase):
    def test_zk_deploy_valid(self):
        result = vida_covenant_zk_deploy(
            scheme="Falcon-512",
            proof_bytes="0x1234",
            public_inputs="0x5678",
            verifier_program_hash="a" * 64,
        )
        self.assertTrue(result["ok"], result.get("error"))

    def test_zk_deploy_invalid_scheme(self):
        result = vida_covenant_zk_deploy(
            scheme="ECDSA-256",
            proof_bytes="0x00",
            public_inputs="0x00",
            verifier_program_hash="0x00",
        )
        self.assertFalse(result["ok"])

    def test_zk_verify_valid(self):
        result = vida_covenant_zk_verify(
            scheme="ML-DSA-44",
            proof_bytes="0x2345",
            public_inputs="0x6789",
            verifier_program_hash="b" * 64,
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["verified"])

    def test_zk_verify_invalid_scheme(self):
        result = vida_covenant_zk_verify(
            scheme="RSA-2048",
            proof_bytes="0x00",
            public_inputs="0x00",
            verifier_program_hash="0x00",
        )
        self.assertFalse(result["ok"])

    def test_zk_status(self):
        result = vida_covenant_zk_status("0xaaaa")
        self.assertTrue(result["ok"])
        self.assertIn("active", result)

    def test_zk_benchmarks(self):
        result = vida_covenant_zk_benchmarks()
        self.assertTrue(result["ok"])
        self.assertIn("Falcon-512", result["benchmarks"])


class TestTestVectors(unittest.TestCase):
    def test_vectors_contain_all_schemes(self):
        self.assertIn("Falcon-512", TEST_VECTORS)
        self.assertIn("ML-DSA-44", TEST_VECTORS)
        self.assertIn("SLH-DSA-128s", TEST_VECTORS)

    def test_vectors_have_required_fields(self):
        for scheme, vector in TEST_VECTORS.items():
            with self.subTest(scheme=scheme):
                self.assertIn("tx_hash", vector)
                self.assertIn("proof_bytes", vector)
                self.assertIn("public_inputs", vector)
                self.assertIn("verifier_program_hash", vector)


if __name__ == "__main__":
    unittest.main()
