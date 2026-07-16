"""
Agent pot hard-rule script *templates* (offline).

These are not consensus-validating SilverScript programs yet.
They define the policy object that:
  1) soft sessions enforce today
  2) future on-chain introspection will encode
  3) fund_agent_pot attaches as metadata / commitment hash
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional, Sequence

from .agent_pot import SOMPI_PER_KAS


TEMPLATE_VERSION = 1
STRATEGY_MVP = "covenant_bound_p2pk_pot"  # lineage + off-chain policy hash
STRATEGY_KIP17 = "kip17_max_tx_dest"  # future: true hard max_tx + dest


def build_agent_pot_script_template(
    *,
    max_kas_per_tx: float,
    max_kas_per_day: float,
    allowed_destinations: Sequence[str],
    owner_address: Optional[str] = None,
    strategy: str = STRATEGY_MVP,
) -> dict[str, Any]:
    """
    Build a versioned pot policy template.

    MVP strategy: fund a covenant-bound P2PK pot; max_tx + dest enforced by
    Vida soft policy (+ optional future script). KIP17 strategy is documented
    but not live-ready.
    """
    if max_kas_per_tx <= 0 or max_kas_per_day <= 0:
        return {"ok": False, "error": "max_kas_per_tx and max_kas_per_day must be positive"}
    dests = [d.strip() for d in allowed_destinations if d and str(d).strip()]
    if strategy == STRATEGY_KIP17 and not dests:
        return {
            "ok": False,
            "error": "kip17 strategy requires non-empty allowed_destinations",
        }

    max_tx_sompi = int(round(max_kas_per_tx * SOMPI_PER_KAS))
    max_day_sompi = int(round(max_kas_per_day * SOMPI_PER_KAS))
    pot_sompi = max_day_sompi + int(0.05 * SOMPI_PER_KAS)

    policy = {
        "vida_pot_policy": TEMPLATE_VERSION,
        "strategy": strategy,
        "max_tx_sompi": max_tx_sompi,
        "max_day_sompi": max_day_sompi,
        "allowed_destinations": dests,
        "owner_address": owner_address,
        "require_dest_allowlist": len(dests) > 0,
    }
    # Stable JSON for commitment
    canonical = json.dumps(policy, sort_keys=True, separators=(",", ":"))
    policy_hash = hashlib.sha256(canonical.encode()).hexdigest()

    # Pseudocode / future opcodes — not executable bytecode
    pseudocode = [
        "// Vida agent pot policy v1 — TEMPLATE ONLY",
        f"// strategy: {strategy}",
        f"// max_tx_sompi: {max_tx_sompi}",
        f"// max_day_sompi: {max_day_sompi} (soft / fund-size bound)",
        f"// dest_count: {len(dests)}",
        f"// policy_hash: {policy_hash}",
        "on_spend:",
        "  require covenant_binding continues OR burn_to_owner",
        "  if hard_max_tx:",
        f"    assert output_value_to_external <= {max_tx_sompi}",
        "  if dest_allowlist:",
        "    assert payment_dest in allowed_destinations",
        "  // KIP-17 introspection would encode the above on-chain",
    ]

    live_ready = False  # hard script not consensus-wired in Vida yet
    return {
        "ok": True,
        "template_version": TEMPLATE_VERSION,
        "strategy": strategy,
        "live_script_ready": live_ready,
        "policy": policy,
        "policy_hash": policy_hash,
        "canonical_json": canonical,
        "pot_fund_sompi": pot_sompi,
        "pot_fund_kas": pot_sompi / SOMPI_PER_KAS,
        "pseudocode": "\n".join(pseudocode),
        "on_chain_today": {
            "covenant_lineage": True,
            "max_tx_enforced_by_chain": False,
            "dest_enforced_by_chain": False,
            "note": (
                "fund_agent_pot creates covenant-bound pot UTXO; "
                "max_tx/dest enforced by Vida session until KIP17 template ships"
            ),
        },
        "enforcement_now": {
            "soft_session": True,
            "covenant_pot_lineage": strategy == STRATEGY_MVP,
            "hard_script": False,
        },
    }


def verify_policy_hash(template: dict[str, Any]) -> bool:
    if not template.get("ok"):
        return False
    policy = template.get("policy")
    if not policy:
        return False
    canonical = json.dumps(policy, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest() == template.get("policy_hash")
