# Vida

**The agent wallet. Kaspa + Bittensor.**

Vida is a wallet built for autonomous AI agents, not humans. Agents use it to discover subnet services on Bittensor, negotiate covenant terms on Kaspa, and pay for compute, inference, storage, and data — all within session-gated caps you control. The agent never touches your keys. You revoke access by deleting a file.

**What makes it unique:** Vida is the only wallet where agents can connect directly to Bittensor subnets, the only wallet with L1 covenant negotiation between agents, and the only wallet with persistent cross-session agent memory.

---

## What makes Vida unique

**1. Agents connect directly to Bittensor subnets** — An agent can discover subnet services (LLM inference, GPU compute, storage, image generation), pay TAO for access, and query the subnet's API. No other wallet can do this.

**2. L1 covenant negotiation** — Agents negotiate pot terms (max per tx, per day, destinations) using templates, strategies, and volume discounts. The negotiation history is persistent across sessions via AgentMemory.

**3. Cross-session agent memory** — Vida remembers every deal, every counterparty, every subnet used. Deals, success rates, volume discounts, and context survive interruptions.

**4. Verification ladder (L1-L5)** — Every financial operation is verified at L1 (deterministic) or L2 (rule). L4 (model judge) is blocked for money. The `@require_l1_spend` decorator enforces that every spend returns a txid.

**5. Session-gated permissions** — The agent never touches your seed phrase. You grant per-transaction caps, per-day limits, destination allowlists, and expiry. Revoke by deleting a file.

---

## Kaspa (KAS)

### Mainnet: send/receive

```python
from vida.transactions import VidaTransactor
from vida.wallet import Vida  # Requires VIDA_LEGACY_WALLET_ALLOWED=1

wallet = Vida("wallet.json")
tx = VidaTransactor(wallet)
result = await tx.send(to_address="kaspa:qzyswp...", amount_kas=1.0)
```

Policy enforced before broadcast:
- Amount ≤ session's `max_kas_per_tx`
- Destination in `allowed_destinations` (if set)
- Daily total ≤ `max_kas_per_day`
- UTXO smallest-first selection with dust threshold

### RPC: wRPC via Kaspa SDK

```python
from vida.plugins.covenant.kaspa_rpc import get_balance, get_utxos, get_network_info

# Auto-discovers a node via PNN (Resolver) — no hardcoded URLs
balance = get_balance("kaspa:qplmcgy...")
# → {"ok": True, "balance_sompi": 85813020870, "balance_kas": "858.13"}
```

- Uses official Kaspa Python SDK (v2.0.1+) with wRPC WebSocket
- Resolver for peer-to-peer node discovery
- Structured error types: `ConnectionError_`, `TimeoutError_`, `BalanceError`, `TransactionError`
- Falls back to REST API (`api.kaspa.org/transactions`) if SDK submit fails

### Covenants (mainnet + testnet)

Covenant pots are SilverScript contracts that enforce spending rules at the network level — no software can bypass them. The Toccata hard fork (DAA ~389M, June 2026) enabled covenants on Kaspa mainnet. Current mainnet DAA is 490M — 101M blocks past the fork.

```python
from vida.plugins.covenant import plan_agent_pot, check_spend_kas

plan = plan_agent_pot(max_kas_per_tx=1.0, max_kas_per_day=5.0)
check_spend_kas(policy=plan, amount_kas=2.0, destination="...")
# → {"ok": False, "error": "amount exceeds max_tx_sompi"}
```

The covenant module works on both mainnet and testnet-10. Set `set_network("mainnet")` for mainnet operations.

---

## Bittensor (TAO)

### Finney mainnet (pre-dTAO)

Vida connects to the live Bittensor chain. All verified against the current Finney runtime (July 2026). dTAO has NOT been deployed yet — the pre-dTAO model (`add_stake`/`remove_stake`) is still active.

```python
from vida.plugins.tao import vida_tao_delegate, vida_tao_balance

# Stake TAO to a subnet hotkey (current Finney model)
result = vida_tao_delegate(
    wallet_id="agent_wallet",
    amount_tao=5.0, netuid=19,
    hotkey="5CQKp5...",
    session_path="session.json",
    confirm=True,
)
# → {"ok": True, "extrinsic_hash": "0x...", "action": "delegate"}
```

**dTAO readiness:** When dTAO is deployed, the payment model changes from direct staking to subnet token swaps. The `AgentSubnetPurchase.pay()` method is structured to be updated at that point. Tracked in AGENTS.md.

### Subnet marketplace — agents buy services directly

```python
from vida.plugins.tao import tao_list_subnets, tao_subnet_info, tao_subnet_query

# Discover: what subnets are available?
tao_list_subnets(service_type="llm_inference")
# → 3 subnets: SN 1 (Omron), SN 9 (Pretraining), SN 19 (Inference)

# Inspect: what does SN 19 offer?
tao_subnet_info(19)
# → {"name": "Inference (LLM)", "cost": "0.00005 TAO/request", ...}

# Pay: stake TAO to access the subnet
# → via vida_tao_delegate (see above)

# Query: use the subnet's service
tao_subnet_query(netuid=19, body={"model": "deepseek", "prompt": "..."})
# → {"ok": True, "data": {"response": "..."}}
```

The registry covers **9 subnets** across 8 service types:

| Service | Subnets | Typical cost |
|---------|---------|-------------|
| LLM inference | SN 1, 9, 19 | 0.00005-0.0001 TAO/req |
| GPU compute | SN 14 | 0.01 TAO/hour |
| Storage | SN 27 | 0.0001 TAO/GB |
| Image generation | SN 34 | 0.001 TAO/img |
| Audio (TTS/STT) | SN 3 | 0.00005 TAO/min |
| Video generation | SN 29 | 0.005 TAO/video |
| Data scraping | SN 4 | 0.0001 TAO/1k pages |
| AI agents | SN 1 | 0.0005 TAO/req |

---

## Agent memory

Vida agents remember everything across sessions:

```python
from vida.agents.memory import AgentMemory, DealRecord

mem = AgentMemory("agent_wallet")
mem.record_deal(DealRecord(id="d1", deal_type="tao_stake", counterparty_id="sn19", amount_tao=5.0))
mem.get_counterparty("sn19")          # → profile with success rate, volume, history
mem.volume_discount_rate("sn19")      # → 0.20 if 1000+ TAO total
mem.get_context("current_goal")       # → survives interruptions
```

- **Deal history** — every transaction, every stake, every subnet purchase
- **Counterparty profiles** — success rates, volume, preferred strategies
- **Subnet usage** — which subnets deliver, which don't, favorites
- **KV store** — arbitrary key-value persisted across sessions
- **Context** — what the agent was doing, survives interruptions

---

## Agent negotiation

Agents negotiate covenant pot terms with each other. Built for agent-to-agent commerce.

```python
from vida.agents.negotiation import SessionManager, apply_template

mgr = SessionManager()
session = mgr.create_session("counterparty_agent", template="standard")

# Make initial offer
offer = session.make_initial_offer()

# Counterparty responds — agent concedes or walks
response, accepted = session.respond_to_offer(counterparty_terms)
if accepted:
    result = session.accept_terms(counterparty_terms)
```

- **3 templates** — micro (0.1 KAS), standard (1 KAS), power (10 KAS)
- **2 strategies** — BOULWARE (default), CONCEDE (trusted counterparties)
- **Volume discounts** — up to 30% for 10,000+ KAS total
- **Subscriptions** — recurring pots with 15% fee discount
- **Human escalation** — deals > 100 KAS flagged for approval
- **Persistent memory** — learns per-counterparty, adapts strategy

---

## Architecture

```
Owner ─── grants session caps ───→ Vida Kernel
                                       │
                          ┌────────────┼────────────┐
                          │            │            │
                     Kaspa core    TAO plugin   Covenant (SilverScript)
                   (send/recv)   (stake/pay)   (mainnet + TN10)
                   wRPC + SDK    Finney mainnet  Toccata active
                          │            │            │
                          └────────────┼────────────┘
                                       │
                                  Agent tools
                          (orchestrator / MCP server)
                                       │
                                  LLM agent (K2.5)
                                       │
                                  Agent memory
                          (deals, profiles, subnets)
```

### Verification ladder

Every tool result includes a verification level. Financial operations never use L4.

| Level | Name | What it means |
|-------|------|---------------|
| L1 | DETERMINISTIC | Assertion, exit code, golden output |
| L2 | RULE | Schema validation, policy check |
| L3 | FIELD_TRUTH | Delayed confirmation (e.g., tx status) |
| L4 | MODEL_JUDGE | Model by rubric (blocked for financial ops) |
| L5 | HUMAN_CHECKPOINT | Human approval required |

---

## Security

| Layer | Mechanism |
|-------|-----------|
| Key storage | AES-256-GCM encrypted JSON (scrypt KDF, 2^17 N, 128 MiB) |
| Session binding | AAD binds session to host + expiry |
| Spend counters | Authenticated, tamper-evident, per-day tracking |
| File permissions | 0600 on keys and sessions |
| Memory | Secure scrub on revoke |
| Key generation | secp256k1 + ML-DSA-65 (post-quantum) |
| Legacy wallet | `wallet.py` — runtime guard, requires `VIDA_LEGACY_WALLET_ALLOWED=1` |

---

## Status

| Capability | Status | Detail |
|-----------|--------|--------|
| KAS send/receive | ✅ Mainnet | Session-gated, wRPC via Kaspa SDK |
| TAO stake/unstake | ✅ Finney | Session-gated, pre-dTAO |
| TAO subnet marketplace | ✅ Finney | 9 subnets, discover + pay + query |
| Agent orchestrator | ✅ Working | K2.5-powered, 16 tools |
| Agent memory | ✅ Working | Persistent deals, profiles, subnets |
| Agent negotiation | ✅ Working | Templates, strategies, volume discounts |
| Subscriptions | ✅ Working | Recurring pots, 15% discount |
| MCP server | ✅ Working | 12 tools, 2 resources |
| Verification ladder | ✅ Working | L1-L5, `@require_l1_spend` enforced |
| Covenant pot planning | ✅ Offline | Templates, policies, validation |
| Covenant deploy | ⚠️ Tested on TN10 | Mainnet should work (Toccata active) |
| SilverScript quine | ⚠️ TN10 | Deployed, spend path being finalized |
| Kaspa mainnet covenants | ✅ Active | Toccata fork at DAA 389M, currently 490M |
| dTAO deployment | ⏳ When live | Code structured for update |

---

## Tests

```bash
python -m pytest tests/ -q
# 156 passed in 18s
```

| Suite | Type | Count |
|-------|------|-------|
| Negotiation | Unit | 27 |
| Agent memory | Unit | 9 |
| TAO subnet marketplace | Unit | 10 |
| TAO staking, sessions, robustness | Unit | 62 |
| Kaspa SDK integration | Live (testnet-10) | 6 |
| Covenant scaffold | Unit | 39 |
| Covenant robustness | Unit | 3 |

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
├── wallet.py                 # LEGACY — runtime guard, testing only
├── transactions.py           # Transaction building, signing, broadcast
├── agents/
│   ├── orchestrator.py       # Agent loop (goal → plan → execute)
│   ├── staking_optimizer.py  # K2.5-powered agent executor
│   ├── tool_schema.py        # OpenAI-compatible function schema
│   ├── verification.py       # L1-L5 verification ladder
│   ├── memory.py             # Persistent cross-session memory
│   └── negotiation/          # Template-based pot negotiation
├── plugins/
│   ├── covenant/
│   │   ├── tools.py          # 17 Hermes agent tools
│   │   ├── kaspa_rpc.py      # wRPC via Kaspa SDK (Resolver)
│   │   ├── pot_spend.py      # Real spend policy + build→sign→submit
│   │   ├── sdk_integration.py# Kaspa SDK covenant deploy/spend
│   │   └── silverscript/     # SilverScript contracts
│   └── tao/
│       ├── tools.py          # 9 TAO tools (balance, delegate, subnets)
│       ├── subnet_marketplace.py  # 9 subnets, discovery, pricing
│       ├── subnet_client.py  # Agent purchase + query workflow
│       └── substrate_client.py   # Finney chain connection
├── tests/
│   ├── test_negotiation.py           # 27
│   ├── test_agent_memory.py          # 9
│   ├── test_tao_subnet_marketplace.py# 10
│   ├── test_tao_*.py                # 62
│   └── test_kaspa_rpc_integration.py# 6
└── scripts/
    ├── vida_mcp_server.py    # MCP server (12 tools, 2 resources)
    └── run_full_audit.py     # 71-check exhaustive audit
```

---

## On-chain proofs

### Kaspa mainnet
- Agent send, 10 KAS: [`d32b4504...`](https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7)

### Testnet-10 covenants
- Lifecycle 1: `b58280037a692f4cd1ae087d9e258505add8e4fd4976a1146c6951b6ee471797`
- Lifecycle 2: `6d58b529ca25819a8cc58ae110d1b113cd688cf4b1cbbe15ef3dd7e799434028`
- Lifecycle 3: `2d0ade44cb97f07350a93848a1d6edb4dcb49fcbce60298e17b3acc351300046`

### TAO Finney
- Owner stake, 0.05 TAO: `0xdc2cd8...`
- Agent session stake, 0.02 TAO: `0x44c9b9...`

---

## License

- **Kaspa core + TAO plugin:** MIT
- **Covenant module:** Commercial license

Fees and donations are separate and configurable via env vars:
- `VIDA_FEE_ADDRESS` — protocol fee address (default: the one documented in fees.py)
- `VIDA_DONATION_ADDRESS` — voluntary donations / dev fund (separate from fees)