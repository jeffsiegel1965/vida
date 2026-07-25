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

### Session cap enforcement

Agent sessions carry per-transaction and per-day spending limits, plus optional destination allowlists. Caps are enforced at two levels:

- **Single-process**: an in-process `RLock` with atomic `reserve_session_spend()` / `record_session_spend()` / `release_session_spend()`. Proven closure of a race where 20 concurrent threads each passed a 100 KAS daily cap — measured 200 KAS committed before the fix, exactly 100 KAS after.

- **Cross-process**: an `fcntl.flock` on `<session>.lock` serialises spend counting across separate agent processes sharing one session file. The on-disk counter is authoritative — re-read under the lock rather than trusted from memory. Same pattern applied to both the Kaspa path (`transactions.py`) and the TAO path (`plugins/tao/session.py`).

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

result = check_spend_kas(policy=plan, amount_kas=2.0, destination="kaspa:address...")
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
130 tests · 20s · pytest

Session caps:       22 tests (single-process race, cross-process flock, release, expiry)
Covenant scaffold:   4 tests (scaffold operations)
Covenant robustness: 8 tests (edge cases, error handling)
TAO plugin:         62 tests (stake, unstake, P2P, sessions)
Kaspa core:         27 tests (wallet, transactions, secure ops)
Integration:         7 tests (Kaspa RPC integration against testnet-10)
```

---

## Wallet Dashboard UI

A terminal-themed web dashboard for managing agent authority. Dark green-on-black, monospace. Served by termcn at `/wallet`.

### Emergency Revoke

Red pulsing button at the top of every view. Single click immediately revokes ALL active agent sessions and deletes their session files. No confirmation beyond the initial dialog. Irreversible — the agent loses all spending, staking, and transfer authority instantly.

### Grant Panel

Configure and create a new agent session. Owner provides:

- **Wallet ID** — which provisioned wallet to authorize
- **Owner password** — decrypts the funds key, never stored
- **Mode** — COMMAND (agent proposes, owner approves), HYBRID (auto within limits, flag above), FULL (unrestricted within caps)
- **Max per transaction** — slider, 0–1,000 KAS
- **Max per day** — slider, 0–10,000 KAS
- **Expiry** — slider, 1–720 hours
- **Destination allowlist** — comma-separated Kaspa addresses; empty = unrestricted

On submit, `grant_agent_session()` decrypts the wallet, re-encrypts the key material under a random machine key, writes a 0600 session file with AAD-bound limits, and returns a session ID. The agent never sees the password.

### Active Sessions Panel

Every active session is displayed as a card:

- **Mode badge** — FULL (red), HYBRID (yellow), COMMAND (green)
- **Daily spend bar** — visual progress bar: green below 60%, yellow 60-90%, red above 90%
- **Remaining time** — hours until expiry
- **Quick-adjust sliders** — modify per-transaction cap on any session without re-granting
- **Per-session revoke** — terminate a single session without affecting others
- **Destination list** — truncated addresses with tooltips

Refreshes every 5 seconds. Sessions beyond expiry are automatically filtered out.

### Overflow Auto-Transfer

Configure an automatic sweep to cold storage:

- **Threshold slider** — 0–100,000 KAS. When the wallet balance exceeds this, excess is transferred.
- **Destination address** — the cold storage Kaspa address to sweep to.

Settings persist across restarts via `~/.vida/sessions_meta.json`.

### Locked Address

Read-only display of the provisioned wallet's Kaspa address. All agent spends, stakes, and transfers originate from this address. Changing it requires re-provisioning.

### API Server

The dashboard is backed by `scripts/wallet_api_server.py` on port 8769:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/wallet/sessions` | GET | List active sessions with spend data |
| `/api/v1/wallet/status` | GET | Wallet address, network, lock status |
| `/api/v1/wallet/grant` | POST | Create agent session |
| `/api/v1/wallet/revoke` | POST | Revoke single session |
| `/api/v1/wallet/revoke-all` | POST | Emergency revoke all sessions |
| `/api/v1/wallet/adjust` | POST | Modify session limits |
| `/api/v1/wallet/overflow` | POST | Configure auto-transfer |
| `/health` | GET | Service health check |

---

## License

- **Kaspa core + TAO plugin:** MIT
- **Covenant module:** Commercial license

Development fund address configurable via `VIDA_DEV_FUND` / `VIDA_DEV_FUND_TESTNET` env vars.

---

**Don't trust marketing. Read the code. Run the tests. Self-custody means self-responsibility.**