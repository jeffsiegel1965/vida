# Covenant Negotiation — Improvement Schedule

## Phase 1: Test Coverage (Priority — before any more code changes)
Estimated: 1 session

- [ ] TestNegotiationSessionMultiRound — 3-round flow with convergence
- [ ] TestNegotiationSessionRoundLimits — max_rounds raises NegotiationError
- [ ] TestNegotiationSessionConcessionBounds — min/max enforced
- [ ] TestNegotiationSessionEscalation — high-value auto-escalate
- [ ] TestNegotiationSessionBATNA — fallback on expiry
- [ ] TestDealBook — record, history, last_terms, is_first_deal, avg_deal_value
- [ ] TestNegotiatorTemplateDeal — one-step flow with escalation

## Phase 2: Quine Script Implementation (requires Kimi K3)
Blocked on: K3 upstream availability. Uses 1M context for full SilverScript analysis.

- [ ] Research Kaspa Toccata/SilverScript introspection opcodes
- [ ] Convert QUINE pseudocode to actual SilverScript template bytes
- [ ] Add self-verification (embedded policy_hash introspection)
- [ ] Add generation counter encoding in UTXO value
- [ ] Add fee handling specification
- [ ] Add dust-limit failure mode
- [ ] Test: generate quine script + verify on kascov-lab

## Phase 3: Kimi K3 Deep-Dive Sessions
Requires: K3 upstream available, $25 credit active (~15-20 sessions)

- [ ] **P0 — Vida full covenant codebase review** (~$0.46)
      Load all 2,850 lines + tests + deployment history
      Target: fix storage mass blocker, identify script bugs

- [ ] **P1 — Creative Suite coherence pass** (~$0.98)
      Load all 15 modules + sample film. One-shot analysis.
      Target: pipeline optimization, HyperFrames integration gaps

- [ ] **P1 — Kaspa covenant-specific analysis** (~$0.46)
      Covenant code + kascov-lab integration + TN10 proofs
      Target: get quine pot live on testnet

- [ ] **P2 — Multi-suite cross-analysis** (~$1.50)
      Load Vida + Creative + Kaspa together. Architectural review.
      Target: identify shared patterns, security audit

## Phase 4: Production Hardening

- [ ] Add `NegotiationError` tests to verify_exception message contents
- [ ] Add `to_policy_template(strategy="self_replicating_quine_pot")` integration test
- [ ] Wire quine strategy into `tools.covenant_negotiate_terms()`
- [ ] Generate test quine pot on testnet-10 via kascov-lab
- [ ] Push Vida commits (ee6a98d + prior quine work)

## Cost Budget

| Phase | Sessions | Est. Cost | Notes |
|-------|----------|-----------|-------|
| 1 — Tests | 1 | $0.01 (DeepSeek) | No K3 needed |
| 2 — Quine script | 2-3 | $1.50 (K3) | Requires K3 online |
| 3 — Deep-dives | 4 | $3.40 (K3) | Core value |
| 4 — Hardening | 2 | $0.02 (DeepSeek) | No K3 needed |
| **Total** | **~10** | **$4.93** | **$20 of $25 credit remains** |

## Quick Start (Next Session)
```bash
# 1. Run Phase 1 tests (DeepSeek, $0.01)
.venv/bin/python -m pytest tests/test_covenant_negotiation.py -v

# 2. Check Kimi K3 status
curl -s --max-time 30 https://api.zyloo.io/v1/chat/completions \
  -H "Authorization: Bearer \$ZYLOO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"zyloo/kimi-k3","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'

# 3. When K3 is back:
zyloo-kimi chat
```