"""Vida covenant monetization — low fees in KAS, separate from donations.

Model:
  - Covenant pot funding: 0.1% fee (min 0.01 KAS, max 1 KAS) to fee address
  - Covenant pot spend: 0.05% fee (min 0.005 KAS, max 0.5 KAS)
  - Agent covenant negotiation: free
  - kascov API queries: free
  - First pot free per wallet

Separate addresses:
  - FEE address: protocol fees collected on every transaction
  - DONATION address: voluntary contributions / dev fund (separate from fees)

Both are configurable via env vars. Neither is enforced on-chain — fees are
a good-faith support mechanism, implemented in Python for transparency.
Any forker can modify or remove them. The real moat is the ecosystem.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

# ── Fee address ──
# Protocol fee collected on every covenant transaction.
# This is the address the user explicitly provided for fees.
# Override: VIDA_FEE_ADDRESS=kaspa:your_address
_FEE_ADDRESS_ENV = "VIDA_FEE_ADDRESS"
FEE_ADDRESS = os.environ.get(_FEE_ADDRESS_ENV, "kaspa:qzmqqnkmqhtghmyh5hax5m2082em85j2ap5th06rnmhy2nmm078nsvqc7vwh3")
FEE_ADDRESS_TESTNET = os.environ.get(
    "VIDA_FEE_ADDRESS_TESTNET", "kaspatest:qzmqqnkmqhtghmyh5hax5m2082em85j2ap5th06rnmhy2nmm078nsvqc7vwh3"
)

# ── Donation address (dev fund) ──
# Voluntary contributions. Separate from protocol fees.
# Override: VIDA_DONATION_ADDRESS=kaspa:your_address
_DONATION_ADDRESS_ENV = "VIDA_DONATION_ADDRESS"
DONATION_ADDRESS = os.environ.get(
    _DONATION_ADDRESS_ENV, "kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k"
)
DONATION_ADDRESS_TESTNET = os.environ.get(
    "VIDA_DONATION_ADDRESS_TESTNET", "kaspatest:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k"
)


@dataclass
class FeeSchedule:
    """Fee rates for covenant services."""

    # Pot funding fee
    fund_fee_pct: float = 0.001  # 0.1%
    fund_fee_min_kas: float = 0.01
    fund_fee_max_kas: float = 1.0

    # Per-spend fee
    spend_fee_pct: float = 0.0005  # 0.05%
    spend_fee_min_kas: float = 0.005
    spend_fee_max_kas: float = 0.5

    # Free tier: first N pots per wallet are free
    free_pots_per_wallet: int = 1


FEE_SCHEDULE = FeeSchedule()


def calc_fund_fee(pot_kas: float, volume_discount_pct: float = 0.0) -> float:
    """Calculate fee for funding a covenant pot. Returns 0 for invalid input."""
    if not isinstance(pot_kas, (int, float)) or not math.isfinite(pot_kas) or pot_kas <= 0:
        return 0.0
    fee = pot_kas * FEE_SCHEDULE.fund_fee_pct
    fee = max(fee, FEE_SCHEDULE.fund_fee_min_kas)
    fee = min(fee, FEE_SCHEDULE.fund_fee_max_kas)
    if volume_discount_pct > 0:
        fee = fee * (1 - min(volume_discount_pct, 0.5))
    return round(max(fee, 0.0), 6)


def calc_spend_fee(amount_kas: float, volume_discount_pct: float = 0.0) -> float:
    """Calculate fee for spending from a covenant pot. Returns 0 for invalid input."""
    if not isinstance(amount_kas, (int, float)) or not math.isfinite(amount_kas) or amount_kas <= 0:
        return 0.0
    fee = amount_kas * FEE_SCHEDULE.spend_fee_pct
    fee = max(fee, FEE_SCHEDULE.spend_fee_min_kas)
    fee = min(fee, FEE_SCHEDULE.spend_fee_max_kas)
    if volume_discount_pct > 0:
        fee = fee * (1 - min(volume_discount_pct, 0.5))
    return round(max(fee, 0.0), 6)


def get_fee_address(network: str = "mainnet") -> str:
    """Get the protocol fee address for the given network."""
    if network == "mainnet":
        return FEE_ADDRESS
    return FEE_ADDRESS_TESTNET


def get_donation_address(network: str = "mainnet") -> str:
    """Get the donation/dev fund address for the given network."""
    if network == "mainnet":
        return DONATION_ADDRESS
    return DONATION_ADDRESS_TESTNET


def describe_fees() -> dict:
    """Return fee schedule for display, with both addresses."""
    return {
        "fund_fee_pct": FEE_SCHEDULE.fund_fee_pct * 100,
        "fund_fee_min_kas": FEE_SCHEDULE.fund_fee_min_kas,
        "fund_fee_max_kas": FEE_SCHEDULE.fund_fee_max_kas,
        "spend_fee_pct": FEE_SCHEDULE.spend_fee_pct * 100,
        "spend_fee_min_kas": FEE_SCHEDULE.spend_fee_min_kas,
        "spend_fee_max_kas": FEE_SCHEDULE.spend_fee_max_kas,
        "free_pots_per_wallet": FEE_SCHEDULE.free_pots_per_wallet,
        "fee_address": FEE_ADDRESS,
        "donation_address": DONATION_ADDRESS,
        "currency": "KAS",
        "note": "Fees (protocol) and donations (dev fund) go to separate addresses. Both are configurable via env vars.",
        "forkability_note": "Implemented in Python for transparency. Forkers can modify or remove.",
    }
