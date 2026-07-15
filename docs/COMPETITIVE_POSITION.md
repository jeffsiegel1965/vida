# Competitive position — is Vida unique?

**Honest answer:** Not the only agent wallet in the world.  
**Useful uniqueness:** local, owner-custody **agent wallet centered on Kaspa**, with **TAO as a Vida plugin rail** (not a separate product), session policy, Hermes/OpenClaw fit, and mainnet receipts.

Unique = **combination + chain focus + proof**, not every feature in isolation.

---

## What the market has

| Product | What it is | Custody | Autonomy | Chains | Agent-native? |
|--------|------------|---------|----------|--------|----------------|
| **Vida** | Local open-source agent wallet | You hold seed; session for agent | FULL / HYBRID / COMMAND + caps (software) | **Kaspa** core; **TAO** plugin | Hermes, OpenClaw, other local agents |
| **Hermes / OpenClaw** | Agent runtimes | Not wallets | Tool-running agents | N/A | Need a wallet (Vida, OpenClawCash, etc.) |
| **OpenClawCash** | Web app / API agent wallets | Policies (limits, address rules); agent moves value without raw key on disk (their model) | Policy controls | **EVM + Solana** | Yes — those chains |
| **Talisman / SubWallet / Nova / taostats wallet** | Human wallets | Self-custody | Manual | Substrate / TAO | No |
| **btcli / Bittensor SDK** | Dev tooling | Coldkey / hotkey files | Scripts can automate | Bittensor | Programmatic, not grant/revoke product UX |
| **Exchange / app stake** | Custodial or app UX | Platform | Autopilot-ish | TAO (limited) | Not local agent economy |
| **Stakao-class** | TAO stake autopilot | Claims non-custodial automation | Rebalance / AI stake | Bittensor subnets | Staking product, not Kaspa micropay wallet |
| **Kasware / Kaspa browser wallets** | User Kaspa wallets | Self-custody | Manual | Kaspa | Not agent session / policy product |

---

## Feature comparison (honest)

| Capability | Vida | OpenClawCash-class | Human TAO wallets | Stakao-class |
|------------|------|--------------------|-------------------|--------------|
| Owner holds seed locally | Yes | Varies (API model) | Yes | Claims non-custodial |
| Agent acts without seeing seed | Yes (session) | Design goal | No | Limited to stake |
| Amount caps + revoke | Yes | Yes | App limits | Product rules |
| Destination allowlist | Yes (session v2) | Yes | Sometimes | N/A |
| **Kaspa mainnet agent send** | **Yes (receipts)** | No | N/A | No |
| **TAO stake + P2P transfer** | **Yes (Finney proofs locally)** | No | Manual / SDK | Stake focus |
| PQ identity (ML-DSA-65) forward | Yes (not on-chain yet) | Not their pitch | Rare | No |
| MIT free local code | Yes | Product / API | Mixed | Product |
| On-chain hard caps (covenants) | **Not yet** | Policy layer | No | No |
| Bulletproof vs host compromise | **No** | **No** | **No** | **No** |

---

## Where Vida is distinctive

1. **Kaspa-first agent money** — most agent wallets chase EVM/Solana; Kaspa is underserved; fees suit micropayments.
2. **Agent runtime fit** — Hermes/OpenClaw are hot local agents and are **not** wallets; Vida fills that gap on Kaspa.
3. **Dual-rail direction** — Kaspa for settlement/pay + TAO for intelligence-economy stake/pay under one owner-custody model.
4. **Proof culture** — Kaspa mainnet receipts in README; TAO Finney stake/transfer under `docs/proofs/`.
5. **Honesty** — session caps are software (not covenants); PQ not on-chain yet. Documented residual risks in `docs/SECURITY_HARDENING.md`.

---

## Where Vida is not unique / not ahead

- Not the only “agent can move crypto” product.
- Not the only AI-related TAO staking story (Stakao, exchanges, SDK scripts).
- Not the best multi-chain human wallet.
- Not unhackable.
- Yield optimizer is heuristic MVP, not a full quant product.
- Public mindshare is weak until the repo is public and polished.

---

## Positioning language

**Use:**

> Vida is one owner-custody agent wallet for Hermes/OpenClaw: Kaspa for pay, TAO plugin for agentic stake + P2P + emission auto-stake. You hold the seed; you set COMMAND→FULL; the agent only acts inside limits you grant. Not a standalone TAO app.

**Avoid:**

> First / only / unbreakable / guaranteed APY / replaces every wallet.

---

## One-glance matrix

```
                    Kaspa agent pay   TAO agent stake/pay   Local seed   Session policy   Public SaaS
Vida                    ●                  ●                   ●              ●              ○
OpenClawCash            ○                  ○                   △              ●              ●
Talisman etc.           ○                  manual              ●              ○              ○
Stakao-class            ○                  stake AI            △              △              ●
Hermes/OpenClaw alone   ○                  ○                   N/A            N/A            ○
```

● strong · △ partial · ○ weak/none

---

## Verdict

| Question | Answer |
|----------|--------|
| Unique in the world? | **No** as a category (“agent moves crypto”). |
| Unique in a useful way? | **Yes:** Kaspa-native local agent wallet + owner sessions + TAO plugin, with receipts. |
| Closest shapes? | OpenClawCash (EVM/Sol agent money). Stakao-class (TAO stake automation). |
| Moat today? | Kaspa niche + dual-rail + proof — **not** network effects yet. |
| Moat later? | Covenants, polished Hermes tools, public adoption, multi-agent payment norms. |

---

## Related

- `docs/PRODUCT.md` — canonical product definition


- `docs/SECURITY_HARDENING.md` — residual risks and session v2
- `docs/plugins/AUTONOMY_KASPA_VS_TAO.md` — Kaspa vs TAO autonomy parity
- `docs/proofs/` — live receipts
