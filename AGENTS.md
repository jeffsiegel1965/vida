# AGENTS.md — Vida Project Context

This file is the single source of truth for any AI agent working on the Vida codebase.
Read this at the start of every session. Update it when you discover something new.

## Task Routing

If you are asked to do a task, find the row below and read the file listed first.
If no row matches, read the README.md and then the relevant module.

| If you need to... | Read this first |
|-------------------|-----------------|
| Send / receive KAS | `vida/transactions.py` + `vida/secure_wallet.py` |
| Deploy a covenant | `vida/plugins/covenant/sdk_integration.py` + `silverscript/` |
| Spend from a covenant | `vida/plugins/covenant/pot_spend.py` |
| Open an escrow | `vida/plugins/covenant/escrow.py` |
| Create a payment channel | `vida/plugins/covenant/channels.py` (KCC-0402 mode) |
| Negotiate with an agent | `vida/agents/negotiation/` |
| Check agent memory | `vida/agents/memory.py` |
| Stake / unstake TAO | `vida/plugins/tao/substrate_client.py` |
| Discover subnet services | `vida/plugins/tao/subnet_marketplace.py` |
| Query a subnet | `vida/plugins/tao/subnet_client.py` |
| Auto-pay a subnet API | `vida/plugins/tao/x402.py` |
| Verify a transaction | `vida/agents/verification.py` |
| Run the MCP server | `scripts/vida_mcp_server.py` |
| Check covenant status | `vida/plugins/covenant/tools.py` |
| Review CoAMM integration | `docs/coamm-integration.md` |
| Review KCC ecosystem specs | `docs/kccs.md` |
| Review x402 spec gaps | `docs/x402-spec-gaps.md` |
| Post to X (milestone) | `scripts/post_milestone.sh` |
| Post to X (proof card) | `scripts/post_proof_card.py` |
| Post to X (weekly digest) | `scripts/post_weekly_digest.sh` |
| Generate a proof card image | `scripts/post_proof_card.py` |
| Run the pipeline test film | `scripts/run_pipeline.py` |
| Fix CI (ruff) | `ruff check --fix --unsafe-fixes . && ruff format .` |
| Check audit status | `AUDIT.md` |
| Read the full spec | `README.md` |

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
                                       │
                          Subnet gateway fees (0.05%)
```

## Key Files

### Core wallet
| File | Purpose |
|------|---------|
| `vida/secure_wallet.py` | Production wallet. AES-256-GCM, scrypt KDF, session files. |
| `vida/wallet.py` | LEGACY — runtime guard (`VIDA_LEGACY_WALLET_ALLOWED=1`). Testing only. |
| `vida/transactions.py` | Kaspa transaction building/signing/broadcasting. |
| `docs/coamm-integration.md` | CoAMM (Zealous Swap) integration plan — design doc, not yet built. |
| `docs/x402-spec-gaps.md` | x402 spec gaps found by Rust implementer — affects Vida's x402.py |

### Agent layer
| File | Purpose |
|------|---------|
| `vida/agents/orchestrator.py` | Agent loop: goal → plan → execute → report. 19 tools. |
| `vida/agents/staking_optimizer.py` | K2.5-powered agent executor. |
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
| `vida/plugins/covenant/escrow.py` | Agent-to-agent escrow (release/refund/resolve). |
| `vida/plugins/covenant/channels.py` | Payment channels (KCC-0402 + bidirectional). 36 tests. |
| `vida/plugins/covenant/fees.py` | Fee schedules (KAS + TAO), addresses. |
| `vida/plugins/covenant/sdk_integration.py` | SDK-based covenant deploy/spend. |
| `vida/plugins/covenant/silverscript/` | SilverScript contract sources (quine, agent pot). |

### TAO plugin
| File | Purpose |
|------|---------|
| `vida/plugins/tao/substrate_client.py` | Finney chain connection. `add_stake`, `remove_stake`, `transfer`. |
| `vida/plugins/tao/subnet_marketplace.py` | Registry of 9 subnets with pricing, API endpoints, service types. |
| `vida/plugins/tao/subnet_client.py` | Agent purchase workflow: resolve → pay (stake) → query API. |
| `vida/plugins/tao/tools.py` | 9 Hermes tools (balance, delegate, subnets, info, query). |
| `vida/plugins/tao/x402.py` | HTTP 402 auto-pay for subnet APIs. |

### Tests
| File | Count |
|------|-------|
| `tests/test_negotiation.py` | 27 |
| `tests/test_agent_memory.py` | 9 |
| `tests/test_tao_subnet_marketplace.py` | 10 |
| `tests/test_tao_*.py` | 62 (staking, sessions, robustness, PQ) |
| `tests/test_escrow.py` | 17 |
| `tests/test_channels.py` | 36 |
| `tests/test_x402.py` | 7 |
| `tests/test_kaspa_rpc_integration.py` | 6 (live testnet-10) |
| **Total** | **221** |

## Rules

1. **Never store API keys in code.** Use env vars: `ZYLOO_API_KEY`, `VIDA_FEE_ADDRESS`, `VIDA_DONATION_ADDRESS`.
2. **Verify everything against live chains.** Don't repeat stale claims. Test on mainnet when possible.
3. **Every tool must return `{"ok": bool, ...}`.** No exceptions.
4. **No tool aliases.** If a tool name says "balance", it must return a balance.
5. **Financial operations must use L1-L2 verification.** `@require_l1_spend` enforces this. Never L4 for money.
6. **The legacy wallet (`wallet.py`) is testing-only.** `VIDA_LEGACY_WALLET_ALLOWED=1` required. Use `secure_wallet.py` for real funds.
7. **Self-custody means self-responsibility.** No marketing claims.
8. **Do not push infra scripts to public repo.** Review before committing.

## What's Real vs Not

| Capability | Status | Detail |
|-----------|--------|--------|
| KAS send/receive | ✅ Mainnet | Session-gated, wRPC via Kaspa SDK |
| TAO stake/unstake | ✅ Finney | Session-gated, pre-dTAO (verified Jul 19) |
| TAO subnet marketplace | ✅ Finney | 9 subnets, discover + pay + query |
| x402 auto-pay | ✅ Built | HTTP 402, auto-pay subnet APIs |
| Subnet gateway fees | ✅ Built | 0.05% per query, free tier, TAO fee address |
| Payment channels | ✅ Built | KCC-0402 + bidirectional, 36 tests |
| Escrow covenants | ✅ Built | 3 paths, 17 tests, fees baked in |
| Multisig (Bittensor v11) | ✅ Built | M-of-N, 17 tests |
| Agent orchestrator | ✅ Working | K2.5-powered, 19 tools |
| Agent memory | ✅ Working | Deals, profiles, subnets, conviction voting |
| Agent negotiation | ✅ Working | 3 templates, 2 strategies, volume discounts |
| Subscriptions | ✅ Working | Recurring pots, 15% discount |
| MCP server | ✅ Working | 12 tools, 2 resources |
| Verification ladder | ✅ Working | L1-L5, `@require_l1_spend` enforced |
| Kaspa covenants (SilverScript) | ✅ Mainnet | Toccata active (DAA 490M) |
| Covenant v1 transactions | ✅ Unblocked | compute_budget=10 applied to pot_spend.py. smartgoo confirmed Jul 21. |
| Covenant deploy | ⚠️ Tested on TN10 | Mainnet ready, needs funded key |
| dTAO deployment | ⏳ Not on Finney yet | Pre-dTAO is correct. Code structured for update. |

## Common Mistakes

- **Don't claim chain state without checking.** Always verify against live chain data.
- **Don't alias tools.** `wallet_balance` → `covenant_status` was caught by auditors.
- **Don't hardcode API keys.** The `***` placeholder in the agent loop was a real bug.
- **Don't forget the verification ladder.** `@require_l1_spend` is mandatory for financial ops.
- **Don't push marketing docs.** The `docs/brand/` directory was removed.
- **Don't claim "agent economy"** without agent-to-agent commerce. (We now have negotiation.)
- **Don't push infra scripts to public repo.** Check `git status` before committing.

## Past Decisions

- kascov-lab dependency removed (Jul 18, 2026). Replaced with REST API.
- REST API replaced with Kaspa Python SDK (Jul 19, 2026). wRPC + Resolver.
- Negotiation protocol rebuilt (Jul 19, 2026). Templates, memory, subscriptions. 27 tests.
- TN12 migration reverted (Jul 18, 2026). TN12 doesn't exist as public network.
- Toccata status corrected (Jul 19, 2026). Was listed as "not on mainnet" — DAA 490M proves it's active.
- Fee/donation addresses separated (Jul 19, 2026). `VIDA_FEE_ADDRESS` / `VIDA_DONATION_ADDRESS`.
- KCC-0402 channel alignment (Jul 20, 2026). BIP340 vouchers, 36 tests.
- STE100 README rewrite (Jul 20, 2026). No marketing language.
- Social preview optimized: 1.1MB PNG → 202KB JPEG (Jul 20, 2026).
- Covenant v1 compute_budget fix (Jul 21, 2026). smartgoo: set tx.version=1, inp.compute_budget=10 after create_transaction(). Applied to pot_spend.py.

## Memory

Update this file when you discover:
- A new bug pattern or recurring mistake
- A tool that doesn't return `ok`
- An API change in Kaspa or Bittensor
- A decision future agents should know about