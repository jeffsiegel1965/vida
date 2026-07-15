"""TAO stake action policy helpers (Phase 1B)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..policy import PolicyDecision, PolicyRequest, evaluate_policy


@dataclass
class StakeRequest:
    action: str  # delegate | undelegate
    amount_tao: float
    netuid: int
    hotkey: str = ""  # validator hotkey ss58 when required
    confirm: bool = False


def evaluate_stake(
    *,
    mode: str,
    amount: float,
    action: str,
    netuid: int,
    threshold: float = 0.0,
    max_per_tx: float = 0.0,
    daily_limit: float = 0.0,
    daily_spent: float = 0.0,
    allowed_actions: Optional[list[str]] = None,
    allowed_subnets: Optional[list[int]] = None,
    session_revoked: bool = False,
    confirm: bool = False,
) -> PolicyDecision:
    """
    Policy for stake actions.

    confirm=True is required for any successful auto path in tools (Hermes),
    but policy itself still enforces mode/caps/subnets.
    COMMAND always needs_approval even if confirm is True (owner path may set mode FULL).
    """
    if session_revoked:
        return PolicyDecision(False, "session revoked", False)

    if allowed_subnets is not None and netuid not in allowed_subnets:
        return PolicyDecision(
            False, f"netuid {netuid} not in allowed_subnets {allowed_subnets}", False
        )

    actions = allowed_actions
    if actions is None:
        # default stake allowlist when not specified
        actions = ["delegate", "undelegate"]

    return evaluate_policy(
        mode=mode,
        amount=amount,
        threshold=threshold,
        max_per_tx=max_per_tx,
        daily_limit=daily_limit,
        daily_spent=daily_spent,
        allowed_actions=actions,
        action=action,
    )


@dataclass
class SpendTracker:
    """Simple in-process daily spend tracker for tests / single process."""

    daily_spent: float = 0.0
    day: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)

    def _roll(self) -> None:
        import time

        today = time.strftime("%Y-%m-%d")
        if self.day != today:
            self.day = today
            self.daily_spent = 0.0

    def add(self, amount: float, meta: Optional[dict[str, Any]] = None) -> None:
        self._roll()
        self.daily_spent += float(amount)
        self.history.append({"amount": amount, "meta": meta or {}})
