# Vida Wallet

**Self-custodial agent wallet for Kaspa and Bittensor. Free. MIT.**

> *"Not vapor. A thoughtfully engineered, security-conscious agent wallet
> that solves a real problem."* — Grok independent review, July 2026

Vida gives agents controlled access to KAS and TAO — session-gated,
spend-capped, host-bound — without handing over full custody.

## What makes it different

**Session-gated access** is the core. Owner creates time-boxed,
host-bound, spend-capped session files. Agents get scoped permissions
without ever seeing the master password or seed.

**TAO is an intelligence rail, not just a staking asset.** Most wallets
treat Bittensor as another token to hold. Vida treats it as a
decentralized intelligence marketplace that agents can actually use.
Agents discover subnet services by capability, pay via x402 within
session budgets, and consume results autonomously — all while the owner
controls how much can be spent and on which subnets.

**Dual-rail architecture.** Kaspa for fast settlement and micropayments.
TAO for intelligence and compute markets. One custody plane, one policy
plane. Clean separation of concerns.

**Agent-first, not consumer.** CLI and MCP. No browser extension.

## What it does

### Kaspa

| Capability | Network |
|---|---|
| Send / receive | ✅ Mainnet |
| Covenant deploy & spend | ✅ Testnet-10 |
| Escrow | ✅ Testnet-10 |
| Payment channels | ✅ Testnet-10 |

### Bittensor (TAO)

| Capability | Status |
|---|---|
| Stake / unstake | ✅ Finney |
| Session-gated access | ✅ |
| Subnet capability discovery | ✅ — find subnets by service type |
| Autonomous service consumption | ✅ — discover → pay → consume in one call |
| Quality-based subnet routing | ✅ — track performance, route to best |
| Session-scoped subnet budgets | ✅ — cap TAO spend per session |
| x402 micropayments | ✅ |
| Agent registration | ✅ |

## How agents use TAO subnets

```python
from vida.plugins.tao.gateway import AutonomousGateway, SubnetBudget

# Owner sets a session budget — 0.1 TAO total for subnet services
budget = SubnetBudget(max_spend_tao=0.1, max_queries=50)

# Agent gets a gateway with that budget
gateway = AutonomousGateway(budget=budget, wallet_id="agent-1")

# Agent asks: "I need LLM inference for this prompt"
result = gateway.consume(
    capability="llm",
    prompt="Summarize this contract clause...",
    max_cost_tao=0.005,
)

# Vida handles discovery → quality routing → payment → consumption
# Returns the subnet's response + which subnet was used + cost + latency
print(result["subnet"])     # "Inference (LLM) — netuid 19"
print(result["data"])       # The LLM's response
print(result["cost_tao"])   # 0.005 TAO
print(result["latency_ms"]) # 234ms
```

The agent never sees the master key. The owner controls the budget.
The subnet marketplace routes queries to the best-performing subnets.

## Security

**Strong design for the threat model. Honest about limitations.**

- AES-256-GCM encryption at rest, scrypt KDF (n=2^17 / ~128 MiB), 24-word BIP39
- Sessions: machine key, host fingerprint binding, tamper-evident limits
- Verification ladder: deterministic proof required for financial operations
- Model-judge blocked for money movement

**Documented limitations (not hidden):**
- Session limits are policy, not pure cryptography — treat session files as secrets
- Python cannot reliably wipe keys from RAM
- Covenants/escrow/channels still testnet-10; mainnet gated on external toolchain
- Pre-1.0 — only latest tag gets security fixes
- No third-party formal audit yet (planned)

## Architecture

```
Owner → creates session (spend cap, expiry, subnet budget, allowed ops)
         │
    Vida Kernel
         │
    ┌────┼────┐
  Kaspa  TAO  Covenant
         │
    Subnet Gateway (discovery + quality routing + x402 payments)
         │
    MCP Server (12 tools + 2 resources)
```

## MCP Server

Agents connect through standard MCP. Tools include: balances, send KAS,
stake/unstake TAO, discover subnets, consume subnet services,
covenant deploy/spend, escrow, channels.

```bash
python3 scripts/vida_mcp_server.py
```

## Tests

246 tests covering wallet security, transactions, TAO operations,
subnet gateway, covenant deployment, escrow, channels.

```bash
python3 -m pytest tests/ -q
```

## Free. Everything. Forever.

No fees on any operation. No commercial license. No royalties.
The wallet is the on-ramp.

## License

MIT. All code in this repository.