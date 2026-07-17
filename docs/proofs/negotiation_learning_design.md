# Vida Agent Negotiation — Learning & Adaptation System

## Goal
Make the covenant negotiation protocol learn from experience, adapt strategies per counterparty, and support volume discounts and subscriptions.

## Current State
- `negotiation.py` has `NegotiationSession`, `Negotiator`, `ConcessionStrategy` (BOULWARE/LINEAR/CONCEDE)
- `CovenantTerms` has: max_kas_per_tx, max_kas_per_day, allowed_destinations, duration_hours, parties, voting_threshold, dispute_resolver, owner_return_delay_blocks, fee_sharing
- Strateless: no memory of past negotiations, no learning

## Design

### 1. NegotiationMemory — Persistent Learning
```python
@dataclass
class NegotiationOutcome:
    counterparty_id: str          # agent identifier hash
    strategy_used: ConcessionStrategy
    rounds_to_deal: int
    final_terms: CovenantTerms
    pot_funded: bool              # was the covenant actually created?
    pot_sompi: int                # size of pot funded
    fee_paid_kas: float
    timestamp: float

class NegotiationMemory:
    """Persistent learning engine for negotiation strategies."""
    
    def __init__(self, storage_path: str):
        self._outcomes: list[NegotiationOutcome] = []
        self._load()
    
    def record(self, outcome: NegotiationOutcome): ...
    def best_strategy_for(self, counterparty: str) -> ConcessionStrategy: ...
    def estimated_acceptance(self, terms: CovenantTerms, counterparty: str) -> float: ...
    def volume_discount(self, counterparty: str, pot_sompi: int) -> float: ...
```

### 2. Volume Discounts
- Track total pot value funded per counterparty
- Apply discount tiers:
  - 0-100 KAS total: 0% discount
  - 100-1000 KAS total: 10% discount on fees
  - 1000-10000 KAS total: 20% discount
  - 10000+ KAS total: 30% discount + priority support
- Discount applies to the `calc_fund_fee()` and `calc_spend_fee()` functions

### 3. Subscription Model
- Allow recurring subscription pots (weekly/monthly)
- Subscription terms: fixed amount, fixed interval, auto-renewal flag
- Subscription discount: 15% off fees for auto-renewing subscriptions
- Implementation: `SubscriptionTerms` dataclass + `SubscriptionManager`

### 4. Adaptive Strategy Selection
- Track which strategy gets deals accepted fastest per counterparty
- Default to BOULWARE for new counterparties
- After 3+ deals with same counterparty, switch to optimal strategy
- Concession rate adjusts based on past response times

### 5. Counterparty Profiles
```python
@dataclass
class CounterpartyProfile:
    agent_id: str
    deal_count: int
    total_pot_kas: float
    avg_rounds_to_deal: float
    preferred_strategy: ConcessionStrategy
    last_interaction: float
    avg_response_time: float  # seconds
```

## Implementation Plan

### Phase 1 — Memory + Recording (1 session, ~$0.50)
1. Add `NegotiationOutcome` dataclass
2. Add `NegotiationMemory` with JSON persistence
3. Record outcome when pot is funded
4. Display stats in `covenant_status()`

### Phase 2 — Volume Discounts (0.5 session, ~$0.25)
1. Add discount calculation to `fees.py`
2. Wire into `calc_fund_fee()` and `calc_spend_fee()`
3. Update `describe_fees()` to show discounts

### Phase 3 — Adaptive Strategy (1 session, ~$0.50)
1. Add `best_strategy_for()` to `NegotiationMemory`
2. Update `Negotiator.create_offer()` to auto-select strategy
3. Add `ConcessionStrategy.AUTO` that delegates to memory

## Files to Modify
- `vida/plugins/covenant/negotiation.py` — add memory, profiles, adaptive strategy
- `vida/plugins/covenant/fees.py` — add volume discount logic
- `vida/plugins/covenant/tools.py` — expose new capabilities
- `vida/plugins/covenant/config.py` — add storage path config

## Deliverable
Write the enhanced `negotiation.py` with all the above features. Keep backward compatibility with the existing API. Add tests in `tests/test_covenant_negotiation.py`.

## Constraints
- JSON file-based persistence (no database)
- Thread-safe (use threading.Lock)
- All existing negotiation tests must still pass
- Default behavior unchanged when no memory file exists