# Hostile QA — Kaspa public tip

**Scope:** `origin/main` Kaspa core + TAO plugin.

## Current bar (after kaspa-security-only update)

| Item | Status |
|------|--------|
| Caps on `send()` | Enforced (`check_session_spend`) |
| Delete `enc_spend` | **Fail-closed** (S14) |
| Tests | 13 + 14 |
| CI | `.github/workflows/ci.yml` |
| Receipts | Mainnet + TN10 API-verified historically |
| TAO plugin | Shipped in `vida/plugins/tao/` (14 modules, 62 tests) |
| Covenants module | **Not in this public tree** (research track, commercial license) |

## Residual

- Session file reader can extract session key
- Session file writer can reseal daily (`machine_key` colocated)
- Policy ≠ on-chain covenants

## Re-check

```bash
pip install -r requirements.txt
python tests/qa_tests.py          # 13
python tests/qa_secure_tests.py   # 14
```
