#!/usr/bin/env python3
"""
Owner: add ML-DSA-65 PQ identity to an existing TAO account (if missing).

    python scripts/upgrade_tao_pq.py --wallet-id live-e2e

Does not change the SS58 funds address. PQ is forward identity only.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

E2E_STORE = ROOT / "data" / "tao_live_e2e" / "accounts"
DEFAULT_STORE = ROOT / "data" / "tao_accounts"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wallet-id", required=True)
    ap.add_argument("--store-dir", default="")
    args = ap.parse_args()

    from vida.plugins.tao.accounts import TaoAccountStore
    from vida.plugins.tao.provision import ensure_tao_pq_identity

    store_dir = args.store_dir
    if not store_dir:
        if (E2E_STORE / args.wallet_id / "tao_account.json").is_file():
            store_dir = str(E2E_STORE)
        else:
            store_dir = str(DEFAULT_STORE)

    password = os.environ.get("VIDA_TAO_PASSWORD") or getpass.getpass("TAO wallet password: ")
    r = ensure_tao_pq_identity(
        wallet_id=args.wallet_id,
        password=password,
        store=TaoAccountStore(store_dir),
    )
    print(r)
    if r.get("ok"):
        print("\nPQ-ready: ML-DSA-65 identity stored encrypted.")
        print("Still NOT on-chain — Finney uses sr25519 for spends.")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
