"""Vida covenant monetization — low fees in KAS.

Model:
  - Covenant pot funding: 0.1% fee (min 0.01 KAS, max 1 KAS) to dev fund
  - Covenant pot spend: 0.05% fee (min 0.005 KAS, max 0.5 KAS)
  - Agent covenant negotiation: free
  - kascov API queries: free
  - First pot free per wallet

HONEST NOTE ON FORKABILITY:
These fees are implemented in Python for transparency and ease of audit.
Any forker can modify or remove them — the fee is a good-faith support
mechanism, not a technical enforcement. We compete on quality, not fee
extraction. The real moat is the kascov-lab binary (complex to build)
and the Vida ecosystem.

All fees are transparent, documented, and paid in KAS.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

# Dev fund address for fee collection
DEV_FUND_ADDRESS = "kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k"

# Dev fund address (testnet-10 variant)
DEV_FUND_ADDRESS_TESTNET = "kaspatest:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k"


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


def calc_fund_fee(pot_kas: float) -> float:
    """Calculate fee for funding a covenant pot. Returns 0 for invalid input."""
    if not isinstance(pot_kas, (int, float)) or not math.isfinite(pot_kas) or pot_kas <= 0:
        return 0.0
    fee = pot_kas * FEE_SCHEDULE.fund_fee_pct
    fee = max(fee, FEE_SCHEDULE.fund_fee_min_kas)
    fee = min(fee, FEE_SCHEDULE.fund_fee_max_kas)
    return round(fee, 6)


def calc_spend_fee(amount_kas: float) -> float:
    """Calculate fee for spending from a covenant pot. Returns 0 for invalid input."""
    if not isinstance(amount_kas, (int, float)) or not math.isfinite(amount_kas) or amount_kas <= 0:
        return 0.0
    fee = amount_kas * FEE_SCHEDULE.spend_fee_pct
    fee = max(fee, FEE_SCHEDULE.spend_fee_min_kas)
    fee = min(fee, FEE_SCHEDULE.spend_fee_max_kas)
    return round(fee, 6)


def get_dev_address(network: str = "mainnet") -> str:
    """Get dev fund address for the given network."""
    if network == "mainnet":
        return DEV_FUND_ADDRESS
    return DEV_FUND_ADDRESS_TESTNET


def describe_fees() -> dict:
    """Return fee schedule for display."""
    return {
        "fund_fee_pct": FEE_SCHEDULE.fund_fee_pct * 100,
        "fund_fee_min_kas": FEE_SCHEDULE.fund_fee_min_kas,
        "fund_fee_max_kas": FEE_SCHEDULE.fund_fee_max_kas,
        "spend_fee_pct": FEE_SCHEDULE.spend_fee_pct * 100,
        "spend_fee_min_kas": FEE_SCHEDULE.spend_fee_min_kas,
        "spend_fee_max_kas": FEE_SCHEDULE.spend_fee_max_kas,
        "free_pots_per_wallet": FEE_SCHEDULE.free_pots_per_wallet,
        "dev_address": DEV_FUND_ADDRESS,
        "currency": "KAS",
        "note": "Fees are transparent and paid in KAS per transaction.",
        "forkability_note": "These fees are implemented in Python for transparency. A forker can modify them. The real moat is the kascov-lab binary and the Vida ecosystem.",
    }