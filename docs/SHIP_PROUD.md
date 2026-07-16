# Ship-proud criteria (Vida)

**Definition:** Defensible to a hostile expert who reads the code, runs the tests, and tries the documented bypasses.  
**Not the definition:** Unbreakable, root-proof, covenant-hard, first/only, guaranteed yield.

Three product tiers (always separate):

| Tier | Meaning |
|------|---------|
| **Keys-safe** | No seeds/keys published; encryption + gitignore discipline |
| **Open-source WIP** | Code + tests + honest docs; residual risks stated |
| **Ship-proud (process-path)** | Hostile expert cannot find a *process* bypass of caps/session gates; gate script green; marketing matches code |

Absolute ship-proud vs full host compromise **does not exist** for a software agent wallet.

---

## Process-path ship-proud checklist

Automated: `bash scripts/ship_proud_gate.sh`

| # | Criterion | Evidence |
|---|-----------|----------|
| 1 | Money paths enforce caps | Kaspa `send` S12; TAO stake/transfer tests + PoCs |
| 2 | Missing `enc_spend` fail-closed | S14 + TAO robustness + gate PoCs |
| 3 | Tamper AAD / enc_spend rejected | S11, S13, TAO session tests |
| 4 | No password on agent tool surface | TAO robustness password-kwarg test |
| 5 | Transfer dest allowlist default | TAO grant rules |
| 6 | Atomic session write + flock | `secure_wallet._write_0600`, `tao/session._write_0600` |
| 7 | Secrets not in git | gate scan + `data/` ignored |
| 8 | Test suites green | 13 + 14 Kaspa; 64 TAO when plugin present |
| 9 | Honesty table in README/SECURITY | policy ≠ covenants; FS residual |
| 10 | CI workflow present for Kaspa core | `.github/workflows/ci.yml` (when published) |

---

## Explicitly **out** of process-path ship-proud

| Residual | Why |
|----------|-----|
| Session file **reader** steals signing key | Design: agent must unlock without password |
| Session file **writer** reseals daily | `machine_key` must be available to agent process |
| Root / malware on host | Out of app scope |
| On-chain covenants | Protocol / tooling track |
| Optimize **execute** live receipt | Needs owner password; optional proof script |
| Public GitHub == local product | Partial pushes; TAO may be local-only |

---

## When to say the words

| Phrase | Allowed when |
|--------|----------------|
| “Keys-safe” | Secrets scan clean + encryption path used for real funds |
| “Open-source WIP” | Tests green + honesty docs |
| “Ship-proud (process-path)” | `ship_proud_gate.sh` exit 0 **this run** |
| “Ship-proud absolute / bulletproof” | **Never** for this architecture without covenants + hardware root of trust |

---

## Operator rules for ship-proud use

1. Working balance only in agent-accessible wallets  
2. Short sessions, tight caps, prefer dest allowlists  
3. Wipe plaintext mnemonic after grant  
4. Revoke session when done  
5. Do not claim hard on-chain limits  

See `docs/SECURITY_HARDENING.md`.
