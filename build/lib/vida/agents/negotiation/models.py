"""Negotiation data models — the contracts agents negotiate over.

Simplified design based on commercial principles:
- 4 core parameters (not 9)
- 2 strategies (BOULWARE default, CONCEDE for trusted)
- Templates > custom negotiation
- Human escalation for large deals
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# ── Strategies ──


class ConcessionStrategy(Enum):
    """Negotiation concession strategy.

    BOULWARE: Start high, concede slowly. Default for unknown counterparties.
    CONCEDE:  Start fair, concede quickly. Use for trusted/repeat counterparties.
    """

    BOULWARE = "boulware"
    CONCEDE = "concede"


# ── Covenant Terms (the things being negotiated) ──


@dataclass
class CovenantTerms:
    """The terms of a covenant pot that an agent can negotiate.

    Simplified from 9 parameters to 4 essential ones.
    """

    max_kas_per_tx: float = 1.0  # KAS
    max_kas_per_day: float = 5.0  # KAS
    allowed_destinations: list[str] = field(default_factory=list)
    duration_hours: int = 720  # 30 days default

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CovenantTerms:
        return cls(
            max_kas_per_tx=float(d.get("max_kas_per_tx", 1.0)),
            max_kas_per_day=float(d.get("max_kas_per_day", 5.0)),
            allowed_destinations=list(d.get("allowed_destinations", [])),
            duration_hours=int(d.get("duration_hours", 720)),
        )


# ── Templates (take-it-or-leave-it offers) ──


TEMPLATES: dict[str, CovenantTerms] = {
    "micro": CovenantTerms(
        max_kas_per_tx=0.1,
        max_kas_per_day=0.5,
        duration_hours=168,  # 7 days
    ),
    "standard": CovenantTerms(
        max_kas_per_tx=1.0,
        max_kas_per_day=5.0,
        duration_hours=720,  # 30 days
    ),
    "power": CovenantTerms(
        max_kas_per_tx=10.0,
        max_kas_per_day=50.0,
        duration_hours=2160,  # 90 days
    ),
}


def apply_template(name: str, destinations: Optional[list[str]] = None) -> CovenantTerms:
    """Apply a named template, optionally adding destinations."""
    if name not in TEMPLATES:
        name = "standard"
    terms = TEMPLATES[name]
    if destinations:
        terms.allowed_destinations = destinations
    return terms


# ── Negotiation Session State ──


@dataclass
class NegotiationRound:
    """A single round of offers in a negotiation session."""

    round_number: int
    proposer: str  # "us" or "them"
    terms: CovenantTerms
    accepted: bool = False
    message: str = ""
    timestamp: float = field(default_factory=time.time)


# ── Outcomes (for memory/learning) ──


@dataclass
class NegotiationOutcome:
    """Record of a completed negotiation."""

    counterparty_id: str
    strategy_used: ConcessionStrategy
    rounds_to_deal: int
    final_terms: CovenantTerms
    pot_funded: bool
    pot_sompi: int = 0
    fee_paid_kas: float = 0.0
    template_used: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["strategy_used"] = self.strategy_used.value
        d["final_terms"] = self.final_terms.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NegotiationOutcome:
        return cls(
            counterparty_id=d["counterparty_id"],
            strategy_used=ConcessionStrategy(d.get("strategy_used", "boulware")),
            rounds_to_deal=d.get("rounds_to_deal", 0),
            final_terms=CovenantTerms.from_dict(d.get("final_terms", {})),
            pot_funded=d.get("pot_funded", False),
            pot_sompi=d.get("pot_sompi", 0),
            fee_paid_kas=d.get("fee_paid_kas", 0.0),
            template_used=d.get("template_used", ""),
            timestamp=d.get("timestamp", time.time()),
        )


# ── Counterparty Profile (learning) ──


@dataclass
class CounterpartyProfile:
    """Learned profile for a counterparty agent."""

    agent_id: str
    deal_count: int = 0
    total_pot_kas: float = 0.0
    avg_rounds_to_deal: float = 0.0
    preferred_strategy: ConcessionStrategy = ConcessionStrategy.BOULWARE
    last_interaction: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "deal_count": self.deal_count,
            "total_pot_kas": self.total_pot_kas,
            "avg_rounds_to_deal": self.avg_rounds_to_deal,
            "preferred_strategy": self.preferred_strategy.value,
            "last_interaction": self.last_interaction,
        }


# ── Negotiation Memory (persistent learning) ──


class NegotiationMemory:
    """Persistent learning engine for negotiation strategies.

    Stores outcomes and counterparty profiles in JSON files.
    Supports volume discounts based on total deal history.
    """

    DISCOUNT_TIERS = [
        (0, 0.0),  # 0% discount for < 100 KAS
        (100, 0.10),  # 10% for 100-1000 KAS
        (1000, 0.20),  # 20% for 1000-10000 KAS
        (10000, 0.30),  # 30% for 10000+ KAS
    ]

    def __init__(self, storage_path: str = ""):
        if not storage_path:
            storage_path = str(Path.home() / ".vida" / "negotiation_memory.json")
        self._path = Path(storage_path)
        self._outcomes: list[NegotiationOutcome] = []
        self._profiles: dict[str, CounterpartyProfile] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                self._outcomes = [NegotiationOutcome.from_dict(o) for o in data.get("outcomes", [])]
                for k, v in data.get("profiles", {}).items():
                    self._profiles[k] = CounterpartyProfile(
                        agent_id=v["agent_id"],
                        deal_count=v.get("deal_count", 0),
                        total_pot_kas=v.get("total_pot_kas", 0.0),
                        avg_rounds_to_deal=v.get("avg_rounds_to_deal", 0.0),
                        preferred_strategy=ConcessionStrategy(v.get("preferred_strategy", "boulware")),
                        last_interaction=v.get("last_interaction", 0.0),
                    )
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "outcomes": [o.to_dict() for o in self._outcomes],
            "profiles": {k: v.to_dict() for k, v in self._profiles.items()},
        }
        self._path.write_text(json.dumps(data, indent=2))

    def record(self, outcome: NegotiationOutcome) -> None:
        """Record a completed negotiation outcome."""
        self._outcomes.append(outcome)

        # Update counterparty profile
        profile = self._profiles.get(outcome.counterparty_id, CounterpartyProfile(agent_id=outcome.counterparty_id))
        profile.deal_count += 1
        profile.total_pot_kas += outcome.pot_sompi / 100_000_000  # sompi → KAS
        profile.last_interaction = outcome.timestamp

        # Update rolling average
        old_total = profile.avg_rounds_to_deal * (profile.deal_count - 1)
        profile.avg_rounds_to_deal = (old_total + outcome.rounds_to_deal) / profile.deal_count

        # Update preferred strategy if we have enough data
        if profile.deal_count >= 3:
            profile.preferred_strategy = outcome.strategy_used

        self._profiles[outcome.counterparty_id] = profile
        self._save()

    def best_strategy_for(self, counterparty: str) -> ConcessionStrategy:
        """Get the best strategy for a counterparty based on history."""
        profile = self._profiles.get(counterparty)
        if profile and profile.deal_count >= 3:
            return profile.preferred_strategy
        return ConcessionStrategy.BOULWARE

    def get_profile(self, counterparty: str) -> Optional[CounterpartyProfile]:
        """Get profile for a specific counterparty."""
        return self._profiles.get(counterparty)

    def volume_discount(self, counterparty: str) -> float:
        """Get volume discount rate for a counterparty (0.0 to 0.3)."""
        profile = self._profiles.get(counterparty)
        if not profile:
            return 0.0

        total_kas = profile.total_pot_kas
        for threshold, discount in reversed(self.DISCOUNT_TIERS):
            if total_kas >= threshold:
                return discount
        return 0.0

    def stats(self) -> dict[str, Any]:
        """Get negotiation memory statistics."""
        return {
            "total_deals": len(self._outcomes),
            "unique_counterparties": len(self._profiles),
            "total_pot_kas": sum(p.total_pot_kas for p in self._profiles.values()),
            "avg_rounds_to_deal": (sum(o.rounds_to_deal for o in self._outcomes) / len(self._outcomes))
            if self._outcomes
            else 0,
        }
