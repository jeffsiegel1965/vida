# Covenant blocker status (Vida product view)

**Updated:** 2026-07-14 (TN10 micro-proof complete)

## Product summary

| Question | Answer |
|----------|--------|
| Are covenants impossible on Kaspa? | **No** — TN10 has real covenants |
| Did **we** prove a lifecycle? | **Yes** — genesis→transition→burn ([proof](../proofs/covenant_tn10_microproof.md)) |
| In-process Vida deploy/spend? | **Not yet** — plugin offline; use `scripts/covenant_tn10_lab.sh` / kascov-lab |
| Agent soft caps today? | **Yes** — session policy |
| Agent on-chain hard caps product? | **Not yet** — design in `covenant/AGENT_HARD_CAP_DESIGN.md` |

## Our TN10 proof (abbreviated)

| | |
|--|--|
| covenant_id | `9fe45342dc674e7cb2fd70061cb51746d47e4fba228a5c0861a8b6748790204f` |
| genesis | `42f13ec8…34fe` |
| transition | `bf0d2c82…11ef` |
| burn | `6dbe577a…66d6` |

Full: [`docs/proofs/covenant_tn10_microproof.md`](../proofs/covenant_tn10_microproof.md)

## Tooling

| Tool | Status |
|------|--------|
| PyPI `kaspa` 2.0.1 | Still drops `computeBudget` |
| PR #1074 WASM build | Local PASS round-trip (`BUILD_1074.md`) |
| kascov-lab | Used for live TN10 micro-proof |
| #1073 / #1074 | Issue open; PR open as of earlier check |

## Next engineering

1. Wire plugin live path to post-Toccata client (labkit / WASM / fixed Python)  
2. Implement agent-pot max_tx + dest on covenant UTXOs  
3. Keep soft sessions as double gate  

## Related

- `docs/plugins/covenant/GO_NOGO.md`  
- `docs/plugins/covenant/AGENT_HARD_CAP_DESIGN.md`  
- `docs/plugins/covenant/C_TN10_STATUS.md`  
- `scripts/covenant_tn10_lab.sh`  
