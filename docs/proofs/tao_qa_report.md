# Vida TAO module — QA report (public)

**Date:** 2026-07-15 (refreshed)  
**Scope:** TAO plugin — unit tests, session security, live Finney health/plan  
**Constraints:** No production key modification; working-balance only

## Three-tier verdict

| Tier | Result |
|------|--------|
| **Keys-safe** | **PASS** — encrypted accounts; session excludes PQ; money tools session-only; no password kwargs; delete `enc_spend` fail-closed |
| **Open-source WIP** | **YES** — 14 modules, 62+ tests, Finney health + plan proven |
| **Ship-proud (process-path)** | **YES** — `scripts/ship_proud_gate.sh` green |

## Tests

| Suite | Count | Result |
|-------|-------|--------|
| `test_tao_infra.py` | 15 | OK |
| `test_tao_balance.py` | 3 | OK |
| `test_tao_derive.py` | 5 | OK |
| `test_tao_stake.py` | 13 | OK |
| `test_tao_session.py` | 5 | OK |
| `test_tao_p2p_optimizer.py` | 4 | OK |
| `test_tao_pq.py` | 5 | OK |
| `test_tao_robustness.py` | 14 | OK (incl. fail-closed `enc_spend`, optimize gates) |
| **Total** | **64** | **OK** |

## Security PoCs

| Check | Result |
|-------|--------|
| Money tools without session | **Rejected** |
| Delete `enc_spend` → load session | **Fail-closed** |
| Over `max_tao_per_tx` | **Rejected** |
| Wrong scope (stake under TRANSFER_ONLY) | **Rejected** |
| Wrong destination | **Rejected** |
| Zero/negative caps | **Rejected** |
| No `password` kwarg on tools | **Verified** |
| `confirm=False` on stake | **Rejected** |

## Live Finney

| Check | Result |
|-------|--------|
| Health | **ok** — Bittensor WSS, live block height |
| Optimize **plan** | **ok** — action `stake`, target uid 52, emission-based scoring |
| Account balance | ~0.0216 TAO free (demo wallet, nonce 3) |
| Optimize **execute** | Code path session-gated; live receipt deferred (needs owner password) |

## Residual

1. Session file theft = temporary signing power (software policy, not covenants).
2. PQ identity at rest only — Finney uses sr25519 on-chain.
3. Yield optimizer is heuristic MVP, not guaranteed APY.
4. Working-balance only; not a hardware wallet.
5. Host compromise still wins.

## Verdict

**TAO module is QA-green as open-source WIP (local).**  
Not ship-proud absolute (no covenants, session-file residual).  
Do **not** commit `data/`, session files, mnemonics, or passwords.