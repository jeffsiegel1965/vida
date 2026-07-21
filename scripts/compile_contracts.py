"""Generate constructor args JSON for Vida SilverScript contracts and compile them.

Usage: python3 compile_contracts.py
"""

import json
import subprocess
import sys
from pathlib import Path

SILVERC = Path.home() / "OpenSilver" / "upstream" / "silverscript" / "target" / "debug" / "silverc"
CONTRACTS_DIR = Path.home() / ".hermes" / "projects" / "vida-release" / "vida" / "plugins" / "covenant" / "silverscript" / "contracts"


def byte_array(data: list[int]) -> dict:
    """Build a byte array expression."""
    return {"kind": "array", "data": [{"kind": "byte", "data": b} for b in data]}


def pubkey_expr(hex_str: str) -> dict:
    """Convert a 32-byte hex string to a pubkey expression."""
    return byte_array([int(hex_str[i:i+2], 16) for i in range(0, 64, 2)])


def int_expr(value: int) -> dict:
    return {"kind": "int", "data": value}


def bool_expr(value: bool) -> dict:
    return {"kind": "bool", "data": value}


# Default test pubkeys (32 bytes each)
OWNER = "00" * 32
FALLBACK = "01" * 32
RECIPIENT = "02" * 32
SENDER = "03" * 32
BENEFICIARY = "04" * 32
ADMIN = "05" * 32


# ── Constructor args for each contract ──

CONTRACTS = {
    "DeadMansSwitch": {
        "ctor": [
            pubkey_expr(OWNER),      # init_owner
            pubkey_expr(FALLBACK),    # init_fallback
            int_expr(100_000),        # init_timeout_age (~7 days at 1 block/sec)
            int_expr(0),             # init_last_ping_age
        ],
    },
    "StreamingPayment": {
        "ctor": [
            pubkey_expr(SENDER),      # init_sender
            pubkey_expr(RECIPIENT),   # init_recipient
            int_expr(1_000_000),      # init_rate_per_claim (0.01 KAS)
            int_expr(100_000_000),    # init_total_allowance (1 KAS)
            int_expr(100_000_000),    # init_remaining_allowance
            int_expr(86_400),         # init_period (~1 day)
            int_expr(0),             # init_next_release_time
        ],
    },
    "Vesting": {
        "ctor": [
            pubkey_expr(BENEFICIARY), # init_beneficiary
            pubkey_expr(ADMIN),       # init_admin
            int_expr(100_000_000),    # init_total_allocation (1 KAS)
            int_expr(0),             # init_claimed_amount
            int_expr(86_400),         # init_cliff_time (~1 day)
            int_expr(86_400),         # init_period
            int_expr(10_000_000),     # init_release_per_period (0.1 KAS)
            bool_expr(True),         # init_revocable
        ],
    },
    "Ownable": {
        "ctor": [
            pubkey_expr(OWNER),       # init_owner
            bool_expr(False),        # init_has_pending_owner
            pubkey_expr("00" * 32),  # init_pending_owner (zeroed)
        ],
    },
    "TimeLock": {
        "ctor": [
            pubkey_expr(OWNER),       # init_owner
            pubkey_expr(BENEFICIARY), # init_beneficiary
            int_expr(100_000),        # init_unlock_time (blocks)
            bool_expr(True),         # init_soft_cancel_enabled
        ],
    },
    "AtomicSwapHTLC": {
        "ctor": [
            pubkey_expr(RECIPIENT),   # init_recipient
            pubkey_expr(OWNER),       # init_refunder
            byte_array([0] * 32),    # init_secret_hash (placeholder)
            int_expr(100_000),        # init_timeout
        ],
    },
    "SocialRecovery": {
        "ctor": [
            pubkey_expr(OWNER),       # init_owner
            bool_expr(False),        # init_has_pending_owner
            pubkey_expr("00" * 32),  # init_pending_owner
            int_expr(2),             # init_guardian_threshold (2 of 3)
            pubkey_expr("01" * 32),  # init_guardian1
            pubkey_expr("02" * 32),  # init_guardian2
            pubkey_expr("03" * 32),  # init_guardian3
            int_expr(0),             # init_activation_time
            int_expr(10_000),        # init_recovery_delay (~2.8 hours)
        ],
    },
}


def main():
    if not SILVERC.exists():
        print(f"Error: silverc not found at {SILVERC}")
        print("Run: cd ~/OpenSilver && bash scripts/bootstrap-silverc.sh")
        sys.exit(1)

    CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)

    for name, config in CONTRACTS.items():
        sil_path = CONTRACTS_DIR / f"{name}.sil"
        json_path = CONTRACTS_DIR / f"{name}.json"
        ctor_path = CONTRACTS_DIR / f"{name}_ctor.json"

        if not sil_path.exists():
            print(f"⚠  Source not found: {sil_path}")
            continue

        # Write constructor args
        with open(ctor_path, "w") as f:
            json.dump(config["ctor"], f, indent=2)

        # Compile with silverc
        print(f"Compiling {name}...", end=" ")
        result = subprocess.run(
            [str(SILVERC), str(sil_path), "--ctor", str(ctor_path)],
            capture_output=True, text=True, cwd=str(CONTRACTS_DIR),
        )

        if result.returncode == 0 and json_path.exists():
            with open(json_path) as f:
                data = json.load(f)
            script_bytes = bytes(data["script"])
            print(f"✅ {len(script_bytes)} bytes")
        else:
            print(f"❌ {result.stderr.strip()[:200]}")

        # Clean up ctor temp file
        ctor_path.unlink(missing_ok=True)

    print("\nDone. Compiled contracts:")
    for p in sorted(CONTRACTS_DIR.glob("*.json")):
        size = p.stat().st_size
        print(f"  {p.name} ({size:,} bytes)")


if __name__ == "__main__":
    main()
