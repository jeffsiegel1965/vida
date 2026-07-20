"""Verification ladder — replacing binary ok/not-ok with the 5-level system.

Levels:
  L1 — DETERMINISTIC: assertion, exit code, golden output
  L2 — RULE: schema validation, policy check
  L3 — FIELD_TRUTH: delayed confirmation from external source
  L4 — MODEL_JUDGE: model by rubric (flagged for financial ops)
  L5 — HUMAN_CHECKPOINT: human approval gate
"""

from __future__ import annotations

import functools
import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class VerificationLevel(IntEnum):
    """Five-level verification ladder from Macedo 2026."""

    DETERMINISTIC = 1  # L1: assertion, exit code, golden output
    RULE = 2  # L2: schema, policy check
    FIELD_TRUTH = 3  # L3: actual transaction confirmation
    MODEL_JUDGE = 4  # L4: model by rubric (flag if used for spend!)
    HUMAN_CHECKPOINT = 5  # L5: human approval gate


@dataclass
class VerifiedResult:
    """Result of a verified operation."""

    ok: bool
    level: VerificationLevel
    evidence: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    verified_at: float = field(default_factory=time.time)

    def is_autonomous(self) -> bool:
        return self.level <= VerificationLevel.RULE

    def is_financial(self) -> bool:
        return self.detail.get("financial", False)


# ── L1 verification functions ──


def verify_plan_output(result: dict[str, Any]) -> VerifiedResult:
    """L1 DETERMINISTIC verification: check tool output has expected shape.

    For financial operations, also checks for txid/extrinsic_hash evidence.
    """
    if not isinstance(result, dict):
        return VerifiedResult(ok=False, level=VerificationLevel.DETERMINISTIC, evidence="result is not a dict")
    ok = result.get("ok", False)
    evidence = []
    if ok:
        evidence.append("tool returned ok")
    else:
        evidence.append(result.get("error", "no error field"))

    # Financial operations must have txid (Kaspa) or extrinsic_hash (TAO)
    is_financial = result.get("_verification", {}).get("financial") or result.get("financial")
    txid = result.get("txid") or result.get("extrinsic_hash")
    if is_financial and ok and not txid:
        return VerifiedResult(
            ok=False,
            level=VerificationLevel.DETERMINISTIC,
            evidence="financial operation returned ok without txid or extrinsic_hash",
            detail=result,
        )
    if txid:
        evidence.append(f"txid={txid[:16]}...")

    return VerifiedResult(
        ok=ok,
        level=VerificationLevel.DETERMINISTIC,
        evidence="; ".join(evidence),
        detail=result,
    )


def verify_balance(balance_result: dict[str, Any]) -> VerifiedResult:
    """L1 DETERMINISTIC verification: balance must be a positive number."""
    balance = balance_result.get("balance_sompi", 0)
    ok = balance > 0
    return VerifiedResult(
        ok=ok,
        level=VerificationLevel.DETERMINISTIC,
        evidence=f"balance {balance} sompi" if ok else "zero or negative balance",
        detail=balance_result,
    )


# ── L2 verification functions ──


def verify_spend_policy(amount: float, max_tx: float, destination: str, allowlist: list[str]) -> VerifiedResult:
    """L2 RULE verification: check spend against session caps."""
    checks = []
    if amount > max_tx:
        checks.append(f"amount {amount} exceeds max_tx {max_tx}")
    if allowlist and destination not in allowlist:
        checks.append(f"destination {destination} not in allowlist")
    ok = len(checks) == 0
    return VerifiedResult(
        ok=ok,
        level=VerificationLevel.RULE,
        evidence="; ".join(checks) if checks else "all policy checks passed",
        detail={"max_tx": max_tx, "amount": amount, "financial": True},
    )


# ── L4 guard for financial operations ──


def enforce_no_l4_for_spend(verification: VerifiedResult) -> VerifiedResult:
    """Ensure a financial operation is never approved at L4 (model judge) alone."""
    if verification.is_financial() and verification.level == VerificationLevel.MODEL_JUDGE:
        return VerifiedResult(
            ok=False,
            level=VerificationLevel.MODEL_JUDGE,
            evidence="L4 model judge rejected for financial operation — requires L1 or L2",
            detail=verification.detail,
        )
    return verification


# ── Decorator: force L1 (or higher) on spend functions ──


def require_l1_spend(fn: Callable) -> Callable:
    """Decorator: enforce L1 verification on any financial operation.

    Usage:
        @require_l1_spend
        def send_kas(amount, destination):
            ...
            return {"ok": True, "txid": ...}

    If the result doesn't pass L1 deterministic checks, the spend is rejected.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> dict[str, Any]:
        result = fn(*args, **kwargs)
        if not isinstance(result, dict):
            return {"ok": False, "error": f"spend function must return dict, got {type(result)}"}
        if not result.get("ok"):
            return result  # Already failed — pass through

        # Verify the result passes L1 checks
        v = verify_plan_output(result)
        if v.ok:
            # Explicitly check for financial operations without txid or extrinsic_hash
            is_financial = result.get("_verification", {}).get("financial") or result.get("financial")
            txid = result.get("txid") or result.get("extrinsic_hash")
            if is_financial and not txid:
                return {"ok": False, "error": "financial operation returned ok without txid or extrinsic_hash"}

            result["_verification"] = {
                "level": "L1_DETERMINISTIC",
                "evidence": v.evidence,
            }
            return result

        # L1 failed — reject
        return {"ok": False, "error": f"spend rejected by L1 verification: {v.evidence}"}

    return wrapper
