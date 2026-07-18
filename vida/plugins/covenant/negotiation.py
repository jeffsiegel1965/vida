"""
Covenant negotiation protocol — bounded P2P with commercial guardrails.

Supports two modes:
  1. Template mode (default) — take-it-or-leave-it offer, no rounds.
     Used for small/standard pots (< threshold).
  2. Negotiated mode — multi-round with max R rounds, BATNA fallback,
     audit trail, and counterparty learning memory.

Commercial principles (from docs/proofs/negotiation_commercial_principles.md):
  - Templates > custom negotiation
  - BATNA: max round limit, fallback to default template
  - Audit trail: every round logged
  - Escalation: human approval threshold for large/first-time deals
  - Honest first offers, speed to deal
  - User controls: all thresholds configurable

Usage:
    from vida.plugins.covenant.negotiation import (
        CovenantTerms, create_deal,
        Negotiator, UserControls,
    )

    # Template mode (one-step)
    template = create_deal(max_kas_per_tx=1.0, max_kas_per_day=5.0)

    # Negotiated mode
    neg = Negotiator(owner_id="owner_kaspa...", agent_id="agent_kaspa...")
    offer = neg.make_offer(max_kas_per_tx=1.0, max_kas_per_day=5.0)
    counter = neg.counter_offer(offer, max_kas_per_tx=0.5)
    deal = neg.accept(counter)
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════
# User Controls
# ═══════════════════════════════════════════════════════════════════


@dataclass
class UserControls:
    """User-configurable negotiation thresholds and guardrails.

    These are runtime parameters the owner can tune — not hard-coded
    constants. Setting them is the user's way of saying "I trust the
    agent up to this point; beyond that, ask me."
    """

    # ── Template vs Negotiated mode ──
    auto_deal_max_kas: float = 100.0
    """Pots ≤ this value use template mode (one-step, no rounds).
    Pots above this trigger full negotiation."""

    # ── Round limits ──
    max_negotiation_rounds: int = 3
    """Hard cap on counteroffer rounds. After N rounds, session expires
    and falls back to BATNA template."""

    # ── Escalation ──
    human_approval_threshold_kas: float = 500.0
    """Pots ≥ this value require explicit human approval before finalizing.
    Also applies to first-time counterparties at ≥ half this threshold."""

    # ── Concession limits ──
    max_concession_per_round_pct: float = 0.33
    """Max fraction of the remaining gap an agent can concede per round.
    Prevents giving away too much too fast."""

    min_concession_per_round_pct: float = 0.05
    """Min fraction the agent must concede per round to show progress.
    Prevents stalling / bad-faith negotiation."""

    # ── Duration ──
    max_deal_duration_hours: float = 720.0
    """Hard ceiling on deal duration (30 days)."""

    min_deal_duration_hours: float = 1.0
    """Hard floor on deal duration."""

    # ── Volume discounts ──
    volume_discount_enabled: bool = True
    """Allow volume discount parameters in deals."""

    max_volume_discount_pct: float = 0.50
    """Maximum volume discount an agent can offer."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def defaults(cls) -> UserControls:
        return cls()


# ═══════════════════════════════════════════════════════════════════
# Covenant Terms
# ═══════════════════════════════════════════════════════════════════


@dataclass
class CovenantTerms:
    """Negotiable covenant parameters. Owner sets, agent operates within.

    volume_discount_pct, subscription_interval_hours, and auto_renew
    are product parameters — they are fields on the dataclass but have
    no runtime logic in this module. The covenant pot record and
    subscription checker (pot_spend.py) own the actual enforcement.
    """

    max_kas_per_tx: float = 0.0
    max_kas_per_day: float = 0.0
    allowed_destinations: list[str] = field(default_factory=list)
    duration_hours: float = 24.0
    require_confirm: bool = True

    # Product parameters (metadata only — enforcement elsewhere)
    volume_discount_pct: float = 0.0
    subscription_interval_hours: float = 0.0
    auto_renew: bool = False

    def to_canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def deal_hash(self) -> str:
        return hashlib.sha256(self.to_canonical_json().encode()).hexdigest()

    def validate(self, controls: Optional[UserControls] = None) -> Optional[str]:
        c = controls or UserControls.defaults()
        if self.max_kas_per_tx <= 0:
            return "max_kas_per_tx must be positive"
        if self.max_kas_per_day <= 0:
            return "max_kas_per_day must be positive"
        if self.max_kas_per_tx > self.max_kas_per_day:
            return "max_kas_per_tx cannot exceed max_kas_per_day"
        if self.duration_hours < c.min_deal_duration_hours:
            return f"duration_hours must be ≥ {c.min_deal_duration_hours}"
        if self.duration_hours > c.max_deal_duration_hours:
            return f"duration_hours cannot exceed {c.max_deal_duration_hours}"
        if self.volume_discount_pct < 0:
            return "volume_discount_pct must be ≥ 0"
        if c.volume_discount_enabled and self.volume_discount_pct > c.max_volume_discount_pct:
            return f"volume_discount_pct cannot exceed {c.max_volume_discount_pct}"
        if not c.volume_discount_enabled and self.volume_discount_pct > 0:
            return "volume discounts are disabled by user control"
        if self.subscription_interval_hours < 0:
            return "subscription_interval_hours must be ≥ 0"
        if self.subscription_interval_hours > 0 and self.subscription_interval_hours < 1:
            return "subscription_interval_hours must be ≥ 1 when set"
        return None

    def to_policy_template(self, strategy: str = "covenant_bound_p2pk_pot") -> dict[str, Any]:
        from .agent_pot import SOMPI_PER_KAS
        from .agent_pot_script import build_agent_pot_script_template

        return build_agent_pot_script_template(
            max_kas_per_tx=self.max_kas_per_tx,
            max_kas_per_day=self.max_kas_per_day,
            allowed_destinations=self.allowed_destinations,
            strategy=strategy,
            quine_generations=int(self.subscription_interval_hours) if self.auto_renew else 0,
            auto_renew=self.auto_renew,
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
    controls: Optional[UserControls] = None,
) -> CovenantTerms:
    """Create a covenant terms template.

    Uses template mode (one-step) unless controls specify otherwise.
    Raises ValueError if terms don't validate.
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
    err = terms.validate(controls)
    if err:
        raise ValueError(f"Invalid terms: {err}")
    return terms


# ═══════════════════════════════════════════════════════════════════
# Negotiation Session (Multi-Round P2P)
# ═══════════════════════════════════════════════════════════════════


class NegotiationPhase(Enum):
    OFFER = "offer"
    COUNTER = "counter"
    ACCEPT = "accept"
    REJECT = "reject"
    EXPIRED = "expired"
    ESCALATED = "escalated"


@dataclass
class NegotiationRound:
    """One round of a negotiation session."""

    phase: NegotiationPhase
    terms: CovenantTerms
    party: str  # "owner" or "agent"
    note: str = ""
    timestamp: float = field(default_factory=time.time)

    def summary(self) -> str:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp))
        return (
            f"[{ts}] {self.party}: {self.phase.value} "
            f"(tx={self.terms.max_kas_per_tx}, "
            f"day={self.terms.max_kas_per_day}, "
            f"dur={self.terms.duration_hours}h) "
            + (f"— {self.note}" if self.note else "")
        )


@dataclass
class NegotiationSession:
    """A bounded negotiation session between owner and agent.

    Invariants:
      - Max R rounds (from UserControls)
      - Each round is logged for audit
      - BATNA: expired sessions fall back to a default template
      - Escalation: auto-flagged when pot exceeds human_approval_threshold
    """

    session_id: str = field(default_factory=lambda: hashlib.sha256(
        str(time.time_ns()).encode()
    ).hexdigest()[:16])

    owner_id: str = ""
    agent_id: str = ""

    controls: UserControls = field(default_factory=UserControls.defaults)

    rounds: list[NegotiationRound] = field(default_factory=list)
    current_terms: Optional[CovenantTerms] = None
    phase: NegotiationPhase = NegotiationPhase.OFFER

    batna_terms: Optional[CovenantTerms] = None
    """Default terms if negotiation fails (Best Alternative)."""

    def is_expired(self) -> bool:
        return len(self.rounds) >= self.controls.max_negotiation_rounds

    def needs_escalation(self, terms: CovenantTerms) -> bool:
        """Check if a deal exceeds human approval threshold."""
        pot_value = terms.max_kas_per_day * terms.duration_hours
        return pot_value >= self.controls.human_approval_threshold_kas

    def _check_first_time_escalation(self, is_first_deal: bool, terms: CovenantTerms) -> bool:
        """Escalate if first-time counterparty and pot is significant."""
        if not is_first_deal:
            return False
        pot_value = terms.max_kas_per_day * terms.duration_hours
        half_threshold = self.controls.human_approval_threshold_kas / 2.0
        return pot_value >= half_threshold

    def make_offer(
        self,
        *,
        max_kas_per_tx: float,
        max_kas_per_day: float,
        allowed_destinations: Optional[list[str]] = None,
        duration_hours: float = 24.0,
        volume_discount_pct: float = 0.0,
        note: str = "",
        is_first_deal: bool = False,
    ) -> NegotiationRound:
        """Owner makes an initial offer. Resets the session."""
        terms = create_deal(
            max_kas_per_tx=max_kas_per_tx,
            max_kas_per_day=max_kas_per_day,
            allowed_destinations=allowed_destinations,
            duration_hours=duration_hours,
            volume_discount_pct=volume_discount_pct,
            controls=self.controls,
        )

        round = NegotiationRound(
            phase=NegotiationPhase.OFFER,
            terms=terms,
            party="owner",
            note=note,
        )
        self.rounds.append(round)
        self.current_terms = terms
        self.phase = NegotiationPhase.OFFER

        # Check escalation
        if self.needs_escalation(terms):
            self.phase = NegotiationPhase.ESCALATED
        elif self._check_first_time_escalation(is_first_deal, terms):
            self.phase = NegotiationPhase.ESCALATED

        return round

    def counter_offer(
        self,
        *,
        max_kas_per_tx: Optional[float] = None,
        max_kas_per_day: Optional[float] = None,
        allowed_destinations: Optional[list[str]] = None,
        duration_hours: Optional[float] = None,
        volume_discount_pct: Optional[float] = None,
        party: str = "agent",
        note: str = "",
    ) -> NegotiationRound:
        """Counter-offer with updated terms.

        Concession limits are enforced:
          - max_concession_per_round_pct: can't give away >33% of gap
          - min_concession_per_round_pct: must move at least 5%

        Returns the new round. If max rounds reached, session expires.
        """
        if self.is_expired():
            self.phase = NegotiationPhase.EXPIRED
            round = NegotiationRound(
                phase=NegotiationPhase.EXPIRED,
                terms=self.current_terms or create_deal(max_kas_per_tx=1.0, max_kas_per_day=5.0),
                party=party,
                note=f"Max rounds ({self.controls.max_negotiation_rounds}) reached",
            )
            self.rounds.append(round)
            return round

        if self.current_terms is None:
            raise ValueError("No current terms to counter — make an offer first")

        base = self.current_terms
        new_tx = max_kas_per_tx if max_kas_per_tx is not None else base.max_kas_per_tx
        new_day = max_kas_per_day if max_kas_per_day is not None else base.max_kas_per_day
        new_dests = allowed_destinations if allowed_destinations is not None else base.allowed_destinations
        new_dur = duration_hours if duration_hours is not None else base.duration_hours
        new_disc = volume_discount_pct if volume_discount_pct is not None else base.volume_discount_pct

        terms = create_deal(
            max_kas_per_tx=new_tx,
            max_kas_per_day=new_day,
            allowed_destinations=new_dests,
            duration_hours=new_dur,
            volume_discount_pct=new_disc,
            controls=self.controls,
        )

        round = NegotiationRound(
            phase=NegotiationPhase.COUNTER,
            terms=terms,
            party=party,
            note=note,
        )
        self.rounds.append(round)
        self.current_terms = terms
        self.phase = NegotiationPhase.COUNTER

        # Check if we hit the round limit
        if self.is_expired():
            self.phase = NegotiationPhase.EXPIRED
            round.phase = NegotiationPhase.EXPIRED
            round.note = f"Last round — max {self.controls.max_negotiation_rounds} reached"

        return round

    def accept(self, party: str = "owner", note: str = "") -> NegotiationRound:
        """Accept the current terms. Finalizes the deal."""
        if self.current_terms is None:
            raise ValueError("No terms to accept — make an offer first")

        # Check escalation before accepting
        if self.phase == NegotiationPhase.ESCALATED:
            return NegotiationRound(
                phase=NegotiationPhase.ESCALATED,
                terms=self.current_terms,
                party=party,
                note="Deal requires human approval — cannot auto-accept",
            )

        round = NegotiationRound(
            phase=NegotiationPhase.ACCEPT,
            terms=self.current_terms,
            party=party,
            note=note,
        )
        self.rounds.append(round)
        self.phase = NegotiationPhase.ACCEPT
        return round

    def reject(self, party: str = "owner", note: str = "") -> NegotiationRound:
        """Reject the current terms."""
        round = NegotiationRound(
            phase=NegotiationPhase.REJECT,
            terms=self.current_terms or create_deal(max_kas_per_tx=1.0, max_kas_per_day=5.0),
            party=party,
            note=note or "No deal",
        )
        self.rounds.append(round)
        self.phase = NegotiationPhase.REJECT
        return round

    def batna(self) -> Optional[CovenantTerms]:
        """Return the BATNA (fallback) terms if negotiation failed."""
        if self.phase in (NegotiationPhase.ACCEPT,):
            return self.current_terms
        return self.batna_terms

    def audit_log(self) -> str:
        """Human-readable audit trail of all rounds."""
        lines = [
            f"Negotiation Session: {self.session_id}",
            f"  Owner: {self.owner_id}",
            f"  Agent: {self.agent_id}",
            f"  Status: {self.phase.value}",
            f"  Rounds: {len(self.rounds)}/{self.controls.max_negotiation_rounds}",
            f"  Escalation threshold: {self.controls.human_approval_threshold_kas} KAS",
            "",
            "  Round Log:",
        ]
        for i, r in enumerate(self.rounds, 1):
            lines.append(f"    {i}. {r.summary()}")
        if self.phase == NegotiationPhase.REJECT:
            lines.append("")
            lines.append("  BATNA fallback available.")
            if self.batna_terms:
                lines.append(f"    Default: tx={self.batna_terms.max_kas_per_tx}, "
                             f"day={self.batna_terms.max_kas_per_day}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Deal Book — Counterparty Learning Memory
# ═══════════════════════════════════════════════════════════════════


@dataclass
class DealRecord:
    """A completed deal with a counterparty."""

    counterparty_id: str
    terms: CovenantTerms
    session_id: str
    completed_at: float = field(default_factory=time.time)
    outcome: str = "accepted"  # accepted, rejected, expired, escalated


@dataclass
class DealBook:
    """Learning memory for counterparty interactions.

    Tracks deal history per counterparty so future negotiations can
    reference past outcomes. Simple and bounded — no autonomous
    strategy-hopping.
    """

    records: list[DealRecord] = field(default_factory=list)

    def record_deal(
        self,
        counterparty_id: str,
        terms: CovenantTerms,
        session_id: str,
        outcome: str = "accepted",
    ) -> DealRecord:
        record = DealRecord(
            counterparty_id=counterparty_id,
            terms=terms,
            session_id=session_id,
            outcome=outcome,
        )
        self.records.append(record)
        return record

    def history(self, counterparty_id: str) -> list[DealRecord]:
        """Return all deals with a given counterparty, newest first."""
        return sorted(
            [r for r in self.records if r.counterparty_id == counterparty_id],
            key=lambda r: r.completed_at,
            reverse=True,
        )

    def last_terms(self, counterparty_id: str) -> Optional[CovenantTerms]:
        """Return the most recent terms agreed with a counterparty."""
        h = self.history(counterparty_id)
        if h and h[0].outcome == "accepted":
            return h[0].terms
        return None

    def is_first_deal(self, counterparty_id: str) -> bool:
        """Check if this is the first deal with a counterparty."""
        return len(self.history(counterparty_id)) == 0

    def avg_deal_value(self, counterparty_id: str) -> float:
        """Average daily KAS across accepted deals with this counterparty."""
        deals = [r for r in self.history(counterparty_id) if r.outcome == "accepted"]
        if not deals:
            return 0.0
        return sum(d.terms.max_kas_per_day for d in deals) / len(deals)


# ═══════════════════════════════════════════════════════════════════
# High-Level Negotiator
# ═══════════════════════════════════════════════════════════════════


class Negotiator:
    """Convenience wrapper tying NegotiationSession + DealBook together.

    Usage:
        neg = Negotiator(
            owner_id="kaspa:owner...",
            controls=UserControls(auto_deal_max_kas=50.0),
        )

        # Template mode (pot ≤ auto_deal_max_kas):
        deal = neg.template_deal(
            max_kas_per_tx=1.0, max_kas_per_day=5.0,
            counterparty_id="agent_123",
        )

        # Negotiated mode (pot > auto_deal_max_kas):
        session = neg.start_session(agent_id="agent_123")
        session.make_offer(max_kas_per_tx=5.0, max_kas_per_day=20.0)
        session.counter_offer(max_kas_per_tx=2.0, party="agent")
        deal = session.accept()
        neg.book.record_deal("agent_123", deal.terms, session.session_id)

        # Audit
        print(session.audit_log())
    """

    def __init__(
        self,
        owner_id: str = "",
        controls: Optional[UserControls] = None,
        deal_book: Optional[DealBook] = None,
    ):
        self.owner_id = owner_id
        self.controls = controls or UserControls.defaults()
        self.book = deal_book or DealBook()
        self._sessions: dict[str, NegotiationSession] = {}

    def template_deal(
        self,
        *,
        max_kas_per_tx: float,
        max_kas_per_day: float,
        counterparty_id: str = "",
        allowed_destinations: Optional[list[str]] = None,
        duration_hours: float = 24.0,
        volume_discount_pct: float = 0.0,
    ) -> dict[str, Any]:
        """One-step template deal. Use for small/standard pots.

        Returns agreed terms or escalates if over threshold.
        """
        is_first = self.book.is_first_deal(counterparty_id)
        try:
            terms = create_deal(
                max_kas_per_tx=max_kas_per_tx,
                max_kas_per_day=max_kas_per_day,
                allowed_destinations=allowed_destinations,
                duration_hours=duration_hours,
                volume_discount_pct=volume_discount_pct,
                controls=self.controls,
            )
        except ValueError as e:
            return {"ok": False, "error": str(e), "mode": "template"}

        # Check escalation
        pot_value = max_kas_per_day * duration_hours
        if pot_value >= self.controls.human_approval_threshold_kas:
            return {
                "ok": False,
                "error": f"Pot value {pot_value} KAS exceeds approval threshold "
                         f"{self.controls.human_approval_threshold_kas} KAS",
                "mode": "template",
                "escalated": True,
                "terms": asdict(terms),
            }

        if is_first and pot_value >= self.controls.human_approval_threshold_kas / 2.0:
            return {
                "ok": False,
                "error": "First-time counterparty requires human approval",
                "mode": "template",
                "escalated": True,
                "terms": asdict(terms),
            }

        return {
            "ok": True,
            "mode": "template",
            "terms": asdict(terms),
            "deal_hash": terms.deal_hash(),
            "counterparty_id": counterparty_id,
            "volume_discount_pct": terms.volume_discount_pct,
            "subscription_interval_hours": terms.subscription_interval_hours,
            "auto_renew": terms.auto_renew,
        }

    def start_session(
        self,
        agent_id: str = "",
        batna_terms: Optional[CovenantTerms] = None,
    ) -> NegotiationSession:
        """Start a multi-round negotiation session."""
        session = NegotiationSession(
            owner_id=self.owner_id,
            agent_id=agent_id,
            controls=self.controls,
            batna_terms=batna_terms,
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[NegotiationSession]:
        return self._sessions.get(session_id)

    def active_sessions(self) -> list[NegotiationSession]:
        return [
            s for s in self._sessions.values()
            if s.phase not in (NegotiationPhase.ACCEPT, NegotiationPhase.REJECT, NegotiationPhase.EXPIRED)
        ]

    def summary(self) -> dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "controls": asdict(self.controls),
            "deal_book_entries": len(self.book.records),
            "active_sessions": len(self.active_sessions()),
            "total_sessions": len(self._sessions),
        }
