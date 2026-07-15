# Vida — product definition (source of truth)

Use this to keep README, marketing, and GitHub About aligned.

---

## What Vida is

**One product:** owner-custody **agent wallet**.

| Layer | Role |
|-------|------|
| **Control plane** | Hermes / OpenClaw / local agents (not a standalone bank UI) |
| **Kaspa core** | Agent pay (KAS) — sessions, caps, mainnet-proven |
| **TAO plugin** | **Part of Vida** — agentic stake, P2P TAO, emission-aware auto-stake MVP |
| **Covenant plugin** | Offline scaffold; live later |

**TAO is not a separate product.** It is an optional *rail* (extra deps) of the same Vida system: same owner-custody idea, same COMMAND→FULL spectrum, same “seed never to the agent.”

---

## What Vida is not

- Not a custodial exchange  
- Not a standalone “Tao app” next to Kaspa  
- Not “Hermes itself” (Hermes is the agent; Vida is the wallet layer)  
- Not guaranteed APY / unbreakable / only agent wallet on earth  

---

## Autonomy (both rails)

```
Owner-only → COMMAND → HYBRID → FULL (agentic inside caps)
```

User sets parameters (hours, max/tx, max/day, subnets, destinations, mode).  
Hermes helps configure and operate. Full agentic still = **your** limits.

---

## TAO capabilities (inside Vida)

1. **Stake / unstake** (session or owner)  
2. **P2P transfer** (agent↔agent or agent→human)  
3. **Emission-aware auto-stake** (`vida_tao_optimize`) — heuristic MVP, not guaranteed yield  

---

## Install honesty

- Core Kaspa: `requirements.txt`  
- TAO rail: `requirements.txt` includes substrate-interface + mnemonic — still **Vida**, not a second repo story  

---

## Canonical one-liners

| Use | Line |
|-----|------|
| Default | Vida: Hermes-driven agent wallet—Kaspa pay + TAO stake/P2P; you set COMMAND→FULL. |
| TAO emphasis | Vida’s TAO rail: agentic stake toward emission + P2P, same owner-custody as Kaspa. |
| Avoid | “Standalone TAO wallet” / “separate Tao product” |

---

## Doc map

| Doc | Job |
|-----|-----|
| README | Public entry |
| HERMES_INTEGRATION | Control spectrum |
| plugins/tao.md | TAO rail operator guide |
| MARKETING | Social/launch copy |
| COMPETITIVE_POSITION | Niche honesty |
| GITHUB_ABOUT | Repo About field |
