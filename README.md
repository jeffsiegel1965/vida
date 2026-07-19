# Vida

**Agent-compatible wallet for Kaspa and Bittensor.**

Vida is a wallet designed so an AI agent can send, receive, and stake cryptocurrency under limits you control. It is not an agent itself — it is the permission layer an agent operates through.

The wallet runs on Kaspa mainnet (KAS) and Bittensor Finney (TAO).

---

## Status

| Layer | Status | Detail |
|-------|--------|--------|
| Wallet (send/receive KAS) | ✅ Mainnet | Session-gated, capped |
| TAO (stake/unstake/transfer) | ✅ Finney | Session-gated, capped |
| Agent loop (LLM → plan → execute) | ✅ Working | K2.5-powered orchestrator |
| MCP server | ✅ Working | 12 tools, 2 resources |
| Covenant module | ⚠️ TN10 offline | Kaspa REST API for balance/UTXO queries |
| SilverScript quine | ⚠️ Compiled | Not live — kascov-lab dependency removed |
| Agent negotiation | ❌ Stripped | Needs redesign — backed up to dev/ |
| Mainnet covenants | ❌ Not possible | Kaspa Toccata not yet on mainnet |

---

## What's real

### Kaspa core
Send and receive KAS through an agent session. The agent gets per-transaction and per-day caps. You hold the keys. Proven on mainnet.

### TAO plugin
Stake, unstake, and P2P transfer TAO through a session. Emission-based optimization plans generated locally.

### Agent orchestrator
`vida/agents/orchestrator.py` — a real agent loop. Takes a natural language goal, calls K2.5 to plan execution, runs each step against real Vida tools, and reports results.

### MCP server
`scripts/vida_mcp_server.py` — exposes 12 tools + 2 resources. Compatible with Claude Desktop, Cursor, Grok Build.

### Security model
`vida/secure_wallet.py` — AES-256-GCM encrypted wallet files, scrypt KDF (2^17 rounds), host-bound session files, authenticated spend counters.

### Kaspa REST API client
`vida/plugins/covenant/kaspa_rpc.py` — zero-dependency Python client for the Kaspa REST API. Balances, UTXOs, transaction submission, network info. No Rust binary required.

---

## What's not real (yet)

| Claim | Reality |
|-------|---------|
| "Agent economy platform" | No agent-to-agent commerce exists. Negotiation stripped as premature. |
| "Mainnet covenants" | Kaspa Toccata covenants not on mainnet yet. |
| "SilverScript quine spends" | Compiled and debugger-verified, but kascov-lab dependency removed. |
| "Agent chooses autonomously" | Orchestrator exists but has no memory, inter-agent comms, or error recovery. |

---

## Quick start

```bash
git clone https://github.com/jeffsiegel1965/vida.git
cd vida
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Create wallet
python scripts/setup_owner_wallet.py

# Grant an agent session: 1 KAS/tx, 5 KAS/day, 24 hours
python scripts/grant_session.py --hours 24 --max-tx 1 --max-day 5

# Run the agent orchestrator
PYTHONPATH=$PWD python -m vida.agents.staking_optimizer \
  "Check covenant status and plan a 5 KAS pot"

# Start the MCP server
VIDA_SESSION=/path/to/session.json python scripts/vida_mcp_server.py
```

Tests:
```bash
PYTHONPATH=$PWD python -m pytest tests/ -q
# 104 passed in 17s
```

---

## Architecture

```text
Owner ─── grants session caps ───→ Vida Kernel
                                       │
                          ┌────────────┼────────────┐
                          │            │            │
                     Kaspa core    TAO plugin   Covenant
                     (send/recv)  (stake/swap)  (TN10 offline)
                          │            │            │
                          └────────────┼────────────┘
                                       │
                                  Agent tools
                          (orchestrator.py / MCP server)
                                       │
                                  LLM agent
```

---

## License

- **Kaspa core + TAO plugin:** MIT — free to use, modify, distribute
- **Covenant module:** Commercial license

Development fund address configurable via `VIDA_DEV_FUND` / `VIDA_DEV_FUND_TESTNET` env vars.

---

**Don't trust marketing. Read the code. Run the tests. Self-custody means self-responsibility.**
