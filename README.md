# Vida

**The agent wallet. Kaspa + Bittensor.**

<p align="center">
  <img src="assets/social-preview.jpg" width="800" alt="Vida — The Agent Wallet" />
</p>

Vida is a wallet for autonomous AI agents. It is not a wallet for humans.
Agents use Vida to discover subnet services on Bittensor.
Agents use Vida to negotiate covenant terms on Kaspa.
Agents use Vida to pay for compute, inference, storage, and data.
You control the session caps. The agent does not have access to your keys.
To revoke access, delete a file.

**Unique features:**
- Vida is the only wallet where agents connect directly to Bittensor subnets.
- Vida is the only wallet with L1 covenant negotiation between agents.
- Vida is the only wallet with persistent cross-session agent memory.

---

## Unique features

**1. Direct agent access to Bittensor subnets**
An agent can discover subnet services (LLM inference, GPU compute, storage, image generation).
An agent can pay TAO for access.
An agent can query the subnet API.
No other wallet makes this possible.

**2. L1 covenant negotiation**
Agents negotiate pot terms (max per tx, per day, destinations).
The negotiation uses templates, strategies, and volume discounts.
The negotiation history persists across sessions.
AgentMemory stores the history.

**3. Cross-session agent memory**
Vida stores every deal, every counterparty, and every subnet.
Deals, success rates, volume discounts, and context survive interruptions.

**4. Verification ladder (L1-L5)**
The verification ladder checks every financial operation.
L1 and L2 are deterministic. L4 (model judge) is blocked for money.
The `@require_l1_spend` decorator requires that every spend returns a txid.

**5. Session-gated permissions**
The agent does not have access to your seed phrase.
You set per-transaction caps, per-day limits, destination allowlists, and expiry.
To revoke access, delete a file.

**6. Multisig (Bittensor v11)**
Multisig is an M-of-N wallet for subnet treasury management.
Agents can propose, approve, execute, and cancel multisig operations.
The design aligns with the v431/v11 tooling release.

**7. Bittensor v11 conviction voting**
Vida tracks locked α-token and TAO positions for subnet ownership voting.
Vida can record, release, and list conviction positions in AgentMemory.

---

## Kaspa (KAS)

### Mainnet: send and receive

```python
from vida.transactions import VidaTransactor
from vida.secure_wallet import SecureVida

wallet = SecureVida("wallet.json")
tx = VidaTransactor(wallet)
result = await tx.send(to_address="kaspa:qzyswp...", amount_kas=1.0)
```

Policy enforced before broadcast:
- Amount is less than or equal to the session `max_kas_per_tx`
- Destination is in `allowed_destinations` (if set)
- Daily total is less than or equal to `max_kas_per_day`
- UTXO smallest-first selection with dust threshold

### RPC: wRPC via Kaspa SDK

```python
from vida.plugins.covenant.kaspa_rpc import get_balance, get_utxos, get_network_info

# Auto-discovers a node via PNN (Resolver) — no hardcoded URLs
balance = get_balance("kaspa:qplmcgy...")
# → {"ok": True, "balance_sompi": 85813020870, "balance_kas": "858.13"}
```

- Uses official Kaspa Python SDK (v2.0.1 or later) with wRPC WebSocket
- Uses Resolver for peer-to-peer node discovery
- Uses structured error types: `ConnectionError_`, `TimeoutError_`, `BalanceError`, `TransactionError`
- Falls back to REST API (`api.kaspa.org/transactions`) if SDK submit fails

### Covenants (mainnet and testnet)

Covenant pots are SilverScript contracts. They enforce spending rules at the network level.
No software can bypass them.
The Toccata hard fork (DAA ~389M, June 2026) enabled covenants on Kaspa mainnet.
The current mainnet DAA is 490M — 101M blocks past the fork.

```python
from vida.plugins.covenant import plan_agent_pot, check_spend_kas

plan = plan_agent_pot(max_kas_per_tx=1.0, max_kas_per_day=5.0)
check_spend_kas(policy=plan, amount_kas=2.0, destination="...")
# → {"ok": False, "error": "amount exceeds max_tx_sompi"}
```

The covenant module works on mainnet and testnet-10.
Set `set_network("mainnet")` for mainnet operations.

### Escrow covenants

Agent-to-agent escrow with three paths:

```python
from vida.plugins.covenant.escrow import vida_escrow_create, vida_escrow_status

# Deploy: lock funds in escrow
escrow = vida_escrow_create(
    buyer_address="kaspa:buyer...",
    seller_address="kaspa:seller...",
    amount_kas=10.0,
)
# → {"ok": True, "escrow_id": "escrow_...", "fee_kas": 0.01, ...}

# Release: seller delivers, arbiter countersigns
# → vida_escrow_release(escrow_id, seller_sig, arbiter_sig)

# Refund: buyer reclaims after timeout
# → vida_escrow_refund(escrow_id, buyer_sig)

# Resolve: arbiter routes to buyer or seller (constrained — can't steal)
# → vida_escrow_resolve(escrow_id, arbiter_sig, recipient)
```

Fee: 0.1% of the escrow amount (min 0.01 KAS, max 1 KAS) to the fee address.

### Payment channels

Off-chain micropayments with on-chain settlement.
Two agents open a channel. They exchange thousands of updates.
They settle on Kaspa once.

```python
from vida.plugins.covenant.channels import vida_channel_open, vida_channel_update, vida_channel_close

# Open: 10 KAS channel between two agents
ch = vida_channel_open("agent_a", "agent_b", capacity_kas=10.0)

# Update: after 100 micropayments, balances shift
vida_channel_update(ch["channel_id"], "sig_a", "sig_b", 6.0, 4.0)

# Close: settle on-chain
vida_channel_close(ch["channel_id"])
```

Fee: 0.1% of channel capacity.

---

### Covenant pattern library

Vida has a library of reusable covenant patterns. Each pattern is a pre-compiled SilverScript contract with typed parameters (owner address, timelock duration, guardian addresses, etc.).

| Pattern | Description |
|---------|-------------|
| **TimeLock** | Lock funds until a block height. Use for delayed payments, vesting cliffs. |
| **Ownable** | Single-owner covenant. Use for agent-controlled pots. |
| **AtomicSwap** | HTLC (Hashed Timelock Contract). Use for trustless cross-party exchange. |
| **Vesting** | Linear release over time. Use for grants, salaries, token distributions. |
| **SocialRecovery** | Owner + N guardian addresses. Use for wallet recovery. |
| **StreamingPayment** | Continuous payment stream per second. Use for pay-as-you-go. |
| **DeadMansSwitch** | If owner does not touch for N blocks, beneficiary claims. |

Deploy any pattern:

```python
from vida.plugins.covenant.tools import covenant_deploy_ownable

result = covenant_deploy_ownable(
    private_key_hex="...",
    value_sompi=100_000_000,  # 1 KAS
)
# → {"ok": True, "covenant_id": "...", "txid": "...", "address": "kaspa:..."}
```

V1 covenant transactions use `compute_budget=10` for SilverScript introspection. Confirmed working on testnet-10 by the Kaspa SDK team (smartgoo, Jul 21).

---

## Bittensor (TAO)

Vida has the most comprehensive TAO integration available.
Agents can discover, pay for, and consume subnet services.
This all happens in code, without human intervention.

### Chain status

- **Finney mainnet** — live, verified July 2026. Pre-dTAO model (`add_stake`/`remove_stake`).
- **dTAO** — not deployed yet. Code is structured for update when dTAO arrives.

### Core capabilities

| Capability | How it works |
|-----------|--------------|
| **Stake or unstake** | `vida_tao_delegate(session_path, amount_tao, netuid, hotkey)` |
| **Transfer** | `vida_tao_transfer(session_path, dest, amount_tao)` |
| **Balance check** | `vida_tao_balance(session_path)` |
| **Session management** | `vida_tao_session_info(session_path)` |

### Subnet marketplace — discover, pay, query

Agents browse subnets, pay for access, and consume services.
All in code.

```python
from vida.plugins.tao import tao_list_subnets, tao_subnet_info, tao_subnet_query

# Discover: what subnets are available?
tao_list_subnets(service_type="llm_inference")
# → 3 subnets: SN 1 (Omron), SN 9 (Pretraining), SN 19 (Inference)

# Inspect: what does SN 19 offer?
tao_subnet_info(19)
# → {"name": "Inference (LLM)", "cost": "0.00005 TAO/request", ...}

# Pay: stake TAO to access the subnet
vida_tao_delegate(session_path, amount_tao=5.0, netuid=19, hotkey="5CQKp5...")

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

### x402 — auto-pay subnet APIs

When a subnet responds with HTTP 402 "Payment Required," Vida auto-pays and retries the request.
This is the standard for machine payments.

```python
from vida.plugins.tao.x402 import x402_query

# If the subnet returns 402 + payment terms, Vida auto-pays
result = x402_query("https://subnet.api/query", substrate_client, coldkey_hex)
# → X402Response(paid=True, txid="0x...", original_result={...})
```

Vida fee: 0.05% of the payment amount. The first 100 queries per day are free.

### Subnet gateway fees

Every query routed through Vida includes fee tracking:

```python
result = tao_subnet_query(netuid=19, wallet_id="agent_1", amount_tao=0.001)
# → {"ok": True, "data": {...}, "vida_fee": {"fee_tao": 0.0000005, "is_free": True, ...}}
```

- 0.05% per query (billed to the agent)
- First 100 queries per day are free per wallet
- Separate TAO fee address (`VIDA_TAO_FEE_ADDRESS`)

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
- **Subnet usage** — which subnets deliver, which do not, favorites
- **KV store** — arbitrary key-value persisted across sessions
- **Context** — what the agent was doing, survives interruptions

---

## Agent negotiation

Agents negotiate covenant pot terms with each other.
This is built for agent-to-agent commerce.

```python
from vida.agents.negotiation import SessionManager, apply_template

mgr = SessionManager()
session = mgr.create_session("counterparty_agent", template="standard")

# Make initial offer
offer = session.make_initial_offer()

# Counterparty responds — agent concedes or walks
response, accepted = session.respond_to_offer(counterparty_terms)
if accepted:
    result = session.accept_terms(counterparty_terms, deploy_escrow=True)
```

- **3 templates** — micro (0.1 KAS), standard (1 KAS), power (10 KAS)
- **2 strategies** — BOULWARE (default), CONCEDE (trusted counterparties)
- **Volume discounts** — up to 30% for 10,000+ KAS total
- **Subscriptions** — recurring pots with 15% fee discount
- **Human escalation** — deals over 100 KAS flagged for approval
- **Escrow integration** — accepted terms can deploy an on-chain escrow covenant
- **Persistent memory** — learns per counterparty, adapts strategy

---

## Architecture

```
Owner ─── grants session caps ───→ Vida Kernel
                                       │
                          ┌────────────┼────────────┐
                          │            │            │
                     Kaspa core    TAO plugin   Covenant
                   (send/recv)   (stake/pay)   (SilverScript)
                   wRPC + SDK    Finney        escrow + channels
                   mainnet       pre-dTAO      x402 gateway
                          │            │            │
                          └────────────┼────────────┘
                                       │
                                  Agent tools
                          (orchestrator / MCP server)
                                       │
                                  LLM agent (K2.5)
                                       │
                          Agent memory + negotiation
                     (deals, profiles, subnets, sessions)
                                       │
                          Subnet gateway fees (0.05%)
```

### Verification ladder

Every tool result includes a verification level.
Financial operations never use L4.

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
| Session binding | AAD binds session to host and expiry |
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
| TAO stake/unstake | ✅ Finney | Session-gated, pre-dTAO (verified Jul 19) |
| TAO subnet marketplace | ✅ Finney | 9 subnets, discover + pay + query |
| x402 auto-pay | ✅ Built | HTTP 402 Payment Required, auto-pay subnet APIs |
| Subnet gateway fees | ✅ Built | 0.05% per query, free tier, TAO fee address |
| Payment channels | ✅ Built | Off-chain micropayments, on-chain settlement, 17 tests |
| Escrow covenants | ✅ Built | 3 paths, 17 tests, fees baked in |
| Agent orchestrator | ✅ Working | K2.5-powered, 19 tools |
| Agent memory | ✅ Working | Persistent deals, profiles, subnets, conviction voting |
| Agent negotiation | ✅ Working | Templates, strategies, volume discounts, escrow integration |
| Subscriptions | ✅ Working | Recurring pots, 15% discount |
| Multisig (Bittensor v11) | ✅ Built | M-of-N propose/approve/execute/cancel, 17 tests |
| MCP server | ✅ Working | 12 tools, 2 resources |
| Verification ladder | ✅ Working | L1-L5, `@require_l1_spend` enforced |
| Kaspa covenants (SilverScript) | ✅ Mainnet | Toccata active (DAA 490M) |
| Covenant deploy | ⚠️ Tested on TN10 | Mainnet ready, needs funded key |
| dTAO deployment | ⏳ Not on Finney yet | Pre-dTAO is correct. Code structured for update. |

---

## Tests

```bash
python -m pytest tests/ -q
# 212 passed in 17s
```

| Suite | Type | Count |
|-------|------|-------|
| Negotiation | Unit | 27 |
| Agent memory | Unit | 9 |
| TAO subnet marketplace | Unit | 10 |
| TAO staking, sessions, robustness | Unit | 62 |
| Escrow covenants | Unit | 17 |
| Payment channels | Unit | 17 |
| x402 (auto-pay) | Unit | 7 |
| Kaspa SDK integration | Live (testnet-10) | 6 |
| Covenant scaffold | Unit | 39 |

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
│   ├── orchestrator.py       # Agent loop (goal → plan → execute), 19 tools
│   ├── staking_optimizer.py  # K2.5-powered agent executor
│   ├── tool_schema.py        # OpenAI-compatible function schema
│   ├── verification.py       # L1-L5 verification ladder
│   ├── memory.py             # Persistent cross-session memory
│   └── negotiation/          # Template-based pot negotiation
├── plugins/
│   ├── covenant/
│   │   ├── tools.py          # Covenant tools (status, plan, fees, escrow, patterns)
│   │   ├── sdk_integration.py # SDK-based covenant deploy/spend (v1, compute_budget)
│   │   ├── covenant_patterns.py # Compiled covenant pattern library (7 patterns)
│   │   ├── kaspa_rpc.py      # wRPC via Kaspa SDK (Resolver)
│   │   ├── pot_spend.py      # Real spend policy + build→sign→submit
│   │   ├── escrow.py         # Agent-to-agent escrow (release/refund/resolve)
│   │   ├── channels.py       # Payment channels (off-chain, on-chain settle)
│   │   ├── fees.py           # Fee schedules (KAS + TAO), addresses
│   │   └── silverscript/     # SilverScript contracts (Ownable, TimeLock, HTLC, Vesting, SocialRecovery, Streaming, DeadMansSwitch)
│   └── tao/
│       ├── tools.py          # TAO tools (balance, delegate, subnets)
│       ├── x402.py           # HTTP 402 auto-pay for subnet APIs
│       ├── subnet_marketplace.py  # 9 subnets, discovery, pricing
│       ├── subnet_client.py  # Agent purchase + query + fee tracking
│       └── substrate_client.py   # Finney chain connection
├── tests/
|   ├── test_negotiation.py           # 27
|   ├── test_agent_memory.py          # 9
|   ├── test_tao_subnet_marketplace.py# 10
|   ├── test_tao_*.py                # 62
|   ├── test_escrow.py               # 17
|   ├── test_channels.py             # 36
|   ├── test_x402.py                 # 7
|   ├── test_kaspa_rpc_integration.py# 6
|   └── test_covenant_deploy.py      # 3
└── scripts/
    ├── vida_mcp_server.py    # MCP server (12 tools, 2 resources)
    └── run_full_audit.py     # 71-check exhaustive audit
```

---

## On-chain proofs

### Kaspa mainnet
- Agent send, 10 KAS: [`d32b4504...`](https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7)

### Testnet-10 covenants
- Lifecycle 1: `b58280037a692f4cd1ae087d9e258505add8e4fd4976a1156c6951b6ee471797`
- Lifecycle 2: `6d58b529ca25819a8cc58ae110d1b113cd688cf4b1cbbe15ef3dd7e799434028`
- Lifecycle 3: `2d0ade44cb97f07350a93848a1d6edb4dcb49fcbce60298e17b3acc351300046`

### TAO Finney
- Owner stake, 0.05 TAO: `0xdc2cd8...`
- Agent session stake, 0.02 TAO: `0x44c9b9...`

---

## License

Vida uses a dual license:

- **Kaspa core, TAO plugin, Agent layer, CLI tools:** MIT
- **Covenant module (SilverScript contracts, escrow, negotiation, channels):** Commercial license

The MIT parts are free to use, fork, and modify.
The covenant module is commercial — contact for details.

Fees and donations are separate and configurable via env vars:
- `VIDA_FEE_ADDRESS` — protocol fee address (KAS)
- `VIDA_DONATION_ADDRESS` — voluntary donations / dev fund (KAS)
- `VIDA_TAO_FEE_ADDRESS` — subnet gateway fees (TAO)