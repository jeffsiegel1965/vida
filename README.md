# Vida

**The agent wallet. Kaspa + Bittensor.**

<p align="center">
  <img src="assets/social-preview.jpg" width="800" alt="Vida — The Agent Wallet" />
</p>

Vida is a wallet for autonomous AI agents. Agents use it to discover subnets on Bittensor, negotiate covenants on Kaspa, and pay for compute, inference, storage, and data. You control the session caps. The agent never touches your keys. To revoke access, delete a file.

---

## Quick start

```bash
git clone https://github.com/jeffsiegel1965/vida.git
cd vida
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Create wallet
python scripts/setup_owner_wallet.py

# Grant an agent session: 1 KAS/tx, 5 KAS/day, 24h
python scripts/grant_session.py --hours 24 --max-tx 1 --max-day 5

# Run the agent
PYTHONPATH=$PWD python -m vida.agents.staking_optimizer \
  "Check covenant status and plan a 5 KAS agent pot"
```

---

## Agent memory

Agents remember everything across sessions — deals, counterparty profiles, subnet usage, context.

```python
from vida.agents.memory import AgentMemory, DealRecord

mem = AgentMemory("agent_wallet")
mem.record_deal(DealRecord(id="d1", deal_type="tao_stake", counterparty_id="sn19", amount_tao=5.0))
mem.get_counterparty("sn19")          # success rate, volume, history
mem.volume_discount_rate("sn19")      # 0.20 if 1000+ TAO
mem.get_context("current_goal")       # survives interruptions
```

---

## User control to agent autonomy

| Mode | Agent does | You set |
|------|-----------|---------|
| **Manual** | Proposes spends | Sign each tx |
| **Guarded** | Spends within caps | 1 KAS/tx, 5 KAS/day, allowlist |
| **Autonomous** | Negotiates, deploys, pays | 10 KAS/tx, 100 KAS/day, any dest |

```python
python scripts/grant_session.py --hours 24 --max-tx 1 --max-day 5 --destinations kaspa:abc...
```

---

## Interfaces

| Interface | Use it to | Command |
|-----------|-----------|---------|
| **CLI** | Create wallets, sessions, run agents | `python scripts/...` |
| **Admin dashboard** | Check balance, sessions, txs, covenants, subnets | `python scripts/vida_admin.py` → :8082 |
| **MCP server** | Wire agents directly: balances, pots, channels, stake, queries | `VIDA_SESSION=session.json python scripts/vida_mcp_server.py` |

---

## Bittensor (TAO)

### Stake / unstake

```python
from vida.plugins.tao.substrate_client import delegate_stake
delegate_stake(client, coldkey_hex="...", hotkey="5CQKp5...", amount_tao=5.0, netuid=19)
```

### Direct subnet queries

9 subnets across 8 services. Discover, pay, and query — all in code.

```python
from vida.plugins.tao import tao_subnet_query
tao_subnet_query(netuid=19, body={"model": "deepseek", "prompt": "Hello"})
# → {"ok": True, "data": {"response": "..."}}
```

| Service | Subnets | Cost |
|---------|---------|------|
| LLM inference | SN 1, 9, 19 | 0.00005 TAO/req |
| GPU compute | SN 14 | 0.01 TAO/hr |
| Storage | SN 27 | 0.0001 TAO/GB |
| Image gen | SN 34 | 0.001 TAO/img |
| Audio | SN 3 | 0.00005 TAO/min |
| Video | SN 29 | 0.005 TAO/video |
| Data scraping | SN 4 | 0.0001 TAO/1k |
| AI agents | SN 1 | 0.0005 TAO/req |

### x402 — auto-pay

HTTP 402 → auto-pay → retry.

```python
x402_query("https://subnet.api/query", client, coldkey_hex)
# → paid=True, txid="0x...", data={...}
```

0.05% gateway fee. First 100/day free.

---

## Peer-to-peer payments

```python
from vida.transactions import VidaTransactor
tx = VidaTransactor(SecureVida("wallet.json"))
await tx.send(to_address="kaspa:qzyswp...", amount_kas=1.0)
```

### Payment channels

Off-chain micropayments, on-chain settlement.

```python
from vida.plugins.covenant.channels import vida_channel_open, vida_channel_update, vida_channel_close

ch = vida_channel_open("agent_a", "agent_b", capacity_kas=10.0)
vida_channel_update(ch["channel_id"], "sig_a", "sig_b", 6.0, 4.0)
vida_channel_close(ch["channel_id"])
```

0.1% of channel capacity.

---

## Kaspa covenants

SilverScript contracts enforced at the network level. Toccata active on mainnet (DAA 490M).

### Agent pots

```python
plan = plan_agent_pot(max_kas_per_tx=1.0, max_kas_per_day=5.0)
check_spend_kas(plan, 2.0, "kaspa:...")  # blocked: exceeds max_tx
```

### Escrow

```python
escrow = vida_escrow_create(buyer_address="kaspa:buyer...", seller_address="kaspa:seller...", amount_kas=10.0)
vida_escrow_release(escrow_id, seller_sig, arbiter_sig)
vida_escrow_refund(escrow_id, buyer_sig)
vida_escrow_resolve(escrow_id, arbiter_sig, recipient)
```

0.1% (min 0.01 KAS, max 1 KAS).

### Patterns — pre-compiled, ready to deploy

| Pattern | Use for |
|---------|---------|
| **Ownable** | Single-owner agent pots |
| **TimeLock** | Delayed payments, vesting cliffs |
| **AtomicSwap** | Trustless exchange (HTLC) |
| **Vesting** | Grants, salaries, distributions |
| **SocialRecovery** | Wallet recovery (owner + N guardians) |
| **StreamingPayment** | Pay-as-you-go per second |
| **DeadMansSwitch** | Beneficiary claims if owner inactive |
| **MultiSigVault** | M-of-N treasury |
| **Subscription** | Recurring billing |
| **VaultV1** | Time-delayed withdrawal + panic recovery |

```python
result = covenant_deploy_ownable(private_key_hex="...", value_sompi=100_000_000)
# → covenant_id, txid, address
```

---

## Agent negotiation

```python
session = SessionManager().create_session("counterparty_agent", template="standard")
offer = session.make_initial_offer()
response, accepted = session.respond_to_offer(counterparty_terms)
if accepted:
    result = session.accept_terms(counterparty_terms, deploy_escrow=True)
```

3 templates, 2 strategies, volume discounts up to 30%, subscriptions at 15% off, escrow integration, human escalation at 100 KAS.

---

## Tests

```
257 passed
```

Negotiation 27 · Memory 9 · TAO 72 · Escrow 17 · Channels 36 · x402 7 · Kaspa SDK 6 · Covenants 42 · Multisig 17

---

## On-chain proofs

- KAS send, 10 KAS: [`d32b4504...`](https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7)
- TN10 covenants: `b5828003...`, `6d58b529...`, `2d0ade44...`
- TAO Finney stake: `0xdc2cd8...`, `0x44c9b9...`

---

## License

**MIT** (core, TAO, agent, CLI) / **Commercial** (covenant module).

Fees: `VIDA_FEE_ADDRESS` (KAS), `VIDA_TAO_FEE_ADDRESS` (TAO), `VIDA_DONATION_ADDRESS` (KAS).