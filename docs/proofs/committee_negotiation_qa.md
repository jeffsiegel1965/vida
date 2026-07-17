# Committee QA: Covenant Negotiation Module — Simplified Owner-to-Agent

**Date:** 2026-07-16  
**Reviewer:** Hermes Agent (subagent)  
**Scope:** Read-only audit of `negotiation.py`, `test_covenant_negotiation.py`, `tools.py` imports  
**Status:** ✅ **APPROVE WITH NITS**

---

## 1. Files Reviewed

| File | Lines | Role |
|------|-------|------|
| `vida/plugins/covenant/negotiation.py` | 93 | Module under audit — rewritten from P2P to owner-to-agent template |
| `tests/test_covenant_negotiation.py` | 83 | Test suite — 11 tests |
| `vida/plugins/covenant/tools.py` | 359 | Consumer — imports from negotiation + hosts `covenant_negotiate_terms` |
| `vida/plugins/covenant/__init__.py` | 33 | Public API — does *not* re-export negotiation (correct) |

---

## 2. P2P Removal Check

**Classes/identifiers removed from the old protocol:** `ConcessionStrategy`, `NegotiationPhase`, `NegotiationRound`, `CovenantNegotiator`, `get_negotiator`, `list_sessions`, `create_offer`, `counter_offer`

**Scan result:** Zero references to any of the above across the entire `vida-release/` tree.

**Verdict:** ✅ Clean removal — no dangling imports, no stray mentions in docs or tests.

---

## 3. New API Assessment

### Exports (`negotiation.py`)
- `CovenantTerms` (dataclass) — ships all previous keeper methods
- `create_deal()` — one-step factory with validation

### Coverage of the owner→agent flow

| Step | Mechanism | Covered? |
|------|-----------|----------|
| Owner sets caps | `create_deal(max_kas_per_tx=..., max_kas_per_day=...)` | ✅ |
| Validate constraints | `CovenantTerms.validate()` → `None` or error string | ✅ |
| Deterministic deal id | `CovenantTerms.deal_hash()` — SHA-256 of canonical JSON | ✅ |
| Template for covenant pot | `CovenantTerms.to_policy_template()` → invokes `build_agent_pot_script_template` | ✅ |
| Agent operates within caps | Template-bound pot enforces at spend time | ✅ (delegated to pot_spend) |

### tools.py integration
- Import on line 18: `from .negotiation import CovenantTerms, create_deal`
- `covenant_negotiate_terms()` (line 141) — agent-facing tool that applies owner caps as a hard ceiling, generates template, returns agreed terms + fund plan
- `HERMES_TOOLS` registry includes `covenant_negotiate_terms` for Hermes tool discovery

**Nit:** `covenant_negotiate_terms()` does **not** use the imported `CovenantTerms` or `create_deal`. It constructs all terms from dicts and passes directly to `build_agent_pot_script_template` / `plan_agent_pot`. The import is unused by the code that actually runs.

---

## 4. Test Analysis

**Runner:** `python3 -m unittest tests/test_covenant_negotiation.py -v`  
**Result:** ✅ 11/11 passed (0.000s)

| Test | What it verifies | Status |
|------|-----------------|--------|
| `test_create_deal` | Basic creation, field values, destinations list | ✅ |
| `test_deal_hash_deterministic` | Same inputs → same hash | ✅ |
| `test_deal_hash_changes_with_terms` | Changed input → different hash | ✅ |
| `test_validate_rejects_zero_tx` | `max_kas_per_tx=0` → ValueError | ✅ |
| `test_validate_rejects_negative_duration` | `duration_hours=-1` → ValueError | ✅ |
| `test_validate_rejects_excessive_duration` | `duration_hours=721` → ValueError | ✅ |
| `test_validate_rejects_tx_gt_day` | `max_kas_per_tx(10) > max_kas_per_day(5)` → ValueError | ✅ |
| `test_to_canonical_json` | JSON includes expected keys | ✅ |
| `test_to_policy_template` | Template dict has `ok` and `policy_hash` | ✅ |
| `test_default_allowed_destinations_empty` | Default is `[]`, not `None` | ✅ |
| `test_validate_ok` | Valid terms → `validate()` returns `None` | ✅ |

### Coverage gaps (minor)

| Gap | Impact |
|-----|--------|
| No test for exact content of `to_canonical_json` (sort_keys, separators) | Low — hash determinism depends on it, but is tested indirectly via `deal_hash_deterministic` |
| No test for `duration_hours=0` specifically (covers via negative test) | Low — not a real gap |
| No test for `allowed_destinations=None` passed to `create_deal` | Medium — `create_deal` defaults to `[]` for `None`, but not tested |
| No test for specific error message strings from `validate()` | Low — not critical |

---

## 5. Error Handling

- `create_deal()` raises `ValueError("Invalid terms: <reason>")` on any validation failure
- Error messages from `validate()` are descriptive and specific (e.g. `"max_kas_per_tx must be positive"`)
- No silent fallbacks or swallowed exceptions
- `covenant_negotiate_terms()` in `tools.py` returns `{"ok": False, "error": ...}` dicts for failures (consistent with the rest of the tools module)

**Verdict:** ✅ Clear and appropriate.

---

## 6. Security Review

| Concern | Status | Notes |
|---------|--------|-------|
| Mutable default args | ✅ Safe | `allowed_destinations` uses `field(default_factory=list)` |
| Deterministic ID | ✅ Safe | SHA-256 over canonical JSON — not UUID (no entropy leak) |
| Circular imports | ✅ Mitigated | `to_policy_template` does lazy imports inside the method body |
| Duration bounds | ✅ Safe | Capped at 720h (30 days) |
| Threading lock | ✅ Removed | No concurrent P2P sessions to protect |
| P2P attack surface | ✅ Eliminated | No session state, no counterparty management, no round tracking |
| Unused import in tools.py | ⚠️ Low | `from .negotiation import CovenantTerms, create_deal` is not consumed by tools.py code |

**No exploitable security issues found.**

---

## 7. Findings Summary

| # | Finding | Severity | Recommendation |
|---|---------|----------|----------------|
| 1 | `tools.py` imports `CovenantTerms, create_deal` but `covenant_negotiate_terms()` never uses them | 🟡 Low | Either remove the unused import, or refactor `covenant_negotiate_terms()` to construct a `CovenantTerms` via `create_deal()` for consistency |
| 2 | Missing test for `create_deal(max_kas_per_tx=1.0, max_kas_per_day=5.0, allowed_destinations=None)` | 🟡 Low | Add test to ensure `None` defaults to `[]` |
| 3 | P2P classes fully removed, no dangling references | ✅ Clean | — |
| 4 | All 11 tests pass | ✅ Clean | — |
| 5 | New API covers the owner-sets-caps → template → agent-operates flow | ✅ Clean | — |

---

## 8. Verdict

**APPROVE WITH NITS**

The simplification is clean — 93 lines vs 329, 2 exports vs 9 classes/enums, no dangling references, all tests green. The two nits (unused import in `tools.py`, missing `None`-destinations test edge case) are low-severity and do not block merge.