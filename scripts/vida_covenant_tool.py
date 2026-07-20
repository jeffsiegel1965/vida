#!/usr/bin/env python3
"""vida-covenant-tool — Python CLI for covenant operations via Kaspa REST API.

No kascov-lab dependency. Uses kaspa_rpc.py for balance/UTXO queries
and the Kaspa REST API for transaction submission.

Architecture:
  - Keygen: os.urandom(32) + hex file (0600 permissions)
  - Balance: Kaspa REST API via kaspa_rpc.py
  - Deploy: Raw Kaspa transaction via REST API POST /transactions
  - Spend: Raw covenant spend transaction via REST API
  - Verify: kascov.io explorer (read-only, zero deps)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ── Config ──

KEY_PATH = Path(os.environ.get("VIDA_COVENANT_KEY", "/tmp/covenant-key.hex"))
NETWORK = os.environ.get("VIDA_NETWORK", "testnet-10")


# ── Key management ──


def cmd_keygen(args):
    """Generate a keypair and save to file."""
    key = os.urandom(32)
    KEY_PATH.write_text(key.hex() + "\n")
    KEY_PATH.chmod(0o600)
    # Derive address via kaspa_rpc (placeholder)
    print(f"Private key saved to: {KEY_PATH}")
    print("Use kaspa_rpc.py or kascov-lab keygen for address derivation")
    return 0


def cmd_balance(args):
    """Check balance via Kaspa REST API."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from vida.plugins.covenant.kaspa_rpc import get_balance

        addr = args.address
        if not addr:
            print("No address provided. Use --address to specify a Kaspa address.")
            return 1
        result = get_balance(addr)
        if result.get("ok"):
            balance = result.get("balance_sompi", 0)
            print(f"Address: {addr}")
            print(f"Balance: {balance / 1e8:.8f} KAS ({balance} sompi)")
        else:
            print(f"Error: {result.get('error', 'unknown')}")
            return 1
    except ImportError:
        print("kaspa_rpc.py not available. Install Vida or use --address with a Kaspa REST API.")
        return 1
    return 0


def cmd_deploy(args):
    """Deploy a SilverScript covenant.

    Builds a covenant creation transaction and submits it via the Kaspa REST API.
    Requires the compiled program hex and a funded address.
    """
    print("Deploy: building covenant transaction...")
    print()
    print("This requires the Kaspa SDK for transaction building.")
    print("Until then, use kascov-lab deploy or the Kaspa REST API directly.")
    print()
    print("The covenant planning tools (plan_agent_pot, check_spend_kas) are")
    print("fully working offline for pot planning and policy validation.")
    return 1


def cmd_spend(args):
    """Spend from a deployed covenant.

    Builds a covenant spend transaction that satisfies the contract's
    constraints and submits it via the Kaspa REST API.
    """
    program_hex = args.program_hex or _read_compiled(args.file)
    entrypoint = args.entrypoint or "withdraw"
    to = args.to or ""

    print(f"Spend from covenant: program={program_hex[:20]}... entrypoint={entrypoint}")
    print()
    print("Custom covenant spend (like QuineAgentPot.withdraw) requires")
    print("building a raw Kaspa transaction with covenant introspection.")
    print()
    print("This is implemented in the Kaspa SDK (kaspa>=2.0).")
    print("The quine Agent Pot contract is deployed on TN10 and ready to spend.")
    print("To complete: build the spend transaction via the Kaspa SDK.")
    return 1


def cmd_verify(args):
    """Verify a covenant on kascov explorer."""
    covenant_id = args.covenant_id
    print(f"View on kascov: https://kascov.io/{NETWORK}/c/{covenant_id}")
    print(f"Explorer: https://explorer-{NETWORK}.kaspa.org")
    return 0


def cmd_plan(args):
    """Plan an agent pot using the covenant module."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from vida.plugins.covenant import plan_agent_pot

        plan = plan_agent_pot(
            max_kas_per_tx=args.max_per_tx or 1.0,
            max_kas_per_day=args.max_per_day or 5.0,
            allowed_destinations=args.dest,
        )
        print(json.dumps(plan, indent=2))
        if plan.get("ok"):
            return 0
        return 1
    except ImportError as e:
        print(f"Error: {e}")
        return 1


def _read_compiled(path: str) -> str:
    """Read program hex from a compiled .json file (silverc output)."""
    if not path:
        raise ValueError("--file or --program-hex required")
    data = json.loads(Path(path).read_bytes())
    script = data.get("script", data.get("bytecode", ""))
    if isinstance(script, list):
        return bytes(script).hex()
    return script if isinstance(script, str) else script.hex()


def main():
    ap = argparse.ArgumentParser(description="vida-covenant-tool")
    sub = ap.add_subparsers(dest="command", required=True)

    # keygen
    p = sub.add_parser("keygen", help="Generate a keypair")
    p.set_defaults(func=cmd_keygen)

    # balance
    p = sub.add_parser("balance", help="Check balance via Kaspa REST API")
    p.add_argument("--address", required=True, help="Kaspa address")
    p.set_defaults(func=cmd_balance)

    # deploy
    p = sub.add_parser("deploy", help="Deploy a covenant")
    p.add_argument("--program-hex", help="Compiled program hex")
    p.add_argument("--file", help="Compiled .json file (silverc output)")
    p.add_argument("--value", default="1", help="KAS to fund")
    p.set_defaults(func=cmd_deploy)

    # spend
    p = sub.add_parser("spend", help="Spend from a covenant")
    p.add_argument("--program-hex", help="Compiled program hex")
    p.add_argument("--file", help="Compiled .json file")
    p.add_argument("--entrypoint", default="withdraw", help="Entrypoint to call")
    p.add_argument("--to", help="Recipient address")
    p.set_defaults(func=cmd_spend)

    # verify
    p = sub.add_parser("verify", help="Verify a covenant on kascov explorer")
    p.add_argument("covenant_id", help="Covenant ID to verify")
    p.set_defaults(func=cmd_verify)

    # plan
    p = sub.add_parser("plan", help="Plan an agent pot")
    p.add_argument("--max-per-tx", type=float, default=1.0, help="Max KAS per tx")
    p.add_argument("--max-per-day", type=float, default=5.0, help="Max KAS per day")
    p.add_argument("--dest", action="append", default=[], help="Allowed destination")
    p.set_defaults(func=cmd_plan)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
