# Security Policy

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Vida handles real cryptocurrency. A publicly disclosed vulnerability could cost users their funds before a fix ships.

Instead, use **GitHub Private Vulnerability Reporting**:
1. Go to the repository's **Security** tab
2. Click **Report a vulnerability**
3. Describe the issue, affected version, and reproduction steps

We aim to acknowledge reports within 72 hours and to ship a fix or mitigation before any public disclosure. Please allow reasonable time before disclosing publicly.

## Scope

In scope:
- Key extraction, private-key or seed leakage
- Encryption weaknesses (KDF, AES-GCM usage, nonce handling)
- Session-grant bypass beyond the documented limitations
- Transaction-construction bugs that lose or misdirect funds

Known and documented limitations (see README honesty section) are **not** vulnerabilities:
- Session limits are **software policy**, not on-chain covenants
- A **reader** of the agent session file can extract the session signing key and spend until revoke/expiry
- A **writer** who can edit the session file can also reseal the authenticated daily counter (`enc_spend`) because `machine_key` is stored in the same file — delete/missing counter is **fail-closed** on unlock; full FS-adversary resistance is not claimed
- `vida/wallet.py` stores keys unencrypted (legacy/test layer) — use `secure_wallet.py` for real funds
- Post-quantum keys are not verified on-chain (Kaspa consensus does not yet support PQ signatures)
- Agent session files contain signing material — treat as secret; keep working balances only
- Python cannot reliably wipe key material from RAM

## Supported versions

Only the latest tagged release receives security fixes while the project is pre-1.0.
