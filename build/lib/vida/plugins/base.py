"""Plugin protocol and context (no chain secrets in agent scope)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from .policy import PolicyDecision, PolicyRequest, evaluate_policy


@dataclass
class VidaPluginContext:
    """
    What a plugin may see when acting for an owner/session.

    Never includes seed, password, or long-term private keys.
    Chain plugins receive handles/ids and request signing via core later.
    """

    wallet_id: str
    network: str = "mainnet"
    session_id: Optional[str] = None
    mode: str = "COMMAND"  # FULL | HYBRID | COMMAND
    threshold: float = 0.0
    max_per_tx: float = 0.0
    daily_limit: float = 0.0
    daily_spent: float = 0.0
    allowed_actions: Optional[list[str]] = None
    allowed_subnets: Optional[list[int]] = None
    session_revoked: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def decide(self, request: PolicyRequest) -> PolicyDecision:
        return evaluate_policy(
            mode=self.mode,
            amount=request.amount,
            threshold=self.threshold,
            max_per_tx=self.max_per_tx,
            daily_limit=self.daily_limit,
            daily_spent=self.daily_spent,
            allowed_actions=self.allowed_actions,
            action=request.action,
        )


@runtime_checkable
class VidaPlugin(Protocol):
    """Minimum surface every Vida chain/feature plugin implements."""

    name: str
    chain: str
    capabilities: list[str]

    def describe(self) -> dict[str, Any]:
        """Public metadata for registry / Hermes."""
        ...

    def status(self, ctx: VidaPluginContext) -> dict[str, Any]:
        """Read-only chain/plugin status."""
        ...
