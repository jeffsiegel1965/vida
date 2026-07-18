"""
Agent working-pot design helpers (offline).

Maps soft session caps → how much to fund into covenant-constrained UTXOs
when the live path is available. No broadcast.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence


SOMPI_PER_KAS = 100_000_000


def plan_agent_pot(
    *,
    max_kas_per_tx: float,
    max_kas_per_day: float,
    allowed_destinations: Optional[Sequence[str]] = None,
    session_hours: float = 8.0,
    fee_buffer_kas: float = 0.05,
    strategy: str = "covenant_bound_p2pk_pot",
    quine_generations: int = 0,
    auto_renew: bool = False,
) -> dict[str, Any]:
    """
    Recommend pot funding and hard-rule targets for agent working balance.

    Hybrid model (see AGENT_HARD_CAP_DESIGN.md):
    - Fund pot ≈ max_kas_per_day + fees (on-chain can't easily do UTC daily).
    - Hard max_tx + dest allowlist are the primary covenant targets.
    """
    if max_kas_per_tx <= 0 or max_kas_per_day <= 0:
        return {
            "ok": False,
            "error": "max_kas_per_tx and max_kas_per_day must be positive",
        }
    if session_hours <= 0:
        return {"ok": False, "error": "session_hours must be positive"}
    if fee_buffer_kas < 0:
        return {"ok": False, "error": "fee_buffer_kas must be >= 0"}

    dests = list(allowed_destinations or [])
    fund_kas = float(max_kas_per_day) + float(fee_buffer_kas)
    # Don't fund more than ~day * tx ceiling without explicit larger pot
    if max_kas_per_tx > max_kas_per_day:
        note_tx = "max_tx > max_day — pot still sized by max_day; per-tx hard cap should be max_tx"
    else:
        note_tx = "per-tx hard cap <= daily pot size"

    return {
        "ok": True,
        "model": "hybrid_soft_daily_hard_tx_dest",
        "fund_pot_kas": fund_kas,
        "fund_pot_sompi": int(round(fund_kas * SOMPI_PER_KAS)),
        "hard_rules": {
            "max_kas_per_tx": float(max_kas_per_tx),
            "allowed_destinations": dests,
            "require_dest_allowlist": len(dests) > 0,
        },
        "soft_rules": {
            "max_kas_per_day": float(max_kas_per_day),
            "session_hours": float(session_hours),
            "enforcement": "vida_session_policy",
        },
        "notes": [
            note_tx,
            "Daily calendar reset stays soft until epoch-pot design; fund only one day at a time.",
            "Never fund vault/life savings into the agent pot.",
            "On-chain hard caps need post-Toccata client (see TN10 micro-proof).",
        ],
        "live_ready": False,
        "reference_proof": "docs/proofs/covenant_tn10_microproof.md",
        "design_doc": "docs/plugins/covenant/AGENT_HARD_CAP_DESIGN.md",
    }


def validate_agent_pot_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Sanity-check a plan dict (from plan_agent_pot or hand-built)."""
    if not plan.get("ok"):
        return {"ok": False, "error": plan.get("error") or "plan not ok"}
    fund = float(plan.get("fund_pot_kas") or 0)
    hard = plan.get("hard_rules") or {}
    max_tx = float(hard.get("max_kas_per_tx") or 0)
    if fund <= 0 or max_tx <= 0:
        return {"ok": False, "error": "fund_pot_kas and max_kas_per_tx must be positive"}
    dests = hard.get("allowed_destinations")
    if hard.get("require_dest_allowlist") and not dests:
        return {"ok": False, "error": "require_dest_allowlist set but destinations empty"}
    return {"ok": True, "fund_pot_kas": fund, "max_kas_per_tx": max_tx}
