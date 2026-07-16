# Covenant track — C: Live TN10 attempt status

**Date:** 2026-07-14  
**Result:** **SUCCESS — micro-proof complete**

---

## Outcome

| Gate | Status |
|------|--------|
| Post-Toccata client | **kascov-lab** (rusty-kaspa `98a4ccd…`) + local **#1074 WASM** also built |
| On-chain covenant lifecycle | **GENESIS + TRANSITION + BURN accepted** |
| Our proof file | [`docs/proofs/covenant_tn10_microproof.md`](../../proofs/covenant_tn10_microproof.md) |

### Txids (testnet-10)

| Step | Txid |
|------|------|
| Genesis | `42f13ec89e5c996091c5be0f7d7cb5c2e9cb1a18c4b7de2f7e723950a77c34fe` |
| Transition | `bf0d2c826da11f1b426dccbe61895cf15d18700e4ad4caf4e15e3674f2a511ef` |
| Burn | `6dbe577adb05afd4afc34c31475b558d52adee78323a2ebf44f72260993266d6` |
| covenant_id | `9fe45342dc674e7cb2fd70061cb51746d47e4fba228a5c0861a8b6748790204f` |

---

## Still open for product

- Vida plugin live `deploy`/`spend` not flipped on  
- Agent max/dest hard-cap scripts not implemented  
- PyPI `kaspa` 2.0.1 still broken for budget wire format  

See A/B docs and agent design for next engineering.
