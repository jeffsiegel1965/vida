#!/usr/bin/env python3
"""
Create Mainnet Vida Wallet for Testing

This script creates a production-ready mainnet wallet for testing.
The wallet will be stored securely and can be used for dust testing.

Usage:
    python scripts/create_mainnet_wallet.py [--path ~/.vida/wallets/mainnet_test.json]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def create_mainnet_wallet(wallet_path: str = None):
    """Create a new mainnet wallet interactively."""
    try:
        # Add vida directory to path
        sys.path.insert(0, str(ROOT / "vida"))
        from secure_wallet import create_secure_wallet

        print("🔐 Creating new Vida mainnet wallet for testing...")
        print("⚠️  This will create a REAL mainnet wallet with recovery phrase")
        print("💡 Keep your recovery phrase secure - it controls real funds")

        response = input("\nContinue? (y/N): ")
        if response.lower() != "y":
            print("❌ Cancelled")
            return False

        # Set default wallet path if not provided
        if not wallet_path:
            wallet_dir = Path.home() / ".vida" / "wallets"
            wallet_dir.mkdir(parents=True, exist_ok=True)
            wallet_file = wallet_dir / "mainnet_test.json"
        else:
            wallet_file = Path(wallet_path)
            wallet_file.parent.mkdir(parents=True, exist_ok=True)

        print(f"📁 Wallet will be saved to: {wallet_file}")

        if wallet_file.exists():
            print(f"❌ Error: Wallet already exists at {wallet_file}")
            return False

        # Create wallet
        print("🔑 Creating wallet... (you'll be prompted for password)")
        create_secure_wallet(str(wallet_file), network="mainnet")

        print(f"✅ Mainnet wallet created: {wallet_file}")
        print(f"💰 Fund this wallet with KAS to run dust tests")
        print(f"🧪 Test command: python scripts/dust_test.py --wallet-path {wallet_file} --amount 0.03")

        return True

    except ImportError as e:
        print(f"❌ Error: Could not import Vida modules: {e}")
        print("💡 Make sure you're in the vida-release directory with venv activated")
        return False
    except Exception as e:
        print(f"❌ Error creating wallet: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Create Vida mainnet wallet for testing")
    parser.add_argument("--path", help="Wallet file path (default: ~/.vida/wallets/mainnet_test.json)")

    args = parser.parse_args()

    success = create_mainnet_wallet(args.path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
