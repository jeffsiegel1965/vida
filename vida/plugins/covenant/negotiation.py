"""
Agent-to-agent covenant negotiation protocol.

Parameters, rounds, concession strategies, and deal encoding.
Designed for autonomous agents to negotiate covenant terms,
then commit the deal on-chain via policy_hash.

Usage:
    from vida.plugins.covenant.negotiation import CovenantNegotiator

    negotiator = CovenantNegotiator()
    offer = negotiator.create_offer(max_kas_per_tx=1.0, max_kas_per_day=5.0)
    counter = negotiator.counter_offer(offer, max_kas_per_tx=0.5)
    deal = negotiator.accept(counter)
    commitment = negotiator.encode_deal(deal)
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


# ── Negotiation parameter space ──


class NegotiationPhase(Enum):
    OFFER = "offer"
    COUNTER = "counter"
    ACCEPT = "accept"
    REJECT = "reject"
    WALK_AWAY = "walk_away"
    COMMITTED = "committed"
    EXPIRED = "expired"


class ConcessionStrategy(Enum):
    """How an agent concedes during negotiation."""

    NONE = "none"
    LINEAR = "linear"
    BOULWARE = "boulware"
    CONCEDE = "concede"


@dataclass
class CovenantTerms:
    """Full set of negotiable covenant parameters."""

    max_kas_per_tx: float = 0.0
    max_kas_per_day: float = 0.0
    allowed_destinations: list[str] = field(default_factory=list)
    require_dest_allowlist: bool = False
    duration_blocks: int = 0
    duration_hours: float = 0.0
    parties: list[str] = field(default_factory=list)
    voting_threshold: float = 1.0
    dispute_resolver: str = ""
    owner_return_delay_blocks: int = 0
    fee_sharing: dict[str, float] = field(default_factory=dict)
    require_confirm: bool = True
    allow_agent_negotiation: bool = True

    def to_canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def deal_hash(self) -> str:
        return hashlib.sha256(self.to_canonical_json().encode()).hexdigest()

    def validate(self) -> Optional[str]:
        if self.max_kas_per_tx <= 0:
            return "max_kas_per_tx must be positive"
        if self.max_kas_per_day <= 0:
            return "max_kas_per_day must be positive"
        if self.require_dest_allowlist and not self.allowed_destinations:
            return "require_dest_allowlist set but no destinations"
        if self.voting_threshold <= 0 or self.voting_threshold > 1:
            return "voting_threshold must be in (0, 1]"
        if self.owner_return_delay_blocks < 0:
            return "owner_return_delay_blocks must be >= 0"
        return None

    def to_policy_template(self) -> dict[str, Any]:
        from .agent_pot import SOMPI_PER_KAS
        from .agent_pot_script import build_agent_pot_script_template
        return build_agent_pot_script_template(
            max_kas_per_tx=self.max_kas_per_tx,
            max_kas_per_day=self.max_kas_per_day,
            allowed_destinations=self.allowed_destinations,
            owner_address=self.parties[0] if self.parties else None,
        )


@dataclass
class NegotiationRound:
    phase: NegotiationPhase
    terms: CovenantTerms
    proposer: str = ""
    timestamp: float = field(default_factory=time.time)
    message: str = ""


@dataclass
class NegotiationSession:
    negotiation_id: str = field(default_factory=lambda: hashlib.sha256(
        f"{time.time()}{os.urandom(8).hex()}".encode()).hexdigest()[:16])
    agent_a: str = ""
    agent_b: str = ""
    rounds: list[NegotiationRound] = field(default_factory=list)
    deal_hash: str = ""
    status: str = "active"
    deadline: float = 0.0
    strategy_a: ConcessionStrategy = ConcessionStrategy.BOULWARE
    strategy_b: ConcessionStrategy = ConcessionStrategy.LINEAR

    def add_round(self, round: NegotiationRound):
        self.rounds.append(round)

    def latest_terms(self) -> Optional[CovenantTerms]:
        if not self.rounds:
            return None
        return self.rounds[-1].terms

    def is_expired(self) -> bool:
        return self.deadline > 0 and time.time() > self.deadline


class CovenantNegotiator:
    """
    Autonomous agent negotiation of covenant terms.
    """

    def __init__(self, strategy: ConcessionStrategy = ConcessionStrategy.BOULWARE):
        self.strategy = strategy
        self._sessions: dict[str, NegotiationSession] = {}
        self._lock = threading.Lock()

    def create_offer(self, *, agent_id: str, agent_a: str, agent_b: str,
                     max_kas_per_tx: float, max_kas_per_day: float,
                     allowed_destinations: Optional[list[str]] = None,
                     duration_hours: float = 24.0,
                     deadline_minutes: float = 60.0, **kwargs) -> NegotiationSession:
        terms = CovenantTerms(
            max_kas_per_tx=max_kas_per_tx,
            max_kas_per_day=max_kas_per_day,
            allowed_destinations=allowed_destinations or [],
            duration_hours=duration_hours,
            **{k: v for k, v in kwargs.items() if hasattr(CovenantTerms, k)},
        )
        session = NegotiationSession(
            agent_a=agent_a, agent_b=agent_b,
            deadline=time.time() + deadline_minutes * 60,
            strategy_a=self.strategy,
        )
        session.add_round(NegotiationRound(
            phase=NegotiationPhase.OFFER,
            terms=terms, proposer=agent_a,
            message=f"Offer from {agent_a[:12]}",
        ))
        self._sessions[session.negotiation_id] = session
        return session

    def get_session(self, negotiation_id: str) -> Optional[NegotiationSession]:
        return self._sessions.get(negotiation_id)

    def counter_offer(self, negotiation_id: str, proposer: str,
                      **modified_terms) -> Optional[NegotiationSession]:
        session = self._sessions.get(negotiation_id)
        if not session:
            return None
        if session.is_expired():
            session.status = "expired"
            return session
        current = session.latest_terms()
        if not current:
            return None
        if proposer == session.agent_a:
            strategy = session.strategy_a
        elif proposer == session.agent_b:
            strategy = session.strategy_b
        else:
            strategy = ConcessionStrategy.LINEAR
        round_num = len(session.rounds)
        concessions = self._apply_concession_strategy(
            current=current, proposed=modified_terms,
            strategy=strategy, round_num=round_num)
        new_terms = CovenantTerms(**{**asdict(current), **concessions})
        session.add_round(NegotiationRound(
            phase=NegotiationPhase.COUNTER,
            terms=new_terms, proposer=proposer,
            message=f"Counter from {proposer[:12]} (strategy={strategy.value})",
        ))
        return session

    @staticmethod
    def _apply_concession_strategy(
        current: CovenantTerms, proposed: dict[str, Any],
        strategy: ConcessionStrategy, round_num: int,
        max_rounds: int = 10,
    ) -> dict[str, Any]:
        if strategy == ConcessionStrategy.NONE:
            result = {}
            for key in ("max_kas_per_tx", "max_kas_per_day"):
                if key in proposed:
                    p = float(proposed.get(key, 0))
                    c = float(getattr(current, key, 0))
                    result[key] = max(p, c)
            return result
        if strategy == ConcessionStrategy.CONCEDE:
            return {k: v for k, v in proposed.items()
                    if k in ("max_kas_per_tx", "max_kas_per_day",
                              "allowed_destinations", "duration_hours")}
        if strategy == ConcessionStrategy.LINEAR:
            progress = min(round_num / max_rounds, 1.0)
            result = {}
            for key in ("max_kas_per_tx", "max_kas_per_day"):
                if key in proposed:
                    cv = float(getattr(current, key, 0))
                    pv = float(proposed.get(key, 0))
                    diff = cv - pv
                    result[key] = round(max(cv - diff * progress, pv), 6)
            return result
        if strategy == ConcessionStrategy.BOULWARE:
            progress = min(round_num / max_rounds, 1.0)
            factor = 0.1 if progress < 0.7 else min(0.1 + 0.9 * ((progress - 0.7) / 0.3), 1.0)
            result = {}
            for key in ("max_kas_per_tx", "max_kas_per_day"):
                if key in proposed:
                    cv = float(getattr(current, key, 0))
                    pv = float(proposed.get(key, 0))
                    diff = cv - pv
                    result[key] = round(max(cv - diff * factor, pv), 6)
            return result
        return proposed

    def accept(self, negotiation_id: str, agent: str) -> Optional[NegotiationSession]:
        with self._lock:
            session = self._sessions.get(negotiation_id)
            if not session:
                return None
            if session.is_expired():
                session.status = "expired"
                return session
            if session.status != "active":
                return session
            latest = session.latest_terms()
            if not latest:
                return None
            err = latest.validate()
            if err:
                session.add_round(NegotiationRound(
                    phase=NegotiationPhase.REJECT, terms=latest,
                    proposer=agent, message=f"Rejected: {err}"))
                session.status = "rejected"
                return session
            session.add_round(NegotiationRound(
                phase=NegotiationPhase.ACCEPT, terms=latest,
                proposer=agent, message=f"Accepted by {agent[:12]}"))
            session.deal_hash = latest.deal_hash()
            session.status = "committed"
        return session

    def reject(self, negotiation_id: str, agent: str, reason: str = "") -> Optional[NegotiationSession]:
        session = self._sessions.get(negotiation_id)
        if not session:
            return None
        latest = session.latest_terms() or CovenantTerms()
        session.add_round(NegotiationRound(
            phase=NegotiationPhase.REJECT, terms=latest,
            proposer=agent, message=reason or f"Rejected by {agent[:12]}"))
        session.status = "rejected"
        return session

    def encode_deal(self, negotiation_id: str) -> dict[str, Any]:
        session = self._sessions.get(negotiation_id)
        if not session or session.status != "committed":
            return {"ok": False, "error": "deal not committed"}
        terms = session.latest_terms()
        if not terms:
            return {"ok": False, "error": "no terms"}
        template = terms.to_policy_template()
        if not template.get("ok"):
            return {"ok": False, "error": template.get("error", "policy template failed")}
        return {
            "ok": True, "negotiation_id": negotiation_id,
            "deal_hash": session.deal_hash,
            "canonical_terms": terms.to_canonical_json(),
            "terms_dict": asdict(terms),
            "policy_template": template,
            "policy_hash": template.get("policy_hash"),
            "commitment": {
                "deal_hash": session.deal_hash,
                "policy_hash": template.get("policy_hash"),
                "network": "testnet-10",
                "note": "Commit this deal_hash in the covenant UTXO metadata",
            },
            "rounds": len(session.rounds),
            "parties": [session.agent_a, session.agent_b],
        }

    def list_sessions(self, agent_id: Optional[str] = None) -> list[dict]:
        result = []
        for sid, session in self._sessions.items():
            if agent_id and agent_id not in (session.agent_a, session.agent_b):
                continue
            result.append({
                "negotiation_id": sid, "status": session.status,
                "agent_a": session.agent_a[:20], "agent_b": session.agent_b[:20],
                "rounds": len(session.rounds),
                "deal_hash": session.deal_hash[:16] if session.deal_hash else "",
                "expired": session.is_expired(),
            })
        return result


_DEFAULT_NEGOTIATOR: CovenantNegotiator | None = None


def get_negotiator(strategy: ConcessionStrategy = ConcessionStrategy.BOULWARE) -> CovenantNegotiator:
    global _DEFAULT_NEGOTIATOR
    if _DEFAULT_NEGOTIATOR is None:
        _DEFAULT_NEGOTIATOR = CovenantNegotiator(strategy=strategy)
    return _DEFAULT_NEGOTIATOR