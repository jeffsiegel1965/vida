# Vida Wallet

**Self-custodial agent wallet for Kaspa and Bittensor. Free. MIT.**

> *"Not vapor. A thoughtfully engineered, security-conscious agent wallet
> that solves a real problem."* — Grok independent review, July 2026

Vida gives agents controlled access to KAS and TAO — session-gated,
spend-capped, host-bound — without handing over full custody.

## What makes it different

**Session-gated access** is the core. Owner creates time-boxed,
host-bound, spend-capped session files. Agents get scoped permissions
without ever seeing the master password or full seed. Exactly what
you want for local agents controlling funds without full key exposure.

**Dual-rail:** Kaspa mainnet (send/receive) + Bittensor Finney
(staking, subnet queries, x402). Testnet-10 covenants, escrow,
payment channels. Few wallets target this agent + dual-ecosystem use case.

**Agent-first, not consumer.** CLI and MCP. No browser extension.
Explicit non-goals: custodial service, EVM, fiat ramps, browser UX.

## What it does

| Capability | Kaspa | Bittensor |
|---|---|---|
| Send / receive | ✅ Mainnet | ✅ Finney |
| Session-gated agent access | ✅ | ✅ |
| Covenant deploy & spend | ✅ Testnet-10 | — |
| Escrow | ✅ Testnet-10 | — |
| Payment channels | ✅ Testnet-10 | — |
| Stake / unstake | — | ✅ |
| Subnet queries | — | ✅ |
| Agent registration | — | ✅ |
| x402 facilitator | — | ✅ |

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
Owner → creates session (spend cap, expiry, allowed operations)
         │
    Vida Kernel
         │
    ┌────┼────┐
  Kaspa  TAO  Covenant
         │
    MCP Server (12 tools + 2 resources)
```

## MCP Server

Agents connect through standard MCP. Tools include: balances, send KAS,
stake/unstake TAO, subnet queries, covenant deploy/spend, escrow, channels.

```bash
python3 scripts/vida_mcp_server.py
```

## Free. Everything. Forever.

No fees on any operation. No commercial license. No royalties.
The wallet is the on-ramp. Vida Commerce (separate project)
is where monetization happens through contract negotiation.

## Roadmap

- **Phase 1** (Aug 2026): Polish, PyPI, Docker, external audit
- **Phase 2**: Mainnet covenants (gated on Toccata toolchain)
- **Later**: Multi-agent economy, hardware wallet signing, BIP39 interop

## License

MIT. All code in this repository.