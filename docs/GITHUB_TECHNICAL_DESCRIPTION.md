# Vida — GitHub technical description

## Tagline
**Life for your AI agent on Kaspa** — free, owner-custody agent wallet; TAO (Bittensor) plugin.

## About (repo short blurb — ~350 chars)
Vida is one open-source agent wallet (not a standalone bank, not a separate TAO app): Kaspa core for pay; TAO **plugin rail** for agentic stake, P2P, and emission-aware auto-stake. Hermes/OpenClaw drive it; you set COMMAND→FULL. Owner-custody. MIT. Session caps are software policy until covenants land.

## Topics / tags
`kaspa` `bittensor` `tao` `ai-agent` `wallet` `self-custody` `hermes` `openclaw` `post-quantum` `ml-dsa`

## README highlights for GitHub About / website

### What it is
| Module | Status |
|--------|--------|
| **Kaspa agent wallet** | Mainnet sends + owner seed + encrypted vault + agent sessions |
| **TAO plugin (Vida rail)** | Same product: agentic stake, P2P, emission auto-stake MVP, sessions, Finney proofs, PQ at rest |
| **Covenant plugin** | Offline scaffold only (live needs post-Toccata SDK / PR #1074) |

### Security model (one paragraph)
Owner holds BIP39 seed; secrets encrypted at rest (scrypt + AES-GCM). Agent receives a **time-boxed session** with per-tx/day caps (and optional destination allowlists)—never the seed. Caps are **policy-enforced**, not on-chain covenants. Post-quantum **ML-DSA-65** identity stored encrypted; **Kaspa still Schnorr** and **TAO still sr25519** on-chain today.

### Install
```bash
git clone https://github.com/jeffsiegel1965/vida.git
cd vida
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# optional TAO:
pip install -r requirements-tao.txt
python tests/qa_secure_tests.py
python -m unittest discover -s tests -p 'test_tao*.py'
```

### Proofs
- Kaspa mainnet agent send: see README receipts table  
- TAO Finney: `docs/proofs/tao_*.md` (stake, session stake, P2P)

### Docs map
| Doc | Purpose |
|-----|---------|
| `docs/PRODUCT.md` | Canonical one-product definition |
| `docs/plugins/tao.md` | TAO rail operator guide |
| `docs/HERMES_TOOLS.md` | Agent tool contract |
| `docs/SECURITY_HARDENING.md` | Residual risks |
| `docs/COMPETITIVE_POSITION.md` | Honest niche (not “only wallet”) |
| `docs/plugins/COVENANT_BLOCKER_STATUS.md` | Covenant toolchain status |

## Release notes sketch (this push)

**Added**
- TAO plugin (sessions, stake, transfer, PQ-ready at rest, optimizer MVP)
- Hermes session-only money tools
- Kaspa session v2 enforcement (caps, confirm, dest allowlist)
- Covenant offline scaffold
- Public Finney proofs + QA report

**Honesty**
- Soft policy caps; no live covenants yet  
- PQ not on-chain  
- Working-balance only for agents  

## Security reporting
See `SECURITY.md` — private vulnerability reporting preferred.
