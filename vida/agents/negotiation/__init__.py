"""Vida Agent Negotiation Module.

Agent-to-agent negotiation for covenant pot terms.
Designed for agent commerce — agents negotiate terms, create pots,
and track deal history for volume discounts.

Usage:
    from vida.agents.negotiation import (
        SessionManager, NegotiationMemory, SubscriptionManager,
        CovenantTerms, ConcessionStrategy, apply_template, TEMPLATES,
        HUMAN_ESCALATION_KAS,
    )

    # Create a session
    mgr = SessionManager()
    session = mgr.create_session("agent_123", template="standard")

    # Make initial offer
    offer = session.make_initial_offer()

    # Respond to counterparty
    response, accepted = session.respond_to_offer(counterparty_terms)

    # Accept or walk
    if accepted:
        result = session.accept_terms(counterparty_terms)
    else:
        result = session.reject_and_walk("deal too rich")
"""

from .engine import (
    DEFAULT_STRATEGY,
    HUMAN_ESCALATION_KAS,
    MAX_ROUNDS,
    NegotiationSession,
    SessionManager,
)
from .models import (
    TEMPLATES,
    ConcessionStrategy,
    CounterpartyProfile,
    CovenantTerms,
    NegotiationMemory,
    NegotiationOutcome,
    NegotiationRound,
    apply_template,
)
from .subscriptions import (
    SUBSCRIPTION_DISCOUNT,
    Subscription,
    SubscriptionManager,
)

__all__ = [
    "ConcessionStrategy",
    "CounterpartyProfile",
    "CovenantTerms",
    "DEFAULT_STRATEGY",
    "HUMAN_ESCALATION_KAS",
    "MAX_ROUNDS",
    "NegotiationMemory",
    "NegotiationOutcome",
    "NegotiationRound",
    "NegotiationSession",
    "SessionManager",
    "SUBSCRIPTION_DISCOUNT",
    "Subscription",
    "SubscriptionManager",
    "TEMPLATES",
    "apply_template",
]
