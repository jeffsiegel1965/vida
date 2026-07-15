# Vida

**Agentic wallet. You hold the seed. Your agent acts inside limits you set.**

Vida (*life* in Spanish) is a free, open-source **agent wallet** for local AI agents (Hermes, OpenClaw, and others). It is **not** a bank, **not** cloud custody, and **not** a raw private key in the agent’s chat.

| You | The agent |
|-----|-----------|
| Hold the 24-word seed | Never sees the seed or password |
| Set hours, max/tx, max/day, mode | Pays / stakes only inside that session |
| Revoke by deleting the session file | Needs a new grant after revoke |

**One product:** Kaspa core + optional **TAO plugin rail**. Not a standalone bank. Not a standalone TAO app.

**MIT · Owner-custody · Working balances only**

---

## What it is (plain language)

An **agentic wallet** means: software your agent can use to **pay and act on-chain**, while **you** keep ownership and policy.

```
Owner only  →  COMMAND  →  HYBRID  →  FULL
              (ask you)   (small OK)  (agentic inside caps)
```

| Rail | What the agent can do (inside your grant) |
|------|-------------------------------------------|
| **Kaspa core** | Receive, hold, send **KAS** (mainnet-proven) |
| **TAO plugin** | Stake / unstake, **P2P TAO**, emission-based **plan** (execute only with session + confirm — **not** guaranteed yield) |

---

## Proof, not pitch

### Kaspa

| What | Network | Tx |
|------|---------|-----|
| Agent send, 10 KAS | **mainnet** | [`d32b4504…5825e7`](https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7) |
| Owner send, 5 KAS | testnet-10 | [`75dc9254…07d27c`](https://explorer-tn10.kaspa.org/txs/75dc925425eeb107a65f9bcbf41496320769d82809ea7f440dbdc7f00d07d27c) |
| Policy-gated agent send, 1.5 KAS | testnet-10 | [`915bce02…3b0ac3`](https://explorer-tn10.kaspa.org/txs/915bce0262de48d56796d6c5a54230249c4a6314cc660d024f852ae5c63b0ac3) |

### TAO (Finney)

Live **stake** + **P2P** receipts and session notes: [`docs/proofs/`](docs/proofs/).  
Optimizer: **plan** proven on Finney; **execute** is session-gated MVP — not APY marketing.

### Tests (run them yourself)

```bash
python tests/qa_tests.py          # Kaspa core — 13
python tests/qa_secure_tests.py   # encryption + sessions — 13
# full tree (needs TAO deps — see requirements-tao.txt):
bash scripts/ci_tao.sh
```

---

## Quickstart (Kaspa)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run yourself — not through an agent
python scripts/setup_owner_wallet.py   # write down the 24 words
python scripts/grant_session.py        # hours + max KAS/tx + max KAS/day

# Revoke anytime
python scripts/grant_session.py --revoke
```

Agent spend path: `vida/transactions.py` with a granted session (`confirm=True` for agent sends).

---

## Optional: TAO plugin rail

Same owner-custody model (session, caps, confirm). Extra deps:

```bash
pip install -r requirements-tao.txt
python scripts/grant_tao_session.py --help
python scripts/vida_status.py --help
```

Guide: [`docs/plugins/tao.md`](docs/plugins/tao.md) · Product: [`docs/PRODUCT.md`](docs/PRODUCT.md) · Tools: [`docs/HERMES_TOOLS.md`](docs/HERMES_TOOLS.md)

---

## How owner-custody works

1. **You** create the wallet on your machine. Seed shown once.  
2. Wallet file is **password-encrypted** (scrypt + AES-GCM).  
3. **You** grant a **time-boxed session** with caps.  
4. The agent uses that session — **no password in chat**.  
5. Caps are enforced on money paths in **this process**. They are **software policy**, not on-chain covenants.

---

## Honesty (read before funding)

| Claim people hear | Reality |
|-------------------|---------|
| “Hard limits” | **Policy in the wallet process.** Not chain covenants (yet). |
| “Safe if the session file is stolen” | **No.** On a machine you control, a reader can abuse the session; keep a **working balance** only. |
| “Authenticated daily spend is FS-proof” | **No.** Missing counter is refused on unlock; a **writer** with the session file can still reseal spend (colocated machine key). |
| “Post-quantum protected coins” | **Not on Kaspa / Finney funds keys today.** PQ identity at rest; chain still uses classical schemes for spends. |
| “Guaranteed TAO yield” | **No.** Optimizer is a heuristic plan. |
| “Production bank / SLA” | **No.** Local MIT software. |

Also:

- Prefer **`secure_wallet.py`** for real funds. Legacy `wallet.py` can write plaintext keys (tests/helpers).  
- Not a hardware wallet — keys exist in process memory while unlocked.  
- Lose seed + password → funds gone.

More: [`docs/SECURITY_HARDENING.md`](docs/SECURITY_HARDENING.md) · [`SECURITY.md`](SECURITY.md)

---

## Docs map

| Doc | For |
|-----|-----|
| [`docs/PRODUCT.md`](docs/PRODUCT.md) | Product definition |
| [`docs/HERMES_TOOLS.md`](docs/HERMES_TOOLS.md) | Agent tool rules (session-only money) |
| [`docs/HERMES_INTEGRATION.md`](docs/HERMES_INTEGRATION.md) | Hermes wiring |
| [`docs/COMPETITIVE_POSITION.md`](docs/COMPETITIVE_POSITION.md) | Niche vs others (no monopoly claims) |

Status: `python scripts/vida_status.py`

---

## Roadmap

- [x] Kaspa agentic wallet (seed, sessions, caps on send, mainnet receipts)  
- [x] TAO plugin rail (sessions, stake, P2P; optimize **plan** MVP)  
- [ ] On-chain covenants (Kaspa toolchain — [rusty-kaspa #1073](https://github.com/kaspanet/rusty-kaspa/issues/1073))  
- [ ] Bitcoin rail (later)

---

## Security disclosure

**Do not open a public issue for vulnerabilities.** Use GitHub private reporting (Security → Report a vulnerability) or see [SECURITY.md](SECURITY.md).

---

## License & support

**MIT** — free forever. No ads, no telemetry, no paid core tier.

Optional development fund (KAS):

```
kaspa:qqnnn7wlwz92a70v7km4j3c74lgvnymc60rl2p4gza7dgu6l4pv8g0560yzzn
```

Nothing required to use the software.

---

**Don’t trust marketing. Run the tests. Read `vida/secure_wallet.py`, `vida/transactions.py`, and `vida/plugins/tao/`. Fund only what you can afford to experiment with.**
