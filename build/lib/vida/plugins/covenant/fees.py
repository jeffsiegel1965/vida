"""Vida covenant monetization — low fees in KAS, separate from donations.

Model:
  - Covenant pot funding: 0.1% fee (min 0.01 KAS, max 1 KAS) to fee address
  - Covenant pot spend: 0.05% fee (min 0.005 KAS, max 0.5 KAS)
  - Agent covenant negotiation: free
  - kascov API queries: free
  - First pot free per wallet

TAO subnet gateway:
  - Subnet query: 0.05% fee (min 0.0001 TAO, max 0.1 TAO)
  - Subnet staking: 0.1% fee (min 0.01 TAO, max 1 TAO)
  - Agent registration: free
  - First 100 queries per day free per wallet

Separate addresses:
  - FEE address (KAS): protocol fees collected on every covenant transaction
  - DONATION address (KAS): voluntary contributions / dev fund
  - TAO FEE address: subnet gateway fees collected in TAO

All configurable via env vars. Implemented in Python for transparency.
Forkers can modify or remove. The real moat is the ecosystem.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

# ── Fee address (KAS) ──
_FEE_ADDRESS_ENV = "VIDA_FEE_ADDRESS"
FEE_ADDRESS = os.environ.get(_FEE_ADDRESS_ENV, "kaspa:qzmqqnkmqhtghmyh5hax5m2082em85j2ap5th06rnmhy2nmm078nsvqc7vwh3")
FEE_ADDRESS_TESTNET = os.environ.get(
    "VIDA_FEE_ADDRESS_TESTNET", "kaspatest:qzmqqnkmqhtghmyh5hax5m2082em85j2ap5th06rnmhy2nmm078nsvqc7vwh3"
)

# ── Donation address (KAS) ──
_DONATION_ADDRESS_ENV = "VIDA_DONATION_ADDRESS"
DONATION_ADDRESS = os.environ.get(
    _DONATION_ADDRESS_ENV, "kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k"
)
DONATION_ADDRESS_TESTNET = os.environ.get(
    "VIDA_DONATION_ADDRESS_TESTNET", "kaspatest:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k"
)

# ── TAO fee address (subnet gateway fees) ──
# Set VIDA_TAO_FEE_ADDRESS=5GrwvaEF5zXb26Fz... to override.
_TAO_FEE_ADDRESS_ENV = "VIDA_TAO_FEE_ADDRESS"
TAO_FEE_ADDRESS = os.environ.get(_TAO_FEE_ADDRESS_ENV, "5H5x9KXVeAPuEciBnoSWGNQAamxBBLML2ALZnw5SCRL3eezc")


@dataclass
class FeeSchedule:
    """Fee rates for covenant services (KAS)."""

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


@dataclass
class SubnetFeeSchedule:
    """Fee rates for Bittensor subnet gateway services (TAO)."""

    # Per-query fee
    query_fee_pct: float = 0.0005  # 0.05%
    query_fee_min_tao: float = 0.0001
    query_fee_max_tao: float = 0.1

    # Staking fee
    stake_fee_pct: float = 0.001  # 0.1%
    stake_fee_min_tao: float = 0.01
    stake_fee_max_tao: float = 1.0

    # Free tier: first N queries per day per wallet are free
    free_queries_per_day: int = 100


FEE_SCHEDULE = FeeSchedule()
SUBNET_FEE_SCHEDULE = SubnetFeeSchedule()


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


def calc_subnet_query_fee(amount_tao: float) -> float:
    """Calculate Vida's fee for a subnet query. Returns 0 for invalid input."""
    if not isinstance(amount_tao, (int, float)) or not math.isfinite(amount_tao) or amount_tao <= 0:
        return 0.0
    fee = amount_tao * SUBNET_FEE_SCHEDULE.query_fee_pct
    fee = max(fee, SUBNET_FEE_SCHEDULE.query_fee_min_tao)
    fee = min(fee, SUBNET_FEE_SCHEDULE.query_fee_max_tao)
    return round(fee, 6)


def calc_subnet_stake_fee(amount_tao: float) -> float:
    """Calculate Vida's fee for staking TAO to a subnet. Returns 0 for invalid input."""
    if not isinstance(amount_tao, (int, float)) or not math.isfinite(amount_tao) or amount_tao <= 0:
        return 0.0
    fee = amount_tao * SUBNET_FEE_SCHEDULE.stake_fee_pct
    fee = max(fee, SUBNET_FEE_SCHEDULE.stake_fee_min_tao)
    fee = min(fee, SUBNET_FEE_SCHEDULE.stake_fee_max_tao)
    return round(fee, 6)


def get_fee_address(network: str = "mainnet") -> str:
    """Get the protocol fee address (KAS) for the given network."""
    if network == "mainnet":
        return FEE_ADDRESS
    return FEE_ADDRESS_TESTNET


def get_donation_address(network: str = "mainnet") -> str:
    """Get the donation/dev fund address (KAS) for the given network."""
    if network == "mainnet":
        return DONATION_ADDRESS
    return DONATION_ADDRESS_TESTNET


def get_tao_fee_address() -> str:
    """Get the TAO fee address for subnet gateway fees."""
    return TAO_FEE_ADDRESS


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
        "subnet_query_fee_pct": SUBNET_FEE_SCHEDULE.query_fee_pct * 100,
        "subnet_query_fee_min_tao": SUBNET_FEE_SCHEDULE.query_fee_min_tao,
        "subnet_query_fee_max_tao": SUBNET_FEE_SCHEDULE.query_fee_max_tao,
        "subnet_stake_fee_pct": SUBNET_FEE_SCHEDULE.stake_fee_pct * 100,
        "subnet_stake_fee_min_tao": SUBNET_FEE_SCHEDULE.stake_fee_min_tao,
        "subnet_stake_fee_max_tao": SUBNET_FEE_SCHEDULE.stake_fee_max_tao,
        "free_queries_per_day": SUBNET_FEE_SCHEDULE.free_queries_per_day,
        "fee_address": FEE_ADDRESS,
        "donation_address": DONATION_ADDRESS,
        "tao_fee_address": TAO_FEE_ADDRESS,
        "currency_kas": "KAS",
        "currency_tao": "TAO",
        "note": "Fees (protocol) and donations (dev fund) go to separate addresses. "
        "TAO fees go to a separate TAO address. All configurable via env vars.",
        "forkability_note": "Implemented in Python for transparency. Forkers can modify or remove.",
    }
