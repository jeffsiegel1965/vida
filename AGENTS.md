# AGENTS.md — Vida Project Context

This file is the single source of truth for any AI agent working on the Vida codebase.
Read this at the start of every session. Update it when you discover something new.

## Identity

You are working on **Vida** — a wallet built for AI agents on Kaspa (KAS) and Bittensor (TAO).
Vida gives agents constrained access to spend, stake, negotiate, and consume subnet services.
You hold the keys. You set the limits. Revoke by deleting a file.

## Architecture

```
Owner ─── grants session caps ───→ Vida Kernel
                                       │
                          ┌────────────┼────────────┐
                          │            │            │
                     Kaspa core    TAO plugin   Covenant
                   (send/recv)   (stake/pay)   (SilverScript)
                   wRPC + SDK    Finney        mainnet + TN10
                   mainnet       pre-dTAO      Toccata active
                          │            │            │
                          └────────────┼────────────┘
                                       │
                                  Agent tools
                          (orchestrator / MCP server)
                                       │
                                  LLM agent (K2.5)
                                       │
                               Agent memory + negotiation
                          (deals, profiles, subnets, sessions)
```

## Key Files

### Core wallet
| File | Purpose |
|------|---------|
| `vida/secure_wallet.py` | Production wallet. AES-256-GCM, scrypt KDF, session files. |
| `vida/wallet.py` | LEGACY — runtime guard (`VIDA_LEGACY_WALLET_ALLOWED=1`). Testing only. |
| `vida/transactions.py` | Kaspa transaction building/signing/broadcasting. |

### Agent layer
| File | Purpose |
|------|---------|
| `vida/agents/orchestrator.py` | Agent loop: goal → plan → execute → report. 16 tools. |
| `vida/agents/staking_optimizer.py` | LLM-powered agent executor (K2.5 via Zyloo). |
| `vida/agents/tool_schema.py` | OpenAI-compatible function calling schema. |
| `vida/agents/verification.py` | 5-level verification ladder. `@require_l1_spend` enforces txid on financial ops. |
| `vida/agents/memory.py` | Persistent cross-session agent memory (deals, counterparties, subnets, KV). |
| `vida/agents/negotiation/` | Agent-to-agent negotiation: templates, strategies, subscriptions, volume discounts. |

### Kaspa plugin
| File | Purpose |
|------|---------|
| `vida/plugins/covenant/kaspa_rpc.py` | wRPC via Kaspa SDK + Resolver. Structured errors. REST API fallback. |
| `vida/plugins/covenant/tools.py` | 17 covenant tools (status, plan, fees, kascov, validate). |
| `vida/plugins/covenant/pot_spend.py` | Spend policy enforcement. Real `spend_to_agent()` (build→sign→submit). |
| `vida/plugins/covenant/fees.py` | Fee and donation addresses. Separate, configurable via env vars. |
| `vida/plugins/covenant/sdk_integration.py` | SDK-based covenant deploy/spend. |
| `vida/plugins/covenant/silverscript/` | SilverScript contract sources (quine, agent pot). |

### TAO plugin
| File | Purpose |
|------|---------|
| `vida/plugins/tao/substrate_client.py` | Finney chain connection. `add_stake`, `remove_stake`, `transfer`. |
| `vida/plugins/tao/subnet_marketplace.py` | Registry of 9 subnets with pricing, API endpoints, service types. |
| `vida/plugins/tao/subnet_client.py` | Agent purchase workflow: resolve → pay (stake) → query API. |
| `vida/plugins/tao/tools.py` | 9 Hermes tools (balance, delegate, subnets, info, query). |

### Tests
| File | Count |
|------|-------|
| `tests/test_negotiation.py` | 27 |
| `tests/test_agent_memory.py` | 9 |
| `tests/test_tao_subnet_marketplace.py` | 10 |
| `tests/test_tao_*.py` | 62 (staking, sessions, robustness, PQ) |
| `tests/test_kaspa_rpc_integration.py` | 6 (live testnet-10) |
| `tests/test_covenant_scaffold.py` | 39 |
| `tests/test_covenant_robustness.py` | 3 |
| **Total** | **156** |

## Rules

1. **Never store API keys in code.** Use env vars: `ZYLOO_API_KEY`, `VIDA_FEE_ADDRESS`, `VIDA_DONATION_ADDRESS`.
2. **Verify everything against live chains.** Don't repeat stale claims. Test on mainnet when possible.
3. **Every tool must return `{"ok": bool, ...}`.** No exceptions.
4. **No tool aliases.** If a tool name says "balance", it must return a balance.
5. **Financial operations must use L1-L2 verification.** `@require_l1_spend` enforces this. Never L4 for money.
6. **The legacy wallet (`wallet.py`) is testing-only.** `VIDA_LEGACY_WALLET_ALLOWED=1` required. Use `secure_wallet.py` for real funds.
7. **Self-custody means self-responsibility.** No marketing claims.

## What's Real vs Not

| Capability | Status | Detail |
|-----------|--------|--------|
| KAS send/receive | ✅ Mainnet | Session-gated, wRPC via Kaspa SDK |
| TAO stake/unstake | ✅ Finney | Session-gated, pre-dTAO (verified Jul 19) |
| TAO subnet marketplace | ✅ Finney | 9 subnets, discover + pay + query |
| Agent loop (LLM → plan → execute) | ✅ Working | K2.5-powered, 16 tools |
| Agent memory | ✅ Working | Deals, counterparties, subnets, KV, context |
| Agent negotiation | ✅ Working | 3 templates, 2 strategies, subscriptions, volume discounts |
| MCP server | ✅ Working | 12 tools + 2 resources |
| Verification ladder | ✅ Working | L1-L5, `@require_l1_spend` enforced |
| Kaspa covenants (SilverScript) | ✅ Mainnet | Toccata fork at DAA 389M, currently 490M |
| Covenant pot planning | ✅ Offline | Templates, policies, validation |
| Covenant deploy on mainnet | ⚠️ Need funded key | SDK tools work, mainnet accepts covenants |
| SilverScript quine spend | ⚠️ Partially blocked | BUILD + SIGN work, SUBMIT has REST API fallback |
| dTAO deployment | ⏳ Not on Finney yet | Pre-dTAO is correct. Code structured for update. |

## Common Mistakes

- **Don't claim chain state without checking.** Always verify against live chain data.
- **Don't alias tools.** `wallet_balance` → `covenant_status` was caught by auditors.
- **Don't hardcode API keys.** The `***` placeholder in the agent loop was a real bug.
- **Don't forget the verification ladder.** `@require_l1_spend` is mandatory for financial ops.
- **Don't push marketing docs.** The `docs/brand/` directory was removed.
- **Don't claim "agent economy"** without agent-to-agent commerce. (We now have negotiation.)

## Past Decisions

- kascov-lab dependency removed (Jul 18, 2026). Replaced with REST API.
- REST API replaced with Kaspa Python SDK (Jul 19, 2026). wRPC + Resolver.
- Negotiation protocol rebuilt (Jul 19, 2026). Templates, memory, subscriptions. 27 tests.
- TN12 migration reverted (Jul 18, 2026). TN12 doesn't exist as public network.
- Toccata status corrected (Jul 19, 2026). Was listed as "not on mainnet" — DAA 490M proves it's active.
- Fee/donation addresses separated (Jul 19, 2026). `VIDA_FEE_ADDRESS` / `VIDA_DONATION_ADDRESS`.

## Memory

Update this file when you discover:
- A new bug pattern or recurring mistake
- A tool that doesn't return `ok`
- An API change in Kaspa or Bittensor
- A decision future agents should know about