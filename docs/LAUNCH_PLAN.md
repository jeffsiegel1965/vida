# Vida Launch Plan — X + community

**Status:** copy ready · waiting on: GitHub public URL, X account, better art (optional)

---

## Recommended handle
- **@VidaWallet** (first choice)
- Fallbacks: @VidaOnKaspa, @VidaKaspa, @GetVidaWallet
- Avoid: "Vito" (typo), generic crypto-bot names

## Bio (X, under 160)
```
Agentic wallet for Kaspa. You hold the seed. Agent spends only inside policy limits you set. PQ identity at rest (ML-DSA-65). Mainnet receipts. MIT. Not a bank.
```

## Location / website
- Location: Kaspa
- Website: GitHub repo URL (add after push)
- Pinned post: the intro thread below

## Where to introduce (priority order)
1. **X (@VidaWallet)** — public face, shareable
2. **Kaspa Discord** — project showcase / #general (highest signal for Kaspa users)
3. **r/kaspa** — short post + GitHub + mainnet receipt
4. **Optional later:** Kaspa Telegram groups only if organic interest

Do NOT spam. One solid post per venue. Reply to genuine questions.

---

## Intro post (single, under 280)
```
Agentic wallet. You hold the seed.

Vida: local AI agents can send KAS inside limits you set.
Owner custody. Policy caps on send (not chain covenants yet).
ML-DSA-65 identity at rest. Mainnet receipts. MIT.

GitHub: [REPO_URL]
```

---

## Intro thread (recommended pin)

**1/**
Agentic wallet. You hold the seed.

Most AI agents can talk.
Few can pay without taking your keys.

Vida is an owner-custody agent wallet for Kaspa.
Hermes (or any local agent) can act on-chain inside sessions you grant.

**2/**
Why it exists:

Hand an agent a raw private key → one bad prompt drains you.
Many EVM “agent wallets” don’t speak Kaspa.

Vida is built for Kaspa owner custody + agent sessions (policy caps, not magic).

**3/**
How it works:

• You create the wallet yourself
• 24-word seed stays on your paper — never in the cloud, never in the agent
• Password encrypts the wallet file
• You grant a time-boxed session: max per tx, max per day
• Revoke in one second

**4/**
Post-quantum identity at rest (ML-DSA-65).

Every Vida wallet carries an ML-DSA-65 key encrypted next to Schnorr funds material.
Kaspa still verifies Schnorr on-chain today — coins are not PQ-secured by the network yet.
When Kaspa upgrades, you are not starting from zero.

**5/**
Why Kaspa:

Sub-cent fees. Fast confirmation.
Agent micropayments make sense here.
Many EVM agent wallets ignore Kaspa. Vida does not.

**6/**
Receipts, not hype.

Mainnet send built by this code:
https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7

Run the tests yourself (core 13 + secure 14). CI workflow ships with the repo.

**7/**
Honest limits:

Session caps are **policy** in the wallet process — not on-chain covenants yet.
Missing daily counter → unlock refused; a full FS writer can still reseal spend (machine_key colocated).
Keep only a working balance in an agent-accessible wallet.

**8/**
MIT. Optional KAS development fund (never required).

Code + docs: [REPO_URL]

Agentic wallet. You hold the seed.

---

## Discord / Reddit short version
```
Vida — free agent wallet for Kaspa (MIT).

Problem: agents that can talk but can’t safely hold/spend KAS.
Solution: you hold the 24-word seed; agent gets time-boxed limited sessions.
First free owner-custody agent wallet built for Kaspa. Works with Hermes and other local agents.
Post-quantum ready (ML-DSA-65 / NIST Level 3) — identity on every wallet for when Kaspa upgrades.
Mainnet-proven. 26 automated tests.

GitHub: [REPO_URL]
Mainnet receipt: https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7

Review the code before funding. Keep serious money cold.
```

---

## Graphic
- Temporary: `docs/brand/vida-mark.svg` (butterflies + road + Vida wordmark)
- Export to PNG for X header/avatar when tools allow
- Better art: unpark `BRANDING_BRIEF.md` once FAL key / image credits exist
  (Christopher Robin whimsy × Grateful Dead dancing bears, butterflies instead of bears)

## What Jeff does vs what Hermes does
**You (Jeff):**
1. Create X account @VidaWallet (or chosen handle) on your phone
2. Create GitHub token so we can push the repo (or push yourself)
3. Paste the public GitHub URL into the posts
4. Post from the phone app (free) — or approve Hermes to post once xurl is set up

**Hermes can do:**
- Draft/refine posts (done)
- Convert SVG → PNG if tools allow
- Install/configure xurl AFTER you complete OAuth outside the agent
- Post only with your explicit OK

## Cost note
X API posting may require paid developer credits later. For launch day, posting from the phone app is free and fine.
