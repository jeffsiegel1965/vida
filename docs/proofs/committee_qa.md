# Push-readiness QA audit — Vida Wallet

**Audit date:** 2026-07-16  
**Reviewed commit:** `9559815` (38 files, +5379/-94)  
**Branch:** `main`, 1 ahead of `origin/main`  
**Hostile reviewer posture:** Assumes every claim is a lie until proven by code or chain.

---

## Verdict: **HOLD** — 2 blockers, 1 minor, 1 advisory

---

## 🚫 BLOCKER 1: Covenant CI references `toolchain/kascov/` — does not exist in tracked tree

**File:** `.github/workflows/covenant-ci.yml`

```yaml
- name: Cache cargo build
  with:
    path: toolchain/kascov/target
- name: Build kascov-lab
  working-directory: toolchain/kascov
  run: cargo build --release -p kascov-lab
```

**Reality:** `git ls-files toolchain/` returns nothing. The `toolchain/` directory is not in the tracked tree. The `build-kascov` job will fail on first run.

**Fix:** Either (a) commit the toolchain submodule/directory, or (b) integrate the kascov binary as a pip-installable dependency, or (c) gate the covenant CI behind a path check with a fallback.

---

## 🚫 BLOCKER 2: Covenant CI runs `pip install -e .` — no `setup.py` or `pyproject.toml` exists

**File:** `.github/workflows/covenant-ci.yml`

```yaml
- name: Install deps
  run: |
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
```

**Reality:** `git ls-files setup.py pyproject.toml setup.cfg` returns nothing. The `test-covenant` job will fail at `pip install -e .` because there is no package definition.

**Fix:** Add a `pyproject.toml` (or `setup.py`) with the `vida` package. Currently only `requirements.txt` exists, which isn't sufficient for `pip install -e .`.

---

## ⚠️ PUSH WITH FIXES: Test count mismatch — README says 64, actual is 62

**READ.me (line 117):**
```bash
python -m unittest discover -s tests -p 'test_tao*.py'   # 64
```

**`ci.yml` (line 32):**
```yaml
- name: TAO plugin tests (62)
```

**Actual count:** `grep -c 'def test_' tests/test_tao_*.py` = **62** (3+5+15+4+5+12+5+13).

The CI workflow is correct. The README is wrong by 2. A hostile reviewer will notice the discrepancy immediately.

**Fix:** Change `# 64` to `# 62` in README.md line 117.

---

## ⚠️ PUSH WITH FIXES: Broken install reference — `requirements-tao.txt` does not exist

**File:** `docs/plugins/tao.md` (line 28)

```bash
pip install -r requirements.txt -r requirements-tao.txt
```

**Reality:** Only `requirements.txt` exists in the tracked tree. The TAO deps reference is broken. If a user follows these instructions, `pip` will error.

**Fix:** Either (a) create `requirements-tao.txt`, or (b) update the install docs to reference the correct file.

---

## ✅ PASS — Secrets scan

`grep` for mnemonic, private key, password, AKIA, GitHub tokens, and other secret patterns across the tracked tree returned **zero matches**. Clean.

---

## ✅ PASS — Stale/misleading claims

Searched all `.md` files for `"free forever"`, `"production-ready"`, `"bulletproof"`, `"unpublished"`, `"MIT only"`, `"first/only"` — **zero matches**. The earlier clean-up commits (ee7f110, e4c56ea) already addressed these.

---

## ✅ PASS — Branding

- H1: `# Vida Wallet` ✓
- Tagline: `Powering the agent economy. Revocable autonomy. Agentic P2P payments and transfers.` ✓
- No occurrence of `"agents can talk but can't pay"` or similar embarrassing phrases in the README.
- MARKETING.md uses honest positioning language and explicitly lists what **not** to say.

---

## ✅ PASS — Honesty table

The README "Honesty" section correctly documents:
- Software policy ≠ chain covenants
- Session file theft = key compromise within caps
- Daily counter is filesystem-defeatable
- PQ identity at rest only, not on-chain
- Yield optimizer is heuristic, not guaranteed
- No production SLA

---

## ✅ PASS — License consistency

- `LICENSE`: MIT (standard)
- README correctly states: "Kaspa core + TAO plugin: MIT … Covenant module: Commercial license. Not yet shipped."
- No `covenant/` code is licensed MIT — the commercial module is correctly described as not-yet-shipped.
- The covenant module source exists in `vida/plugins/covenant/` but is marked as in-development. No license file conflicts.

---

## ✅ PASS — `.gitignore`

Comprehensive exclusions for:
- `*.json` and `*.json.*` (treats all JSON as potential key material)
- `*.bak`, `*.env`, `*.pem`, `*.key`, `keystore*`
- `*seed*.txt`, `*mnemonic*.txt`, `*export*.csv`
- `vida_secure.json`, `vida_mainnet.json`, `agent_session*.json`
- `!docs/proofs/` and `!docs/proofs/**/*.md` — correctly allows markdown proof files
- `data/` and `tao_agent_session.json`

---

## ✅ PASS — No embarrassing content

Searched all `.py` and `.md` files for TODO, FIXME, HACK, XXX, WIP, and profanity — **zero matches**. File names are clean and professional.

---

## ✅ PASS — Link integrity

All referenced paths in the README that exist in the tracked tree:
- `docs/SECURITY_HARDENING.md` ✓
- `SECURITY.md` ✓
- `docs/proofs/` ✓ (directory exists with 12 files)
- `docs/plugins/tao.md` ✓
- `docs/plugins/` ✓ (directory exists)

The three Kaspa explorer links in the README are well-formed and point to the correct explorers.

---

## 📋 Additional observations (not blockers)

| Issue | Severity | Note |
|-------|----------|------|
| Uncommitted modified files (`requirements.txt`, `vida/transactions.py`) | Advisory | `git status` shows changes not staged for commit. If the user pushes before addressing these, the working tree won't match the commit. |
| 13 untracked files (brand assets, new scripts, new docs) | Advisory | Not pushed, no impact on this commit. Should be reviewed before a future push. |
| `ORIGIN_HOSTILE_QA.md` says "62 tests" for TAO — this is correct ✓ | Info | Internal doc is consistent with actual count. |

---

## Summary

| Check | Result |
|-------|--------|
| 1. Secrets scan | ✅ PASS |
| 2. Stale claims | ✅ PASS |
| 3. Test count claims | ❌ **MISMATCH** (README: 64, actual: 62) |
| 4. README claims vs reality | ⚠️ See blocker 3 |
| 5. License consistency | ✅ PASS |
| 6. Branding | ✅ PASS |
| 7. .gitignore | ✅ PASS |
| 8. CI workflow | ❌ **2 blockers** (missing toolchain, missing setup.py) |
| 9. Embarrassing content | ✅ PASS |
| 10. Broken links | ✅ PASS |
| 11. Honesty table | ✅ PASS |

**Verdict: HOLD** until the two CI blockers are resolved and the test count mismatch is fixed.