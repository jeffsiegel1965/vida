# Vida

**Your agent's wallet. Your rules. Real money.**

Vida is the first wallet built for AI agents — not humans. Your agent sends KAS and TAO, negotiates deals with other agents, and stakes validators. You decide the limits. You revoke anytime. The agent never touches your seed.

It works on Kaspa (KAS) and Bittensor (TAO). The contract system uses Kaspa covenants — SilverScript smart contracts that run on L1.

---

## For everyone

### What this is

An AI agent with a wallet is a powerful thing. An AI agent with **your** wallet keys is a disaster.

Vida gives your agent a **session** — a limited, revocable grant. The agent can send up to X KAS per transaction, Y KAS per day, only to addresses you approve. It can negotiate terms with other agents, stake TAO, and create on-chain covenants. It cannot access your seed, change its own limits, or outlast the session.

You hold the keys. The agent holds a permission slip.

### What this is not

- Not a cloud wallet. Not a custodial service. Your seed stays on your machine.
- Not a hardware wallet. Keys exist in memory while unlocked.
- Not a bank. Self-custody means self-responsibility.
- Not a promise. Code is proof. Run the tests.

### Quick start

```bash
git clone https://github.com/jeffsiegel1965/vida.git
cd vida
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Step 1: Create your wallet
python scripts/setup_owner_wallet.py
# → write down the 24 words. Store them offline.

# Step 2: Grant your agent a session
python scripts/grant_session.py --hours 24 --max-tx 1 --max-day 5

# Step 3: Done. Your agent can now send up to 1 KAS/tx, 5 KAS/day.
# Revoke anytime: python scripts/grant_session.py --revoke
```

That's it. Three commands. Your agent is live on mainnet with guardrails.

### What you can do

| You want to... | How |
|----------------|-----|
| Give an agent spending money | `grant_session.py` |
| Let agents negotiate terms with each other | [Covenant negotiation](#covenant-negotiation) |
| Stake TAO without giving up your keys | `tao stake --amount 0.05` |
| Create a self-replicating contract | [SilverScript quine](#silverscript-quine) |
| See every deal an agent has made | [DealBook](#dealbook-audit-log) |
| Take it all back | Delete the session file |

### Why covenants

Kaspa covenants are on-chain smart contracts. Not "we promise" — the network itself enforces the rules. When an agent creates a covenant pot, the money is locked in a contract that says "pay the agent up to X per day, only to these addresses." No software policy in the middle. On-chain. Hard.

Vida's covenant system supports two modes:

- **MVP pot** — software-policy enforced, good for testing and low-value operations
- **SilverScript quine** — self-replicating on-chain covenant (same pattern as KII's mainnet quine), generations auto-renew, owner burns to reclaim

---

## For developers

### Architecture

```
┌──────────────────────────────────────────────────┐
│                   Owner                           │
│  (seed phrase — never shared)                     │
└──────────────┬───────────────────────────────────┘
               │ grants caps
               ▼
┌──────────────────────────────────────────────────┐
│            Session File                           │
│  max_kas_per_tx  │  max_kas_per_day               │
│  allowed_destinations  │  duration_hours           │
│  deal_hash (SHA-256 integrity)                    │
└──────────────┬───────────────────────────────────┘
               │ agent operates within caps
               ▼
┌──────────────────────────────────────────────────┐
│               Vida Kernel                         │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Kaspa    │  │ TAO      │  │ Covenant        │  │
│  │ core     │  │ plugin   │  │ module          │  │
│  │ send/rcv │  │ stake/p2p│  │ negotiate/pot   │  │
│  └──────────┘  └──────────┘  └────────────────┘  │
└──────────────┬───────────────────────────────────┘
               │
               ▼
    Kaspa mainnet · TAO Finney · testnet-10/12
```

### Rails

| Rail | License | What the agent can do |
|------|---------|----------------------|
| **Kaspa core** | MIT | Receive, hold, send KAS. Mainnet-proven. |
| **TAO plugin** | MIT | Stake, unstake, P2P transfer, emission-based optimization. |
| **Covenant module** | Commercial | Fund/spend agent pots, P2P negotiation, SilverScript quine, DealBook audit log. |

### Covenant negotiation

Two agents walk into a deal. Agent A proposes: "Give me 5 KAS/day for 24 hours, I'll send it to these addresses." Agent B's owner policy says: "max 2 KAS/tx, first-time counterparty escalates to me."

```python
from vida.plugins.covenant import Negotiator

neg = Negotiator(owner_id="jeff")
result = neg.template_deal(
    max_kas_per_tx=5.0,
    max_kas_per_day=10.0,
    duration_hours=24.0,
    counterparty_id="agent_abc",
)
# → Escalates: first-time counterparty, pot value 10 KAS
```

#### Multi-round negotiation

```python
from vida.plugins.covenant import Negotiator

neg = Negotiator(owner_id="jeff")
session = neg.start_session(agent_id="agent_xyz")

session.make_offer(max_kas_per_tx=5.0, max_kas_per_day=10.0)
session.counter_offer(
    max_kas_per_tx=2.0, max_kas_per_day=5.0,
    party="owner", note="Too rich. Cut to 2/5."
)
final = session.accept(party="agent")
```

**Limits:**
- Max 10 negotiation rounds
- Max 25% concession per round
- First-time counterparties > 50% of approval threshold → human escalation

#### DealBook (audit log)

Every deal is recorded. Query history, average terms, first-time checks:

```python
from vida.plugins.covenant.negotiation import DealBook

book = DealBook()
book.record_deal("agent_abc", terms, "session_001")
book.average_max_kas_per_tx("agent_abc")  # 3.5 KAS
book.is_first_deal("agent_new")           # True
```

### Agent pot strategies

| Strategy | Enforcement | When to use | Status |
|----------|-------------|-------------|--------|
| `covenant_bound_p2pk_pot` | Software policy | Testing, low-value, trusted agents | ✅ Shipped |
| `self_replicating_quine_pot` | On-chain SilverScript | Production, high-value, autonomous agents | ✅ SilverScript compiled & debugger-verified |

### SilverScript quine

The quine contract reproduces its own hash in each generation's change output. Each generation decrements a counter. The owner can burn any generation via signature to reclaim funds.

```json
{
  "strategy": "self_replicating_quine_pot",
  "quine_generations": 96,
  "auto_renew": true,
  "policy_hash": "a1b2c3..."
}
```

Based on KII's mainnet pattern (covenant `b802c18b...`, ~96 generations from 1 KAS).

### Pot spend policy

Before broadcasting any spend, Vida checks:

| Check | Enforces |
|-------|----------|
| `amount_sompi ≤ max_tx_sompi` | Per-tx hard ceiling |
| `destination in allowlist` (optional) | Address whitelist |
| `amount_sompi ≤ max_tx_sompi` (owner return too) | No bypass on key compromise |

### Hermes agent tools

19 tools for Hermes Agent to interact with covenants:

```
covenant_status          → Module health
covenant_negotiate_terms → One-step agent offer + strategy selection
covenant_multi_round_negotiate → Full session with audit log
covenant_quine_info      → SilverScript deployment info
covenant_fee_schedule    → Fee structure
covenant_kascov_*        → Explorer integration (live/verify/search)
covenant_spend_policy_check → Pre-flight validation
```

### Tests

```bash
# Full suite — 139 tests, 17 seconds
python3 -m pytest tests/ -v
```

| Suite | Tests | Covers |
|-------|-------|--------|
| Covenant negotiation | 19 | Multi-round, caps, escalation, DealBook |
| Covenant robustness | — | Edge cases, error handling |
| Covenant scaffold | — | Module setup, basic ops |
| TAO | 62 | Staking, P2P, optimization |
| Kaspa core | 27 | Wallet, transactions, security |

### CI

[![Covenant CI](https://github.com/jeffsiegel1965/vida/actions/workflows/covenant-ci.yml/badge.svg)](https://github.com/jeffsiegel1965/vida/actions/workflows/covenant-ci.yml)
[![Kaspa + TAO tests](https://github.com/jeffsiegel1965/vida/actions/workflows/ci.yml/badge.svg)](https://github.com/jeffsiegel1965/vida/actions/workflows/ci.yml)

Both pass on every push to `main`.

---

### Proof

**Kaspa mainnet — agent send, 10 KAS:**
[`d32b4504…5825e7`](https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7)

**Covenant lifecycle (testnet-10, fresh demo):**
```
Genesis    9b046551ea7ed627...
Transition 6521184b58682bf1...
Burn       fcb5d907e0ef6b71...
```
Covenant: [`b5828003…471797`](https://kascov.io/c/testnet-10/b58280037a692f4cd1ae087d9e258505add8e4fd4976a1146c6951b6ee471797)

**TAO Finney — agent stake, 0.02 TAO:**
`0x44c9b9…`

---

### Plugin platform

```python
# Every plugin follows the same contract
class MyPlugin:
    def grant(self, session: Session) -> GrantResult
    def execute(self, action: str, params: dict) -> ActionResult
    def revoke(self) -> None
```

| Plugin | Rail | Status |
|--------|------|--------|
| Kaspa core | KAS | MIT |
| TAO | TAO | MIT |
| Covenant | KAS covenants | Commercial |

---

### License

- **Kaspa core + TAO plugin:** MIT
- **Covenant module:** Commercial

Development fund (KAS):
```
kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k
```

---

**Don't trust marketing. Run the tests. Read the code. Self-custody means self-responsibility.**