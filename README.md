# Vida

**Agent-compatible wallet for Kaspa and Bittensor.**

Vida is a wallet designed so an AI agent can send, receive, and stake cryptocurrency under limits you control. The agent never touches your seed phrase. You grant it a session with caps, and you can revoke it anytime.

The wallet runs on Kaspa mainnet (KAS) and Bittensor Finney (TAO).

---

## What it does

### Kaspa core
Send and receive KAS through an agent session. The agent gets per-transaction and per-day caps. You hold the keys. Proven on mainnet.

### TAO plugin
Stake TAO to validators, unstake, P2P transfers — all through an agent session with caps. Emission-based optimization plans generated locally.

### Agent orchestrator
`vida/agents/orchestrator.py` — a natural-language agent loop. Takes a goal, calls K2.5 to plan execution, runs each step against real Vida tools, reports results.

### MCP server
`scripts/vida_mcp_server.py` — 12 MCP tools + 2 resources. Compatible with Claude Desktop, Cursor, Grok Build. The `vida_agent_goal` tool wraps the orchestrator.

### Security model
`vida/secure_wallet.py` — AES-256-GCM encrypted wallet, scrypt KDF, time-boxed session files with spending caps, host-bound authentication.

### Kaspa REST API client
`vida/plugins/covenant/kaspa_rpc.py` — zero-dependency Python client for the Kaspa REST API. Balances, UTXOs, transaction submission, network info.

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
  "Check Vida covenant status and plan a 5 KAS agent pot"

# Start the MCP server (for Claude Desktop, Cursor, Grok Build)
VIDA_SESSION=/path/to/session.json python scripts/vida_mcp_server.py
```

Tests:
```bash
PYTHONPATH=$PWD python -m pytest tests/ -q
# 104 passed in 17s
```

---

## Agent loop

The orchestrator implements:

```
Goal ("stake 50 TAO, plan the pot, check covenants")
  ↓
K2.5 decomposes → 4-step JSON plan
  ↓
covenant_status() → covenant_live_gates() → covenant_describe() → covenant_plan_pot()
  ↓
Result: 4/4 steps completed, per-step status + timing
```

16 covenant tools dispatched via `_TOOL_IMPL` + `_safe_tool`. Each returns `{"ok": bool, ...}`. String params from LLMs are coerced automatically.

---

## Covenant module

The covenant module (`vida/plugins/covenant/`) creates on-chain Kaspa covenants. Fully offline planning and policy enforcement. Live deployment available via the Kaspa REST API.

### Agent pot planning
```python
from vida.plugins.covenant import plan_agent_pot

plan = plan_agent_pot(
    max_kas_per_tx=1.0,
    max_kas_per_day=5.0,
    allowed_destinations=["kaspa:address..."],
)
# → { "ok": True, "fund_pot_kas": 5.05, ... }
```

### Spend policy enforcement
```python
from vida.plugins.covenant import check_spend_kas

result = check_spend_kas(
    policy=plan, amount_kas=2.0, destination="kaspa:address..."
)
# → { "ok": False, "error": "amount exceeds max_tx_sompi", ... }
```

### Kaspa REST API
```python
from vida.plugins.covenant.kaspa_rpc import get_balance, get_utxos

balance = get_balance("kaspatest:address...")
utxos = get_utxos("kaspatest:address...")
```

---

## Architecture

```text
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

---

## Tests

```text
104 tests · 17s · pytest

Covenant scaffold:    scaffold operations
Covenant robustness:  edge cases, error handling
TAO plugin:           62 tests (stake, unstake, P2P, sessions)
Kaspa core:           27 tests (wallet, transactions, secure ops)
```

---

## License

- **Kaspa core + TAO plugin:** MIT
- **Covenant module:** Commercial license

Development fund address configurable via `VIDA_DEV_FUND` / `VIDA_DEV_FUND_TESTNET` env vars.

---

**Don't trust marketing. Read the code. Run the tests. Self-custody means self-responsibility.**