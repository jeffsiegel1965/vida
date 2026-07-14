#!/usr/bin/env python3
"""
Grant the agent time-boxed autonomous access to the Vida Kaspa wallet.
RUN THIS YOURSELF — password is never given to the agent.

    python scripts/grant_session.py
    python scripts/grant_session.py --dest kaspa:qq... --dest kaspa:qr...
    python scripts/grant_session.py --revoke

Requires positive per-tx and per-day caps (safety default).
"""

from __future__ import annotations

import argparse
import getpass
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vida"))
from secure_wallet import grant_agent_session, revoke_agent_session

BASE = Path(__file__).resolve().parent.parent
WALLET = BASE / "vida_secure.json"
SESSION = BASE / "agent_session.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revoke", action="store_true")
    ap.add_argument("--hours", type=float, default=None)
    ap.add_argument("--max-per-tx", type=float, default=None)
    ap.add_argument("--max-per-day", type=float, default=None)
    ap.add_argument(
        "--dest",
        action="append",
        default=None,
        help="Allowed destination (repeatable). If set, agent may only send here.",
    )
    ap.add_argument(
        "--allow-unlimited",
        action="store_true",
        help="Dangerous: allow 0 caps. Prefer positive limits.",
    )
    args = ap.parse_args()

    if args.revoke:
        if revoke_agent_session(SESSION):
            print("Agent session revoked (file scrubbed and deleted).")
        else:
            print("No active session file found.")
        return 0

    if not WALLET.exists():
        print("No secure wallet found. Run scripts/setup_owner_wallet.py first.")
        return 1

    print("Grant the agent autonomous spending access")
    print("-" * 44)
    if args.hours is None:
        hours = float(input("Session length in hours [8]: ").strip() or "8")
    else:
        hours = float(args.hours)
    if args.max_per_tx is None:
        per_tx = float(input("Max KAS per transaction [5]: ").strip() or "5")
    else:
        per_tx = float(args.max_per_tx)
    if args.max_per_day is None:
        per_day = float(input("Max KAS per day [20]: ").strip() or "20")
    else:
        per_day = float(args.max_per_day)

    dests = args.dest
    if dests is None and sys.stdin.isatty():
        raw = input("Allowed destinations (comma-separated, empty = any) []: ").strip()
        if raw:
            dests = [x.strip() for x in raw.split(",") if x.strip()]

    pw = getpass.getpass("Wallet password (input hidden): ")

    try:
        info = grant_agent_session(
            WALLET,
            pw,
            SESSION,
            hours=hours,
            max_kas_per_tx=per_tx,
            max_kas_per_day=per_day,
            allowed_destinations=dests,
            allow_unlimited=bool(args.allow_unlimited),
        )
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    exp = time.strftime("%Y-%m-%d %H:%M", time.localtime(info["expires_at"]))
    print(f"\nSession granted until {exp}")
    print(f"Limits: {per_tx} KAS/tx, {per_day} KAS/day")
    if dests:
        print(f"Destinations: {dests}")
    else:
        print("Destinations: unrestricted (prefer --dest for payment agents)")
    print(f"Session file: {info['session_path']}")
    print("\nThe agent can spend within these limits WITHOUT your password.")
    print("Use confirm=True on sends. Revoke: scripts/grant_session.py --revoke")
    print("After grant, keep mnemonic offline — never next to the session file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
