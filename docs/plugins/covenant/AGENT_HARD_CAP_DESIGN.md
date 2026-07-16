# Covenant track — B: Offline agent design (hard caps later)

**Date:** 2026-07-14  
**Status:** Design only. No live deploy. Depends on **A = NO-GO** for on-chain until #1074 client exists.  
**Product rule:** Soft session policy stays; covenants are an **optional hard layer** under agent working funds.

---

## Goal (what “more bulletproof” means here)

Put the agent’s **working KAS** into UTXOs the **network** will only let spend if rules pass:

| Soft (today) | Hard (covenant target) |
|--------------|-------------------------|
| Vida process checks max/tx, max/day, dest | Script / covenant binding enforces what it can |
| Stolen session key can still sign free UTXOs | Stolen key only spends **constrained** coins |
| Revoke = delete session | Revoke = don’t fund more; old covenant rules still bind those UTXOs |

Still **not** root-proof on the machine holding the owner seed.

---

## Two-bucket model (owner setup)

```
[Cold / owner vault]     — seed, password wallet, life savings
        │  owner-only send (no agent session)
        ▼
[Agent working pot]      — small balance
        │  funded into covenant-constrained UTXOs (when live)
        ▼
[Agent session]          — signs spends that still must satisfy covenant + soft policy
```

**Rule:** Never put life savings in the agent pot. Covenants protect the pot’s **shape of spend**, not a compromised owner key.

---

## Target rules for agent pot (MVP covenant policy)

Design for TN10 first, then mainnet when tooling is stable.

| Rule | Soft today | Covenant target |
|------|------------|-----------------|
| Max amount per spend | `max_kas_per_tx` | Script / authorized outputs bound amount |
| Max destinations | allowlist | `CovenantBinding` / authorized output set |
| Time window | session `expires_at` | CLTV / CSV style lock where applicable |
| Daily cap | process `enc_spend` | **Harder:** may need multiple epochs or owner re-fund; pure “per calendar day” is awkward on-chain — prefer **per-UTXO budget** or **epoch pot** |
| Who can sign | session schnorr key | Same pubkey or delegated key **only** under script |

### Practical MVP (recommended)

Don’t try to encode “UTC calendar day” on-chain first.

**MVP hard rules:**

1. **Max single payment** ≤ X KAS (matches max/tx).  
2. **Allowed destinations only** (1–N addresses).  
3. **Optional absolute timelock** (funds unusable until height/time — escape hatch or cliff).  
4. **Change** stays under same covenant (or returns to owner vault).

**Daily cap:** keep **soft** in Vida session **and** limit pot size (e.g. fund only 1 day of max_day into the pot). That is the honest hybrid.

```
max_day (soft)  ≈  how much you fund into the pot
max_tx  (soft + hard)  ≈  per-payment covenant limit
dest    (soft + hard)  ≈  allowlist in binding
```

---

## Flow (when C is green)

```
1. Owner creates SecureVida wallet (seed stays owner).
2. Owner grants soft session (hours, max_tx, max_day, dests).
3. Owner (or controlled script) deploys covenant UTXO(s) funded from vault:
     - budget 10–20 per signing input (pre-sign)
     - binding: authorized outputs / agent payment template
4. Agent only selects UTXOs tagged as agent-pot (never vault).
5. On spend: soft policy check → build v1 tx with computeBudget → sign → broadcast.
6. Node rejects if covenant/script fails — even if soft policy was bypassed.
```

### Fail modes (design for honesty)

| Failure | Response |
|---------|----------|
| SDK drops computeBudget | Refuse build; never claim success |
| Soft OK, chain reject | Surface node error; no fake txid |
| Soft bypassed (malware) | Chain still enforces covenant on pot UTXOs |
| Vault key on same host | Covenant does **not** save life savings |

---

## Mapping to Vida code (offline → later live)

| Component | Now | Later (post-C) |
|-----------|-----|----------------|
| `vida/plugins/covenant` | Scaffold: status, budget validate, deploy/spend **refuse** | Wire post-#1074 client; real deploy/spend |
| `secure_wallet` sessions | Soft caps | Still required (UX + double gate) |
| `transactions.py` | Free UTXO selection | Prefer **agent-pot** UTXOs; reject vault |
| Proofs | Third-party refs only | `docs/proofs/covenant_tn10_deploy.md` + spend |

### Offline helpers already aligned

- `offline_validate_budget(n)` — budget units rules from #1073  
- `sketch_timelock` — metadata only  
- `deploy()` / `spend()` → `ok: False` until live  

---

## Script sketch (conceptual — not bytecode claim)

```
# Payment covenant (idea only)
# Unlock: Schnorr sig by agent session key
# AND outputs match authorized template:
#   - payment ≤ max_tx to address ∈ allowlist
#   - change → same covenant or owner vault
# Optional: nLockTime / CLTV for “not before”
```

Exact opcodes and `CovenantBinding` layout: follow **kascov guide** + rusty-kaspa post-Toccata docs when implementing C.  
**This file is not a compile guarantee.**

---

## Agent product UX (Hermes)

| Mode | Soft | Hard (when live) |
|------|------|------------------|
| COMMAND | Owner approves each spend | Still signs only pot UTXOs |
| HYBRID | Auto under threshold | Threshold ≤ covenant max_tx |
| FULL | Auto inside session | Auto inside session **and** covenant |

Hermes never receives seed. Grant stays owner CLI.

---

## What we explicitly do **not** design here

- Guaranteed yield / TAO covenants  
- PQ on-chain spends  
- “Bulletproof vs root”  
- Encoding full UTC daily reset on-chain (v1)  

---

## Exit criteria for B (done)

- [x] Two-bucket model written  
- [x] MVP hard rules (max_tx, dest, pot size ≈ day)  
- [x] Hybrid soft+hard daily story honest  
- [x] Code mapping + fail modes  
- [x] No false live claim  

**Next:** **C** only when A unblocks (#1074 client + round-trip).
