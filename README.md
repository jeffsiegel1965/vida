# Vida

**Agent-compatible wallet for Kaspa and Bittensor.**

Vida is a wallet designed so an AI agent can send, receive, and stake cryptocurrency under limits you control. It is not an agent itself — it is the permission layer an agent operates through.

The wallet runs on Kaspa mainnet (KAS) and Bittensor Finney (TAO). The covenant module creates on-chain SilverScript contracts on testnet-10.

---

## Status

| Layer | Status | Detail |
|-------|--------|--------|
| Wallet (send/receive KAS) | ✅ Mainnet | Session-gated, capped |
| TAO (stake/unstake/transfer) | ✅ Finney | Session-gated, capped |
| Agent loop (LLM → plan → execute) | ✅ Working | K2.5-powered orchestrator |
| MCP server | ✅ Working | 12 tools, 2 resources |
| Covenant module | ⚠️ TN10 only | Gated, requires kascov-lab binary |
| SilverScript quine | ⚠️ Deployed, unspendable | Tooling gap — kascov-lab doesn't recognize custom contracts |
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

An agent saying "plan a 5 KAS pot and check what covenants are available" gets:
1. K2.5 decomposes the goal → JSON plan
2. `covenant_plan_pot(5,5)` runs → pot calculated
3. `covenant_describe()` runs → capabilities listed

### MCP server
`scripts/vida_mcp_server.py` — exposes 12 tools + 2 resources. Compatible with Claude Desktop, Cursor, Grok Build. The `vida_agent_goal` tool wraps the agent orchestrator.

### Security model
`vida/secure_wallet.py` — AES-256-GCM encrypted wallet files, scrypt KDF (2^17 rounds), host-bound session files, authenticated spend counters, atomic TOCTOU-safe writes.

### Covenant TN10 proofs
Three full covenant lifecycles (genesis → transition → burn) executed on testnet-10:

```text
Lifecycle 1: covenant b58280037a692f4cd1ae087d9e258505add8e4fd4976a1146c6951b6ee471797
Lifecycle 2: covenant 6d58b529ca25819a8cc58ae110d1b113cd688cf4b1cbbe15ef3dd7e799434028 (quine)
Lifecycle 3: covenant 2d0ade44cb97f07350a93848a1d6edb4dcb49fcbce60298e17b3acc351300046 (quine)
```

---

## What's not real (yet)

| Claim | Reality |
|-------|---------|
| "Agent economy platform" | No agent-to-agent commerce exists. Negotiation protocol was stripped as premature. |
| "Mainnet covenants" | Kaspa Toccata covenants not deployed on mainnet. All proofs on testnet-10. |
| "Self-replicating quine spends" | The quine contract compiles and deploys, but kascov-lab cannot spend from it. Tooling gap. |
| "Agent chooses this autonomously" | The orchestrator exists but has no persistent memory, no inter-agent communication, and no error recovery. |

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

# Start the MCP server (for Claude Desktop / Cursor / Grok Build)
VIDA_SESSION=/path/to/session.json python scripts/vida_mcp_server.py
```

Tests:

```bash
PYTHONPATH=$PWD python -m pytest tests/ -q
104 passed in 17s
```

---

## Agent loop

The orchestrator (`vida/agents/orchestrator.py`) implements:

```
Goal ("stake 50 TAO with highest APY")
  ↓
K2.5 decomposes → 3-step JSON plan
  ↓
covenant_describe() → step 1
covenant_plan_pot(50, 50) → step 2
covenant_live_gates() → step 3
  ↓
Result: 3/3 steps completed, per-step status + timing
```

Available tools: 16 covenant tools via `_TOOL_IMPL` + `_safe_tool` dispatcher. Each returns `{"ok": bool, ...}`.

The MCP server exposes these tools to any MCP-compatible client. The `vida_agent_goal` tool takes a natural language goal and runs the full loop.

---

## Covenant module

The covenant module (`vida/plugins/covenant/`) is a commercial plugin that creates on-chain Kaspa covenants.

**Current state:** Offline-only by default. Requires `VIDA_COVENANT_LIVE=1` + the `kascov-lab` Rust binary. All on-chain proofs are on testnet-10.

### What's fully working offline
- Agent pot planning (`plan_agent_pot`): calculate funding, set hard rules
- Spend policy validation (`check_spend_kas`): enforce caps before broadcast
- Pot record persistence: metadata saved to disk
- 17 Hermes agent tools: status, describe, plan, validate, kascov queries

### What needs kascov-lab binary
- Covenant deploy (`kascov-lab deploy`): birth a compiled SilverScript program
- Covenant spend (`kascov-lab spend`): spend from a deployed covenant
- Full lifecycle (`kascov-lab demo`): genesis → transition → burn

### What's blocked
- Custom SilverScript spends: kascov-lab only knows 3 contract types (Mecenas, Escrow, LastWill)
- Quine spend: our QuineAgentPot contract is deployed but unspendable via kascov-lab
- WASM bridge: Node.js covenant helpers have hash mismatch (documented in proof doc)

### QuineAgentPot contract

`vida/plugins/covenant/silverscript/quine_agent_pot.sil`

```silver
contract QuineAgentPot(pubkey owner, int maxTxSompi) {
    entrypoint withdraw(pubkey recipient) {
        require(checkSig(owner));  // Owner must authorize
        require(output[0].scriptPubKey == input[0].scriptPubKey);  // Self-replicate
        require(output[1].value <= maxTxSompi);  // Bound payment
        require(input[0].value >= output[0].value + output[1].value);  // Fee guard
    }
    entrypoint burn(sig ownerSig) {
        require(checkSig(ownerSig, owner));  // Owner-close
    }
}
```

Status: Compiled (113 bytes), deployed on TN10 (covenant `6d58b529`), spend path blocked by kascov-lab tooling gap.

---

## Architecture

```text
Owner ─── grants session caps ───→ Vida Kernel
                                       │
                          ┌────────────┼────────────┐
                          │            │            │
                     Kaspa core    TAO plugin   Covenant
                     (send/recv)  (stake/swap)  (TN10 only)
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

## Plugin platform

Every plugin follows the same session model:
- Owner grants caps per plugin
- Agent acts inside those caps
- Revoke by deleting the session file

| Plugin | Rail | Status | License |
|--------|------|--------|---------|
| Kaspa core | KAS | Shipped | MIT |
| TAO | TAO | Shipped | MIT |
| Covenant | KAS covenants | TN10 only | Commercial |

---

## License

- **Kaspa core + TAO plugin:** MIT
- **Covenant module:** Commercial license

Development fund address configurable via `VIDA_DEV_FUND` / `VIDA_DEV_FUND_TESTNET` env vars.

---

**Don't trust marketing. Read the code. Run the tests. Self-custody means self-responsibility.**
