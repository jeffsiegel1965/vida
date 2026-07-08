# Vida — Day-One Reply Pack

Copy/paste answers for launch day. Tone: calm, honest, receipts over hype.
Swap `[REPO_URL]` for the real GitHub link when live.

---

## How is this different from Coinbase AgentKit / MetaMask Agent / Crossmint?

Those are solid — for EVM chains.

Vida is built for **Kaspa**:
- You hold the 24-word seed (owner custody, not a corporate wallet product)
- Free MIT open source
- Time-boxed agent sessions with per-tx and per-day limits
- Post-quantum identity (ML-DSA-65) ready for when Kaspa upgrades
- Mainnet-proven sends with public receipts

Coinbase/MetaMask/etc. don’t speak Kaspa. Vida does.
We’re not competing with them on Ethereum — we’re filling the gap on Kaspa.

---

## Is the seed safe? Does the AI ever see it?

**No. The agent never sees your seed.**

You run the setup script yourself in your own terminal. The 24 words print once on your screen. You write them on paper. They are never stored in plaintext and never sent to any AI, cloud, or chat.

The agent only gets a **time-boxed session file** you grant later — with limits you set — and never your password.

---

## Can I use this with Hermes?

**Yes.** That’s a core use case.

Vida was built so a local agent like Hermes can hold and send KAS inside limits you set — so the agent can *act* on-chain, not just talk.

Works with other local agents too. Not locked to one product.

---

## Is it really the first of its kind on Kaspa?

First **free, owner-custody agent wallet for Kaspa** with:
- password-encrypted wallet
- time-boxed limited agent sessions
- mainnet-proven sends
- post-quantum identity on every wallet

There are Kaspa tools, MCP demos, and DeFi agent experiments — none of those are this full stack as a free product you can run yourself. If we’re wrong, show us and we’ll update the claim. That’s how it should work.

---

## Post-quantum — does that mean my coins are quantum-safe today?

**Honest answer: not on-chain yet.**

Kaspa mainnet still verifies **Schnorr** signatures today. So coins on the chain are not PQ-secured by the network yet.

What Vida does: every wallet already carries an **ML-DSA-65** (NIST Level 3) identity, encrypted at rest. When Kaspa adds PQ verification, Vida users don’t scramble — they’re already equipped.

Built for today. Ready for tomorrow. We won’t pretend otherwise.

---

## Who holds my money? Are you custodial?

**We hold nothing.**

Your seed = your money. Lose the 24 words and password → funds are gone forever. Same as any real self-custody wallet.

We’re not a bank, exchange, or cloud wallet.

---

## How do the agent spending limits work? Can the AI drain me?

You set:
- max KAS per transaction
- max KAS per day
- how many hours the session lasts

Revoke anytime by deleting the session file (one second).

**Honest limit:** those caps are enforced by the wallet process (policy), not yet by on-chain covenants. Anyone who can read the session file on the machine could extract the session key. So:
- only grant sessions on machines you trust
- only put a **working balance** in the agent wallet
- keep serious money cold

We’re building toward covenant-enforced limits when Kaspa support is solid.

---

## Is it free? What’s the catch?

**Free forever. MIT license.**

No ads. No telemetry. No paid tier for the core wallet.

Optional donations to the Vida Wallet Development Fund support next modules (covenants, TAO, Bitcoin):
`kaspa:qqc5cnjk03hfmjzuxvylfsxddddqr5qk65r6rqm5j7076c8szj5nkw6s42v3e`

Nothing required to use it.

---

## Where’s the proof it works?

Mainnet receipt (agent-executed send):
https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7

Code + 24/24 tests:
[REPO_URL]

Don’t trust us — verify the tx and run the tests.

---

## How do I install it?

```
git clone [REPO_URL]
cd vida
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python scripts/setup_owner_wallet.py
```

Run setup yourself — not through an AI chat. Write the 24 words on paper.

Full README: [REPO_URL]

---

## Why should I trust a brand-new wallet?

You shouldn’t — blindly.

What we offer instead:
1. Small codebase (~1,100 lines) — readable in an afternoon
2. 24/24 automated tests you can run
3. Public mainnet receipts
4. Honest “what Vida is not” section (we document limits up front)
5. MIT — fork it, audit it, reject it

Review first. Fund a tiny working balance second. Scale trust with evidence.

---

## Does it work with Ledger / hardware wallets?

Not yet. Vida is a software agent wallet for working balances.

Serious money → keep on your Ledger / cold storage.
Agent money → small Vida balance with tight session limits.

Hardware integration is a future item if the community wants it.

---

## What about covenants / TAO / Bitcoin?

Roadmap (in order):
1. ✅ Core Kaspa agent wallet (this release)
2. Covenant module (when Kaspa consensus support is solid)
3. TAO (Bittensor) module
4. Bitcoin module

Free core first. Modules next. No vaporware dates.

---

## Someone said they found a bug / this is insecure

Please report privately — don’t dump details in public first.

GitHub → Security → Report a vulnerability  
(or see SECURITY.md)

We’ll acknowledge and fix before any public disclosure when we can. Real reports welcome. FUD without evidence: we’ll ask for the proof.

---

## One-liner for quick replies

> Vida: free Kaspa agent wallet. You hold the seed. Your AI spends only inside limits you set. Post-quantum ready. Mainnet-proven. MIT.
