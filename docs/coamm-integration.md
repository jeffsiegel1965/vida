# CoAMM Integration — Vida + Zealous Swap

**Status:** Design document — no code written yet
**Date:** 2026-07-20
**Source:** [Zealous Swap CoAMM Whitepaper v1.0](https://github.com/zealousswap/CoAMM-whitepaper/blob/main/ZealousSwap-CoAMM-Whitepaper-v1.0.pdf)
**Network target:** Kaspa testnet-10 (Toccata covenants)

---

## 1. What We're Integrating

Zealous Swap's CoAMM is a constant-product AMM (x·y = k) running entirely in Kaspa L1 covenants.
Vida agents will use CoAMM pools as a **price oracle and liquidity exit** — converting earned fees,
paying for subnets in a different token, or rebalancing agent treasury.

We are **not** building a competing AMM. CoAMM is the liquidity layer; Vida is the agent
wallet/treasury/negotiation layer. They are complementary.

---

## 2. What Vida Already Supports

| Feature | Status | Notes |
|---------|--------|-------|
| Covenant token standard (ownership modes 0x00, 0x01, 0x02) | ✅ Built | Token module supports pubkey, script-hash, and covenant-id ownership |
| Token split/join | ✅ Built | Note management for exact amounts |
| Covenant transaction construction | ✅ Built | TxBuilder in `vida/transactions/` |
| Toccata introspection | ✅ Built | KAS spend, value constraints, script-hash validation |
| Agent wallet / permissioning | ✅ Built | Session-gated, per-tx caps, destination allowlists |

**Gap:** Vida does not yet build transactions that:
- Spend a pool UTXO and re-create it with updated reserves
- Enforce the constant-product invariant in-script
- Route across two pools in one transaction (multi-hop)
- Read pool state (reserves, fee counters, token_covid) for quote computation

---

## 3. Integration Architecture

```
                    ┌─────────────────────┐
                    │   Vida Agent Wallet  │
                    │  (permissions, caps, │
                    │   session-gated)     │
                    └────────┬────────────┘
                             │
                    ┌────────▼────────┐
                    │  CoAMM Client   │  ← NEW module
                    │  (tx builder,   │
                    │   quote engine, │
                    │   pool client)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Covenant Tx    │
                    │  Builder        │  ← existing, extended
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Pool     │  │ Token    │  │ User     │
        │ Covenant │  │ Covenant │  │ Wallet   │
        │ UTXO     │  │ UTXOs    │  │ UTXOs    │
        └──────────┘  └──────────┘  └──────────┘
```

No new dependencies. CoAMM integration is a pure client-side transaction builder
that uses existing covenant infrastructure.

---

## 4. Transaction Shapes

### 4.1 KAS → Token Swap

**Inputs:**
- Pool UTXO (leader)
- Reserve token note (observed, authorized by pool's covenant id)
- User's KAS input (trader signs)

**Outputs:**
- Successor pool (value = V + dx, reserves updated)
- Token payout to user (dy)
- Successor reserve (T - dy)
- Change to user (KAS)

**Validation:** Pool checks invariant with `prod_ge` (128-bit exact).
Token covenant checks reserve note authorization independently.

### 4.2 Token → KAS Swap

**Inputs:**
- Pool UTXO (leader)
- Reserve token note (observed)
- User's token payment (user signs)

**Outputs:**
- Successor pool (value = V - dkas)
- Successor reserve (T + dtkn)
- KAS proceeds to user

### 4.3 Token → Token Multi-Hop

**Inputs:**
- Pool_X UTXO (leader)
- Reserve_X token note (observed)
- Pool_Y UTXO (leader)
- Reserve_Y token note (observed)
- User's token X input (user signs)

**Outputs:**
- Successor Pool_X (value = V_x - dkas)
- Successor reserve_X (T_x + dtkn_in)
- Successor Pool_Y (value = V_y + dkas)
- Successor reserve_Y (T_y - dtkn_out)
- Token Y payout to user
- Change to user

**Key property:** Intermediate KAS is never a UTXO — value conservation inside the
transaction carries it between Pool_X and Pool_Y. No router contract.

### 4.4 Note Management (Pre-swap)

Before any swap, the client may need split/join rounds:

```
if user_note < amount:
    JOIN two smallest notes → one larger note
    repeat until covering note exists
SPLIT covering note → piece[amount] + remainder[]
SWAP piece[amount]
```

Each split/join is its own covenant transaction. The swap is the final one.

---

## 5. Quote Engine

A client-side function that reads pool state and computes the maximum output
for a given input:

```
# KAS → Token
dy_max = Teff - ceil(Veff * Teff / (Veff + floor(dx * 997 / 1000)))

# Token → KAS
dkas_max = Veff - ceil(Veff * Teff / (Teff + floor(dtkn * 997 / 1000)))
```

The pool accepts any dy ≤ dy_max. The fee is the 997/1000 credit on the input.
Protocol fee (1/6 of the fee) is accrued in pool state counters, not deducted
from the swap output.

Quote computation needs:
- Pool's KAS value (UTXO value)
- Token reserve amount (from reserve note state)
- Protocol fee counters (from pool state)
- Paired token covenant id (for multi-hop routing)

---

## 6. Pool Discovery

Vida needs to find pools and read their state. Two approaches:

**A. Covenant id registry** (lightweight)
- A known catalogue of pool covenant ids
- Client fetches pool UTXO by covenant id, reads state from the mutable region
- Simplest, but requires manual registration

**B. Indexer** (heavier)
- Watch the chain for pool-family genesis transactions
- Maintain a local map of pool → token + reserves
- Required for a production agent that discovers pools dynamically

**Recommended:** Start with (A) for the spike. Add (B) when agents need to
discover pools without manual configuration.

---

## 7. Pool State Schema

Pool state fields (from the mutable region, after prefix):

| Field | Type | Description |
|-------|------|-------------|
| `lp_supply` | u64 | Total liquidity shares, including locked minimum |
| `fee_to` | 32 bytes | Blake2b hash of protocol fee wallet pubkey |
| `protocol_fee_kas` | u64 | Accrued KAS protocol fees (inside pool value) |
| `protocol_fee_tkn` | u64 | Accrued token protocol fees (inside reserve note) |
| `token_covid` | 32 bytes | Covenant id of the paired token family |

**Effective reserves** (used for pricing, not raw):

```
Veff = pool_value - protocol_fee_kas
Teff = reserve_amount - protocol_fee_tkn
```

---

## 8. Fee Model

| Component | Share | Mechanism |
|-----------|-------|-----------|
| LP fee | 5/6 of 0.3% (0.25%) | Stays in reserves, compounds into the curve |
| Protocol fee | 1/6 of 0.3% (0.05%) | Accrued in counters, claimed by fee_to wallet |

The protocol fee is side-accumulated, not minted as shares. The `collect_protocol`
operation pays the counters to the fee wallet and resets them.

---

## 9. Dependencies

**None.** CoAMM integration adds no new Python packages, no new chain dependencies,
and no external APIs. Everything is:
- Kaspa SDK (already in `pyproject.toml`)
- Covenant transaction builder (already in Vida)
- Client-side arithmetic (pure Python — already in the codebase)

---

## 10. Integration Plan (When Ready)

### Phase 1 — Spike (testnet-10)
1. Find or deploy a CoAMM pool on TN10
2. Read pool UTXO state, compute reserves
3. Build a KAS→Token swap transaction, submit to TN10
4. Verify atomicity and fee behavior
5. Document: what worked, what broke, what the covenant code cost was

### Phase 2 — Agent Tool
6. Add `coamm_swap` tool to the agent orchestrator
7. Add `coamm_quote` tool for price discovery
8. Wire through session-gated permissions (caps, allowlists)
9. Test: agent negotiates a deal, earns fees, swaps them via CoAMM

### Phase 3 — Multi-Hop
10. Build the multi-hop route builder
11. Add path discovery (find cheapest route across pools)
12. Test: token-X → token-Y in one transaction

### Phase 4 — Production
13. Launch on mainnet when Zealous Swap deploys there
14. Add pool discovery indexer
15. Add batching for high-frequency swaps

---

## 11. Open Questions

1. **Is there a CoAMM pool already deployed on TN10?** Zealous Swap's whitepaper
   says "testnet-10 (Toccata covenants)" — check if they have live test pools.

2. **What is the template hash for the pool covenant?** Needed to construct
   same-template successor outputs. Either compute from source or read from
   a live pool's spend.

3. **License interface:** BUSL-1.1 prohibits commercial use without written
   permission. We need to confirm with Louis Saad that Vida agents using
   CoAMM pools (as a consumer, not a fork) is permitted. This is a usage
   question, not a forking question.

4. **Minimum trade size:** ~0.02 KAS floor from storage mass. Confirm
   empirically on TN10.

---

## 12. References

- [CoAMM Whitepaper PDF](https://github.com/zealousswap/CoAMM-whitepaper/blob/main/ZealousSwap-CoAMM-Whitepaper-v1.0.pdf)
- [Zealous Swap](https://zealousswap.com)
- KIP-16, KIP-17, KIP-20, KIP-21 (Toccata covenant specs)
- Vida docs: `docs/covenants.md`, `docs/tokens.md`
- Toccata reference: `toccata.md` (in vault)