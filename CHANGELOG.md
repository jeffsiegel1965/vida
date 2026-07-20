# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - Unreleased

### Added
- Kaspa SDK integration (wRPC + Resolver) — replaces REST API, auto-discovers nodes
- TAO subnet marketplace — 9 subnets, agents discover + pay + query subnet services
- Agent memory — persistent cross-session memory (deals, counterparties, subnets, KV)
- Agent negotiation — 3 templates (micro/standard/power), 2 strategies, subscriptions, volume discounts
- Escrow covenant module — release/refund/resolve paths, fees baked in, 17 tests
- Verification ladder (L1-L5) — `@require_l1_spend` enforces txid on financial ops
- Session-gated permissions — agent never touches keys, revocable caps
- Secure wallet (AES-256-GCM, scrypt KDF) — replaces legacy plaintext wallet
- Toccata mainnet support — verified active (DAA 490M, fork at 389M)
- Fee/donation address separation — `VIDA_FEE_ADDRESS` / `VIDA_DONATION_ADDRESS`
- Social preview banner — "Vida — The Agent Wallet"
- Live TN10 integration test — proves full pipeline (connect, build, sign, submit)
- CI workflow for ruff linting + formatting

### Changed
- `transactions.py` migrated from legacy wallet (`Vida`) to secure wallet (`SecureVida`)
- `submit_transaction` uses correct `RpcTransaction` format per SDK stubs
- REST API fallback for transaction submission (field name conversion)
- AGENTS.md rewritten with accurate state, new files, Toccata fix
- README completely rewritten with separate TAO/Kaspa sections, honest status
- License updated to dual MIT + Commercial

### Fixed
- Runtime guard on legacy wallet (`VIDA_LEGACY_WALLET_ALLOWED=1` required)
- Bare `except Exception:` clauses replaced with structured error types
- `tao_stake_optimize` alias removed from orchestrator
- `print()` replaced with `logger.warning()` in memory module
- Orchestrator import chain (covenant tools not exported)
- Toccata status corrected from "not on mainnet" to "active on mainnet"
- Submit format fixed per SDK stubs v2.0.1

### Security
- Legacy wallet now fails-closed by default
- `@require_l1_spend` decorator rejects financial ops without txid
- L4 (model judge) verification blocked for financial operations
- Session keys are ephemeral, host-bound, time-boxed