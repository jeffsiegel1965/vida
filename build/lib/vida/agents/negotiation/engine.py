"""Negotiation engine — session management, concession strategies, and deal flow.

An agent initiates a negotiation session, makes offers, and the counterparty
responds. The engine tracks rounds, applies strategy, and produces a final
agreement or expiration.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from .models import (
    ConcessionStrategy,
    CovenantTerms,
    NegotiationMemory,
    NegotiationOutcome,
    NegotiationRound,
    apply_template,
)

# ── Configuration ──

MAX_ROUNDS = 10  # Max offer/counter-offer rounds
HUMAN_ESCALATION_KAS = 100.0  # Deals > 100 KAS need human approval
DEFAULT_STRATEGY = ConcessionStrategy.BOULWARE


# ── Strategy implementations ──


def _concede_boulware(
    our_last: CovenantTerms,
    their_last: CovenantTerms,
    round_number: int,
) -> CovenantTerms:
    """BOULWARE strategy: start high, concede slowly over rounds.

    Concession schedule:
    - Rounds 1-3: hold firm
    - Rounds 4-6: small concession (10% per round)
    - Rounds 7-9: larger concession (20% per round)
    - Round 10: take it or leave it
    """
    progress = round_number / MAX_ROUNDS  # 0.0 to 1.0

    if progress < 0.3:
        # Hold firm: offer same as ours
        return our_last

    if progress < 0.6:
        # Small concession: move 10% toward theirs
        factor = 0.1
    elif progress < 0.9:
        # Larger concession: move 20% toward theirs
        factor = 0.3
    else:
        # Final round: take their offer or walk
        return their_last

    # Concede toward the midpoint between our_last and their_last
    return _interpolate(our_last, their_last, factor)


def _concede_fast(
    our_last: CovenantTerms,
    their_last: CovenantTerms,
    round_number: int,
) -> CovenantTerms:
    """CONCEDE strategy: start fair, concede quickly.

    Used for trusted/repeat counterparties. Concessions happen faster
    and go further.
    """
    progress = round_number / MAX_ROUNDS

    if progress < 0.2:
        return our_last
    if progress < 0.4:
        return _interpolate(our_last, their_last, 0.3)
    if progress < 0.7:
        return _interpolate(our_last, their_last, 0.6)
    return their_last


def _interpolate(a: CovenantTerms, b: CovenantTerms, factor: float) -> CovenantTerms:
    """Interpolate between two term sets. factor=0 → a, factor=1 → b."""
    return CovenantTerms(
        max_kas_per_tx=a.max_kas_per_tx + (b.max_kas_per_tx - a.max_kas_per_tx) * factor,
        max_kas_per_day=a.max_kas_per_day + (b.max_kas_per_day - a.max_kas_per_day) * factor,
        allowed_destinations=b.allowed_destinations if factor > 0.5 else a.allowed_destinations,
        duration_hours=int(a.duration_hours + (b.duration_hours - a.duration_hours) * factor),
    )


STRATEGIES = {
    ConcessionStrategy.BOULWARE: _concede_boulware,
    ConcessionStrategy.CONCEDE: _concede_fast,
}


# ── Negotiation Session ──


class NegotiationSession:
    """A single negotiation session between two agents.

    Tracks rounds, applies strategy, and produces an outcome.
    Sessions expire after MAX_ROUNDS or timeout.
    """

    def __init__(
        self,
        counterparty_id: str,
        strategy: ConcessionStrategy = DEFAULT_STRATEGY,
        template: str = "standard",
        memory: Optional[NegotiationMemory] = None,
    ):
        self.counterparty_id = counterparty_id
        self.strategy = strategy
        self.template = template
        self.memory = memory or NegotiationMemory()
        self.rounds: list[NegotiationRound] = []
        self.created_at = time.time()
        self.expires_at = self.created_at + 3600  # 1 hour timeout
        self.final_terms: Optional[CovenantTerms] = None
        self.is_complete = False
        self.is_accepted = False
        self.error: Optional[str] = None

        # Set initial offer from template
        self.our_terms = apply_template(template)

    @property
    def round_count(self) -> int:
        return len(self.rounds)

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def make_initial_offer(self) -> CovenantTerms:
        """Make the first offer to the counterparty."""
        return self.our_terms

    def respond_to_offer(self, their_terms: CovenantTerms) -> tuple[CovenantTerms, bool]:
        """Respond to a counterparty's offer.

        Returns:
            (our_response, accepted): our new terms and whether we accept theirs.
        """
        if self.is_complete:
            return self.our_terms, False

        if self.is_expired:
            self.is_complete = True
            self.error = "session expired"
            return self.our_terms, False

        # Record their offer
        round_num = self.round_count + 1
        self.rounds.append(
            NegotiationRound(
                round_number=round_num,
                proposer="them",
                terms=their_terms,
            )
        )

        # Check if we can accept their offer outright
        if self._terms_acceptable(their_terms):
            self.final_terms = their_terms
            self.is_complete = True
            self.is_accepted = True
            return their_terms, True

        # Check for max rounds
        if round_num >= MAX_ROUNDS:
            self.is_complete = True
            self.error = f"max rounds ({MAX_ROUNDS}) reached"
            return self.our_terms, False

        # Apply concession strategy
        strategy_fn = STRATEGIES.get(self.strategy, _concede_boulware)
        response = strategy_fn(self.our_terms, their_terms, round_num)
        self.our_terms = response

        # Record our response
        self.rounds.append(
            NegotiationRound(
                round_number=round_num,
                proposer="us",
                terms=response,
            )
        )

        return response, False

    def accept_terms(
        self,
        terms: CovenantTerms,
        deploy_escrow: bool = False,
        buyer_address: str = "",
        seller_address: str = "",
        arbiter_address: str = "",
    ) -> dict[str, Any]:
        """Accept the counterparty's terms and complete the session.

        If deploy_escrow is True, automatically creates an on-chain escrow
        covenant to enforce the agreed terms. Requires buyer/seller addresses.
        """
        self.final_terms = terms
        self.is_complete = True
        self.is_accepted = True

        # Record outcome
        outcome = NegotiationOutcome(
            counterparty_id=self.counterparty_id,
            strategy_used=self.strategy,
            rounds_to_deal=self.round_count,
            final_terms=terms,
            pot_funded=False,
            template_used=self.template,
        )
        self.memory.record(outcome)

        # Check if human escalation is needed
        needs_human = terms.max_kas_per_tx > HUMAN_ESCALATION_KAS

        return {
            "ok": True,
            "accepted": True,
            "terms": terms.to_dict(),
            "rounds": self.round_count,
            "needs_human_approval": needs_human,
            "message": "Deal accepted!"
            if not needs_human
            else f"Deal accepted! Amount {terms.max_kas_per_tx} KAS exceeds "
            f"auto-approval limit — human approval required.",
        }

    def reject_and_walk(self, reason: str = "") -> dict[str, Any]:
        """Walk away from the negotiation."""
        self.is_complete = True
        self.is_accepted = False
        self.error = reason or "walked away"
        return {
            "ok": False,
            "error": self.error,
            "rounds": self.round_count,
        }

    def _terms_acceptable(self, terms: CovenantTerms) -> bool:
        """Check if terms are acceptable as-is."""
        # Must be within our template bounds (with some flexibility)
        template_terms = apply_template(self.template)
        overage = 0.2  # 20% flexibility

        if terms.max_kas_per_tx > template_terms.max_kas_per_tx * (1 + overage):
            return False
        if terms.max_kas_per_day > template_terms.max_kas_per_day * (1 + overage):
            return False
        if terms.duration_hours > template_terms.duration_hours * (1 + overage):
            return False
        return True

    def summary(self) -> dict[str, Any]:
        """Get a human-readable summary of the session."""
        return {
            "counterparty": self.counterparty_id,
            "strategy": self.strategy.value,
            "template": self.template,
            "rounds": self.round_count,
            "is_complete": self.is_complete,
            "is_accepted": self.is_accepted,
            "expired": self.is_expired,
            "error": self.error,
            "duration_seconds": time.time() - self.created_at,
        }

    def audit_trail(self) -> list[dict[str, Any]]:
        """Get the full audit trail of rounds."""
        return [
            {
                "round": r.round_number,
                "proposer": r.proposer,
                "terms": r.terms.to_dict(),
                "accepted": r.accepted,
                "message": r.message,
                "timestamp": r.timestamp,
            }
            for r in self.rounds
        ]


# ── Session Manager (tracks all active sessions) ──


class SessionManager:
    """Manages multiple active negotiation sessions."""

    def __init__(self, memory: Optional[NegotiationMemory] = None):
        self._sessions: dict[str, NegotiationSession] = {}
        self.memory = memory or NegotiationMemory()

    def create_session(
        self,
        counterparty_id: str,
        template: str = "standard",
        strategy: Optional[ConcessionStrategy] = None,
    ) -> NegotiationSession:
        """Create a new negotiation session."""
        if strategy is None:
            strategy = self.memory.best_strategy_for(counterparty_id)

        session = NegotiationSession(
            counterparty_id=counterparty_id,
            strategy=strategy,
            template=template,
            memory=self.memory,
        )
        self._sessions[counterparty_id] = session
        return session

    def get_session(self, counterparty_id: str) -> Optional[NegotiationSession]:
        """Get an existing session."""
        return self._sessions.get(counterparty_id)

    def active_sessions(self) -> list[dict[str, Any]]:
        """List all active (non-complete) sessions."""
        return [s.summary() for s in self._sessions.values() if not s.is_complete and not s.is_expired]

    def cleanup_expired(self) -> int:
        """Clean up expired sessions. Returns count removed."""
        expired = [k for k, v in self._sessions.items() if v.is_expired]
        for k in expired:
            del self._sessions[k]
        return len(expired)
