# x402 Spec Discussion — Kas-Smiths Forum

**Thread:** Kaspa x402: pay-per-request KAS payments for APIs and AI agents
**URL:** https://kas-smiths.org/t/kaspa-x402-pay-per-request-kas-payments-for-apis-and-ai-agents/15/12
**Post #12 by:** Ross (Rust implementer)
**Date:** ~July 2026

---

## Summary

Ross is implementing x402 v2 in Rust from the spec text alone (not porting TypeScript).
He found four spec gaps that affect his implementation:

## Gaps Found

### 1. Transaction ID / Authorization Digest Preimage

- `kaspa-sdk-safe-json-v2.0.0` has no normative definition. The schema types `transaction` as an opaque string.
- Test vectors ship final `transactionId`s and digests but **no hash preimage**.
- The v1 spec digest conventions (UTF-8 strings, `_le64` concatenation) don't apply to v2.
- From `exact-authorization.ts`, the actual construction appears to be **SHA-256 over key-sorted canonical JSON**.
- **Impact on Vida:** If Vida's x402 uses a different serialization than the spec intends, authorization digests won't match.
- **Fix:** Ross offers to draft the missing text.

### 2. Expiry Relationships

- Unclear what should be enforced among `maxTimeoutSeconds`, `challengeExpiresAt`, and `authorization.expiresAt`.
- Each has per-field constraints, but no ordering rules between them.
- Which side (server vs facilitator vs adapter) checks which?
- Ross invented: `authorization.expiresAt ≤ challengeExpiresAt`, both within the offer window.
- **Impact on Vida:** Vida's x402 expiry logic may not match the intended model.

### 3. Finality Numbers

- No recommended confirmation depth for `accepted`/`confirmed` status.
- Left to adapter policy, but Ross wants guidance before mainnet-readiness.
- **Impact on Vida:** Vida's `x402.py` should explicitly document its confirmation depth.

### 4. Additive External-Advance Attack

- Anyone can advance a head by its threshold (0.1 KAS, paid to the merchant).
- A third party could **repeatedly stale the expected head transition** for every in-flight payer.
- With `maxPaymentRetries: 0`, each affected payer needs a fresh wallet authorization.
- Ross suggests: per-client or auth-gated additive offers as mitigation.
- Standard-native-as-fallback may be sufficient.
- **Impact on Vida:** If Vida's x402 adapter has `maxPaymentRetries` near 0, it's vulnerable to griefing.

## Relevance to Vida

Vida's `x402.py` implements the x402 spec for auto-paying subnet APIs.
These spec gaps directly affect Vida's implementation:

| Gap | Vida file | Risk |
|-----|-----------|------|
| Digest preimage | `x402.py` — authorization digest computation | Misaligned auth |
| Expiry ordering | `x402.py` — timeout/expiry checks | Wrong party checks wrong field |
| Finality depth | `x402.py` — transaction confirmation | Confirms too early or late |
| Advance attack | `x402.py` — retry policy | Griefing vulnerability |

## Recommendation

Monitor this thread for Ross's interop reports and any spec clarifications.
If the spec authors update the docs with preimage fixtures and expiry rules,
Vida's `x402.py` should be updated to match.

Saved: 2026-07-20