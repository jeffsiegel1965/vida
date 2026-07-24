# AGENTS.md — Vida Project Context

This file is the single source of truth for any AI agent working on the Vida codebase.
Read this at the start of every session. Update it when you discover something new.

## Identity

You are working on **Vida** — an agent-compatible wallet for Kaspa (KAS) and Bittensor (TAO).
You are not building a product. You are building infrastructure that agents use.

## Architecture

```
Owner ─── grants session caps ───→ Vida Kernel
                                       │
                          ┌────────────┼────────────┐
                          │            │            │
                     Kaspa core    TAO plugin   Covenant
                     (send/recv)  (stake/swap)  (TN10 RPC)
                          │            │            │
                          └────────────┼────────────┘
                                       │
                                  Agent tools
                          (orchestrator.py / MCP server)
                                       │
                                  LLM agent
```

## Key Files

| File | Purpose |
|------|---------|
| `vida/secure_wallet.py` | Production wallet. AES-256-GCM, scrypt KDF, session files. |
| `vida/wallet.py` | LEGACY wallet. Plaintext keys. Only for testing. |
| `vida/transactions.py` | Real Kaspa transaction building/signing/broadcasting. |
| `vida/agents/orchestrator.py` | Agent loop: goal → plan → execute → report. |
| `vida/agents/staking_optimizer.py` | LLM-powered agent (K2.5 via Zyloo). |
| `vida/agents/tool_schema.py` | OpenAI-compatible function calling schema. |
| `vida/agents/verification.py` | 5-level verification ladder (L1-L5). |
| `vida/plugins/covenant/tools.py` | 17 Hermes covenant tools. |
| `vida/plugins/covenant/kaspa_rpc.py` | Zero-dependency Kaspa REST API client. |
| `vida/plugins/covenant/silverscript/` | SilverScript contract sources. |
| `scripts/vida_mcp_server.py` | MCP server (12 tools, 2 resources). |
| `tests/test_kaspa_rpc_integration.py` | Live integration tests against testnet-10. |

## Rules

1. **Never store API keys in code.** Use env vars: `ZYLOO_API_KEY`, `VIDA_DEV_FUND`.
2. **Never push without approval.** All changes go through hostile QA first.
3. **Every tool must return `{"ok": bool, ...}`.** No exceptions.
4. **No tool aliases.** If a tool name says "balance", it must return a balance.
5. **Financial operations must use L1-L2 verification.** Never L4 (model judge) for money.
6. **The legacy wallet (`wallet.py`) is for testing only.** Always use `secure_wallet.py` for real funds.
7. **Self-custody means self-responsibility.** No marketing claims about "agent economy."

## What's Real vs Not

| Capability | Status |
|-----------|--------|
| Kaspa send/receive via session | ✅ Mainnet |
| TAO stake/unstake via session | ✅ Finney |
| Agent loop (LLM → plan → execute) | ✅ Working (K2.5) |
| MCP server | ✅ Working (12 tools + 2 resources) |
| Single-process session cap enforcement | ✅ RLock + atomic reserve/commit (Jul 24, 2026) |
| Cross-process session cap enforcement | ✅ fcntl.flock + authoritative disk counter (Jul 24, 2026) |
| Covenant pot planning | ✅ Offline |
| Covenant deploy (on-chain) | ⚠️ TN10 only, gated |
| SilverScript quine spend | ⚠️ Compiled, spend blocked (tooling gap) |
| Agent negotiation | ❌ Stripped, needs redesign |
| Mainnet covenants | ❌ Waiting for Kaspa Toccata |

## Common Mistakes

- **Don't alias tools.** Previous auditors found `wallet_balance` → `covenant_status` — never do this.
- **Don't hardcode API keys.** The `***` placeholder in the agent loop was a real bug.
- **Don't forget the verification ladder.** Every financial operation needs L1 or L2 verification.
- **Don't push marketing docs.** The `docs/brand/` directory was removed for this reason.
- **Don't claim "agent economy"** without agent-to-agent commerce.
- **NaN bypass: guard with `math.isfinite` BEFORE any comparison.** `float('nan') < 0` is `False`, so amount guards using only `< <= >` let NaN through. Already found in commerce fees, DEX treasury, and oracle bond registration. Every new amount validation must check `isfinite` first, then `< 0`, then threshold.
- **Session counter writes need TWO locks.** An in-process `RLock` for threads, PLUS an `fcntl.flock` on `<session>.lock` for cross-process. The persistent file is the authority — read the counter from disk under the lock rather than trusting memory. Never merge via `max()` — a fresh process starts at 0.0 and will persist a lower total, erasing sibling processes' spends.
- **Concurrent file writes need per-PID temp names.** Two processes writing to the same `<name>.tmp` race on `replace()`. Use `<name>.<pid>.tmp` instead.

## Past Decisions

- kascov-lab dependency removed (Jul 18, 2026). Replaced with `kaspa_rpc.py` (REST API).
- Negotiation protocol stripped (Jul 18, 2026). Premature — needs redesign.
- TN12 migration reverted (Jul 18, 2026). TN12 doesn't exist as a public network.
- Quine deployed on TN10 (Jul 18, 2026). Covenant `6d58b529...`. Spend blocked by tooling.
- **Session daily-cap race fixed** (Jul 24, 2026). `transactions.send()` checked caps at ~line 227 and recorded at ~line 342 with no lock across the UTXO/sign/broadcast gap. 20 concurrent threads each read the same stale counter — measured 200 KAS against a 100 KAS cap. Fixed with atomic `reserve_session_spend()` under RLock + release-on-failure.
- **Cross-process cap enforcement added** (Jul 24, 2026). The RLock only serialises threads in one process. Two agent processes sharing a session file both passed the daily cap — measured 120 KAS against 100 KAS. Fixed with `fcntl.flock` on `<session>.lock` and authoritative on-disk counter. Two follow-on bugs found and fixed during verification: stale `max()` merge losing writes, and shared temp-file collision. Tests at `tests/test_session_cap_race.py` (in-process, 13 tests) and `tests/test_cross_process_cap.py` (subprocess, 9 tests).
- **NaN comparison bypass is a cross-repo vulnerability** (Jul 24, 2026). `float('nan') < X` is always False. Every fee/amount guard using only `< <= >` accepts NaN: commerce fees (NaN → ENTERPRISE zero-fee tier), DEX treasury (NaN poisons accumulator permanently), oracle bond (NaN registers with zero stake). Fix pattern: `math.isfinite(value)` then `int(value)` before any comparison. Regression tests in each repo.
- **Oracle circuit breaker was dead across restarts** (Jul 24, 2026). `oracle.py` wrote `{"last_price": {...}}` but read the whole object back, keying the dict by the literal string `"last_price"` — `pair in self._last_price` was always False. Measured: a 44.4% jump was ACCEPTED after restart while the README claimed state was "persisted to disk."
- **Oracle test suite shared state with the live service** (Jul 24, 2026). `Oracle()` defaults to `state_dir="~/.vida-oracle"` — tests read and WROTE the real circuit breaker. Masked until the breaker persistence fix exposed it. Now isolated via `conftest.py` redirecting HOME to `tmp_path`.

## Memory

This file is read at the start of every session. Update it when you discover:
- A new bug pattern
- A tool that doesn't return `ok`
- An API change in Kaspa or Bittensor
- A decision that future agents should know about