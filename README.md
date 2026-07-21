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

## Architecture

```
Owner ─── grants session caps ───→ Vida Kernel
                                       │
                          ┌────────────┼────────────┐
                          │            │            │
                     Kaspa core    TAO plugin   Covenant
                   (send/recv)   (stake/pay)   (SilverScript)
                   wRPC + SDK    Finney        escrow + channels
                   mainnet       pre-dTAO      pattern library
                          │            │            │
                          └────────────┼────────────┘
                                       │
                                  Agent layer
                         (orchestrator / MCP server)
                                       │
                                  LLM agent
                                       │
                          Agent memory + negotiation
                                       │
                          Subnet gateway fees (0.05%)
```

### Security

| Layer | Mechanism |
|-------|-----------|
| Key storage | AES-256-GCM encrypted JSON (scrypt KDF, 2^17 N, 128 MiB) |
| Session binding | AAD binds session to host and expiry |
| Spend counters | Authenticated, tamper-evident, per-day tracking |
| File permissions | 0600 on keys and sessions |
| Verification | L1-L5 ladder. `@require_l1_spend` for financial ops. L4 blocked for money. |
| Key generation | secp256k1 + ML-DSA-65 (post-quantum) |

---

## Agent memory

Vida agents remember everything across sessions.

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
- **Subnet usage** — which subnets deliver, which do not
- **Context** — what the agent was doing, survives interruptions

---

## User control to total agent autonomy

Vida operates on a spectrum. You decide where each agent sits.

| Mode | What happens | Session caps |
|------|-------------|--------------|
| **Manual** | Agent proposes, you sign | 0 KAS auto-spend |
| **Guarded** | Agent spends within caps | 1 KAS/tx, 5 KAS/day, allowlist |
| **Autonomous** | Agent negotiates, deploys, pays | 10 KAS/tx, 100 KAS/day, any dest |

The agent does not have access to your seed phrase.
You set per-transaction caps, per-day limits, destination allowlists, and expiry.
To revoke access, delete a file.

---

## User interface

| Interface | What it does |
|-----------|-------------|
| **CLI** | Create wallets, grant sessions, run agents |
| **Admin dashboard** (port 8082) | Wallet balance, active sessions, recent txs, covenant status, subnet marketplace |
| **MCP server** (12 tools) | Agents connect directly. Check balances, deploy pots, open channels, stake TAO, query subnets |

```bash
# Admin dashboard
python scripts/vida_admin.py
# → http://localhost:8082

# MCP server — agents connect here
VIDA_SESSION=session.json python scripts/vida_mcp_server.py
```

---

## Bittensor (TAO)

### Stake and unstake

```python
from vida.plugins.tao.substrate_client import delegate_stake

result = delegate_stake(substrate_client, coldkey_hex="...", hotkey="5CQKp5...", amount_tao=5.0, netuid=19)
```

### Direct subnet connection

9 subnets across 8 service types. Agents discover, pay, and query in code.

```python
from vida.plugins.tao import tao_list_subnets, tao_subnet_info, tao_subnet_query

# Discover
tao_list_subnets(service_type="llm_inference")
# → 3 subnets: SN 1, SN 9, SN 19

# Inspect
tao_subnet_info(19)
# → {"cost": "0.00005 TAO/request", ...}

# Query
tao_subnet_query(netuid=19, body={"model": "deepseek", "prompt": "Hello"})
# → {"ok": True, "data": {"response": "..."}}
```

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

### x402 auto-pay

When a subnet returns HTTP 402, Vida auto-pays and retries.

```python
result = x402_query("https://subnet.api/query", substrate_client, coldkey_hex)
# → X402Response(paid=True, txid="0x...", original_result={...})
```

Gateway fee: 0.05% per query. First 100/day free.

---

## Peer-to-peer payments

```python
from vida.transactions import VidaTransactor
from vida.secure_wallet import SecureVida

wallet = SecureVida("wallet.json")
tx = VidaTransactor(wallet)
result = await tx.send(to_address="kaspa:qzyswp...", amount_kas=1.0)
```

### Payment channels

Off-chain micropayments, on-chain settlement.

```python
from vida.plugins.covenant.channels import vida_channel_open, vida_channel_update, vida_channel_close

ch = vida_channel_open("agent_a", "agent_b", capacity_kas=10.0)
vida_channel_update(ch["channel_id"], "sig_a", "sig_b", 6.0, 4.0)
vida_channel_close(ch["channel_id"])
```

Fee: 0.1% of channel capacity.

---

## Kaspa covenants

Covenant pots are SilverScript contracts. They enforce spending rules at the network level.
No software can bypass them. Toccata active on mainnet (DAA 490M).

### Agent pots

```python
plan = plan_agent_pot(max_kas_per_tx=1.0, max_kas_per_day=5.0)
check_spend_kas(policy=plan, amount_kas=2.0, destination="...")
# → {"ok": False, "error": "amount exceeds max_tx_sompi"}
```

### Escrow

```python
escrow = vida_escrow_create(buyer_address="kaspa:buyer...", seller_address="kaspa:seller...", amount_kas=10.0)
vida_escrow_release(escrow_id, seller_sig, arbiter_sig)   # seller delivers
vida_escrow_refund(escrow_id, buyer_sig)                   # buyer reclaims
vida_escrow_resolve(escrow_id, arbiter_sig, recipient)     # arbiter rules
```

Fee: 0.1% (min 0.01 KAS, max 1 KAS).

### Covenant pattern library

Pre-compiled SilverScript contracts, ready to deploy.

| Pattern | What it does |
|---------|-------------|
| **Ownable** | Single-owner covenant. Agent-controlled pots. |
| **TimeLock** | Lock funds until block height. Delayed payments, vesting cliffs. |
| **AtomicSwap** | HTLC. Trustless cross-party exchange. |
| **Vesting** | Linear release over time. Grants, salaries, distributions. |
| **SocialRecovery** | Owner + N guardians. Wallet recovery. |
| **StreamingPayment** | Pay-per-second stream. Pay-as-you-go. |
| **DeadMansSwitch** | If owner does not touch for N blocks, beneficiary claims. |
| **MultiSigVault** | M-of-N treasury vault. |
| **Subscription** | Recurring payment channel. |
| **VaultV1** | Time-delayed withdrawal with panic recovery. |

```python
result = covenant_deploy_ownable(private_key_hex="...", value_sompi=100_000_000)
# → {"ok": True, "covenant_id": "...", "txid": "...", "address": "kaspa:..."}
```

V1 transactions use `compute_budget=10`. Confirmed by smartgoo (Jul 21).

---

## Agent negotiation

```python
from vida.agents.negotiation import SessionManager

mgr = SessionManager()
session = mgr.create_session("counterparty_agent", template="standard")
offer = session.make_initial_offer()
response, accepted = session.respond_to_offer(counterparty_terms)
if accepted:
    result = session.accept_terms(counterparty_terms, deploy_escrow=True)
```

- 3 templates: micro (0.1 KAS), standard (1 KAS), power (10 KAS)
- 2 strategies: BOULWARE (default), CONCEDE (trusted counterparties)
- Volume discounts up to 30%
- Subscriptions with 15% fee discount
- Human escalation at 100 KAS
- Escrow integration on acceptance

---

## Tests

```
257 passed in 17s
```

| Suite | Count |
|-------|-------|
| Negotiation | 27 |
| Agent memory | 9 |
| TAO marketplace + staking | 72 |
| Escrow | 17 |
| Payment channels | 36 |
| x402 | 7 |
| Kaspa SDK (live TN10) | 6 |
| Covenant deploy | 3 |
| Covenant scaffold | 39 |
| Multisig | 17 |
| Agent memory + orchestrator | 24 |

---

## On-chain proofs

- **KAS send, 10 KAS:** [`d32b4504...`](https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7)
- **TN10 covenants:** `b5828003...`, `6d58b529...`, `2d0ade44...`
- **TAO Finney stake:** `0xdc2cd8...`, `0x44c9b9...`

---

## License

Dual license: **MIT** (Kaspa core, TAO plugin, Agent layer, CLI) / **Commercial** (covenant module).

Fees: `VIDA_FEE_ADDRESS` (KAS), `VIDA_TAO_FEE_ADDRESS` (TAO), `VIDA_DONATION_ADDRESS` (KAS).