# Vida

**Powering the agent economy. Revocable autonomy. Agentic P2P payments.**

Vida is an agentic wallet for Bittensor (TAO) and Kaspa, with working covenants and a P2P negotiation protocol. You hold the seed. Your agent sends, receives, stakes, and negotiates. You set the caps. Owner-custody.

Not cloud custody. Not raw keys in chat. A session file with caps, bounded by a covenant pot.

**License:** Kaspa core + TAO plugin are MIT. The covenant module is commercial.

---

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│   Owner      │────▶│  Session File    │────▶│  Agent               │
│  (seed)      │     │  (caps + policy) │     │  (granted authority) │
└──────────────┘     └──────────────────┘     └──────────────────────┘
                           │                           │
                           ▼                           ▼
                    ┌────────────────────────────────────────┐
                    │           Vida Kernel                   │
                    │  ┌─────────┐  ┌────────┐  ┌─────────┐  │
                    │  │ Kaspa   │  │  TAO   │  │Covenant │  │
                    │  │ core    │  │ plugin │  │ module  │  │
                    │  └─────────┘  └────────┘  └─────────┘  │
                    └────────────────────────────────────────┘
                           │
                           ▼
                    ┌────────────────────────────────────────┐
                    │  On-chain                              │
                    │  KAS mainnet · TAO Finney · TN12       │
                    └────────────────────────────────────────┘
```

## Rails

| Rail | License | Status | What the agent can do |
|------|---------|--------|----------------------|
| **Kaspa core** | MIT | Shipped | Receive, hold, send KAS. Mainnet-proven. |
| **TAO plugin** | MIT | Shipped | Stake/unstake, P2P TAO, emission-based optimization. |
| **Covenant module** | Commercial | Shipped | Agent pot funding/spending, SilverScript quine, P2P negotiation, DealBook audit log. |

## Covenant System

The covenant module is a bounded P2P protocol for agent-to-agent and agent-to-owner value exchange:

### Negotiation Protocol (Phase 1-4)

| Component | What it does |
|-----------|-------------|
| **NegotiationSession** | Multi-round bargaining with round limits (max 10), concession bounds (25% max shift), and escalation to human approval |
| **DealBook** | Persistent deal history — tracks every counterparty, computes average terms, flags first-time counterparties for escalation |
| **CovenantTerms** | Deterministic `deal_hash` (SHA-256) over `max_kas_per_tx`, `max_kas_per_day`, `allowed_destinations`, `duration_hours` |
| **UserControls** | Configurable: `human_approval_threshold_kas`, `auto_deal_max_kas`, `max_negotiation_rounds`, `max_concession_pct` |
| **Negotiator** | Owner-facing wrapper — `template_deal()` for one-step agreements, session management, escalation |

### Agent Pot Strategy

| Strategy | Description | Status |
|----------|-------------|--------|
| `covenant_bound_p2pk_pot` | Software-policy pot with max_tx, max_day, destination allowlist | Shipped (MVP) |
| `self_replicating_quine_pot` | SilverScript quine: self-replicating covenant, generation counter, burn path, auto-renewal | Compiled, debugger-verified |

### SilverScript Quine

The quine covenant (`silverscript/quine_agent_pot.sil`) matches the KII mainnet pattern (covenant `b802c18b...`, 96 generations from 1 KAS). The script:
- Reproduces its own hash in the change output each generation
- Decrements a generation counter
- Provides an owner burn path via signature
- Is compiled and verified via the SilverScript debugger

### kascov-lab Lifecycle

Proven on testnet-10 (and migrated to testnet-12):
- **Genesis** → fund covenant output
- **Transition** → spend from covenant (policy-gated)
- **Burn** → owner return path

### Pot Spend Policy

Software enforcement before broadcast (not on-chain hard caps):

| Check | What it enforces |
|-------|-----------------|
| `max_tx_sompi` | Per-transaction amount limit (enforced even for owner return) |
| `allowed_destinations` | Address allowlist (optional) |
| `owner_return` | Owner address is always allowed, but capped by `max_tx` |

### Hermes Tools

The covenant module exposes 19 Hermes tools for agent interaction:

| Tool | Purpose |
|------|---------|
| `covenant_status` | Module health check |
| `covenant_negotiate_terms` | One-step agent offer with strategy selection |
| `covenant_multi_round_negotiate` | Full multi-round negotiation with audit log |
| `covenant_quine_info` | SilverScript quine deployment info |
| `covenant_fee_schedule` | Fee structure for covenant services |
| `covenant_kascov_*` | kascov explorer integration (live, verify, search, address) |
| `covenant_spend_policy_check` | Pre-flight spend validation |

## Honesty

| If you hear | The truth |
|-------------|-----------|
| "Hard on-chain limits" | **Software policy enforced in this process.** Not chain covenants. |
| "Safe if session file is stolen" | **No.** Anyone who reads the file can spend within caps. Use working balances. |
| "Daily spend counter is filesystem-proof" | **No.** A writer with the session file can reseal the daily counter. |
| "Post-quantum protected funds" | **Not on-chain.** PQ identity at rest only. Kaspa uses Schnorr, TAO uses sr25519. |
| "Guaranteed TAO yield" | **No.** Optimizer is a heuristic plan. |
| "Production bank / SLA" | **No.** Local software. Self-custody means self-responsibility. |

Also:
- `secure_wallet.py` for real funds. Legacy `wallet.py` can write plaintext keys.
- Keys exist in process memory while unlocked — not a hardware wallet.
- Lose seed + password → funds gone.

---

## Tests

```
139 tests · 17s · 3 test files
```

| Test suite | Tests | What it covers |
|-----------|-------|---------------|
| `test_covenant_negotiation.py` | 19 | Multi-round negotiation, round limits, concession bounds, escalation, DealBook, template deals |
| `test_covenant_robustness.py` | Edge cases, error handling, race conditions |
| `test_covenant_scaffold.py` | Module scaffolding, basic operations |
| TAO tests | 62 | Staking, unstaking, P2P, optimization, session management |
| Kaspa core tests | 27 | Wallet, transactions, secure operations |

```bash
cd vida
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

---

## Quick start

```bash
git clone https://github.com/jeffsiegel1965/vida.git
cd vida
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Owner setup
python scripts/setup_owner_wallet.py   # write down the 24 words
python scripts/grant_session.py        # hours + max KAS/tx + max KAS/day

# Agent negotiation
from vida.plugins.covenant import Negotiator
neg = Negotiator(owner_id="owner1")
result = neg.template_deal(
    max_kas_per_tx=1.0, max_kas_per_day=5.0,
    duration_hours=24.0, counterparty_id="agent_abc",
)

# Revoke anytime
python scripts/grant_session.py --revoke
```

---

## Proof, not pitch

### Kaspa mainnet

| What | Network | Tx |
|------|---------|-----|
| Agent send, 10 KAS | **mainnet** | [`d32b4504…5825e7`](https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7) |

### Covenant (testnet-10, migrating to testnet-12)

| What | Covenant ID | Tx |
|------|-------------|-----|
| Genesis → Transition → Burn | `04420a33…` | [`aac176cf…`](https://explorer-tn10.kaspa.org/txs/aac176cfd71e264af907220c58588128479767ac22fc878588bae6c0ab32069f) |

### TAO (Finney)

| What | Status |
|------|--------|
| Owner stake, 0.05 TAO | Live on-chain (`0xdc2cd8…`) |
| Agent session stake, 0.02 TAO | Live on-chain (`0x44c9b9…`) |
| P2P transfer, 0.005 TAO (session) | Live on-chain (`0xa0915a…`) |
| Optimize plan (emission-based) | Proven on Finney |

---

## Plugin platform

Every plugin follows the same session model:

- **Owner grants caps** per plugin
- **Agent acts inside those caps** — no password exposure
- **Revoke by deleting the session file**

| Plugin | Rail | Status |
|--------|------|--------|
| Kaspa core | Native KAS | Shipped (MIT) |
| TAO | Stake, P2P, optimize | Shipped (MIT) |
| Covenant module | On-chain policy, terms templates, P2P negotiation, quine | Shipped (Commercial) |

---

## License

- **Kaspa core + TAO plugin:** MIT. Free to use, modify, distribute.
- **Covenant module:** Commercial license. Shipped.

Optional development fund (KAS):
```
kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k
```

---

**Don't trust marketing. Run the tests. Read the code. Self-custody means self-responsibility.**