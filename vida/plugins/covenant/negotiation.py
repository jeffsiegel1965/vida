"""
Owner-to-agent covenant terms template.

NOT a P2P negotiation protocol. The owner defines terms, the agent
operates within them. No rounds, no concession strategies, no
counterparties. P2P negotiation is deferred to v2.

Simple flow:
    owner sets caps → template created with deterministic deal_hash
    → agent operates inside caps → done

Usage:
    from vida.plugins.covenant.negotiation import CovenantTerms, create_deal

    template = create_deal(
        max_kas_per_tx=1.0, max_kas_per_day=5.0,
        allowed_destinations=["kaspa:..."],
    )
    # template.deal_hash  # deterministic SHA-256
    # template.to_policy_template()  # for covenant pot binding
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class CovenantTerms:
    """Negotiable covenant parameters. Owner sets, agent operates within."""

    max_kas_per_tx: float = 0.0
    max_kas_per_day: float = 0.0
    allowed_destinations: list[str] = field(default_factory=list)
    duration_hours: float = 24.0
    require_confirm: bool = True
    volume_discount_pct: float = 0.0
    subscription_interval_hours: float = 0.0
    auto_renew: bool = False

    def to_canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def deal_hash(self) -> str:
        return hashlib.sha256(self.to_canonical_json().encode()).hexdigest()

    def validate(self) -> Optional[str]:
        if self.max_kas_per_tx <= 0:
            return "max_kas_per_tx must be positive"
        if self.max_kas_per_day <= 0:
            return "max_kas_per_day must be positive"
        if self.max_kas_per_tx > self.max_kas_per_day:
            return "max_kas_per_tx cannot exceed max_kas_per_day"
        if self.duration_hours <= 0:
            return "duration_hours must be positive"
        if self.duration_hours > 720:
            return "duration_hours cannot exceed 720 (30 days)"
        if self.volume_discount_pct < 0 or self.volume_discount_pct > 0.5:
            return "volume_discount_pct must be between 0 and 0.5 (50%)"
        if self.subscription_interval_hours < 0:
            return "subscription_interval_hours must be >= 0"
        if self.subscription_interval_hours > 0 and self.subscription_interval_hours < 1:
            return "subscription_interval_hours must be >= 1 when set"
        return None

    def to_policy_template(self) -> dict[str, Any]:
        from .agent_pot import SOMPI_PER_KAS
        from .agent_pot_script import build_agent_pot_script_template

        return build_agent_pot_script_template(
            max_kas_per_tx=self.max_kas_per_tx,
            max_kas_per_day=self.max_kas_per_day,
            allowed_destinations=self.allowed_destinations,
        )


def create_deal(
    *,
    max_kas_per_tx: float,
    max_kas_per_day: float,
    allowed_destinations: Optional[list[str]] = None,
    duration_hours: float = 24.0,
    volume_discount_pct: float = 0.0,
    subscription_interval_hours: float = 0.0,
    auto_renew: bool = False,
) -> CovenantTerms:
    """Create a covenant terms template from owner-defined caps.

    Returns a CovenantTerms with a deterministic deal_hash.
    Simple one-step creation — no rounds, no counteroffers.
    P2P negotiation is deferred to v2.

    volume_discount_pct: fee discount for high-volume pots (0.0–0.5)
    subscription_interval_hours: auto-refill interval (0 = one-time)
    auto_renew: auto-renew covenant on expiry
    """
    terms = CovenantTerms(
        max_kas_per_tx=max_kas_per_tx,
        max_kas_per_day=max_kas_per_day,
        allowed_destinations=allowed_destinations or [],
        duration_hours=duration_hours,
        volume_discount_pct=volume_discount_pct,
        subscription_interval_hours=subscription_interval_hours,
        auto_renew=auto_renew,
    )
    err = terms.validate()
    if err:
        raise ValueError(f"Invalid terms: {err}")
    return terms
