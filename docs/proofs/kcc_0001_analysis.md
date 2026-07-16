# KCC-0001 Analysis — Covenant Standard

**Source:** https://github.com/kaspanet/kccs/pull/3
**Authors:** Romain Billot (IzioDev), Michael Sutton, Ori Newman
**Status:** Draft (2026-07-15)
**Lines:** 715

## What it defines

| Section | What it covers | Relevance to Vida |
|---------|---------------|-------------------|
| Value ABI | Canonical type names, data pushes, ints, arrays, records | Our `agent_pot_script.py` templates should use this encoding |
| Entrypoints | Dispatch tags, argument sequences | Replaces our ad-hoc entrypoint naming |
| P2SH envelope | Standard covenant wrapping | Our covenant broadcasts should use this format |
| State encoding | How covenant state is serialized | Important for `pot_spend.py` state tracking |
| Template hashes | Deterministic covenant template hashes | Aligns with our `policy_hash` concept |
| Leader/delegator | Multi-input transition roles | Relevant for our negotiation protocol |
| Virtual elements | Hash-committed off-chain data | Future: agent negotiation commitments |

## Impact on Vida

1. **Template alignment**: Our `build_agent_pot_script_template()` should produce KCC-0001-compliant templates when the spec is finalized
2. **P2SH envelope**: The `covenant_fund_agent_pot.js` genesis should use the standard P2SH envelope format
3. **Dispatch tags**: Replace `entrypoint: "reclaim"` with KCC-0001 dispatch tags
4. **Template hashes**: `policy_hash` should match KCC-0001's template hash definition
5. **State encoding**: Our pot record state (`pot_sompi`, `max_tx_sompi`, etc.) should use KCC-0001 canonical encoding

## Action items

- [ ] Monitor KCC-0001 for finalization
- [ ] Update `build_agent_pot_script_template()` to produce KCC-0001 compliant output
- [ ] Update `covenant_fund_agent_pot.js` to use KCC-0001 P2SH envelope
- [ ] Update `policy_hash` computation to match KCC-0001 template hash
- [ ] File an issue: https://github.com/kaspanet/kccs/issues

## Author

IzioDev — same author as PR #1074 (computeBudget fix). This is the authoritative covenant standard for Kaspa.