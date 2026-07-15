# Vida TAO module — QA report (public)

**Date:** 2026-07-14  
**Scope:** Unit tests + Hermes tool session gates + live Finney health/balance smoke  
**Constraints:** No production key modification; working-balance only

## Summary verdict

| Area | Result |
|------|--------|
| All `tests/test_tao*.py` | **PASS — 50/50** |
| HERMES_TOOLS money tools reject missing session | **PASS** |
| Live Finney status/balance (provisioned demo wallet) | **PASS** (RPC healthy) |
| Session grant excludes PQ secret | **PASS** |
| Overall | **PASS** |

## Unit tests

```bash
# from repo root, with TAO deps installed
python -m unittest discover -s tests -p 'test_tao*.py'
# or run each file:
python tests/test_tao_infra.py
python tests/test_tao_balance.py
python tests/test_tao_derive.py
python tests/test_tao_stake.py
python tests/test_tao_session.py
python tests/test_tao_p2p_optimizer.py
python tests/test_tao_pq.py
```

| Suite | Count | Result |
|-------|-------|--------|
| `test_tao_infra.py` | 15 | OK |
| `test_tao_balance.py` | 3 | OK |
| `test_tao_derive.py` | 5 | OK |
| `test_tao_stake.py` | 13 | OK |
| `test_tao_session.py` | 5 | OK |
| `test_tao_p2p_optimizer.py` | 4 | OK |
| `test_tao_pq.py` | 5 | OK |
| **Total** | **50** | **OK** |

## Tool policy

- Money tools (`delegate`, `undelegate`, `transfer`, execute `optimize`) require `VIDA_TAO_SESSION` / `session_path`.
- **No password kwargs** on Hermes tools (owner scripts only).
- Read-only: `status`, `balance`, optimize plan.

## Live smoke (Finney)

Public receipt chain (working-balance demo; not a custody recommendation):

| Action | Evidence |
|--------|----------|
| Stake | extrinsic `0xdc2cd822…119c62c0` (see `tao_phase1b_extrinsic.md`) |
| Agent session stake | `0x44c9b9a5…7ca39a87` |
| P2P transfer | `0xa0915ab9…011251ee` |

## Residual risks (not test failures)

1. Session file theft = signing power (software policy, not covenants).  
2. PQ identity is **at rest only** — Finney still **sr25519** on-chain.  
3. Yield optimizer is **heuristic MVP**, not guaranteed APY.  
4. Working-balance only; not a hardware wallet.  
5. Host compromise still wins.

## Verdict

**TAO module is QA-green for open-source push of code + tests + public proofs.**  
Do **not** commit `data/`, session files, mnemonics, or passwords (gitignored).
