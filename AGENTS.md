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
| `vida/plugins/covenant/kaspa_rpc.py` | SDK-based RPC client (Resolver auto-discovery, wRPC). |
| `vida/plugins/covenant/silverscript/` | SilverScript contract sources. |
| `scripts/vida_mcp_server.py` | MCP server (12 tools, 2 resources). |
| `vida/agents/memory.py` | Persistent cross-session agent memory. |

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
| TAO stake/unstake via session | ✅ Finney (mainnet, pre-dTAO) |
| Agent loop (LLM → plan → execute) | ✅ Working (K2.5) |
| MCP server | ✅ Working (12 tools + 2 resources) |
| Covenant pot planning | ✅ Offline |
| Covenant deploy (on-chain) | ⚠️ TN10 only, gated |
| SilverScript quine spend | ⚠️ Compiled, spend blocked (tooling gap) |
| Agent negotiation | ✅ Rebuilt — templates + memory + subscriptions |
| TAO subnet marketplace | ✅ Discovery + query tools (mainnet, pre-dTAO) |
| Mainnet covenants | ❌ Waiting for Kaspa Toccata |
| dTAO readiness | ✅ Code structured for update when deployed |

## Common Mistakes

- **Don't alias tools.** Previous auditors found `wallet_balance` → `covenant_status` — never do this.
- **Don't hardcode API keys.** The `***` placeholder in the agent loop was a real bug.
- **Don't forget the verification ladder.** Every financial operation needs L1 or L2 verification.
- **Don't push marketing docs.** The `docs/brand/` directory was removed for this reason.
- **Don't claim "agent economy"** without agent-to-agent commerce.

## Past Decisions

- kascov-lab dependency removed (Jul 18, 2026). Replaced with REST API.
- REST API replaced with official Kaspa Python SDK (Jul 19, 2026). `kaspa_rpc.py` now uses `RpcClient` + `Resolver` (wRPC, PNN auto-discovery).
- Negotiation protocol stripped (Jul 18, 2026). Premature — needs redesign.
- TN12 migration reverted (Jul 18, 2026). TN12 doesn't exist as a public network.
- Quine deployed on TN10 (Jul 18, 2026). Covenant `6d58b529...`. Spend blocked by tooling — now unblocked by SDK integration.

## Memory

This file is read at the start of every session. Update it when you discover:
- A new bug pattern
- A tool that doesn't return `ok`
- An API change in Kaspa or Bittensor
- A decision that future agents should know about