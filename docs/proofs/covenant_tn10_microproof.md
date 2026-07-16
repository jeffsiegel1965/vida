# Covenant TN10 micro-proof

**When:** 2026-07-16
**Network:** testnet-10
**Tooling:** `kascov-lab` (rusty-kaspa #1074 WASM) + JS bridge (`covenant_fund_agent_pot.js`)
**Key:** deployer testnet wallet (860 KAS balance)

## Lifecycle 1 (2026-07-14 — kascov-lab `98a4ccd`)

| Step | Tx |
|------|-----|
| **Genesis** | `42f13ec89e5c996091c5be0f7d7cb5c2e9cb1a18c4b7de2f7e723950a77c34fe` |
| **Transition** | `bf0d2c826da11f1b426dccbe61895cf15d18700e4ad4caf4e15e3674f2a511ef` |
| **Burn** | `6dbe577adb05afd4afc34c31475b558d52adee78323a2ebf44f72260993266d6` |

Covenant ID: `9fe45342dc674e7cb2fd70061cb51746d47e4fba228a5c0861a8b6748790204f`

## Lifecycle 2 (2026-07-16 — kascov-lab #1074 WASM + our key)

| Step | Tx |
|------|-----|
| **Genesis (JS bridge)** | `c003393d327bed876f48343fc99953e32b9d845cc5668e4ca6095b68d3e0ab0e` |
| **Genesis (kascov-lab)** | `d4d75348cdc2a9c5449cadec034b8bf1319c9a8dc33657338d1f4105583d97ac` |
| **Transition #1** | `526d6667dc4a9658732a2a2c24416ae4570c11f8509172c4198dae72bd11c328` |
| **Burn** | `152f7a7a744d64f461c5d51c7ae7786b96ccaec9febd4ef5abb7fc5b4e1d594f` |

Covenant ID: `d54c7568b9c273f08e089003f7869c7c1abbcc567df334f4b002dd00df7fdaac`

## Lifecycle 3 (2026-07-16 — kascov-lab #1074 WASM, full path)

| Step | Tx |
|------|-----|
| **Genesis** | `aac176cfd71e264af907220c58588128479767ac22fc878588bae6c0ab32069f` |
| **Transition #1** | `f0884a747cd3c741f584b3a9dbc52f6c2c8c9bc8ff856f8a37d8a34227ab02af` |
| **Burn** | `927efe1285516643af2c5dae3ebbae60347198bc4be35d3591c0860219acd4e3` |

Covenant ID: `04420a33299363e1749bbd18ca082703bef54accc2a62a5d948a8c90af466a7d`

## Status

| Gate | Status |
|------|--------|
| Post-Toccata WASM client | ✅ #1074 WASM built + loaded |
| computeBudget round-trip | ✅ PASS (Node, WASM/JS) |
| On-chain covenant lifecycle | ✅ 2x proven (genesis → transition → burn) |
| Vida plugin live deploy/spend | ⚠️ JS bridge works; Python `lab_client.py` timeout bug |
| Agent hard caps on-chain | ❌ (design in progress) |
| PyPI `kaspa` Python package | ❌ Still drops `computeBudget` on `to_dict` |

## Env setup for live operations

```bash
export VIDA_COVENANT_LIVE=1
export VIDA_KASCOV_KEY=/tmp/vida-covenant-key.hex
export VIDA_KASCOV_LAB=/home/jeff-siegel/.hermes/projects/toolchain/kascov/target/release/kascov-lab
export VIDA_KASPA_WASM=/home/jeff-siegel/.hermes/projects/toolchain/rusty-kaspa-pr1074/wasm/nodejs/kaspa
```

## Blockers

1. **JS spend script** — covenant binding hash mismatch on transition spends. Genesis works, spend fails with "covenants error: input #0 and outputs ... do not correspond to the expected genesis hashing". The `covenant_spend_agent_pot.js` needs the covenant binding logic fixed for transition spends.
2. **Python bridge timeout** — `lab_client.py` `fund_agent_pot()` times out because the Node subprocess hangs after completion. Direct Node invocation works.
3. **PyPI Python SDK** — still drops `computeBudget` on serialize. All working paths go through Node #1074 WASM or kascov-lab binary.