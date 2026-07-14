# Hostile QA — what was already on GitHub (origin/main)

**Date:** 2026-07-14  
**Scope:** Public `jeffsiegel1965/vida` **before** unpushed TAO work  
**Method:** Fresh clone + local `origin/main` after fetch; tests on kaspa-suite venv; API tx checks

---

## Verdict on pre-fix public tree

| Bar | Result |
|-----|--------|
| Tests as published | **13 + 11 = 24** (matched old README “24/24”; secure suite was **11**) |
| Mainnet receipt `d32b4504…` | **Found** on `api.kaspa.org` |
| Testnet receipts | **Found** on `api-tn10.kaspa.org` |
| **Session max KAS/tx/day enforced on `send()`** | **FAIL (critical)** — limits stored in session file, **not applied in `transactions.py`** |
| “Hard limits” wording | **Overclaim** given missing enforcement |
| “First free agent wallet” | **Marketing risk** (competitive, hard to defend) |
| “23 tests” / LOC brag | **Sloppy/stale** |
| Plaintext `wallet.py` | Documented risk — OK if users follow secure path |
| No CI | Still true |

---

## Why this mattered

README told users the agent only spends inside max/tx and max/day.  
On the published code path, **those caps did not block `VidaTransactor.send`**.  
Honesty section said policy not cryptographic—but **policy was incomplete**.

That is exactly the kind of gap that makes you look bad if someone audits.

---

## Fix shipped on branch `fix/origin-session-caps`

1. Session v2-style enforcement: caps, host-bind, dest allowlist, `enc_spend`, `confirm=True` on agent sends  
2. `qa_secure_tests` **13/13** (includes send-path cap tests)  
3. README: drop “first”, fix test counts, “limits enforced on send” + honesty  
4. Soften DAY_ONE / LAUNCH “first of its kind”

**Not included:** TAO plugin dump (still local `main` only).

---

## After this fix is on GitHub

Re-check:

```bash
git clone https://github.com/jeffsiegel1965/vida.git && cd vida
pip install -r requirements.txt
python tests/qa_tests.py          # expect 13
python tests/qa_secure_tests.py   # expect 13
```

Then consider TAO push as a **separate**, still-skeptical step.
