# Vida security posture — honest threat model

## What “bulletproof” can and cannot mean

**No software wallet is bulletproof against full compromise of the host**
(root, malware, or an agent process with unrestricted filesystem access to
session + seed files).

Vida aims for **defense in depth** and **least privilege for agents**:

| Layer | Status |
|-------|--------|
| Seed never to agent tools | Yes |
| Password never required for agent after grant | Yes |
| Time-boxed session | Yes |
| Amount caps enforced on send/stake | Yes (Kaspa + TAO) — software policy |
| Destination allowlist (optional Kaspa; required TAO transfer scope) | Yes (v2) |
| Host-bound sessions | Yes (v2 — other machine refuses unlock) |
| Durable daily spend counter (`enc_spend`) | Yes if present — **missing → refuse unlock**; reset still possible if attacker can **write** session file (colocated `machine_key`) |
| On-chain hard caps (covenants) | **Not available** on Kaspa yet |
| Resistant to root on this server | **No** (by definition) |

## Residual risks (still true)

1. **Session file = temporary key material.** Anyone who can read it on the
   bound host can act until expiry/revoke within caps — or extract the key and
   bypass caps entirely.
2. **`machine_key` is in the session file.** Required for agent unlock without
   password; host-bind reduces offline theft usefulness. A **writer** with the
   file can re-seal `enc_spend` to zero; daily durability is not FS-adversary-proof.
3. **Do not store mnemonic next to the session.** Use
   `scripts/wipe_plaintext_secrets.py` after grant.
4. **Policy is software.** Until chain covenants exist, a stolen coldkey
   (outside session) is unconstrained.
5. **LLM tool args:** never pass passwords/seeds through chat.

## Operator checklist

1. Fund only a **working balance**, not life savings.
2. Grant short sessions (hours, not weeks) with **tight caps**.
3. Prefer **destination allowlists** for payment agents.
4. Wipe plaintext mnemonic/password from agent-readable dirs after grant.
5. Revoke session when the job ends.
6. Keep OS patched; restrict FS permissions; do not run untrusted code as the
   same user as the wallet files.

## Session format v2

- `host_id` bound into AAD
- `allowed_destinations` optional in limits (AAD-bound)
- `enc_spend` sealed under machine key (tamper → unlock/spend fail)

v1 sessions still unlock for compatibility but should be re-granted as v2.


## Hermes tool rules (product)

- Money tools are **session-only** (no `password=` kwargs).
- Kaspa agent session sends require `confirm=True`.
- Grants require **positive** per-tx and per-day caps by default.
- Optional destination allowlists on grant (`--dest`).


## TAO PQ readiness

- ML-DSA-65 identity generated at provision (or `upgrade_tao_pq.py`).
- Encrypted with owner password; **not** in agent sessions.
- Does **not** make Finney transfers quantum-safe.
