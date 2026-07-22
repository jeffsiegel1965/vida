# Vida Wallet — Roadmap to v1.0

## Current: v0.2.0 (July 2026)

### Phase 0: Foundation (✅ Done)

- [x] Secure wallet: AES-256-GCM, scrypt KDF, BIP39 mnemonic
- [x] Session-gated agent delegation (FULL/HYBRID/COMMAND)
- [x] Kaspa mainnet transactions (send/receive, proven)
- [x] TAO Finney integration (stake, unstake, transfer, session-gated)
- [x] Agent orchestrator (19 tools, K2.5-powered)
- [x] Agent memory (persistent deals, counterparty profiles)
- [x] Agent negotiation (3 templates, volume discounts, subscriptions)
- [x] Verification ladder (L1-L5, `@require_l1_spend`)
- [x] Covenant modules: escrow, timelock, vault, payment channels
- [x] MCP server (12 tools, 2 resources)
- [x] TAO subnet marketplace (9 subnets, discover + pay + query)
- [x] x402 auto-pay (HTTP 402 for subnet APIs)
- [x] Multisig (Bittensor v11, M-of-N)
- [x] CI: ruff lint + format + test suite (all green)
- [x] CI: dependency vulnerability scanning (pip-audit)
- [x] Clean public surface (no leaked internal files)
- [x] Honest README with proof txids and limitations
- [x] Dual license: MIT (core) + Commercial (covenants) with clear scope

### Phase 1: Polish & Trust (Target: August 2026)

- [ ] Publish to PyPI as `vida-wallet`
- [ ] Docker/containerization for agent runners
- [ ] End-to-end tutorial: "Your First Agent Wallet"
- [ ] Architecture diagrams (ASCII or SVG in docs/)
- [ ] Backup/restore operational guide
- [ ] External third-party security review of core wallet
- [ ] Enhanced RPC resilience (retry, fallback, circuit breakers)
- [ ] Hardware wallet integration research (Ledger/Trezor signing paths)
- [ ] Fix remaining SDK integration roughness (transaction submit format)
- [ ] Admin dashboard polish (mobile-friendly, session monitoring)
- [ ] BIP39 import/export for interop with Kasware and other wallets
- [ ] Fee model documentation and transparency dashboard

### Phase 2: Covenants Live (Target: October 2026, gated on Kaspa Toccata SDK)

- [ ] Live covenant deployment on Kaspa mainnet (via Toccata)
- [ ] SilverScript quine spend path (currently blocked by toolchain)
- [ ] Agent pot covenant: hard on-chain spend caps
- [ ] Covenant fee collection live
- [ ] Covenant monitoring and status endpoints
- [ ] Multi-party escrow with real mainnet settlement
- [ ] Payment channel mainnet integration
- [ ] Covenant CI: live testnet cycles

### Phase 3: Multi-Agent Economy (Target: Q1 2027)

- [ ] Multi-agent orchestration (coordinated agent fleets)
- [ ] Agent identity and reputation system (cross-wallet)
- [ ] Bittensor dTAO migration support (when Finney upgrades)
- [ ] Agent-to-agent payment standards (Kaspa + TAO)
- [ ] Subnet service registry (decentralized, on-chain)
- [ ] Cross-chain agent payment bridges
- [ ] Agent marketplace / discovery protocol
- [ ] Performance benchmarks and load testing at scale
- [ ] Formal verification of covenant contracts
- [ ] Published security audit (third-party firm)

### Phase 4: Maturity (Target: Mid-2027)

- [ ] v1.0 release
- [ ] Mobile companion app (read-only, notifications)
- [ ] Web dashboard with real-time monitoring
- [ ] Enterprise support tier
- [ ] SDK for third-party plugin development
- [ ] Governance model for protocol upgrades
- [ ] Documentation site (vida-wallet.dev)

## Non-Goals (explicitly out of scope)

- Custodial wallet service (Vida is self-custody by design)
- Exchange integration or fiat on/off-ramps
- EVM/Solana support (Kaspa-native, TAO as secondary rail)
- Browser extension (CLI + agent-first, not consumer UX)

## Versioning

Vida follows [Semantic Versioning](https://semver.org/):
- **0.x**: Pre-1.0, breaking changes may occur in minor versions
- **1.0**: Stable API, backward compatibility guarantees
- **Patch**: Bug fixes, security patches
- **Minor**: New features, non-breaking
- **Major**: Breaking changes
