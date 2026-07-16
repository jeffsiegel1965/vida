# Vida Wallet

**Powering the agent economy. Revocable autonomy. Agentic P2P payments and transfers.**

Vida is an agentic wallet for Bittensor (TAO) and Kaspa, with working covenants. You hold the seed. Your agent sends, receives, and stakes. You set the autonomy parameters. Owner-custody.

Not cloud custody. Not raw keys in chat. Just a session file with caps.

**License:** Kaspa core + TAO plugin are MIT (open source). The covenant module is a commercial license.

---

## Rails

| Rail | License | Status | What the agent can do (inside your grant) |
|------|---------|--------|-------------------------------------------|
| **Kaspa core** | MIT | Shipped | Receive, hold, send KAS. Mainnet-proven. |
| **TAO plugin** | MIT | Shipped | Stake / unstake, P2P TAO, emission-based optimize plan. |
| **Covenant module** | Commercial | **Not yet shipped** | On-chain policy enforcement. Learning negotiation engine. |

---

## Honesty

| If you hear | The truth |
|-------------|----------|
| "Hard on-chain limits" | **Software policy enforced in this process.** Not chain covenants. |
| "Safe if session file is stolen" | **No.** Anyone who reads the file can spend within caps. Recommend working balances only. |
| "Daily spend counter is filesystem-proof" | **No.** A writer with the session file can reseal the daily counter. |
| "Post-quantum protected funds" | **Not on-chain.** PQ identity at rest only. Kaspa uses Schnorr, Finney uses sr25519. |
| "Guaranteed TAO yield" | **No.** Optimizer is a heuristic plan. |
| "Production bank / SLA" | **No.** Local software. Self-custody means self-responsibility. |

Also:
- Prefer `secure_wallet.py` for real funds. Legacy `wallet.py` can write plaintext keys.
- Keys exist in process memory while unlocked — not a hardware wallet.
- Lose seed + password → funds gone.

Docs: [`docs/SECURITY_HARDENING.md`](docs/SECURITY_HARDENING.md) · [`SECURITY.md`](SECURITY.md)

---

## Learning negotiation system

The covenant module learns from every deal. More Vida deployments → more negotiation data → better strategy models → better prices for repeat users.

| Stage | What happens |
|-------|-------------|
| 1–10 deployments | Static fee. Simple caps. Manual strategy. |
| 10–100 deployments | Fee model adapts. Common patterns recognized. Strategy suggestions. |
| 100+ deployments | Negotiated pricing per agent profile. Optimal caps suggested. Automated deal terms. |

This is the arrow of scale: **more users → more data → better negotiation strategies → better prices.** Early deployers help train the system and lock in favorable terms.

---

## Pricing

| Usage | Model |
|-------|-------|
| Personal / dev | Flat per-deployment fee. |
| 10+ deployments/month | **Volume discount.** Negotiated rate. |
| 50+ deployments/month | **Subscription tier.** Fixed monthly rate, unlimited deployments. Priority learning access. |

The open-source core (Kaspa + TAO) is always MIT — free to use, modify, distribute. The covenant module is the commercial layer. Volume discounts and subscriptions apply to covenant module usage only.

---

## Quick start

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

TAO deps are in the same requirements file. Install once, use both rails.

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

# TAO
python -m unittest discover -s tests -p 'test_tao*.py'   # 62
```

---

## Plugin platform

Vida's rail system is extensible. Each plugin follows the same session model:

- **Owner grants caps** per plugin
- **Agent acts inside those caps** — no password exposure
- **Revoke by deleting the session file**

| Plugin | Rail | Status |
|--------|------|--------|
| Kaspa core | Native KAS | Shipped (MIT) |
| TAO | Stake, P2P, optimize | Shipped (MIT) |
| Covenant module | On-chain policy, learning negotiation | In development (Commercial) |

To build a plugin: implement the rail interface, register it, and submit a PR. Docs: [`docs/plugins/`](docs/plugins/).

---

## License

- **Kaspa core + TAO plugin:** MIT ([`LICENSE`](LICENSE)). Free to use, modify, distribute.
- **Covenant module:** Commercial license. Not yet shipped.

Optional development fund (KAS):
```
kaspa:qzyswptp860l9efqarplnclndfsvcdyu4aaz9evk88hrt8475g5v68uqrkg7k
```

---

**Don't trust marketing. Run the tests. Read `vida/secure_wallet.py`, `vida/transactions.py`, and `vida/plugins/tao/`. Self-custody means self-responsibility.**