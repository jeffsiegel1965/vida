"""Vida Wallet — Free. All operations, both KAS and TAO.

KASPA: Free. Covenant deployment, spending, escrow, payment channels.
TAO: Free. Subnet queries, staking, agent registration.

The wallet is the on-ramp. Adoption drives everything. Monetization lives
in Vida Commerce — the contract platform where value is created.

LICENSE: MIT. Both KAS and TAO operations.
"""

from __future__ import annotations


# ═══════════════════════════════════════════════════════════════════
# All operations free
# ═══════════════════════════════════════════════════════════════════

def calc_kas_fee(amount: float) -> float:
    """Always returns 0."""
    return 0.0


def calc_subnet_query_fee(amount: float) -> float:
    """Always returns 0."""
    return 0.0


def calc_subnet_stake_fee(amount: float) -> float:
    """Always returns 0."""
    return 0.0


def get_fee_address(network: str = "mainnet") -> str:
    """No fee address — operations are free."""
    return ""


def get_donation_address(network: str = "mainnet") -> str:
    """No donation address — operations are free."""
    return ""


def get_tao_fee_address() -> str:
    """No TAO fee address — operations are free."""
    return ""


def describe_fees() -> dict:
    return {
        "kaspa": {
            "free": True,
            "license": "MIT",
            "note": "All Kaspa operations are free. Monetization is in Vida Commerce.",
        },
        "tao": {
            "free": True,
            "license": "MIT",
            "note": "All TAO operations are free. Monetization is in Vida Commerce.",
        },
        "message": "Vida Wallet is free. Vida Commerce is the monetization layer.",
    }