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
import threading
_COVENANT_PLUGIN: CovenantPlugin | None = None
_PLUGIN_LOCK = threading.Lock()

def _plugin() -> CovenantPlugin:
    global _COVENANT_PLUGIN
    if _COVENANT_PLUGIN is None:
        with _PLUGIN_LOCK:
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
    result = _plugin().describe()
    if "ok" not in result:
        result["ok"] = True
    return result


def covenant_live_gates() -> dict[str, Any]:
    """Check if live covenant tooling is available on this host."""
    result = live_gates_ok()
    if "ok" not in result:
        result["ok"] = True
    return result


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


def covenant_quine_info() -> dict[str, Any]:
    """Get SilverScript quine covenant deployment info and Toccata resources."""
    return {
        "ok": True,
        "silverscript": {
            "source": "vida/plugins/covenant/silverscript/quine_agent_pot.sil",
            "compiled": "vida/plugins/covenant/silverscript/quine_agent_pot.json",
            "compiler": "silverc",
            "status": "compiled, debugger-verified",
            "entrypoints": ["withdraw(pubkey)", "burn(sig)"],
        },
        "kii_quine": {
            "covenant_id": "b802c18ba691c4a52c4a89de7f72fe475637e3a70f9f56a32663b5754a1ed4af",
            "genesis_tx": "1c1a4c549c664147814d9836e623373991622c1dc711a4227f206ad5f6a241c5",
            "network": "kaspa_mainnet",
            "generations": "~96 from 1 KAS",
        },
        "toccata_resources": {
            "book": "https://docs.kaspa.org/toccata",
            "silverscript": "https://github.com/kaspanet/silverscript",
            "parker_vault": "@parker2017 on X",
            "kas_smiths": "https://kas-smiths.org",
        },
        "deployment": {
            "status": "SilverScript compiled, ready for on-chain deployment",
            "next_steps": [
                "Fund P2SH address from compiled artifact",
                "Verify on kascov explorer",
                "Test self-replication with spend transaction",
            ],
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
    "covenant_quine_info": {
        "fn": covenant_quine_info,
        "description": "SilverScript quine covenant deployment info and Toccata resources",
        "params": {},
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