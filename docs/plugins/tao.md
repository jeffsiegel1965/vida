# Vida TAO rail (Bittensor plugin) — agentic staking + P2P

**Part of Vida—not a standalone TAO wallet.** Same owner-custody and COMMAND→FULL model as Kaspa core; extra deps via `requirements-tao.txt`.

**Headline:** Your agent can **auto-stake TAO toward high-emission validators** on a subnet—while **you** keep the seed and the caps.

**Status:** usable plugin — health, balance, owner provision, agent sessions, live Finney **stake + P2P** proofs, **emission-aware yield optimizer MVP**, PQ-ready identity at rest.

---

## Why this exists

Manual TAO staking means you pick validators and click.  
**Agentic TAO** means a local agent (Hermes, OpenClaw, …) can:

1. Read free balance  
2. **Score validators by on-chain emission** (prefer validator permit)  
3. **Plan** a rebalance: keep a free reserve, stake the rest to the **top emission scorer**  
4. **Execute** only inside a session you granted (max per tx / per day / subnets)  

That is “auto staking for max emission **targeting**”—a **heuristic**, not a guaranteed return.

---

## Install

```bash
pip install -r requirements.txt -r requirements-tao.txt
```

## Owner flow (never give seed to the agent)

```bash
python scripts/provision_tao_account.py
python scripts/grant_tao_session.py --wallet-id <id> \
  --hours 8 --max-per-tx 0.05 --max-per-day 0.1 --subnets 1
export VIDA_TAO_SESSION=data/tao_agent_session.json
```

## Agentic optimize (emission-aware)

```python
from vida.plugins.tao.tools import vida_tao_optimize, vida_tao_delegate

# 1) Plan only (read-ish / no spend) — ranks by emission, proposes stake amount
plan = vida_tao_optimize(
    wallet_id="my-tao",
    netuid=1,
    reserve_tao=0.01,
    execute=False,
)

# 2) Execute under session (needs VIDA_TAO_SESSION + confirm=True)
result = vida_tao_optimize(
    wallet_id="my-tao",
    netuid=1,
    reserve_tao=0.01,
    execute=True,
    confirm=True,
)
```

**What the scorer does (MVP):**  
- Reads subnet emission (+ permit, incentive context)  
- Prefers validators with **validator_permit**  
- Picks top score; stakes `free - reserve` if above min  

**What it does not do:** promise APY, multi-subnet portfolio theory, or MEV-aware routing.

## Other agent tools

See [HERMES_TOOLS.md](../HERMES_TOOLS.md). Money actions: **session + confirm only**.

| Tool | Role |
|------|------|
| `vida_tao_status` / `balance` | Read-only |
| `vida_tao_optimize` | Emission plan / optional auto-stake |
| `vida_tao_delegate` / `undelegate` | Direct stake moves |
| `vida_tao_transfer` | Agent P2P TAO |

## Honesty

| Claim | Reality |
|-------|---------|
| Agent can auto-stake toward high emission | **Yes** — emission heuristic MVP |
| Maximizes your yield forever | **No** — not guaranteed APY |
| Agent can send TAO | Yes, inside session caps |
| On-chain hard caps | **No** (software policy) |
| Post-quantum ready | **ML-DSA-65 at rest** — Finney still **sr25519** |
| Keys in git | **Never** — `data/` gitignored |

## Proofs

Public Finney receipts: [docs/proofs/](../proofs/) (`tao_*.md`, including stake, session stake, P2P).

## Autonomy vs Kaspa

[AUTONOMY_KASPA_VS_TAO.md](AUTONOMY_KASPA_VS_TAO.md)
