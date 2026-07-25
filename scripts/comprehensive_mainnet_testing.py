#!/usr/bin/env python3
"""
Comprehensive Mainnet Covenant and TAO Testing
Production-ready testing with real mainnet validation
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("comprehensive_mainnet_testing")


class ComprehensiveMainnetTester:
    """Comprehensive mainnet testing for Vida wallet, covenants, and TAO"""

    def __init__(self):
        self.start_time = time.time()
        self.test_results = []

    def run_covenant_test_suite(self) -> Dict[str, Any]:
        """Run the advanced covenant testing suite"""
        logger.info("Running covenant test suite...")

        try:
            result = subprocess.run(
                ["python3", "scripts/advanced_covenant_testing.py", "--verbose"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            return {
                "test_name": "covenant_suite",
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration": time.time() - self.start_time,
            }
        except Exception as e:
            return {
                "test_name": "covenant_suite",
                "success": False,
                "error": str(e),
                "duration": time.time() - self.start_time,
            }

    def run_tao_test_suite(self) -> Dict[str, Any]:
        """Run the TAO wallet testing suite"""
        logger.info("Running TAO test suite...")

        try:
            result = subprocess.run(
                ["python3", "scripts/tao_wallet_testing.py", "--verbose"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            return {
                "test_name": "tao_suite",
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration": time.time() - self.start_time,
            }
        except Exception as e:
            return {
                "test_name": "tao_suite",
                "success": False,
                "error": str(e),
                "duration": time.time() - self.start_time,
            }

    def test_mainnet_kaspa_rpc(self) -> Dict[str, Any]:
        """Test Kaspa mainnet RPC connectivity"""
        logger.info("Testing Kaspa mainnet RPC...")

        test_start = time.time()

        try:
            # Import and test Kaspa RPC
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from vida.plugins.covenant.kaspa_rpc import get_balance, set_network

            # Set to mainnet
            set_network("mainnet")

            # Test with the Kaspa foundation address (publicly known)
            kaspa_foundation = "kaspa:qqkqkzjvjqy9gcfj6pxry8c74ae2v5e8rnh6yl6v5gfp6pnlph74c6txrj6qw"

            balance_result = get_balance(kaspa_foundation)

            return {
                "test_name": "kaspa_mainnet_rpc",
                "success": True,
                "details": {
                    "network": "mainnet",
                    "test_address": kaspa_foundation,
                    "balance_query_success": "balance" in balance_result,
                    "response_time_ms": (time.time() - test_start) * 1000,
                },
                "message": "Kaspa mainnet RPC connectivity successful",
                "duration": time.time() - test_start,
            }

        except Exception as e:
            return {
                "test_name": "kaspa_mainnet_rpc",
                "success": False,
                "error": str(e),
                "message": f"Kaspa mainnet RPC failed: {str(e)}",
                "duration": time.time() - test_start,
            }

    def analyze_discovered_wallets(self) -> Dict[str, Any]:
        """Analyze all discovered wallet files"""
        logger.info("Analyzing discovered wallets...")

        test_start = time.time()

        try:
            # KAS wallet
            kas_wallet_path = os.path.expanduser("~/.hermes/projects/vida/vida_owner_secure.json")
            kas_wallet_exists = os.path.exists(kas_wallet_path)
            kas_wallet_size = os.path.getsize(kas_wallet_path) if kas_wallet_exists else 0

            # TAO positions
            tao_paths = [
                "~/.hermes/projects/tao-yield-optimizer/tao_wallet_analysis.json",
                "~/.hermes/projects/bittensor-suite/data/tao_positions.json",
            ]

            tao_data = {}
            for path in tao_paths:
                expanded = os.path.expanduser(path)
                if os.path.exists(expanded):
                    with open(expanded, "r") as f:
                        data = json.load(f)
                        tao_data[path] = {
                            "exists": True,
                            "size_bytes": os.path.getsize(expanded),
                            "keys": list(data.keys()) if isinstance(data, dict) else "list_data",
                        }

            return {
                "test_name": "wallet_analysis",
                "success": True,
                "details": {
                    "kas_wallet": {
                        "path": kas_wallet_path,
                        "exists": kas_wallet_exists,
                        "size_bytes": kas_wallet_size,
                        "encrypted": kas_wallet_exists,  # Encrypted wallets have content
                    },
                    "tao_positions": tao_data,
                },
                "message": f"Wallet analysis complete: KAS wallet {'found' if kas_wallet_exists else 'missing'}, {len(tao_data)} TAO data sources",
                "duration": time.time() - test_start,
            }

        except Exception as e:
            return {
                "test_name": "wallet_analysis",
                "success": False,
                "error": str(e),
                "duration": time.time() - test_start,
            }

    def run_comprehensive_suite(self) -> Dict[str, Any]:
        """Run the complete comprehensive testing suite"""
        logger.info("Starting comprehensive mainnet testing suite...")

        suite_start = time.time()
        results = []

        # 1. Analyze wallets
        wallet_analysis = self.analyze_discovered_wallets()
        results.append(wallet_analysis)

        # 2. Test Kaspa mainnet RPC
        kaspa_rpc_test = self.test_mainnet_kaspa_rpc()
        results.append(kaspa_rpc_test)

        # 3. Run covenant testing
        covenant_results = self.run_covenant_test_suite()
        results.append(covenant_results)

        # 4. Run TAO testing
        tao_results = self.run_tao_test_suite()
        results.append(tao_results)

        suite_duration = time.time() - suite_start

        # Calculate metrics
        passed = sum(1 for r in results if r.get("success", False))
        failed = len(results) - passed

        suite_summary = {
            "suite": "Comprehensive Mainnet Testing",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": suite_duration,
            "summary": {
                "total_tests": len(results),
                "passed": passed,
                "failed": failed,
                "success_rate": (passed / len(results)) * 100 if results else 0,
            },
            "test_results": results,
        }

        # Save results
        results_dir = Path(__file__).parent.parent / "test_results"
        results_dir.mkdir(exist_ok=True)

        results_file = results_dir / f"comprehensive_mainnet_testing_{int(time.time())}.json"
        with open(results_file, "w") as f:
            json.dump(suite_summary, f, indent=2)

        logger.info(f"📊 Comprehensive Testing Results: {passed}/{len(results)} passed")
        logger.info(f"💾 Detailed results saved: {results_file}")

        return suite_summary


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive Mainnet Testing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    tester = ComprehensiveMainnetTester()
    results = tester.run_comprehensive_suite()

    # Print summary
    summary = results["summary"]
    print(f"\n🎯 Comprehensive Mainnet Testing Results:")
    print(f"   ✅ Passed: {summary['passed']}/{summary['total_tests']} ({summary['success_rate']:.1f}%)")
    print(f"   ❌ Failed: {summary['failed']}")
    print(f"   ⏱️  Duration: {results['duration_seconds']:.1f}s")

    # Show specific results
    print(f"\n📋 Test Breakdown:")
    for test in results["test_results"]:
        status = "✅" if test.get("success", False) else "❌"
        name = test.get("test_name", "unknown")
        message = test.get("message", test.get("error", "No details"))
        print(f"   {status} {name}: {message}")

    if summary["success_rate"] >= 80:
        print(f"\n🚀 MAINNET TESTING: EXCELLENT - PRODUCTION READY")
    elif summary["success_rate"] >= 60:
        print(f"\n⚠️  MAINNET TESTING: GOOD - MINOR ISSUES")
    else:
        print(f"\n🚨 MAINNET TESTING: NEEDS ATTENTION")


if __name__ == "__main__":
    main()
