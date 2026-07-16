# Covenant track — A: Go / No-Go (live check)

**Date:** 2026-07-14  
**Method:** GitHub API on #1073 / #1074 + PyPI `kaspa` + local SDK probe + prior Phase 0 notes.  
**No broadcast. No claim of live Vida covenant txs.**

---

## Verdict

| Question | Answer |
|----------|--------|
| **Live TN10 covenant deploy/spend from this machine today?** | **GO for micro-proof** (2026-07-14) — see `docs/proofs/covenant_tn10_microproof.md` |
| **Are covenants dead on Kaspa?** | **No** |
| **Is our blocker consensus or tooling?** | Tooling for **Vida/Python** path still; **kascov-lab** works |
| **Software agent caps (sessions)?** | **GO** |

---

## Live upstream status (API 2026-07-14)

| Item | State | Evidence |
|------|--------|----------|
| [#1073](https://github.com/kaspanet/rusty-kaspa/issues/1073) | **OPEN** | Jeff’s TN10 reject: `used=100000, limit=9999` |
| [#1074](https://github.com/kaspanet/rusty-kaspa/pull/1074) | **OPEN, not merged** | Title: compute commit / mass / generator; head `IzioDev:tmp/generator-changes` |
| mergeable | `true` (API) | Still waiting on merge / release |
| PyPI `kaspa` | **2.0.1** | Still pre–computeBudget wire (see local probe) |

### What collaborators established (issue comments)

1. **Knitser:** Post-Toccata v1 uses per-input `computeBudget`; free allowance when budget=0 is **9999** script units; one Schnorr costs **100000** → matches our error.  
2. **Knitser:** PyPI path **sets** `computeBudget` in memory then **drops it on `to_dict`/JSON** → node sees budget 0.  
3. **IzioDev:** Use **#1074** TN10 SDK with `ComputeCommit`; keep #1073 open until PR merges.  
4. Known-good **third-party** TN10 txs exist (kascov / Knitser references) — **not Vida’s**.

---

## Local probe (this host)

| Check | Result |
|-------|--------|
| Installed `kaspa` (venv) | **Drops `computeBudget` on serialize** (same class as #1073) |
| `rustc` / `cargo` | **Not installed** (cannot build #1074 WASM here without install) |
| `rusty-kaspa` clone | **Not present** |

→ Cannot honestly run **C** (our TN10 deploy+spend) until:

1. Client from **#1074** (or merged release) is installed, **and**  
2. Round-trip proof: `computeBudget: 10` survives serialize, **and**  
3. Deploy+spend accepted with **our** txids.

---

## Go / No-Go matrix

| Workstream | Decision | Why |
|------------|----------|-----|
| **A** Status doc | **DONE** (this file) | Upstream still open |
| **B** Offline agent covenant design | **GO** | No chain dependency |
| **C** TN10 live micro-proof | **NO-GO today** | #1074 unmerged + no post-fix SDK on host |
| Soft session caps | **GO** | Independent of covenants |
| Claim “hard caps live” | **FORBIDDEN** | No our txids |

---

## Unblock checklist for future **C**

- [ ] #1074 merged **or** we pin a built artifact from the PR branch  
- [ ] Install post-fix client (not PyPI 2.0.1 alone)  
- [ ] Prove JSON/dict round-trip of `computeBudget`  
- [ ] Budget **10–20** on **every** signing input (incl. change), set **before** sign  
- [ ] TN10 faucet / small UTXO  
- [ ] Deploy + spend accepted → write `docs/proofs/covenant_tn10_*.md` with **our** hashes  
- [ ] Only then flip plugin `live_enabled` paths  

Reference: [kascov](https://github.com/Knitser/kascov) · [kascov.io/guide](https://kascov.io/guide) · Kaspa suite `COVENANT_BLOCKER_STATUS.md`

---

## Bottom line for Jeff

**Want bulletproof on-chain agent caps?** Path is real.  
**Ready this week without #1074?** **No.**  
**Do next:** offline design (**B**) + keep soft policy; watch/merge #1074; then **C**.
