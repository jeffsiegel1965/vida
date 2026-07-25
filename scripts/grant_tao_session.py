#!/usr/bin/env python3
"""
Grant the agent time-boxed TAO access (owner-run; Hermes can guide the args).

Flexibility: COMMAND (approve each move) → HYBRID (auto under threshold) → FULL (agentic inside caps).
Also: stake, P2P transfer, emission optimize — all under the same session limits.
Vida is not standalone: Hermes uses VIDA_TAO_SESSION after you grant.

    python scripts/grant_tao_session.py --wallet-id my-tao \\
      --max-per-tx 0.05 --max-per-day 0.1 --subnets 1 \\
      --dest 5D...

Revoke:
    python scripts/grant_tao_session.py --revoke

Agent:
    export VIDA_TAO_SESSION=/path/to/session.json
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_STORE = ROOT / "data" / "tao_accounts"
DEFAULT_SESSION = ROOT / "data" / "tao_agent_session.json"
E2E_STORE = ROOT / "data" / "tao_live_e2e" / "accounts"
E2E_SESSION = ROOT / "data" / "tao_live_e2e" / "agent_session.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revoke", action="store_true")
    ap.add_argument("--wallet-id", default="live-e2e")
    ap.add_argument("--store-dir", default="")
    ap.add_argument("--session", default="")
    ap.add_argument("--hours", type=float, default=8.0)
    ap.add_argument(
        "--mode",
        default="FULL",
        choices=["FULL", "HYBRID", "COMMAND"],
        help="COMMAND=you confirm each action; HYBRID=auto under --threshold; FULL=agentic within caps",
    )
    ap.add_argument("--max-per-tx", type=float, default=0.05)
    ap.add_argument("--max-per-day", type=float, default=0.1)
    ap.add_argument("--threshold", type=float, default=0.0)
    ap.add_argument("--subnets", default="1", help="comma-separated netuids; empty=any")
    ap.add_argument(
        "--dest",
        action="append",
        default=None,
        help="Allowed SS58 destinations for transfers (repeatable)",
    )
    ap.add_argument(
        "--scope",
        default="ALL",
        choices=["ALL", "STAKE_ONLY", "TRANSFER_ONLY"],
        help="ALL=stake+transfer+optimize; STAKE_ONLY; TRANSFER_ONLY",
    )
    ap.add_argument(
        "--allow-any-dest", action="store_true", help="Dangerous: allow transfers to any SS58 (default requires --dest)"
    )
    ap.add_argument("--allow-long-session", action="store_true", help="Allow hours > 24")
    ap.add_argument("--allow-unlimited", action="store_true")
    args = ap.parse_args()

    from vida.plugins.tao.session import grant_tao_agent_session, revoke_tao_agent_session

    store_dir = args.store_dir
    session_path = args.session
    if not store_dir:
        if (E2E_STORE / args.wallet_id / "tao_account.json").is_file() or (
            E2E_STORE / args.wallet_id.replace("/", "_") / "tao_account.json"
        ).is_file():
            store_dir = str(E2E_STORE)
            session_path = session_path or str(E2E_SESSION)
        else:
            store_dir = str(DEFAULT_STORE)
            session_path = session_path or str(DEFAULT_SESSION)
    session_path = session_path or str(DEFAULT_SESSION)

    if args.revoke:
        ok = revoke_tao_agent_session(session_path)
        print("revoked" if ok else "no session file")
        return 0

    from vida.plugins.tao.accounts import TaoAccountStore

    store = TaoAccountStore(store_dir)
    password = os.environ.get("VIDA_TAO_PASSWORD")
    if not password:
        password = getpass.getpass("TAO wallet password: ")

    subnets = None
    if args.subnets.strip():
        subnets = [int(x) for x in args.subnets.split(",") if x.strip() != ""]

    r = grant_tao_agent_session(
        store=store,
        wallet_id=args.wallet_id,
        password=password,
        session_path=session_path,
        hours=args.hours,
        mode=args.mode,
        max_tao_per_tx=args.max_per_tx,
        max_tao_per_day=args.max_per_day,
        threshold=args.threshold,
        allowed_subnets=subnets,
        allowed_destinations=args.dest,
        allow_unlimited=bool(args.allow_unlimited),
        scope=args.scope,
        allow_any_dest=bool(args.allow_any_dest),
        allow_long_session=bool(args.allow_long_session),
    )
    print(r)
    if r.get("ok"):
        print(f"\nexport VIDA_TAO_SESSION={session_path}")
        print(f"export VIDA_TAO_STORE={store_dir}")
        print(f"export VIDA_TAO_WALLET={args.wallet_id}")
        print("Agent money tools are session-only (no password in chat).")
        print(f"Revoke: python scripts/grant_tao_session.py --revoke --session {session_path}")
        print("Optional: python scripts/wipe_plaintext_secrets.py --dir <workdir>")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
