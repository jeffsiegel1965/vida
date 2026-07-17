# Vida Wallet — Claude Fable QA Prompt

## Scope
Review the covenant module, MCP server, and security-critical paths. Do NOT review Kaspa core wallet, TAO plugin, or docs — those have been audited separately.

## Project Layout
- `~/.hermes/projects/vida-release/` — root
- `vida/plugins/covenant/` — covenant plugin (14 files)
- `scripts/vida_mcp_server.py` — MCP server
- `scripts/covenant_manager.py` — CLI
- `scripts/covenant_fund_agent_pot.js` — Node #1074 WASM bridge (genesis)
- `scripts/covenant_spend_agent_pot.js` — Node #1074 WASM bridge (spend, known bug)
- `tests/test_covenant_*.py` — 3 test files

## Files to Review (Priority Order)

### 1. HIGH — Covenant Negotiation (`vida/plugins/covenant/negotiation.py`)
- State machine: offer → counter → accept → reject → deal
- Concession strategies (BOULWARE, LINEAR, CONCEDE)
- Race conditions: two agents negotiating simultaneously
- Edge cases: expired offers, replayed offers, malformed terms
- Check: can a malicious agent craft an offer that drains more than intended?

### 2. HIGH — Fee Calculation (`vida/plugins/covenant/fees.py`)
- `calc_fund_fee()` and `calc_spend_fee()` — check for integer overflow, rounding errors
- Fee schedule: 0.1% fund fee (min 0.01 KAS, max 1 KAS), 0.05% spend fee
- Edge cases: pot_kas = 0, negative, NaN, very large (over 2^53)
- First-pot-free logic: can be bypassed by creating a new wallet?
- Forkability note: fee is Python, trivially removable by fork — this is intentional

### 3. HIGH — MCP Server (`scripts/vida_mcp_server.py`)
- Auth: no MCP transport auth, relies on VIDA_SESSION env var
- Input validation: are addresses, amounts, agent IDs validated?
- Error leakage: do exception messages leak internal paths or state?
- Rate limiting: none — can a caller DDoS the wallet API?
- Session file path injection: VIDA_SESSION from env var, not user input — safe?
- Shell injection: confirmed clean (no os.system, subprocess, eval) — double-check

### 4. HIGH — Pot Spend (`vida/plugins/covenant/pot_spend.py`)
- Can a spend exceed the pot's max_tx_sompi?
- Destination allowlist enforcement: can it be bypassed with a different address format?
- Multiple concurrent spends: race conditions on daily budget counter?
- What happens if the pot is empty but a spend is attempted?

### 5. MEDIUM — Lab Client (`vida/plugins/covenant/lab_client.py`)
- `fund_agent_pot()` and `spend_agent_pot()` — subprocess.call to Node.js
- Known bug: Node process hangs after completion (needs `process.exit(0)`)
- `live_gates_ok()` — env var gates, can they be bypassed?
- `run_lab_demo()` — calls kascov-lab binary, check for command injection

### 6. MEDIUM — Agent Pot (`vida/plugins/covenant/agent_pot.py` + `agent_pot_script.py`)
- Pot creation: can a pot be created with zero or negative caps?
- Policy hash: is the deterministic link between negotiation and pot sufficient?
- Max_tx enforcement: checked in Python, not on-chain — document this honestly

### 7. LOW — JS Bridge Scripts (`scripts/covenant_fund_agent_pot.js`, `covenant_spend_agent_pot.js`)
- fund script: works, used for genesis broadcast
- spend script: KNOWN BROKEN — covenant binding hash mismatch on transition spends
- No need to fix, just document the bug

## Attack Scenarios to Test

1. **Agent compromise via prompt injection**: attacker tricks agent into calling MCP tools with attacker-controlled params. Session caps are the only defense. Can caps be bypassed?
2. **Forced negotiation race**: two agents both try to accept the same offer. What happens?
3. **Fee avoidance**: can a caller craft parameters that make `calc_fund_fee()` return 0 for a large pot?
4. **Session file tampering**: if attacker modifies session JSON, can they increase caps?
5. **Replay attack**: can a signed negotiation offer be replayed to create duplicate pots?

## What NOT to Review
- Kaspa core wallet (`vida/transactions.py`, `vida/secure_wallet.py`, `vida/wallet.py`) — already audited
- TAO plugin (`vida/plugins/tao/`) — already reviewed by committee
- Docs/README/marketing — already cleaned
- Tests — unless they reveal a bug in the code they test

## Deliverable
Write findings to `docs/proofs/claude_fable_qa.md` with:
- **Severity** (Critical/High/Medium/Low/Info)
- **File:line** location
- **Description** of the issue
- **Exploitation** — how an attacker would exploit it
- **Fix** — concrete code change or documentation note
- **False positives** — flag anything you can't reproduce

## Constraints
- Do NOT run any code. Read-only review of source files.
- Do NOT broadcast any transactions.
- Do NOT modify any files.
- Total budget: 200K tokens max.