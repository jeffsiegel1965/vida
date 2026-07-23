# Vida Wallet

**Self-custodial wallet for Kaspa and Bittensor. Free. MIT.**

Vida Wallet gives you and your agents full control over digital assets
on two networks — no intermediaries, no fees, no custody.

## What it does

| Capability | Kaspa | Bittensor |
|---|---|---|
| Send / receive | ✅ Mainnet | ✅ Finney |
| Session-based agent access | ✅ | ✅ |
| Covenant deploy & spend | ✅ Testnet-10 | — |
| Escrow | ✅ Testnet-10 | — |
| Payment channels | ✅ Testnet-10 | — |
| Stake / unstake | — | ✅ |
| Subnet queries | — | ✅ |
| Agent registration | — | ✅ |
| x402 facilitator | — | ✅ |

## How agents use it

Agents connect through encrypted session files with scoped permissions
and spend limits. No API keys needed. No delegation of custody.

```
Owner → creates session (spend cap, expiry, allowed operations)
         │
    Vida Kernel
         │
    ┌────┼────┐
  Kaspa  TAO  Covenant
```

## Architecture

- **`vida/secure_wallet.py`** — AES-256-GCM encrypted wallet with scrypt KDF
- **`vida/transactions.py`** — Real Kaspa transaction building, signing, broadcasting
- **`vida/plugins/tao/`** — Bittensor staking, subnet gateway, x402 payments
- **`vida/plugins/covenant/`** — SilverScript compilation, covenant deploy/spend, escrow, channels
- **`vida/agents/`** — Agent loop: goal → plan → execute → verify

## MCP Server

12 tools + 2 resources. Agents can: check balances, send KAS, stake TAO,
query subnets, deploy covenants, manage escrow, and more — all through
the Model Context Protocol.

```bash
python3 scripts/vida_mcp_server.py
```

## Free. Everything. Forever.

No fees on any operation. No commercial license. No royalties.
The wallet is the on-ramp. Vida Commerce (separate project) is
where monetization happens through contract negotiation.

## Tests

282 tests covering wallet security, transaction building, TAO operations,
covenant deployment, escrow, payment channels, and agent orchestration.

```bash
python3 -m pytest tests/ -q
```

## License

MIT. All code in this repository.