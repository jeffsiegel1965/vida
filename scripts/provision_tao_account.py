#!/usr/bin/env python3
"""
Owner-run: provision a TAO account from a mnemonic (never via agent chat).

Reads mnemonic from env VIDA_TAO_MNEMONIC or a file path — not argv (avoids shell history).
Password from env VIDA_TAO_PASSWORD or interactive getpass.

Example:
  export VIDA_TAO_MNEMONIC_FILE=./owner_seed.txt   # 0600 file
  export VIDA_TAO_PASSWORD='...'
  python scripts/provision_tao_account.py --wallet-id mywallet --network finney
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read_mnemonic(args: argparse.Namespace) -> str:
    if args.mnemonic_file:
        p = Path(args.mnemonic_file)
        return p.read_text().strip()
    env_file = os.environ.get("VIDA_TAO_MNEMONIC_FILE")
    if env_file:
        return Path(env_file).read_text().strip()
    env = os.environ.get("VIDA_TAO_MNEMONIC")
    if env:
        return env.strip()
    raise SystemExit(
        "Provide mnemonic via VIDA_TAO_MNEMONIC_FILE or VIDA_TAO_MNEMONIC (not CLI args — stays out of shell history)"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Provision Vida TAO account (owner only)")
    ap.add_argument("--wallet-id", required=True)
    ap.add_argument("--network", default="finney", choices=["finney", "test", "mock"])
    ap.add_argument("--store-dir", default=str(ROOT / "data" / "tao_accounts"))
    ap.add_argument("--mnemonic-file", default=None)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--ss58-prefix", type=int, default=42)
    args = ap.parse_args()

    from vida.plugins.tao.accounts import TaoAccountStore
    from vida.plugins.tao.provision import provision_tao_account

    mnemonic = _read_mnemonic(args)
    password = os.environ.get("VIDA_TAO_PASSWORD") or getpass.getpass("Encrypt password: ")
    store = TaoAccountStore(args.store_dir)
    result = provision_tao_account(
        wallet_id=args.wallet_id,
        mnemonic=mnemonic,
        password=password,
        network=args.network,
        store=store,
        ss58_prefix=args.ss58_prefix,
        overwrite=args.overwrite,
    )
    # Never print secrets
    print(json.dumps({k: v for k, v in result.items() if k != "secrets"}, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
