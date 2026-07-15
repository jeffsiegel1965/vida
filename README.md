# Vida

**Powering the agent economy.** Revocable autonomy. Agentic P2P payments and transfers.

Vida is an open-source **agent wallet** for Kaspa and Bittensor (TAO). Give your agent authority to send, stake, and transfer — inside limits you set, revocable at any time. Not a bank. Not cloud custody. Not a raw key in chat.

| You | The agent |
|-----|-----------|
| Hold the 24-word seed | Never sees the seed or password |
| Grant autonomy with caps (tx, day, dest, scope) | Sends / stakes / transfers inside those caps |
| Revoke by deleting the session file | Needs a new grant after revoke |

**Owner-custody**

The agent operates autonomously within your caps. You stay in control. That is **revocable autonomy** — the core idea.

From a grant you can go:
```
COMMAND  →  HYBRID  →  FULL
(ask you)   (small OK)  (agentic inside caps)
```

---

## Rails

| Rail | What the agent can do (inside your grant) |
|------|-------------------------------------------|
| **Kaspa core** | Receive, hold, send **KAS** (mainnet-proven) |
| **TAO plugin** | Stake / unstake, **P2P TAO**, emission-based optimize **plan** (execute with session + confirm — **not** guaranteed yield) |

Both use the same session model: owner grants caps, agent acts inside them, no password in chat.

---

## Proof, not pitch

### Kaspa

| What | Network | Tx |
|------|---------|-----|
| Agent send, 10 KAS | **mainnet** | [`d32b4504…5825e7`](https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7) |
| Owner send, 5 KAS | testnet-10 | [`75dc9254…07d27c`](https://explorer-tn10.kaspa.org/txs/75dc925425eeb107a65f9bcbf41496320769d82809ea7f440dbdc7f00d07d27c) |
| Policy-gated agent send, 1.5 KAS | testnet-10 | [`915bce02…3b0ac3`](https://explorer-tn10.kaspa.org/txs/915bce0262de48d56796d6c5a54230249c4a6314cc660d024f852ae5c63b0ac3) |

### TAO (Finney)

| What | Status |
|------|--------|
| Owner stake, 0.05 TAO | Live on-chain (`0xdc2cd8…`) |
| Agent session stake, 0.02 TAO (no password) | Live on-chain (`0x44c9b9…`) |
| P2P transfer, 0.005 TAO (session) | Live on-chain (`0xa0915a…`) |
| Optimize **plan** (emission-based) | Proven on Finney (free ≈ 0.0216 TAO, target uid 52) |
| Optimize **execute** | Session-gated MVP — not APY marketing |

Docs: [`docs/proofs/`](docs/proofs/) · [`docs/plugins/tao.md`](docs/plugins/tao.md)

### Tests

```bash
# Kaspa core
python tests/qa_tests.py          # 13
python tests/qa_secure_tests.py   # 14

# TAO (requires requirements-tao.txt)
python -m unittest discover -s tests -p 'test_tao*.py'   # 64
```

---

## Quickstart

```bash
git clone https://github.com/jeffsiegel1965/vida.git
cd vida
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Owner-run (not through the agent)
python scripts/setup_owner_wallet.py   # write down the 24 words
python scripts/grant_session.py        # hours + max KAS/tx + max KAS/day

# Revoke anytime
python scripts/grant_session.py --revoke
```

For TAO:

```bash
pip install -r requirements-tao.txt
python scripts/grant_tao_session.py --help
```

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
| "Hard limits" | **Policy in the wallet process.** Not chain covenants (yet). |
| "Safe if the session file is stolen" | **No.** A reader can abuse the session. **Recommend working balances only.** |
| "Authenticated daily spend is FS-proof" | **No.** Missing counter is refused on unlock; a **writer** with the session file can still reseal spend (colocated machine key). |
| "Post-quantum protected coins" | **Not on Kaspa / Finney funds keys today.** PQ identity at rest; chain still uses classical schemes for spends. |
| "Guaranteed TAO yield" | **No.** Optimizer is a heuristic plan. |
| "Production bank / SLA" | **No.** Local software. |

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
| [`docs/COMPETITIVE_POSITION.md`](docs/COMPETITIVE_POSITION.md) | Niche vs others |

---

## Roadmap

- [x] Kaspa agentic wallet (seed, sessions, caps on send, mainnet receipts)
- [x] TAO plugin rail (sessions, stake, P2P, optimize **plan** MVP)
- [ ] On-chain covenants (Kaspa toolchain)
- [ ] Bitcoin rail (later)

---

## Security disclosure

**Do not open a public issue for vulnerabilities.** Use GitHub private reporting (Security → Report a vulnerability) or see [SECURITY.md](SECURITY.md).

---

## License

- **Kaspa core + TAO plugin:** MIT (see [`LICENSE`](LICENSE)). Free to use, modify, distribute.
- **Covenant module:** Commercial license. Not yet shipped.

Optional development fund (KAS):
```
kaspa:qqnnn7wlwz92a70v7km4j3c74lgvnymc60rl2p4gza7dgu6l4pv8g0560yzzn
```

---

**Don't trust marketing. Run the tests. Read `vida/secure_wallet.py`, `vida/transactions.py`, and `vida/plugins/tao/`. Self-custody means self-responsibility.**