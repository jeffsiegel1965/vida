# Vida — marketing pack (honest)

Use these as-is. Prefer understatement over hype.

---

## Not a standalone bank

Vida is **not** “another app you log into instead of your agent.”  
It’s the **wallet Hermes uses**: you chat with Hermes, set modes and caps, and go from **manual control** to **full agentic** (stake, P2P, emission optimize) without ever handing over the seed.

## Positioning (primary)

**One product (Vida), two rails—not two apps:**

1. **Kaspa** — agent micropayments (fast/cheap settle)  
2. **TAO (Bittensor) plugin** — *inside Vida*: **agentic staking** (high-emission targeting), **P2P TAO**, same caps model as Kaspa  

The TAO story is not “another manual wallet.” It’s: **your agent can rebalance stake toward emission-leading validators on a subnet—automatically—while you keep the seed and the caps.**

---

## One-liner (dual-rail)

**Vida: the wallet Hermes runs—pay on Kaspa, agentic TAO stake + P2P—you set how autonomous.**

### Kaspa-first one-liner (if the channel is Kaspa-only)
**Vida gives your AI agent money on Kaspa—without giving it your seed.**

### TAO-first one-liner (if the channel is Bittensor)
**Your agent stakes TAO for you—toward high-emission validators—inside caps you set. You keep the seed.**

---

## Elevator (30 seconds) — dual emphasis

Most agents can talk. Almost none can **move value** or **work yield** safely.  

**Vida** is a free, open-source **agent wallet**:  
- **You** hold the 24-word seed and set limits.  
- On **Kaspa**, the agent can pay (micropayments that actually make sense).  
- On **TAO**, the agent can **auto-stake** free balance toward validators scoring high on **on-chain emission** (heuristic for “where the network is rewarding activity”)—plan-only by default, execute only with session + confirm.  

Built for Hermes, OpenClaw, and other local agents. MIT forever. Proofs, not pitch decks.

---

## Twitter / X (short) — TAO agentic stake

Your agent shouldn’t need your coldkey in chat.

Vida TAO: owner-custody sessions + **emission-aware stake planning toward high-emission validators** on a subnet.
You set max per tx / per day. Agent plans (or executes) rebalance.
Heuristic emission score—not guaranteed APY.
Finney-proven stake + P2P. MIT.

## Twitter / X (short) — dual

Vida = agent wallet you actually control.
Kaspa: pay. TAO: agentic stake toward emission.
You hold the seed. Sessions + caps. Free. MIT.

## Twitter / X (thread)

1/ AI agents need more than chat. They need **payments** and, on Bittensor, **staking that doesn’t require babysitting**.  
2/ **Vida**: free owner-custody agent wallet. You hold the seed. Time-boxed sessions + spend caps.  
3/ **Kaspa rail**: fast, cheap sends → agent micropayments that work in the real world.  
4/ **TAO rail (agentic):** agent scores validators by **on-chain emission** (+ permit bias), keeps a free reserve, stakes the rest to the top scorer—under **your** limits.  
5/ Default = **plan**. Execute only with session + confirm. Not “guaranteed APY”—emission is a **heuristic for max-emission targeting**, not a promise.  
6/ Finney proofs: stake, agent-session stake, P2P transfer in-repo.  
7/ Honest limits: software policy today; PQ identity at rest; covenants later.  
8/ Code + tests + receipts. github.com/jeffsiegel1965/vida  

---

## Landing hero options

### A — Dual (recommended)
### Life for your AI agent—on Kaspa and TAO
**Pay** with KAS. **Auto-stake** TAO toward high-emission validators.  
You hold the seed. You set the limits. The agent acts inside them.

### B — TAO spotlight
### Agentic TAO staking—without giving up the seed
Your agent rebalances toward **emission-leading validators**.  
You grant a session. You set the caps. You revoke anytime.

### C — Kaspa classic
### Life for your AI agent on Kaspa
You hold the seed. You set the limits. The agent can act—inside them.

---

## Feature bullets (public)

**Core**
- **Owner-custody** — 24-word seed never given to the agent  
- **Agent sessions** — hours, max per tx, max per day, revoke anytime  
- **Proof-first** — mainnet / Finney receipts in the repo  

**Kaspa**
- **Agent micropayments** — fees low enough for real agent commerce  

**TAO (emphasize)**
- **Agentic staking** — agent can plan/execute stake moves under policy  
- **Emission-aware targeting** — scores validators using on-chain **emission** (prefer validator permit) to chase **high-emission** placement on a subnet  
- **Auto-rebalance MVP** — keep free reserve; stake remainder to top scorer (`vida_tao_optimize`)  
- **Agent P2P TAO** — session-gated transfers for agent-to-agent value  
- **Same security model** as Kaspa: session ≠ seed  

**Forward**
- **PQ-ready identity** — ML-DSA-65 at rest (chain still classical today)  
- **Covenants** — on-chain hard caps when toolchain ready  

---

## How “max emission” is said honestly

| Say this | Not that |
|----------|----------|
| “Targets high-**emission** validators on a subnet” | “Maximizes your APY” |
| “Emission-weighted auto-stake (heuristic MVP)” | “Best yield in Bittensor” |
| “Agent rebalances free TAO toward top emission scorer” | “Guaranteed rewards” |
| “You choose subnet + caps; agent executes inside them” | “Set and forget forever risk-free” |

**Technical one-liner (docs / GitHub):**  
*Yield optimizer MVP: score subnet validators by on-chain emission (permit-weighted), keep a free TAO reserve, stake the rest to the top scorer—via agent session policy.*

---

## Competitive one-liners

**Dual:**  
Human wallets stake manually. EVM agent wallets ignore Kaspa. Vida: **Kaspa agent pay + TAO agentic emission-stake**, owner-custody both.

**TAO-focused:**  
Stakao-class products automate stake UI. Vida makes **your local agent** the staker **inside the same product as Kaspa pay**—session-capped, emission-aware, seed stays with you.

---

## Press / community reply

“Vida isn’t a bank. It’s owner-custody rails for agents: **pay on Kaspa**, and on **TAO** let the agent **emission-aware stake planning toward high-emission validators** inside limits you set. Emission scoring is a transparent heuristic—not a yield guarantee. Seed never leaves you. Proofs in the repo.”

---

## What we do **not** say

| Avoid | Why |
|-------|-----|
| “Guaranteed APY / max yield” | Emission ≠ future rewards |
| “Only / first agent wallet” | Other chains have agent money products |
| “Unhackable” | Session/host risk real |
| “PQ money on-chain” | Identity ready only |
| “Replaces every TAO dashboard” | Working-balance agent rail |

---

## Donation / support line
Optional donations fund covenants, smarter TAO allocation, multi-rail work—never required.

## Launch checklist
- [ ] GitHub About mentions **agentic TAO / emission-stake**  
- [ ] Pin README honesty + TAO optimizer note  
- [ ] X post: agentic stake + “not APY promise” + proof link  
- [ ] SECURITY.md private reporting  
