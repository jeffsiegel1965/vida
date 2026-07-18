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
from .negotiation import CovenantTerms, create_deal, Negotiator, UserControls


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
    strategy: str = "covenant_bound_p2pk_pot",
    counterparty_id: Optional[str] = None,
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

    strategy (optional): "covenant_bound_p2pk_pot" (MVP) or "self_replicating_quine_pot"

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

    # Build template with selected strategy
    quine_gen = int(agreed["duration_hours"]) if strategy == "self_replicating_quine_pot" else 0
    template = build_agent_pot_script_template(
        max_kas_per_tx=agreed["max_kas_per_tx"],
        max_kas_per_day=agreed["max_kas_per_day"],
        allowed_destinations=agreed["allowed_destinations"],
        strategy=strategy,
        quine_generations=quine_gen,
        auto_renew=(strategy == "self_replicating_quine_pot"),
    )
    if not template.get("ok"):
        return {"ok": False, "error": template.get("error", "template build failed")}

    plan = plan_agent_pot(
        max_kas_per_tx=agreed["max_kas_per_tx"],
        max_kas_per_day=agreed["max_kas_per_day"],
        allowed_destinations=agreed["allowed_destinations"],
        session_hours=agreed["duration_hours"],
    )

    # If counterparty_id provided, record in DealBook via Negotiator
    deal_book_info = {}
    if counterparty_id:
        from vida.plugins.covenant.negotiation import Negotiator
        neg = Negotiator(owner_id="agent_vida")
        result = neg.template_deal(
            max_kas_per_tx=agreed["max_kas_per_tx"],
            max_kas_per_day=agreed["max_kas_per_day"],
            allowed_destinations=agreed["allowed_destinations"],
            duration_hours=agreed["duration_hours"],
            counterparty_id=counterparty_id,
        )
        deal_book_info = {
            "counterparty_id": counterparty_id,
            "is_first_deal": result.get("is_first_deal", False),
            "escalated": result.get("escalated", False),
        }

    return {
        "ok": True,
        "agreed_terms": agreed,
        "policy_hash": template["policy_hash"],
        "policy_template": template,
        "fund_plan": plan,
        "strategy": strategy,
        "enforcement": {
            "soft_session": True,
            "covenant_pot": True,
            "hard_script": strategy == "self_replicating_quine_pot",
            "self_replicating": strategy == "self_replicating_quine_pot",
        },
        **deal_book_info,
    }


def covenant_multi_round_negotiate(
    *,
    owner_id: str = "agent_vida",
    agent_id: str,
    offers: list[dict[str, Any]],
    counterparty_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Multi-round negotiation using the full Negotiator session.

    offers: ordered list of offer dicts, each with:
      - max_kas_per_tx, max_kas_per_day, optional: allowed_destinations, duration_hours
      - party: "owner" or "agent"
      - note: optional round note

    Returns final deal with audit log, or escalation/error info.
    """
    from vida.plugins.covenant.negotiation import Negotiator, UserControls, NegotiationError
    neg = Negotiator(owner_id=owner_id, controls=UserControls.defaults())
    session = neg.start_session(agent_id=agent_id)

    for i, offer in enumerate(offers):
        offer_tx = float(offer.get("max_kas_per_tx", 0))
        offer_day = float(offer.get("max_kas_per_day", 0))
        offer_dests = list(offer.get("allowed_destinations") or [])
        offer_hours = float(offer.get("duration_hours", 24.0))
        party = offer.get("party", "agent")
        note = offer.get("note", f"Round {i+1}")

        if i == 0:
            # First offer starts the session
            session.make_offer(
                max_kas_per_tx=offer_tx,
                max_kas_per_day=offer_day,
                allowed_destinations=offer_dests,
                duration_hours=offer_hours,
                note=note,
                is_first_deal=(counterparty_id is not None and neg.book.is_first_deal(counterparty_id)),
            )
        else:
            try:
                session.counter_offer(
                    max_kas_per_tx=offer_tx,
                    max_kas_per_day=offer_day,
                    allowed_destinations=offer_dests,
                    duration_hours=offer_hours,
                    party=party,
                    note=note,
                )
            except NegotiationError as e:
                return {
                    "ok": False,
                    "error": str(e),
                    "round": i + 1,
                    "audit_log": session.audit_log(),
                    "phase": session.phase.value,
                }

    # Check escalation
    if session.phase.value == "escalated":
        return {
            "ok": False,
            "escalated": True,
            "audit_log": session.audit_log(),
            "phase": "escalated",
            "message": "Deal requires human approval",
        }

    # Accept
    final = session.accept(party="owner")
    if counterparty_id:
        neg.book.record_deal(
            counterparty_id=counterparty_id,
            terms=final.terms,
            session_id=session.session_id,
        )

    return {
        "ok": True,
        "session_id": session.session_id,
        "final_terms": {
            "max_kas_per_tx": final.terms.max_kas_per_tx,
            "max_kas_per_day": final.terms.max_kas_per_day,
            "allowed_destinations": final.terms.allowed_destinations,
            "duration_hours": final.terms.duration_hours,
        },
        "deal_hash": final.terms.deal_hash(),
        "rounds": len(session.rounds),
        "audit_log": session.audit_log(),
        "phase": session.phase.value,
    }


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
    "covenant_negotiate_terms": {
        "fn": covenant_negotiate_terms,
        "description": "Agent proposes covenant terms; owner policy constrains them. Supports quine strategy",
        "params": {
            "agent_offer": "dict",
            "owner_policy": "dict|None",
            "strategy": "str (covenant_bound_p2pk_pot|self_replicating_quine_pot)",
            "counterparty_id": "str|None",
        },
    },
    "covenant_multi_round_negotiate": {
        "fn": covenant_multi_round_negotiate,
        "description": "Multi-round negotiation with round limits, concession bounds, escalation, audit log",
        "params": {
            "owner_id": "str",
            "agent_id": "str",
            "offers": "list[dict]",
            "counterparty_id": "str|None",
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