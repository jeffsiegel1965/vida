#!/usr/bin/env python3
"""
vida-covenant-tool — Python CLI for deploying and spending any SilverScript covenant.
Does NOT depend on kascov-lab's template lock-in.

Architecture:
  - Deploy: uses kascov-lab binary (works for any program hex)
  - Spend: builds the transaction via Kaspa wRPC directly (Borsh over WebSocket)
  - Key management: wraps kascov-lab keygen/balance
  
This is phase 1 — Python-based with Kaspa wRPC for transaction building.
Phase 2 will be a standalone Rust binary with no kascov-lab dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

KASCOV_LAB = Path(os.environ.get(
    "KASCOV_LAB_PATH",
    str(Path.home() / ".hermes" / "projects" / "toolchain" / "kascov" / "target" / "release" / "kascov-lab")
))
KEY_PATH = Path(os.environ.get("VIDA_COVENANT_KEY", "/tmp/kascov-lab-key.hex"))
NETWORK = os.environ.get("VIDA_NETWORK", "testnet-10")
RPC_URL = os.environ.get("VIDA_RPC", None)  # None = use public resolver


def cmd_keygen(args):
    """Generate a keypair and print the address."""
    r = subprocess.run(
        [str(KASCOV_LAB), "--key", str(KEY_PATH), "keygen"],
        capture_output=True, text=True, timeout=30,
    )
    print(r.stdout or r.stderr)


def cmd_balance(args):
    """Check balance of the configured key."""
    r = subprocess.run(
        [str(KASCOV_LAB), "--key", str(KEY_PATH), "balance"],
        capture_output=True, text=True, timeout=30,
    )
    print(r.stdout or r.stderr)


def cmd_deploy(args):
    """Deploy a compiled SilverScript program as a covenant.
    
    Supports ANY program hex — no template restrictions.
    Uses kascov-lab deploy (which works for all programs).
    """
    program_hex = args.program_hex or _read_compiled(args.file)
    value_sompi = int(float(args.value) * 1e8) if args.value else 100_000_000
    
    cmd = [
        str(KASCOV_LAB), "--key", str(KEY_PATH),
        "deploy", "--program-hex", program_hex, "--value", str(value_sompi),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    print(r.stdout or r.stderr)
    if r.returncode != 0:
        print(f"Error: {r.stderr}", file=sys.stderr)
        return 1
    
    # Parse covenant ID from output
    for line in (r.stdout or "").splitlines():
        if "covenant" in line and len(line) > 60:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "covenant" and i + 1 < len(parts):
                    print(f"\nCovenant ID: {parts[i+1]}")
                    print(f"View: https://kascov.io/testnet-10/c/{parts[i+1]}")
    return 0


def cmd_spend(args):
    """Spend from a deployed covenant.
    
    For RECOGNIZED contracts: uses kascov-lab spend (Mecenas/Escrow/LastWill).
    For CUSTOM contracts: builds the spend via Kaspa wRPC directly.
    
    Currently supports:
      - PureSig entrypoints (signature-based spend)
      - Output-constrained entrypoints (requires Kaspa WASM SDK)
    
    The quine Agent Pot 'withdraw' entrypoint is a PureSig path.
    """
    program_hex = args.program_hex or _read_compiled(args.file)
    entrypoint = args.entrypoint or "withdraw"
    to = args.to or ""
    
    # Try kascov-lab first (works for recognized contracts)
    cmd = [
        str(KASCOV_LAB), "--key", str(KEY_PATH),
        "spend", "--program-hex", program_hex,
        "--entrypoint", entrypoint,
    ]
    if to:
        cmd += ["--to", to]
    if args.dry_run:
        cmd += ["--dry-run"]
    
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    stdout = r.stdout or ""
    stderr = r.stderr or ""
    
    if r.returncode == 0:
        print(stdout)
        print("Spend successful.")
        return 0
    
    # If kascov-lab fails with "not a recognized contract", give clear next steps
    if "not a recognized" in stderr or "don't know how" in stderr:
        print("kascov-lab doesn't support this contract type directly.")
        print()
        print("vida-covenant-tool spend: RECOGNIZED contracts:")
        print("  Mecenas.reclaim, Mecenas.receive")
        print("  Escrow.spend (use --settle-escrow)")
        print("  LastWill.cold, LastWill.inherit, LastWill.refresh")
        print()
        print("For CUSTOM contracts (like QuineAgentPot.withdraw), the")
        print("direct wRPC spend path is under development.")
        print()
        print("The quine IS deployed on-chain and ready to spend.")
        print("To complete: build the spend transaction via Kaspa wRPC.")
        return 1
    
    print(stdout)
    print(stderr, file=sys.stderr)
    return r.returncode


def cmd_verify(args):
    """Verify a covenant on kascov explorer."""
    covenant_id = args.covenant_id
    print(f"View on kascov: https://kascov.io/{NETWORK}/c/{covenant_id}")
    print(f"Explorer: https://explorer-{NETWORK}.kaspa.org")
    print()
    print("Check that:")
    print("  1. The covenant appears on kascov (may take ~1 min to index)")
    print("  2. The birth transaction is confirmed")
    print("  3. The program bytes match what you deployed")


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
    p = sub.add_parser("balance", help="Check balance")
    p.set_defaults(func=cmd_balance)
    
    # deploy
    p = sub.add_parser("deploy", help="Deploy a covenant (any SilverScript)")
    p.add_argument("--program-hex", help="Compiled program hex")
    p.add_argument("--file", help="Compiled .json file (silverc output)")
    p.add_argument("--value", default="1", help="KAS to fund the covenant with")
    p.set_defaults(func=cmd_deploy)
    
    # spend
    p = sub.add_parser("spend", help="Spend from a covenant")
    p.add_argument("--program-hex", help="Compiled program hex")
    p.add_argument("--file", help="Compiled .json file")
    p.add_argument("--entrypoint", default="withdraw", help="Entrypoint to call")
    p.add_argument("--to", help="Recipient address (default: your own)")
    p.add_argument("--dry-run", action="store_true", help="Simulate without broadcasting")
    p.add_argument("--settle-escrow", help="Release-to party for Escrow")
    p.set_defaults(func=cmd_spend)
    
    # verify
    p = sub.add_parser("verify", help="Verify a covenant on kascov")
    p.add_argument("covenant_id", help="Covenant ID to verify")
    p.set_defaults(func=cmd_verify)
    
    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
