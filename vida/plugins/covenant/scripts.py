"""
Offline covenant script helpers.

Honest limits:
- Compiles / describes shapes only when local tooling exists.
- Does NOT broadcast. Does NOT claim on-chain success.
- Live path needs post-Toccata client with computeBudget on the wire.
"""

from __future__ import annotations

from typing import Any, Optional


# Timelock-style sketch (documentation / tests only — not a full assembler)
OP_CHECKLOCKTIMEVERIFY_NOTE = (
    "CLTV + Schnorr check is the common TN10 covenant shape (see kascov)."
)


def describe_compute_budget_rules() -> dict[str, Any]:
    """Document the budget rules from rusty-kaspa #1073 discussion."""
    return {
        "field": "computeBudget",
        "when": "v1 / post-Toccata inputs; set BEFORE signing (part of sighash)",
        "recommended_per_signing_input": "10-20",
        "why_not_65535": "committed budget costs compute mass/fee even if unused",
        "schnorr_script_units_approx": 100_000,
        "free_allowance_if_budget_zero": 9_999,
        "sdk_trap": "pre-Toccata kaspa/wasm drop computeBudget on serialize → limit=9999",
        "fix_pr": "https://github.com/kaspanet/rusty-kaspa/pull/1074",
        "issue": "https://github.com/kaspanet/rusty-kaspa/issues/1073",
        "reference": "https://github.com/Knitser/kascov",
    }


def offline_validate_budget(budget: int, *, signing_inputs: int = 1) -> dict[str, Any]:
    """Pure validation helper for planned v1 inputs."""
    if signing_inputs < 1:
        return {"ok": False, "error": "signing_inputs must be >= 1"}
    if budget < 10:
        return {
            "ok": False,
            "error": "budget < 10 likely fails one Schnorr CheckSig (need ~100000 units)",
            "recommended": 10,
        }
    if budget > 20:
        return {
            "ok": True,
            "warning": "budget > 20 increases fee/mass; prefer 10-20 unless you measured",
            "budget": budget,
            "signing_inputs": signing_inputs,
        }
    return {"ok": True, "budget": budget, "signing_inputs": signing_inputs}


def compile_placeholder_timelock_meta(
    *,
    lock_blocks: int,
    note: Optional[str] = None,
) -> dict[str, Any]:
    """
    Metadata-only stub for a future real assembler.

    Returns design intent, not bytecode guaranteed to match consensus.
    """
    if lock_blocks < 0:
        return {"ok": False, "error": "lock_blocks must be >= 0"}
    return {
        "ok": True,
        "kind": "timelock_sketch",
        "lock_blocks": lock_blocks,
        "note": note or OP_CHECKLOCKTIMEVERIFY_NOTE,
        "bytecode_hex": None,
        "live_ready": False,
        "reason": "assembler + post-Toccata SDK not wired in this scaffold",
    }
