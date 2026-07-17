# Covenant Negotiation — Commercial Principles

## Risk: The Monster

The current protocol has:
- 3 concession strategies (BOULWARE, LINEAR, CONCEDE)
- 9 negotiable parameters on CovenantTerms
- Learning memory that adapts per counterparty
- Volume discounts + subscriptions

This can grow unbounded. Every new feature adds a knob. More knobs → more edge cases → unpredictable agent behavior → bad deals.

## Grounding: Commercial Best Practices

### 1. Templates > Custom Negotiation
Real businesses don't negotiate every deal from scratch. They have standard terms, and only deviate for large/strategic partners.

**Apply:** Most covenant pots should be "take it or leave it" template offers. Full negotiation is reserved for deals above a threshold (e.g., >100 KAS pot).

### 2. Price Anchoring
The first offer sets expectations. An agent that always opens with BOULWARE (high initial, concede slowly) trains counterparties to start high too.

**Apply:** Default to honest first offers, not gaming. The learning system should optimize for *speed to deal*, not *maximal extraction*.

### 3. BATNA (Best Alternative to Negotiated Agreement)
What happens if no deal? The agent should have a fallback plan, not negotiate forever.

**Apply:** Negotiation sessions have a max round limit. If no deal after N rounds, the session expires and the agent falls back to a default template.

### 4. Audit Trail
Every commercial negotiation should be auditable. Who offered what, when, and why.

**Apply:** The negotiation rounds already capture this. Add a human-readable summary to `covenant_status()`.

### 5. Escalation
Most deals are automated. Some need a human. Define the threshold.

**Apply:** Pot size > X KAS or first-time counterparty > Y KAS requires human approval. Below that, agent can auto-deal.

### 6. Simplicity > Flexibility
A negotiation system with 9 parameters and 3 strategies is harder to audit than one with 3 parameters and 1 strategy.

**Apply:** Cut parameters that aren't essential. Merge strategies that overlap. The system should be *predictable* first, *smart* second.

## Proposed Simplification

### Cut these parameters (moved to template defaults):
- `voting_threshold` — only relevant for multi-party pots, which are rare
- `dispute_resolver` — only needed for escrow-style pots
- `owner_return_delay_blocks` — too technical, use a simpler "hours" field
- `fee_sharing` — fee is always dev-collected, not split

### Keep these parameters:
- `max_kas_per_tx` — core spend cap
- `max_kas_per_day` — core spend cap
- `allowed_destinations` — security-critical
- `duration_hours` — session lifetime

### Merge strategies:
- BOULWARE → default (slow concession, standard)
- LINEAR → remove (rarely optimal)
- CONCEDE → use for trusted counterparties only

## What to Ask Claude

Write a focused prompt for Claude to review the negotiation.py code against these commercial principles. Ask it to:
1. Identify any parameter that could produce a bad deal
2. Suggest the minimum viable set of parameters
3. Flag any learning system behavior that could go wrong
4. Recommend concrete guardrails (max rounds, max delta, human escalation thresholds)