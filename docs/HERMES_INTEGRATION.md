# Hermes ↔ Vida — not standalone

**Vida is not a separate “bank app” you live in.**  
It is the **wallet layer** that **Hermes (or OpenClaw / other local agents) drives**.

You talk to Hermes. Hermes uses Vida tools/scripts. You stay in control of **how much** autonomy you grant.

---

## Flexibility spectrum (one product, many modes)

| Level | Who drives | What the agent can do | How you set it |
|-------|------------|------------------------|----------------|
| **0 — Owner only** | You (via Hermes or terminal) | Nothing agent-autonomous | No session file, or revoke |
| **1 — COMMAND** | You approve each money move | Agent prepares; **you** confirm each spend/stake/send | Session `mode=COMMAND` (or no session + owner scripts) |
| **2 — HYBRID** | Agent under a threshold | Autonomous below threshold; ask you above | `mode=HYBRID` + `threshold` + caps |
| **3 — FULL (agentic)** | Agent within hard caps | Stake, P2P pay, emission optimize **inside** max/tx, max/day, allowlists, hours | `mode=FULL` + caps (+ optional `--dest`, `--subnets`) |

**Full agentic ≠ give away the seed.**  
Full = “agent may act alone **only** inside parameters you set with Hermes/scripts.”

---

## What Hermes is for

| Hermes helps you… | Not… |
|-------------------|------|
| Check status/balance | See your seed/password |
| Propose grants (“8h, 0.05 TAO/tx, subnet 1, FULL”) | Invent unlimited access |
| Plan emission rebalance | Bypass caps |
| Execute **after** you granted a session | Store mnemonic in chat |
| Revoke (“kill the session”) | Become the custodian |

**Passwords and seeds:** owner terminal / owner-only scripts only.  
**Chat:** session path + policy params, never the seed.

---

## Kaspa + TAO under the same idea

TAO is a **Vida plugin rail**, not a second wallet product. One ownership model; separate chain keys/sessions as required by each network.


| Rail | Hermes-controlled actions |
|------|---------------------------|
| **Kaspa** | Status, agent send KAS under session |
| **TAO** | Status, balance, **P2P transfer**, stake/unstake, **emission auto-stake plan/execute** |

Both rails: same ownership model, same session idea, same “you set parameters → agent runs.”

---

## Example: user tells Hermes

**Tight control**
> “Grant TAO session COMMAND only, 0.01 max per tx, subnet 1, 4 hours. Don’t stake without asking me each time.”

**Balanced**
> “HYBRID: agent may auto-stake up to 0.02 TAO alone; anything bigger needs me. Max 0.1/day.”

**Full agentic**
> “FULL for 24h: max 0.05/tx, 0.2/day, subnets 1, allow optimize + transfer only to these SS58s. Then revoke tomorrow.”

Hermes should translate that into `grant_tao_session.py` / Kaspa `grant_session.py` args and env (`VIDA_TAO_SESSION`), then use tools inside those bounds.

---

## Product rule

```
Standalone wallet app?     NO  (optional CLI scripts exist for owners)
Hermes-integrated rail?    YES
User sets parameters?      YES (modes, caps, allowlists, hours)
Full agentic possible?     YES (FULL + caps — still owner-custody)
Seed to agent?             NEVER
```

---

## Related

- Tool contract: [HERMES_TOOLS.md](HERMES_TOOLS.md)  
- TAO guide: [plugins/tao.md](plugins/tao.md)  
- Autonomy parity: [plugins/AUTONOMY_KASPA_VS_TAO.md](plugins/AUTONOMY_KASPA_VS_TAO.md)  
- Marketing: [MARKETING.md](MARKETING.md)  
