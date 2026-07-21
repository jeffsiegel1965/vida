# Vida

**The agent wallet. Kaspa + Bittensor.**

<p align="center">
  <img src="assets/social-preview.jpg" width="800" alt="Vida — The Agent Wallet" />
</p>

Vida is a wallet for autonomous AI agents. Agents use it to discover subnets on Bittensor, negotiate covenants on Kaspa, and pay for compute, inference, storage, and data. You control the session caps. The agent never touches your keys. To revoke access, delete a file.

---

## Quick Start

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

## Why It's Well-Built

1. **Session-Gated Security**: Agents operate within user-defined limits (per-tx, per-day). Revoke access instantly by deleting a session file.
2. **Verification Ladder**: Every financial operation is verified at multiple levels (`@require_l1_spend` enforces on-chain proof).
3. **Battle-Tested**: 257 tests covering negotiation, memory, TAO staking, escrow, and payment channels.
4. **Kaspa SDK Integration**: Uses the official Kaspa SDK with fixes for `compute_budget` issues.
5. **Dual License**: MIT for core functionality, commercial for covenant modules.

---

## Capabilities

| Feature | Description | Proof TXIDs |
|---------|-------------|-------------|
| **KAS Transactions** | Send/receive KAS with session caps | [`d32b4504...`](https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7) |
| **TAO Staking** | Stake/unstake on Bittensor subnets | `0xdc2cd8...`, `0x44c9b9...` |
| **Covenants** | Deploy and manage SilverScript contracts | `b5828003...`, `6d58b529...` |
| **Payment Channels** | Off-chain micropayments with on-chain settlement | 36 tests |
| **x402 Auto-Pay** | Automatically pay for subnet API calls | 7 tests |
| **Agent Negotiation** | Templates, volume discounts, subscriptions | 27 tests |

---

## Code Examples

### Agent Memory
```python
from vida.agents.memory import AgentMemory, DealRecord

mem = AgentMemory("agent_wallet")
mem.record_deal(DealRecord(id="d1", deal_type="tao_stake", counterparty_id="sn19", amount_tao=5.0))
mem.get_counterparty("sn19")  # success rate, volume, history
```

### TAO Subnet Query
```python
from vida.plugins.tao import tao_subnet_query

tao_subnet_query(netuid=19, body={"model": "deepseek", "prompt": "Hello"})
# → {"ok": True, "data": {"response": "..."}}
```

### Covenant Deployment
```python
result = covenant_deploy_ownable(private_key_hex="...", value_sompi=100_000_000)
# → covenant_id, txid, address
```

---

## Interfaces

| Interface | Use Case | Command |
|-----------|----------|---------|
| **CLI** | Wallet setup, session grants | `python scripts/...` |
| **Admin Dashboard** | Monitor balances, sessions | `python scripts/vida_admin.py` → :8082 |
| **MCP Server** | Direct agent integration | `VIDA_SESSION=session.json python scripts/vida_mcp_server.py` |

---

## License

**MIT** (core, TAO, agent, CLI) / **Commercial** (covenant module).

Fees: `VIDA_FEE_ADDRESS` (KAS), `VIDA_TAO_FEE_ADDRESS` (TAO), `VIDA_DONATION_ADDRESS` (KAS).