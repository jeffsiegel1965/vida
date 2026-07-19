"""Verification ladder — replacing binary ok/not-ok with the 5-level system from arXiv:2607.00038.

Levels:
  L1 — DETERMINISTIC: assertion, exit code, golden output
  L2 — RULE: schema validation, policy check
  L3 — FIELD_TRUTH: delayed confirmation from external source
  L4 — MODEL_JUDGE: model by rubric (flagged for financial ops)
  L5 — HUMAN_CHECKPOINT: human approval gate
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


class VerificationLevel(IntEnum):
    """Five-level verification ladder from Macedo 2026."""
    DETERMINISTIC = 1    # L1: assertion, exit code, golden output
    RULE = 2             # L2: schema, policy check
    FIELD_TRUTH = 3      # L3: actual transaction confirmation
    MODEL_JUDGE = 4      # L4: model by rubric (flag if used for spend!)
    HUMAN_CHECKPOINT = 5 # L5: human approval gate


@dataclass
class VerifiedResult:
    """Result of a verified operation."""
    ok: bool
    level: VerificationLevel
    evidence: str = ""  # how we know it's true
    detail: dict[str, Any] = field(default_factory=dict)
    verified_at: float = field(default_factory=time.time)

    def is_autonomous(self) -> bool:
        """Can this level run without human intervention?"""
        return self.level <= VerificationLevel.RULE

    def is_financial(self) -> bool:
        """Was this a financial operation? If so, L4 is not acceptable."""
        return self.detail.get("financial", False)


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


def verify_plan_output(result: dict[str, Any]) -> VerifiedResult:
    """L1 DETERMINISTIC verification: check tool output has expected shape."""
    if not isinstance(result, dict):
        return VerifiedResult(ok=False, level=VerificationLevel.DETERMINISTIC, evidence="result is not a dict")
    ok = result.get("ok", False)
    return VerifiedResult(
        ok=ok,
        level=VerificationLevel.DETERMINISTIC,
        evidence="tool returned ok" if ok else result.get("error", "no error field"),
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
