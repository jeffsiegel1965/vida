#!/usr/bin/env python3
"""
Covenant manager — human-side tool for creating, checking, and funding agent pots.

Usage:
  python scripts/covenant_manager.py status
  python scripts/covenant_manager.py plan --max-per-tx 1.0 --max-per-day 5.0 --dest kaspatest:...
  python scripts/covenant_manager.py check --amount 0.5 --dest kaspatest:...
  python scripts/covenant_manager.py record <wallet-id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vida.plugins.covenant.tools import (
    covenant_status,
    covenant_describe,
    covenant_live_gates,
    covenant_plan_pot,
    covenant_spend_policy_check,
    covenant_pot_record,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Covenant manager")
    ap.add_argument("command", choices=[
        "status", "describe", "gates", "plan", "check", "record"
    ])

    ap.add_argument("--wallet-id", default="default")
    ap.add_argument("--max-per-tx", type=float, default=0)
    ap.add_argument("--max-per-day", type=float, default=0)
    ap.add_argument("--dest", action="append", default=None)
    ap.add_argument("--amount", type=float, default=0)
    ap.add_argument("--address", default="")
    ap.add_argument("--offer", type=str, default="")
    ap.add_argument("--owner-policy", type=str, default="")

    args = ap.parse_args()

    if args.command == "status":
        r = covenant_status(args.wallet_id)
    elif args.command == "describe":
        r = covenant_describe()
    elif args.command == "gates":
        r = covenant_live_gates()
    elif args.command == "plan":
        r = covenant_plan_pot(
            max_kas_per_tx=args.max_per_tx,
            max_kas_per_day=args.max_per_day,
            allowed_destinations=args.dest,
        )
    elif args.command == "check":
        rec = covenant_pot_record(args.wallet_id)
        if not rec.get("ok"):
            print(f"No pot record for {args.wallet_id}: {rec.get('error')}")
            print("Using example policy for check...")
            policy = {"max_tx_sompi": 100_000_000, "allowed_destinations": args.dest or []}
        else:
            template = rec["record"].get("template") or {}
            policy = template.get("policy") or {}
        r = covenant_spend_policy_check(
            amount_kas=args.amount,
            destination=args.address,
            policy=policy,
        )
    elif args.command == "record":
        r = covenant_pot_record(args.wallet_id)
    else:
        r = {"ok": False, "error": "unknown command"}

    print(json.dumps(r, indent=2, default=str))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())