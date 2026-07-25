"""Test deploy of QuineAgentPot covenant on testnet-10 using the fixed SDK integration.

Uses the new compute_budget=10 pattern from the official SDK examples.

Usage:
    source /tmp/kaspa-venv/bin/activate
    PYTHONPATH=$PWD python tests/test_covenant_deploy.py

The script will generate a new keypair and print a funding address.
Send testnet KAS to that address, then the deploy will proceed.
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vida.plugins.covenant.sdk_integration import (
    COMPUTE_BUDGET,
    TX_VERSION,
    covenant_balance,
    deploy_covenant,
    program_to_covenant_id,
)

# Load the compiled QuineAgentPot program
QUINE_JSON = ROOT / "vida" / "plugins" / "covenant" / "silverscript" / "quine_agent_pot.json"
with open(QUINE_JSON) as f:
    quine_data = json.load(f)
PROGRAM_HEX = bytes(quine_data["script"]).hex()

NETWORK = "testnet-10"
DEPLOY_SOMPI = 100_000_000  # 1 KAS

# Use existing private key if provided via env var
EXISTING_KEY = __import__("os").environ.get("VIDA_TEST_KEY")


async def main():
    print("=" * 60)
    print("QuineAgentPot Covenant Deploy Test")
    print(f"SDK: TX_VERSION={TX_VERSION}, COMPUTE_BUDGET={COMPUTE_BUDGET}")
    print("=" * 60)
    print()

    if EXISTING_KEY:
        from kaspa import Keypair, NetworkType, PrivateKey

        priv_key = PrivateKey(EXISTING_KEY)
        keypair = Keypair.from_private_key(priv_key)
        address = str(keypair.to_address(NetworkType.Testnet))
        pubkey_hex = keypair.xonly_public_key
        print(f"Using existing key — address: {address}")
    else:
        # Generate a new keypair for this test
        from kaspa import Keypair, NetworkType, PrivateKey

        keypair = Keypair.random()
        priv_key = PrivateKey(keypair.private_key)
        address = str(keypair.to_address(NetworkType.Testnet))
        pubkey_hex = keypair.xonly_public_key
        print(f"New key generated — fund this address: {address}")
        print(f"Private key: {keypair.private_key}")
        print()
        print("Then re-run with: VIDA_TEST_KEY=<key> python tests/test_covenant_deploy.py")
        print()
    print(f"Program hex:       {PROGRAM_HEX[:64]}...")
    print(f"Program length:    {len(bytes.fromhex(PROGRAM_HEX))} bytes")
    print(f"Computed covenant ID: {program_to_covenant_id(PROGRAM_HEX)[:32]}...")
    print()
    print(f"Deploy amount: {DEPLOY_SOMPI} sompi ({DEPLOY_SOMPI / 100_000_000} KAS)")
    print()

    # Deploy
    print("Deploying covenant...")
    result = await deploy_covenant(
        program_hex=PROGRAM_HEX,
        private_key_hex=keypair.private_key,
        value_sompi=DEPLOY_SOMPI,
        network=NETWORK,
    )

    print()
    if result.ok:
        print("✅ DEPLOY SUCCESS")
        print(f"  Covenant ID: {result.covenant_id}")
        print(f"  TXID:        {result.txid}")
        print(f"  Address:     {result.address}")
        print(f"  Value:       {result.value_sompi} sompi")

        # Check balance via kascov
        print()
        print("Checking covenant balance...")
        bal = await covenant_balance(result.covenant_id, network=NETWORK)
        if bal.get("ok"):
            print(f"  Balance: {bal['balance_sompi']} sompi")
        else:
            print(f"  Balance check: {bal}")
    else:
        print("❌ DEPLOY FAILED")
        print(f"  Error: {result.error}")


if __name__ == "__main__":
    asyncio.run(main())
