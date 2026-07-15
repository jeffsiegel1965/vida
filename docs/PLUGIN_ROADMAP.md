# Vida Plugin Roadmap

**Status:** active  
**Order of work:** Phase 0 → Phase 1 → Phase 1B → later phases  
**Date:** 2026-07-08

---

## Why plugins

Vida core is an **owner-custody agent wallet**: you hold the seed, you set limits, the agent acts inside them.

Chains and features grow as **plugins**, not rewrites:

| Plugin | Role |
|--------|------|
| **Kaspa** (today’s core) | Fast, cheap settlement / micropayments |
| **TAO** | Intelligence economy — stake, pay, route agent work |
| **Covenant** | Hard on-chain limits when Kaspa supports them | (status: [COVENANT_BLOCKER_STATUS.md](docs/plugins/COVENANT_BLOCKER_STATUS.md))
| **BTC** (later) | Settlement / treasury rail |

**Strategic note:** If TAO becomes the “BTC of intelligence,” many agents will prefer TAO rails for work markets even while Kaspa remains ideal for cheap micropayments. Vida should be the **custody + policy layer** across both — not Kaspa-only forever.

---

## Architecture

```
Vida Core (chain-agnostic)
├── Owner custody (seed / password / encrypted vault)
├── Session grants (time, max/tx, max/day, FULL|HYBRID|COMMAND)
├── Policy engine (same leash rules for every chain)
├── Audit log
└── Plugin registry

Plugins (optional)
├── vida_kaspa      (extract later; works as built-in today)
├── vida_tao        Phase 1 / 1B
├── vida_covenant   when protocol allows live deploy
└── vida_btc        later
```

### Every plugin must provide

1. **Identity** — account/address from owner vault without exposing seed to the agent  
2. **Status** — balance / positions (read-only)  
3. **Actions** — transfer / stake / deploy, all policy-gated  
4. **Session bind** — agent only acts inside granted caps  
5. **Proof** — verifiable ids (txid / extrinsic) + on-chain check  
6. **Hermes tools** — thin wrappers  
7. **Tests** — unit + at least one live proof before “done”

If it can’t do **proof + tests**, it is not shippable.

### Signing boundary (non-negotiable)

- Agent **never** sees the owner 24-word seed or password  
- Core unlocks / session material only  
- Plugins request sign-off through core policy  
- Destructive ops default to `confirm=True` required  

---

## Phases

### Phase 0 — Plugin seam
Thin extension layer in standalone Vida. No new chain yet.

- `VidaPlugin` protocol  
- `PluginRegistry`  
- `PolicyRequest` / allow-deny-needs_approval  
- Dummy plugin that registers and is policy-checked  
- Tests for discovery + policy gate  

**Exit:** `vida.plugins` importable; tests green; Kaspa behavior unchanged.  
**Status:** DONE

### Phase 1 — TAO (infrastructure first → then identity/balance)
**Do not derive addresses until rails exist.**

1. **T1.0 Infrastructure (DONE)** — config, client interface + mock, account schema/store, plugin skeleton; `provision_from_seed` blocked  
2. **T1.1 Live client** — Substrate RPC `health()`  
3. **T1.2 Owner derivation** — seed → SS58, encrypted at rest  
4. **T1.3–T1.4** — balance + proof doc  

**Exit (full):** live health + owner-provisioned balance proof; no stake yet.

### Phase 1B — TAO act (policy-gated stake)
Agent-useful TAO actions under the leash.

- Policy: max TAO/tx, max TAO/day, allowed actions, optional subnet allowlist  
- `delegate` / `undelegate` (and transfer if ready)  
- FULL / HYBRID / COMMAND mapped to hotkey authority  
- One **live extrinsic** (delegate or undelegate) with hash  

**Exit:** agent can stake/unstake only inside caps; receipt published.

### Phase 2 — Unified portfolio
- Single status: KAS + free TAO + staked TAO (+ optional USD)  
- Hermes `vida_portfolio`  

### Phase 3 — Covenant offline module
- Types + compilers + simulate  
- Honest “not on-chain yet”  
- Watch [rusty-kaspa #1073](https://github.com/kaspanet/rusty-kaspa/issues/1073)  

### Phase 4 — Live covenants
- First real on-chain type (timelock → escrow → …)  
- Only after network accepts real covenant scripts  

### Phase 5 — Optional bridge / BTC
- KAS covenant-linked TAO policy only if both sides real  
- BTC plugin as separate rail  

---

## What we will not do

- Wait on covenants to start TAO  
- Ship mock-only TAO as “production”  
- Merge broken `kaspa-suite` TAO client without a live pass  
- Promise unbreakable on-chain budgets before covenants work  
- Give any plugin the owner seed in agent context  

---

## Reuse from kaspa-suite (carefully)

| Asset | Use |
|-------|-----|
| `bittensor/wallet.py`, `client.py`, `staking.py` | Reference / fix, don’t copy blind |
| `hermes_tools/tao_tools.py` | Tool names + shapes |
| `docs/TAO_INTEGRATION_V2_PLAN.md` | Background; MVP is smaller than that plan |
| Covenant docs / blockers | Phase 3–4 only |

Standalone Vida release stays the product surface. kaspa-suite is a parts bin.

---

## Ticket list

See **[PLUGIN_TICKETS.md](./PLUGIN_TICKETS.md)** for Phase 0 / 1 / 1B build tickets.

---

## Success picture (6–12 months)

- Owner: one Vida vault, multiple chains  
- Agent: Hermes / OpenClaw / others spend or stake only inside sessions  
- Kaspa: micropayments proven  
- TAO: stake/transfer proven under policy  
- Covenants: live when Kaspa allows — upgrade soft policy to hard rules  
