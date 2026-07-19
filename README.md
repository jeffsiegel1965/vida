# Vida

Agent-compatible wallet for Kaspa (KAS) and Bittensor (TAO).

Vida is a wallet with a permission layer designed for AI agents. An agent can send, receive, and stake cryptocurrency, but only within limits you set per session — per-transaction cap, per-day cap, destination allowlist, and expiry. The agent never touches your seed phrase. You hold the keys. You revoke the session when you want.

---

## Why

AI agents need to pay for APIs, stake tokens, and transfer value. A plain wallet gives an agent either nothing (can't spend) or everything (full private key access). Vida gives an agent **constrained access** — enough to operate, not enough to drain.

The constraints are enforced at two layers:
- **Software**: the session file checks caps before every spend
- **On-chain** (covenant module): SilverScript contracts on Kaspa testnet-10 enforce rules at the network level

---

## What it does

### Send and receive KAS (mainnet)
```python
from vida.transactions import VidaTransactor
from vida.wallet import Vida

wallet = Vida("wallet.json")
tx = VidaTransactor(wallet)
result = await tx.send(
    to_address="kaspa:qzyswp...",
    amount_kas=1.0,
)
# → SendResult(success=True, txid="...", explorer_url="...")
```

Policy enforced before broadcast:
- Amount ≤ session's `max_kas_per_tx`
- Destination in session's `allowed_destinations` (if set)
- Daily total ≤ `max_kas_per_day`
- UTXO smallest-first selection with dust threshold (0.02 KAS)

### Stake and unstake TAO (Finney)
```python
from vida.plugins.tao import delegate

result = delegate(
    amount=50.0,
    hotkey="5CQKp5...",
    session=session,
)
# → delegated to validator, subject to session caps
```

Emissions, yield optimization, P2P transfers all gated through the same session model.

### Run an agent loop
```python
from vida.agents.orchestrator import AgentOrchestrator

orch = AgentOrchestrator(session=session)
result = await orch.run(
    goal="Check covenant status and plan a 5 KAS agent pot"
)
# → {
#   "ok": True,
#   "steps": 4,
#   "completed": 4,
#   "summary": "✅ covenant_status → ✅ covenant_live_gates ..."
# }
```

The orchestrator takes a natural language goal, calls K2.5 to decompose it into executable steps (with rule-based fallback), dispatches each step against real Vida tools, and reports per-step results with verification level (L1-L5 from arXiv:2607.00038).

### Server to MCP clients
```bash
VIDA_SESSION=session.json python scripts/vida_mcp_server.py
```

Exposes 12 tools + 2 resources via the [Model Context Protocol](https://modelcontextprotocol.io). Connect from Claude Desktop, Cursor, Grok Build, or any MCP client. The `vida_agent_goal` tool wraps the full agent orchestrator.

---

## Architecture

```
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

### Session file (the permission layer)

```json
{
  "network": "mainnet",
  "max_kas_per_tx": 1.0,
  "max_kas_per_day": 5.0,
  "allowed_destinations": ["kaspa:..."],
  "expires_at": 1721328000,
  "host_fingerprint": "a1:b2:c3:..."
}
```

The session file is encrypted at rest (AES-256-GCM, scrypt KDF, 0600 permissions). The agent reads it at startup. It cannot modify it. Revoke by deleting the file.

### Verification ladder (arXiv:2607.00038)

Every tool result includes a verification level:

| Level | Name | What it means |
|-------|------|---------------|
| L1 | DETERMINISTIC | Assertion, golden output, exit code |
| L2 | RULE | Schema validation, policy check |
| L3 | FIELD_TRUTH | Delayed confirmation (e.g., tx status) |
| L4 | MODEL_JUDGE | Model by rubric (flagged for financial ops) |
| L5 | HUMAN_CHECKPOINT | Human approval required |

Financial operations never use L4.

---

## Security

| Layer | Mechanism |
|-------|-----------|
| Key storage | AES-256-GCM encrypted JSON (scrypt KDF, 2^17 N, 128 MiB memory-hard) |
| Session binding | AAD (additional authenticated data) binds session to host + expiry |
| Spend counters | Authenticated, tamper-evident, per-day tracking |
| File permissions | 0600 on keys and sessions |
| Memory | `os.urandom` scrub on revoke |
| Key generation | 24-word BIP39 mnemonic or ML-DSA-65 (post-quantum) |

The legacy `wallet.py` stores private keys in plaintext JSON. It exists for testing only. Always use `secure_wallet.py` for any wallet holding real funds.

---

## Covenant module (TN10 only)

The covenant module creates on-chain SilverScript contracts on Kaspa testnet-10. The network enforces the rules directly — no software can bypass them.

### Agent pot planning
```python
from vida.plugins.covenant import plan_agent_pot

plan = plan_agent_pot(
    max_kas_per_tx=1.0,
    max_kas_per_day=5.0,
    allowed_destinations=["kaspa:address..."],
)
# → { "ok": True, "fund_pot_kas": 5.05, "hard_rules": {...} }
```

### Spend policy validation
```python
from vida.plugins.covenant import check_spend_kas

result = check_spend_kas(
    policy=plan,
    amount_kas=2.0,
    destination="kaspa:address...",
)
# → { "ok": False, "error": "amount exceeds max_tx_sompi", ... }
```

### Kaspa REST API
```python
from vida.plugins.covenant.kaspa_rpc import get_balance, get_utxos

balance = get_balance("kaspatest:qplmcgy...")
# → { "ok": True, "balance_sompi": 85813020870 }

utxos = get_utxos("kaspatest:qplmcgy...")
# → [ { "outpoint": {...}, "utxoEntry": {"amount": "4499500000", ...} }, ... ]
```

### SilverScript quine contract

Compiled and deployed on testnet-10. Self-replicating covenant with owner-authorized withdrawal:

```silver
contract QuineAgentPot(pubkey owner, int maxTxSompi) {
    entrypoint withdraw(pubkey recipient) {
        require(checkSig(owner));
        require(output[0].scriptPubKey == input[0].scriptPubKey);
        require(output[1].value <= maxTxSompi);
    }
    entrypoint burn(sig ownerSig) {
        require(checkSig(ownerSig, owner));
    }
}
```

Deployed at:
- `6d58b529ca25819a8cc58ae110d1b113cd688cf4b1cbbe15ef3dd7e799434028`
- `2d0ade44cb97f07350a93848a1d6edb4dcb49fcbce60298e17b3acc351300046`

Spend path blocked by tooling gap — kascov-lab doesn't recognize custom contracts. The Kaspa SDK integration for custom covenant spends is implemented in `vida/plugins/covenant/sdk_integration.py` but not yet tested against a live node.

---

## On-chain proofs

### Kaspa mainnet
- Agent send, 10 KAS: [`d32b4504...`](https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7)

### Testnet-10 covenants
- Lifecycle 1 (genesis → transition → burn): covenant `b58280037a692f4cd1ae087d9e258505add8e4fd4976a1146c6951b6ee471797`
- Lifecycle 2 (quine deploy): covenant `6d58b529ca25819a8cc58ae110d1b113cd688cf4b1cbbe15ef3dd7e799434028`
- Lifecycle 3 (quine deploy): covenant `2d0ade44cb97f07350a93848a1d6edb4dcb49fcbce60298e17b3acc351300046`

### TAO Finney
- Owner stake, 0.05 TAO: `0xdc2cd8...`
- Agent session stake, 0.02 TAO: `0x44c9b9...`

---

## Tests

```bash
python -m pytest tests/ -q
# 108 passed in 18s
```

| Suite | Type | Count |
|-------|------|-------|
| Covenant scaffold | Unit | 104 |
| Kaspa REST API | Integration (live testnet-10) | 4 |

The integration tests hit the live Kaspa REST API (`api-tn10.kaspa.org`):

```python
def test_balance_known_address(self):
    result = get_balance("kaspatest:qplmcgy...")
    self.assertTrue(result["ok"])
    self.assertGreater(result["balance_sompi"], 0)
```

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
  "Check covenant status and plan a 5 KAS agent pot"

# Start the MCP server
VIDA_SESSION=session.json python scripts/vida_mcp_server.py
```

---

## Project structure

```
vida/
├── secure_wallet.py          # Production wallet (AES-256-GCM)
├── wallet.py                 # LEGACY — plaintext keys, testing only
├── transactions.py           # Transaction building, signing, broadcast
├── agents/
│   ├── orchestrator.py       # Agent loop (goal → plan → execute)
│   ├── staking_optimizer.py  # K2.5-powered agent executor
│   ├── tool_schema.py        # OpenAI-compatible function schema
│   └── verification.py       # L1-L5 verification ladder
├── plugins/
│   ├── covenant/
│   │   ├── tools.py          # 17 Hermes agent tools
│   │   ├── kaspa_rpc.py      # Zero-dependency REST API client
│   │   ├── kascov_client.py  # kascov explorer API (read-only)
│   │   ├── agent_pot.py      # Pot planning and validation
│   │   ├── pot_spend.py      # Spend policy enforcement
│   │   ├── sdk_integration.py # Kaspa SDK covenant deploy/spend
│   │   └── silverscript/     # SilverScript source and compiled artifacts
│   └── tao/
│       ├── tools.py          # TAO balance, delegate, transfer
│       └── ...
├── tests/
│   ├── test_covenant_scaffold.py     # 104 unit tests
│   └── test_kaspa_rpc_integration.py # 4 integration tests
└── scripts/
    ├── vida_mcp_server.py    # MCP server (12 tools, 2 resources)
    └── vida_covenant_tool.py # Covenant CLI
```

---

## License

- **Kaspa core + TAO plugin:** MIT
- **Covenant module:** Commercial license

Development fund address configurable via `VIDA_DEV_FUND` / `VIDA_DEV_FUND_TESTNET` env vars.

---

## Status

| Capability | Status | Detail |
|-----------|--------|--------|
| KAS send/receive | ✅ Mainnet | Session-gated |
| TAO stake/unstake | ✅ Finney | Session-gated |
| Agent orchestrator | ✅ Working | K2.5-powered, 16 tools |
| MCP server | ✅ Working | 12 tools, 2 resources |
| Covenant pot planning | ✅ Offline | Templates, policies |
| Covenant deploy | ⚠️ TN10 | Needs Kaspa SDK integration tested |
| SilverScript quine | ⚠️ TN10 | Deployed, spend blocked by tooling |
| x402 integration | 🔜 Planned | CASA identifier comment pending |
| Agent negotiation | ❌ Stripped | Premature, backed up to `dev/` |
| Mainnet covenants | ❌ Waiting | Kaspa Toccata not yet on mainnet |