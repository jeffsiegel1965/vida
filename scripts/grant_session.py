#!/usr/bin/env python3
"""
Grant the agent time-boxed autonomous access to the Vida wallet.
RUN THIS YOURSELF — it asks for your password (the agent never sees it).

    python scripts/grant_session.py           # from the repo root, inside your venv

Revoke anytime:
    python scripts/grant_session.py --revoke
"""

import getpass
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'vida'))
from secure_wallet import grant_agent_session, revoke_agent_session

BASE = Path(__file__).resolve().parent.parent
WALLET = BASE / "vida_secure.json"
SESSION = BASE / "agent_session.json"


def main():
    if "--revoke" in sys.argv:
        if revoke_agent_session(SESSION):
            print("Agent session revoked (file scrubbed and deleted).")
        else:
            print("No active session file found.")
        return

    if not WALLET.exists():
        print("No secure wallet found. Run scripts/setup_owner_wallet.py first.")
        sys.exit(1)

    print("Grant the agent autonomous spending access")
    print("-" * 44)
    hours = float(input("Session length in hours [24]: ").strip() or "24")
    per_tx = float(input("Max KAS per transaction (0 = unlimited) [5]: ").strip() or "5")
    per_day = float(input("Max KAS per day (0 = unlimited) [20]: ").strip() or "20")
    pw = getpass.getpass("Wallet password (input hidden): ")

    try:
        info = grant_agent_session(
            WALLET, pw, SESSION,
            hours=hours, max_kas_per_tx=per_tx, max_kas_per_day=per_day,
        )
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    exp = time.strftime("%Y-%m-%d %H:%M", time.localtime(info["expires_at"]))
    print(f"\nSession granted until {exp}")
    print(f"Limits: {per_tx} KAS/tx, {per_day} KAS/day")
    print(f"Session file: {info['session_path']}")
    print("\nThe agent can now spend within these limits WITHOUT your password.")
    print("Revoke anytime: scripts/grant_session.py --revoke")


if __name__ == "__main__":
    main()
