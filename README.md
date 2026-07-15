# Vida

**Agentic wallet. You hold the seed. Your agent acts inside limits you set.**

Vida (*life* in Spanish) is a free, open-source **agent wallet for Kaspa** for local AI agents (Hermes and others). It is **not** a bank, **not** cloud custody, and **not** a raw private key in the agent’s chat.

| You | The agent |
|-----|-----------|
| Hold the 24-word seed | Never sees the seed or password |
| Set hours, max/tx, max/day, mode | Sends KAS only inside that session |
| Revoke by deleting the session file | Needs a new grant after revoke |

**MIT · Owner-custody · Working balances only**

---

## Why it exists

Most AI agents can talk. Few can **pay** without taking your keys.

Vida is built for **Kaspa** (fast confirmation, low fees) with full owner-custody:

| What you get | Why it matters |
|---|---|
| **You hold the 24-word seed** | The agent never sees it. No cloud custody. |
| **Password-encrypted wallet** | Stolen file = useless ciphertext without the password. |
| **Time-boxed agent sessions** | Hours, max per tx, max per day — **enforced on send** in this process. |
| **Mainnet-proven sends** | Public receipts below. |
| **Post-quantum identity (ML-DSA-65)** | At rest; Kaspa still verifies Schnorr **on-chain today**. |
| **Works with Hermes** | Local agent can act on-chain inside your grant. |

---

## Receipts first

| What | Network | Transaction |
|---|---|---|
| Agent-executed send, 10 KAS | **Kaspa mainnet** | [`d32b4504…5825e7`](https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7) |
| Owner send, 5 KAS | testnet-10 | [`75dc9254…07d27c`](https://explorer-tn10.kaspa.org/txs/75dc925425eeb107a65f9bcbf41496320769d82809ea7f440dbdc7f00d07d27c) |
| Policy-gated agent send, 1.5 KAS | testnet-10 | [`915bce02…3b0ac3`](https://explorer-tn10.kaspa.org/txs/915bce0262de48d56796d6c5a54230249c4a6314cc660d024f852ae5c63b0ac3) |

**27 automated tests** on a proper install (`qa_tests` 13 + `qa_secure_tests` 14). CI runs them on push/PR.

---

## Quickstart

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

## Run the tests

```bash
python tests/qa_tests.py          # core wallet: 13
python tests/qa_secure_tests.py   # encryption + sessions: 14
```

---

## Honesty (read before funding)

| Claim people hear | Reality |
|-------------------|---------|
| “Hard limits” | **Policy in the wallet process.** Not chain covenants (yet). |
| “Safe if the session file is stolen” | **No.** A reader can abuse the session; keep a **working balance** only. |
| “Authenticated daily is FS-proof” | **No.** Missing `enc_spend` → **unlock refused**; a **writer** with the session file can still reseal spend (colocated machine key). |
| “Post-quantum protected coins” | **Not on Kaspa today.** PQ identity at rest; chain still uses Schnorr for spends. |
| “Production bank / SLA” | **No.** Local MIT software. |

Also:
- Prefer **`secure_wallet.py`** for real funds. Legacy `wallet.py` can write plaintext keys (tests/helpers).
- Not a hardware wallet — keys exist in process memory while unlocked.
- Lose seed + password → funds gone.
- Dust change below ~0.02 KAS may be forfeited to fee (standard Kaspa behavior).

See [SECURITY.md](SECURITY.md).

---

## Architecture

```
vida/
  wallet.py         # keys, signing, delegation modes (legacy plaintext path)
  secure_wallet.py  # 24-word seed, scrypt+AES-GCM, agent sessions (v2)
  transactions.py   # UTXO selection, fees, broadcast, verification, cap checks
  ml_dsa_65.py      # post-quantum ML-DSA-65 wrapper
scripts/
  setup_owner_wallet.py
  grant_session.py
tests/              # 27 automated tests (13 + 14)
```

## Roadmap

- [x] Kaspa agentic wallet (seed, sessions, caps on send, mainnet receipts)
- [x] Session v2 (host-bind, dest allowlist, fail-closed daily counter)
- [ ] On-chain covenants (Kaspa toolchain)
- [ ] Optional rails (e.g. other chains) — **not in this tree yet**

---

## Security disclosure

**Do not open a public issue for vulnerabilities.** Use GitHub private reporting (Security → Report a vulnerability) or see [SECURITY.md](SECURITY.md).

## License & support

**MIT** — free forever. No ads, no telemetry, no paid core tier.

Optional development fund (KAS):

```
kaspa:qqnnn7wlwz92a70v7km4j3c74lgvnymc60rl2p4gza7dgu6l4pv8g0560yzzn
```

Nothing required to use the software.

---

**Don’t trust marketing. Run the tests. Read `vida/secure_wallet.py` and `vida/transactions.py`. Fund only what you can afford to experiment with.**
