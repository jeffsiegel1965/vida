# Vida

**Your agent's wallet. You set the limits. Real money on Kaspa and TAO.**

Vida is an agentic wallet — software that lets AI agents send, receive, and stake cryptocurrency under limits you control. The agent never touches your seed phrase. You grant it a session with caps, and you can revoke it anytime.

It works on **Kaspa mainnet** (KAS) and **Bittensor Finney** (TAO). The covenant module creates on-chain smart contracts — the network itself enforces the rules, not a middleman.

---

## What it does

### Kaspa core (MIT)
Send and receive KAS through an agent session. Proven on mainnet. The agent gets spending caps per transaction and per day. You hold the keys.

### TAO plugin (MIT)
Stake TAO to validators, unstake, do P2P transfers — all through an agent session with caps. Emission-based optimization plans are generated locally (not paid marketing).

### Covenant module (Commercial)
On-chain Kaspa covenants — smart contracts written in SilverScript that lock funds and enforce rules at the network level. The module handles:

- **Agent pot planning** — calculate how much to fund a covenant, what hard limits to set (per-tx max, per-day max, destination allowlist)
- **Pot spend policy** — software-level enforcement of max_tx and allowed destinations before broadcast, including for owner return paths
- **kascov-lab integration** — run the full covenant lifecycle: Genesis (fund a covenant UTXO) → Transition (spend from it under policy) → Burn (owner reclaim)
- **SilverScript quine** — a self-replicating covenant contract (compiled, debugger-verified) that reproduces its own hash across generations, with an owner burn path. Based on the KII mainnet pattern (96 generations from 1 KAS)
- **Pot record persistence** — all covenant funding metadata saved to disk (policies, txids, subscription schedules)
- **Hermes agent tools** — 17 tools for agents to interact with covenants: check status, plan pots, query kascov explorer, validate spend policies

---

## Architecture

```
┌───────────────────────────────────────────────┐
│                  Owner                          │
│  (24-word seed phrase — stored offline)         │
└──────────────────┬────────────────────────────┘
                   │ grants caps
                   ▼
┌───────────────────────────────────────────────┐
│            Session File                         │
│  max_kas_per_tx  │  max_kas_per_day             │
│  allowed_destinations  │  duration_hours         │
└──────────────────┬────────────────────────────┘
                   │ agent operates within caps
                   ▼
┌───────────────────────────────────────────────┐
│               Vida Kernel                       │
│                                                 │
│  ┌─────────────────┐  ┌───────────────────┐    │
│  │  Kaspa core      │  │  TAO plugin       │    │
│  │  · send/receive  │  │  · stake/unstake  │    │
│  │  · mainnet       │  │  · P2P transfer   │    │
│  └─────────────────┘  │  · optimizations   │    │
│                       └───────────────────┘    │
│  ┌────────────────────────────────────────┐    │
│  │  Covenant module (commercial)           │    │
│  │  · pot planning & policy enforcement    │    │
│  │  · kascov-lab lifecycle (TN10)          │    │
│  │  · SilverScript quine contracts         │    │
│  │  · pot record persistence               │    │
│  │  · 17 Hermes agent tools               │    │
│  └────────────────────────────────────────┘    │
└──────────────────┬────────────────────────────┘
                   │
                   ▼
     Kaspa mainnet · TAO Finney · testnet-10
```

---

## Quick start

```bash
git clone https://github.com/jeffsiegel1965/vida.git
cd vida
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Create your wallet — write down the 24 words
python scripts/setup_owner_wallet.py

# Grant an agent session: 1 KAS/tx, 5 KAS/day, 24 hours
python scripts/grant_session.py --hours 24 --max-tx 1 --max-day 5

# Revoke anytime
python scripts/grant_session.py --revoke
```

---

## Agent pot system

An agent pot is a funding plan for a covenant. The module calculates how much KAS to fund, what hard rules the covenant should enforce, and estimates network fees.

```python
from vida.plugins.covenant import plan_agent_pot

plan = plan_agent_pot(
    max_kas_per_tx=1.0,
    max_kas_per_day=5.0,
    allowed_destinations=["kaspa:address..."],
    session_hours=24,
)
# → { "ok": True, "fund_pot_kas": 5.0, "max_tx_sompi": 100000000, ... }
```

### Pot spend policy

Before broadcasting any spend, Vida checks:

| Check | What it prevents |
|-------|-----------------|
| `amount_sompi ≤ max_tx_sompi` | Agent can't exceed per-transaction cap |
| `destination in allowlist` (optional) | Agent can only send to approved addresses |
| Owner return also capped by max_tx | Compromised key can't drain the pot |

```python
from vida.plugins.covenant import check_spend_kas

result = check_spend_kas(
    policy=plan,
    amount_kas=2.0,
    destination="kaspa:address...",
)
# → { "ok": False, "error": "amount exceeds max_tx_sompi", ... }
```

### Covenant lifecycle (via kascov-lab)

Run the full lifecycle on testnet-10:

```bash
# Generate a key
kascov-lab keygen

# Check balance
kascov-lab balance

# Full lifecycle: Genesis → Transition → Burn
kascov-lab demo --transitions 2
```

**Fresh on-chain proof (Jul 18, 2026):**

```
Covenant: b58280037a692f4cd1ae087d9e258505add8e4fd4976a1146c6951b6ee471797
Genesis:  https://explorer-tn10.kaspa.org/txs/9b046551ea7ed627...
View on: https://kascov.io/c/testnet-10/b58280037a692f4cd1ae087d9e258505add8e4fd4976a1146c6951b6ee471797
```

### SilverScript quine

The quine contract reproduces its own covenant hash in the change output of each spend. Each generation decrements a counter. The owner can burn any generation by signing a burn transaction.

```
quine_agent_pot.sil  (compiled, debugger-verified)
  entrypoints: withdraw(pubkey), burn(sig)
  pattern: KII mainnet quine (96 generations from 1 KAS)
  covenant: b802c18ba691c4a52c4a89de7f72fe475637e3a70f9f56a32663b5754a1ed4af
```

---

## Hermes agent tools

The covenant module exposes 17 tools for Hermes Agent integration:

| Tool | What it does |
|------|-------------|
| `covenant_status` | Module health check |
| `covenant_describe` | Capabilities overview |
| `covenant_live_gates` | Check if kascov-lab is available |
| `covenant_plan_pot` | Calculate agent pot funding |
| `covenant_plan_with_fees` | Pot plan with dev fee breakdown |
| `covenant_estimate_fee` | Fee estimation for fund or spend |
| `covenant_fee_schedule` | Full fee structure |
| `covenant_spend_policy_check` | Validate a spend against policy |
| `covenant_pot_record` | Load stored pot records |
| `covenant_validate_pot` | Verify policy template hash integrity |
| `covenant_quine_info` | SilverScript quine deployment info |
| `covenant_kascov_live` | kascov explorer live feed |
| `covenant_kascov_verify` | Verify covenant on-chain |
| `covenant_kascov_search` | Search covenants by query |
| `covenant_kascov_address` | Check which covenants an address controls |

---

## Proof

| Rail | What | Tx |
|------|------|-----|
| Kaspa mainnet | Agent send, 10 KAS | [`d32b4504…`](https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7) |
| Covenant TN10 | Genesis → Transition → Burn | [`9b046551…`](https://explorer-tn10.kaspa.org/txs/9b046551ea7ed627b3caaa2894f24f48d67fd0ffdabb13055cdac233d8de8272) |
| TAO Finney | Owner stake, 0.05 TAO | `0xdc2cd8…` (on-chain) |
| TAO Finney | Agent session stake, 0.02 TAO | `0x44c9b9…` (on-chain) |
| TAO Finney | P2P transfer, 0.005 TAO | `0xa0915a…` (on-chain) |

---

## Tests

```
104 tests · 17s · pytest
```

| Suite | Tests | Coverage |
|-------|-------|----------|
| Covenant scaffold | Scaffolding, basic operations |
| Covenant robustness | Edge cases, error handling |
| TAO staking | 62 | Stake, unstake, P2P, session management |
| Kaspa core | 27 | Wallet, transactions, secure operations |

---

## Plugin platform

Every plugin follows the same session model:

- Owner grants caps per plugin
- Agent acts inside those caps — no password exposure
- Revoke by deleting the session file

| Plugin | Rail | Status | License |
|--------|------|--------|---------|
| Kaspa core | KAS | Shipped | MIT |
| TAO | TAO | Shipped | MIT |
| Covenant module | KAS covenants | Shipped | Commercial |

---

## License

- **Kaspa core + TAO plugin:** MIT — free to use, modify, distribute
- **Covenant module:** Commercial license

Development fund (KAS):
```
kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k
```

---

**Don't trust marketing. Read the code. Run the tests. Self-custody means self-responsibility.**
