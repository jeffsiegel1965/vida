"""Chain-agnostic policy decisions for plugin actions."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PolicyRequest:
    """What a plugin wants to do on behalf of a session/owner."""

    chain: str
    action: str  # e.g. status, transfer, delegate, undelegate
    amount: float = 0.0
    destination: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    needs_approval: bool = False


def evaluate_policy(
    *,
    mode: str,
    amount: float,
    threshold: float = 0.0,
    max_per_tx: float = 0.0,
    daily_limit: float = 0.0,
    daily_spent: float = 0.0,
    allowed_actions: Optional[list[str]] = None,
    action: str = "transfer",
) -> PolicyDecision:
    """
    Evaluate whether an automated agent action is allowed.

    mode: FULL | HYBRID | COMMAND (case-insensitive)
    max_per_tx / daily_limit: 0 means "no cap configured" for that dimension
    (COMMAND still always needs approval for non-read actions).
    """
    mode_u = (mode or "COMMAND").upper()
    action_l = (action or "").lower()

    # Read-only style actions are always fine
    if action_l in {"status", "describe", "list", "portfolio", "positions", "balance"}:
        return PolicyDecision(True, "read-only action", needs_approval=False)

    if not math.isfinite(amount) or amount < 0:
        return PolicyDecision(False, "amount must be finite and non-negative", False)

    if amount == 0:
        return PolicyDecision(False, "amount must be greater than zero", False)

    if allowed_actions is not None:
        allowed_norm = {a.lower() for a in allowed_actions}
        if action_l not in allowed_norm:
            return PolicyDecision(False, f"action '{action_l}' not in allowlist", False)

    if max_per_tx > 0 and amount > max_per_tx:
        return PolicyDecision(False, f"amount {amount} exceeds max_per_tx {max_per_tx}", False)

    if daily_limit > 0 and (daily_spent + amount) > daily_limit + 1e-12:
        return PolicyDecision(
            False,
            f"amount would exceed daily_limit {daily_limit} (spent {daily_spent})",
            False,
        )

    if mode_u == "COMMAND":
        return PolicyDecision(
            False,
            "COMMAND mode requires owner approval for every spend/action",
            needs_approval=True,
        )

    if mode_u == "HYBRID":
        if amount > threshold + 1e-12:
            return PolicyDecision(
                False,
                f"HYBRID: amount {amount} above threshold {threshold}",
                needs_approval=True,
            )
        return PolicyDecision(True, "HYBRID: within threshold and caps", False)

    if mode_u == "FULL":
        return PolicyDecision(True, "FULL: within configured caps", False)

    return PolicyDecision(False, f"unknown mode '{mode}'", needs_approval=True)
