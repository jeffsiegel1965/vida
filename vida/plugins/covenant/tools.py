"""
Covenant Hermes tools — human and agent facing.

Humans: create, fund, check covenant pots.
Agents: negotiate covenant terms, generate pot templates, check spend policy.
"""

from __future__ import annotations

from typing import Any, Optional

from .plugin import CovenantPlugin
from .pot_spend import check_spend_allowed, check_spend_kas, load_pot_record
from .agent_pot import plan_agent_pot, SOMPI_PER_KAS
from .agent_pot_script import build_agent_pot_script_template, verify_policy_hash
from .fees import calc_fund_fee, calc_spend_fee, get_dev_address, describe_fees
from .lab_client import live_gates_ok


# ── Plugin instance (shared across tools) ──
_COVENANT_PLUGIN: CovenantPlugin | None = None


def _plugin() -> CovenantPlugin:
    global _COVENANT_PLUGIN
    if _COVENANT_PLUGIN is None:
        _COVENANT_PLUGIN = CovenantPlugin()
    return _COVENANT_PLUGIN


# ── Human-side tools ──


def covenant_status(wallet_id: str = "default") -> dict[str, Any]:
    """Check covenant module status. Safe for humans and agents."""
    from vida.plugins.base import VidaPluginContext

    ctx = VidaPluginContext(wallet_id=wallet_id)
    return _plugin().status(ctx)


def covenant_describe() -> dict[str, Any]:
    """Describe covenant capabilities and phase."""
    return _plugin().describe()


def covenant_live_gates() -> dict[str, Any]:
    """Check if live covenant tooling is available on this host."""
    return live_gates_ok()


def covenant_plan_pot(
    max_kas_per_tx: float,
    max_kas_per_day: float,
    allowed_destinations: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Plan an agent pot: how much to fund, what hard rules to set."""
    return plan_agent_pot(
        max_kas_per_tx=max_kas_per_tx,
        max_kas_per_day=max_kas_per_day,
        allowed_destinations=allowed_destinations or [],
    )


def covenant_plan_with_fees(
    max_kas_per_tx: float,
    max_kas_per_day: float,
    allowed_destinations: Optional[list[str]] = None,
    network: str = "mainnet",
) -> dict[str, Any]:
    """Plan an agent pot with fee breakdown. Shows total + dev fee."""
    plan = plan_agent_pot(
        max_kas_per_tx=max_kas_per_tx,
        max_kas_per_day=max_kas_per_day,
        allowed_destinations=allowed_destinations or [],
    )
    if not plan.get("ok"):
        return plan
    pot_kas = float(plan["fund_pot_kas"])
    fee = calc_fund_fee(pot_kas)
    plan["fee"] = {
        "dev_fee_kas": fee,
        "dev_fee_sompi": int(round(fee * SOMPI_PER_KAS)),
        "dev_address": get_dev_address(network),
        "network": network,
        "total_kas": pot_kas + fee,
        "total_sompi": int(round((pot_kas + fee) * SOMPI_PER_KAS)),
        "fee_pct": fee / pot_kas * 100 if pot_kas > 0 else 0,
        "note": "Fee is added to the pot funding transaction as an additional output to the dev fund address.",
    }
    return plan


def covenant_estimate_fee(amount_kas: float, fee_type: str = "fund") -> dict[str, Any]:
    """Estimate fee for a covenant operation."""
    if fee_type == "fund":
        fee = calc_fund_fee(amount_kas)
    elif fee_type == "spend":
        fee = calc_spend_fee(amount_kas)
    else:
        return {"ok": False, "error": "fee_type must be 'fund' or 'spend'"}
    return {
        "ok": True,
        "amount_kas": amount_kas,
        "fee_kas": fee,
        "fee_type": fee_type,
        "fee_pct": fee / amount_kas * 100 if amount_kas > 0 else 0,
        "dev_address": get_dev_address("mainnet"),
    }


def covenant_fee_schedule() -> dict[str, Any]:
    """Get the full fee schedule for covenant services."""
    return describe_fees()


def covenant_spend_policy_check(
    amount_kas: float,
    destination: str,
    policy: dict[str, Any],
    owner_address: Optional[str] = None,
) -> dict[str, Any]:
    """Check if a spend would be allowed under a covenant pot policy."""
    return check_spend_kas(
        policy=policy,
        amount_kas=amount_kas,
        destination=destination,
        owner_address=owner_address,
    )


def covenant_pot_record(wallet_id: str) -> dict[str, Any]:
    """Load pot funding record for a wallet."""
    return load_pot_record(wallet_id)


# ── Agent negotiation tools ──


def covenant_negotiate_terms(
    *,
    agent_offer: dict[str, Any],
    owner_policy: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Agent proposes covenant terms; owner policy constrains them.

    agent_offer keys:
      - max_kas_per_tx: float
      - max_kas_per_day: float
      - allowed_destinations: list[str]
      - duration_hours: float

    owner_policy (optional):
      - max_kas_per_tx: float (hard ceiling)
      - max_kas_per_day: float (hard ceiling)
      - allowed_destinations: list[str] (intersection)
      - max_duration_hours: float

    Returns agreed-upon terms or error.
    """
    offer_tx = float(agent_offer.get("max_kas_per_tx") or 0)
    offer_day = float(agent_offer.get("max_kas_per_day") or 0)
    offer_dests = list(agent_offer.get("allowed_destinations") or [])
    offer_hours = float(agent_offer.get("duration_hours") or 0)

    if owner_policy:
        cap_tx = float(owner_policy.get("max_kas_per_tx") or 0)
        cap_day = float(owner_policy.get("max_kas_per_day") or 0)
        cap_dests = list(owner_policy.get("allowed_destinations") or [])
        cap_hours = float(owner_policy.get("max_duration_hours") or 0)

        if cap_tx > 0 and offer_tx > cap_tx:
            offer_tx = cap_tx
        if cap_day > 0 and offer_day > cap_day:
            offer_day = cap_day
        if cap_dests:
            offer_dests = [d for d in offer_dests if d in cap_dests]
        if cap_hours > 0 and offer_hours > cap_hours:
            offer_hours = cap_hours

    if offer_tx <= 0 or offer_day <= 0:
        return {"ok": False, "error": "max_kas_per_tx and max_kas_per_day must be positive"}

    agreed = {
        "max_kas_per_tx": offer_tx,
        "max_kas_per_day": offer_day,
        "allowed_destinations": offer_dests,
        "duration_hours": max(offer_hours, 1.0),
    }
    template = build_agent_pot_script_template(
        max_kas_per_tx=agreed["max_kas_per_tx"],
        max_kas_per_day=agreed["max_kas_per_day"],
        allowed_destinations=agreed["allowed_destinations"],
    )
    if not template.get("ok"):
        return {"ok": False, "error": template.get("error", "template build failed")}

    plan = plan_agent_pot(
        max_kas_per_tx=agreed["max_kas_per_tx"],
        max_kas_per_day=agreed["max_kas_per_day"],
        allowed_destinations=agreed["allowed_destinations"],
        session_hours=agreed["duration_hours"],
    )

    return {
        "ok": True,
        "agreed_terms": agreed,
        "policy_hash": template["policy_hash"],
        "policy_template": template,
        "fund_plan": plan,
        "enforcement": {
            "soft_session": True,
            "covenant_pot": True,
            "hard_script": False,
        },
    }


def covenant_validate_pot(policy_template: dict[str, Any]) -> dict[str, Any]:
    """Validate a pot policy template (hash integrity check)."""
    if not policy_template.get("ok"):
        return {"ok": False, "error": "template not ok"}
    valid = verify_policy_hash(policy_template)
    return {
        "ok": valid,
        "policy_hash": policy_template.get("policy_hash"),
        "hash_valid": valid,
        "live_script_ready": policy_template.get("live_script_ready", False),
    }


# ── kascov explorer integration ──


def covenant_kascov_live(network: str = "testnet-10") -> dict[str, Any]:
    """Check kascov live feed for covenant stats."""
    from .kascov_client import get_kascov

    return get_kascov(network=network).live()


def covenant_kascov_verify(covenant_id: str, network: str = "testnet-10") -> dict[str, Any]:
    """Verify a covenant exists on-chain via kascov API."""
    from .kascov_client import get_kascov

    return get_kascov(network=network).verify_covenant(covenant_id)


def covenant_kascov_search(query: str, network: str = "testnet-10") -> dict[str, Any]:
    """Search kascov for covenants by query."""
    from .kascov_client import get_kascov

    return get_kascov(network=network).search(query)


def covenant_kascov_address(address: str, network: str = "testnet-10") -> dict[str, Any]:
    """Check which smart coins an address controls."""
    from .kascov_client import get_kascov

    return get_kascov(network=network).address(address)


# ── Registry for Hermes tool discovery ──

HERMES_TOOLS: dict[str, dict[str, Any]] = {
    "covenant_status": {
        "fn": covenant_status,
        "description": "Check covenant module status (safe for agents)",
        "params": {"wallet_id": "str"},
    },
    "covenant_describe": {
        "fn": covenant_describe,
        "description": "Describe covenant capabilities and phase",
        "params": {},
    },
    "covenant_live_gates": {
        "fn": covenant_live_gates,
        "description": "Check if live covenant tooling is available",
        "params": {},
    },
    "covenant_plan_pot": {
        "fn": covenant_plan_pot,
        "description": "Plan an agent pot funding and hard rules",
        "params": {
            "max_kas_per_tx": "float",
            "max_kas_per_day": "float",
            "allowed_destinations": "list[str]|None",
        },
    },
    "covenant_negotiate_terms": {
        "fn": covenant_negotiate_terms,
        "description": "Agent proposes covenant terms; owner policy constrains them",
        "params": {
            "agent_offer": "dict",
            "owner_policy": "dict|None",
        },
    },
    "covenant_validate_pot": {
        "fn": covenant_validate_pot,
        "description": "Validate a pot policy template hash",
        "params": {"policy_template": "dict"},
    },
    "covenant_spend_policy_check": {
        "fn": covenant_spend_policy_check,
        "description": "Check if a spend is allowed under a covenant pot policy",
        "params": {
            "amount_kas": "float",
            "destination": "str",
            "policy": "dict",
            "owner_address": "str|None",
        },
    },
    "covenant_pot_record": {
        "fn": covenant_pot_record,
        "description": "Load pot funding record for a wallet",
        "params": {"wallet_id": "str"},
    },
    "covenant_kascov_live": {
        "fn": covenant_kascov_live,
        "description": "Check kascov live feed for covenant stats",
        "params": {"network": "str"},
    },
    "covenant_kascov_verify": {
        "fn": covenant_kascov_verify,
        "description": "Verify a covenant exists on-chain via kascov API",
        "params": {"covenant_id": "str", "network": "str"},
    },
    "covenant_kascov_search": {
        "fn": covenant_kascov_search,
        "description": "Search kascov for covenants by query",
        "params": {"query": "str", "network": "str"},
    },
    "covenant_kascov_address": {
        "fn": covenant_kascov_address,
        "description": "Check which smart coins an address controls",
        "params": {"address": "str", "network": "str"},
    },
    "covenant_plan_with_fees": {
        "fn": covenant_plan_with_fees,
        "description": "Plan an agent pot with fee breakdown",
        "params": {
            "max_kas_per_tx": "float",
            "max_kas_per_day": "float",
            "allowed_destinations": "list[str]|None",
            "network": "str",
        },
    },
    "covenant_estimate_fee": {
        "fn": covenant_estimate_fee,
        "description": "Estimate fee for a covenant operation",
        "params": {"amount_kas": "float", "fee_type": "str"},
    },
    "covenant_fee_schedule": {
        "fn": covenant_fee_schedule,
        "description": "Get the full fee schedule for covenant services",
        "params": {},
    },
}