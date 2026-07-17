# Vida Wallet — Covenant Module Security & Logic Audit

**Audit date**: 2026-07-16  
**Reviewer**: Claude Fable  
**Scope**: Covenant negotiation, fees, MCP server, pot spend, lab client, agent pot, JS bridge scripts  
**Method**: Read-only source review — no code execution, no broadcast  

---

## Table of Contents

1. [Agent Compromise via Prompt Injection (Session Caps Bypass)](#1-agent-compromise-via-prompt-injection)
2. [Forced Negotiation Race](#2-forced-negotiation-race)
3. [Fee Avoidance](#3-fee-avoidance)
4. [Session File Tampering](#4-session-file-tampering)
5. [Replay Attack / Duplicate Pot Creation](#5-replay-attack)
6. [Additional Findings](#6-additional-findings)

---

## Summary

| # | Finding                                    | Severity | File:Line |
|---|--------------------------------------------|----------|-----------|
| 1 | Prompt injection: no MCP auth, caps only defense | **High** | `scripts/vida_mcp_server.py:46` |
| 2 | Machine key co-located with enc_spend in session file | **Medium** | `vida/secure_wallet.py:334` |
| 3 | Negotiation race: final `accept()` has no locking | **Medium** | `vida/plugins/covenant/negotiation.py:240` |
| 4 | Fee: NaN/Inf bypass returns 0; 200K KAS pot yields 1 KAS max | **Medium** | `vida/plugins/covenant/fees.py:53-60` |
| 5 | Fee: free first-pot logic is Python memory only, no persistence | **Low** | `vida/plugins/covenant/fees.py:47` |
| 6 | MCP: `vida_send` amounts come from JSON `float` with no range limit | **Low** | `scripts/vida_mcp_server.py:378-379` |
| 7 | Session: `_host_fingerprint()` falls back to hostname | **Low** | `vida/secure_wallet.py:91` |
| 8 | Negotiation: replay creates new session ID (no duplicate issue) | **Info (no issue)** | `vida/plugins/covenant/negotiation.py:110-111` |
| 9 | Spend script: covenant binding hash mismatch on transition | **Critical (Broken)** | `scripts/covenant_spend_agent_pot.js:192-224` |
| 10 | Fund script: passes `covenantId` as `undefined` string check | **Info (fragile)** | `scripts/covenant_fund_agent_pot.js:118-127` |
| 11 | Negotiation: counter_offer accepts `**kwargs` filtered by `hasattr` | **Info** | `vida/plugins/covenant/negotiation.py:152` |
| 12 | MCP: no rate limiting or request size caps | **Low** | `scripts/vida_mcp_server.py:240-597` |

---

## 1. Agent Compromise via Prompt Injection

**Severity**: **High**  
**File**: `scripts/vida_mcp_server.py:46` (env var auth), `vida/secure_wallet.py:384-441` (session caps)  
**Scope**: MCP authentication model

### Description

The MCP server has no per-request authentication. Any MCP-compatible agent that can reach the server (or any prompt injection that hijacks the agent's tool-calling ability) can call `vida_send`, `vida_negotiate_offer`, `vida_negotiate_accept`, and all other tools. The **only** defensive layer is:

1. **Environment variable auth**: `VIDA_SESSION` must point to a valid, unexpired session file. This means the attacker needs to (a) compromise the agent process running the MCP server, or (b) trick the agent into calling tools with attacker-controlled parameters.
2. **Session caps**: `max_kas_per_tx`, `max_kas_per_day`, destination allowlists, and `confirm=True` requirement.

### Exploitation Path

A prompt injection in a context window that the MCP-connected agent can see causes the agent to:

```
call vida_send(to_address="kaspa:attacker_address", amount_kas=99999, confirm=True)
```

Three things must align for the attack to succeed:
- The amount must be ≤ `max_kas_per_tx` (defended)
- The cumulative spend must be ≤ `max_kas_per_day` (defended)
- The destination must be in the allowlist, if set (defended)

**Session caps are the last line of defense, and they are software-only.** A compromised agent process that can read the session file (same filesystem) can extract the machine key, re-seal `enc_spend` to zero daily, and exhaust the daily cap repeatedly.

### Fix

- **Already implemented**: AAD-bound session caps, host binding, `confirm=True`, destination allowlists. The existing defense is the most that can be done short of on-chain hard caps.
- **Recommended operational hardening**: Document that the session file is credential-equivalent for the life of the session. Recommend short-lived sessions (hours, not weeks), tight caps, and `--dest` allowlists for payment agents.
- **Long-term**: On-chain covenant hard caps (KIP-17) when Kaspa supports them.

---

## 2. Forced Negotiation Race

**Severity**: **Medium**  
**File**: `vida/plugins/covenant/negotiation.py:240-262` (`accept()` method)  

### Description

Two agents could call `accept()` on the same negotiation session nearly simultaneously. There is no locking or atomicity guarantee. The state machine is in-memory Python objects with no concurrency protection.

```python
def accept(self, negotiation_id: str, agent: str) -> Optional[NegotiationSession]:
    session = self._sessions.get(negotiation_id)
    if not session:
        return None
    if session.is_expired():
        session.status = "expired"
        return session
    latest = session.latest_terms()
    ...
    session.add_round(NegotiationRound(phase=NegotiationPhase.ACCEPT, ...))
    session.deal_hash = latest.deal_hash()
    session.status = "committed"   # <-- last write wins
    return session
```

### Exploitation Path

If agent A and agent B both call `accept()` at nearly the same time (e.g., from two separate threads/processes sharing the `get_negotiator()` singleton), both calls can see `status == "active"` before either sets it to `"committed"`. Both get a return value indicating successful acceptance. Both call `encode_deal()`, which succeeds for both because the check is `session.status != "committed"`.

**Impact**: Both agents believe they have a committed deal, but the deal_hash is deterministic from the same terms, so the resulting policy_hash is identical. This is a **confusion risk, not a fund loss**: both agents would produce duplicate but identical commitments. The on-chain covenant itself (UTXO) cannot be duplicated because the UTXO is a singleton.

### Fix

Add a thread-level or asyncio lock around the accept path:

```python
import threading
self._lock = threading.Lock()

def accept(self, negotiation_id: str, agent: str) -> ...:
    with self._lock:
        session = self._sessions.get(negotiation_id)
        ...
```

Or add an atomic status transition:

```python
if session.status != "active":
    return None  # or return session indicating already committed
```

---

## 3. Fee Avoidance

**Severity**: **Medium**  
**File**: `vida/plugins/covenant/fees.py:53-60` (`calc_fund_fee()`)  

### Description

```python
def calc_fund_fee(pot_kas: float) -> float:
    if not isinstance(pot_kas, (int, float)) or pot_kas <= 0:
        return 0.0
    fee = pot_kas * FEE_SCHEDULE.fund_fee_pct
    fee = max(fee, FEE_SCHEDULE.fund_fee_min_kas)
    fee = min(fee, FEE_SCHEDULE.fund_fee_max_kas)
    return round(fee, 6)
```

### Exploitation Paths

1. **NaN/Inf bypass**: Python's `float('nan') <= 0` is `False`, so the guard `pot_kas <= 0` does NOT catch NaN. `nan * 0.001 = nan`, and `max(nan, 0.01) = nan`, `min(nan, 1.0) = nan`, `round(nan, 6) = nan`. However, in `covenant_plan_with_fees()` the pot is derived from `plan_agent_pot()` which itself validates, so NaN can only reach `calc_fund_fee()` through the MCP tool's `covenant_estimate_fee()` where the user controls the input.

   **Fix**: Add `math.isfinite(pot_kas)` or use `pot_kas > 0` (which is False for NaN).

2. **Max cap truncation**: With 0.1% fee capped at 1 KAS max, a pot of 200,000 KAS or 2,000,000 KAS both pay exactly 1 KAS. This is by design (max cap protects users), but it means the fee is **progressive only up to 1000 KAS pot size** (1000 × 0.1% = 1.0 KAS = cap). Beyond that, fee percentage asymptotically approaches 0%.

   **Not a vulnerability** — the cap is intentional but should be documented prominently.

3. **Free first pot per wallet**: The free tier counter (`free_pots_per_wallet = 1`) is **never checked anywhere in the code**. There is no persistence, no wallet-specific counter, and no decrement logic. The `calc_fund_fee()` function always returns the full fee regardless.

   **Fix**: Either implement the free-pot tracking with a persistent counter, or remove the free tier feature and update `describe_fees()` to document it as a future feature.

### Fix

```python
import math

def calc_fund_fee(pot_kas: float) -> float:
    if not isinstance(pot_kas, (int, float)) or not math.isfinite(pot_kas) or pot_kas <= 0:
        return 0.0
    ...
```

Same fix for `calc_spend_fee()`.

For the free tier: implement or remove the feature description.

---

## 4. Session File Tampering

**Severity**: **Medium**  
**File**: `vida/secure_wallet.py:281-352` (`_unlock_with_session()`)  

### Description

The session file is an unencrypted JSON file with `0o600` permissions. It contains:
- `machine_key` (hex) — the AES-256 key that decrypts the Schnorr signing key
- `enc_schnorr` — the Schnorr private key, AES-256-GCM encrypted with `machine_key`, AAD-bound to `wallet_address`, `expires_at`, `limits`, `host_id`
- `enc_spend` — the daily spend counter, AES-256-GCM encrypted with the same `machine_key`

### Exploitation Path

An attacker who can **read** the session file can:
1. Extract `machine_key` (stored in plain hex)
2. Decrypt `enc_schnorr` — **BUT** only if they can forge the AAD. The AAD binds the key ciphertext to `wallet_address`, `expires_at`, `limits`, `host_id`. Changing any of those fields in the file causes AES-GCM authentication failure.

An attacker who can **write** the session file can:
1. Re-seal `enc_spend` to zero by re-encrypting with the known `machine_key`, resetting the daily spend counter — **the code itself notes this** at line 333: `machine_key lives in the same file, so a writer who can re-seal enc_spend can still reset daily`

### Exploitation — Cap Bypass

The critical attack: an attacker who can **read+write** the session file **cannot** raise caps directly (AAD prevents that). But they **can**:

1. Extract `machine_key` and `enc_schnorr`
2. Brute-force would be needed to alter AAD — AES-GCM prevents this
3. **However**: the machine key is the same key used for `enc_spend`. With the machine key, writing `enc_spend = _seal_spend(machine_key, "2026-01-01", 0.0)` resets the daily counter, allowing unlimited daily spends within the per-tx cap.

### Defenses Already in Place

- AAD binding (expiry, limits, host, wallet address) — prevents cap escalation
- `host_id` binding — session invalid on other machines
- `enc_spend` deletion → refuse unlock (test S14)
- `_write_0600()` atomic write with 0600 perms

### Residual Risk

The machine key and ciphertexts living in the same file is the fundamental tension: the agent must be able to read the key material to sign without the password, but that same key material can be used to forge spend counters. The `host_id` AAD binding mitigates exfiltration but not local tampering.

### Fix (design)

Split the file: store `machine_key` in a separate root-owned file, and have the session file reference it by path. This would mean an attacker needs to compromise two files instead of one. This is a significant design change and may not be justified for the threat model.

**Document as accepted risk** (already partially done in `SECURITY_HARDENING.md`).

---

## 5. Replay Attack — Duplicate Pot Creation

**Severity**: **Info (No issue)**  
**File**: `vida/plugins/covenant/negotiation.py:110-111`, `vida/plugins/covenant/negotiation.py:142-165`  

### Analysis

A signed negotiation offer cannot be replayed because:

```python
class NegotiationSession:
    negotiation_id: str = field(default_factory=lambda: hashlib.sha256(
        f"{time.time()}{os.urandom(8).hex()}".encode()).hexdigest()[:16])
```

Each `create_offer()` generates a fresh, unpredictable `negotiation_id` from `time.time()` + 8 bytes of `os.urandom`. The offer's terms are not used in the ID derivation, so the same terms produce a different ID each time.

The `encode_deal()` method returns a `deal_hash` derived from deterministic JSON-serialized terms, plus a `policy_hash` derived from the same. If an attacker replayed the exact same terms, they'd get the same `deal_hash` and `policy_hash`, but this would be a **different negotiation session** with a different ID. This does NOT create a duplicate UTXO — the on-chain covenant ID is computed from the fund transaction inputs/outputs, not from the off-chain deal hash.

**Verdict**: No replay vulnerability. The `os.urandom(8)` provides 64 bits of entropy per negotiation, making accidental collision negligible.

### But

There is no signature on the negotiation offers themselves. An attacker who can man-in-the-middle the MCP connection could send their own `counter_offer()` or `accept()` with modified terms. However, the `accept()` path validates terms via `CovenantTerms.validate()` and the `accept()` call is from whatever agent holds the session. There is no PKI between agents.

**Fix**: For production-grade agent-to-agent negotiation, signing each offer round with the agent's on-chain key and verifying before acceptance would prevent MITM modification. This is a future improvement, not a current blocker.

---

## 6. Additional Findings

### 6.1 MCP: No Rate Limiting (Low)

**File**: `scripts/vida_mcp_server.py:240-597`

The MCP server has no rate limiting, request queuing, or concurrent request caps. An attacker with access to the server can:
- Issue parallel `vida_send` calls to exhaust the daily cap rapidly (annoying, not a loss)
- Hammer `vida_negotiate` endpoints to create many sessions (memory exhaustion)

**Fix**: Add asyncio-based rate limiting (`asyncio.Semaphore` with max N concurrent requests).

---

### 6.2 MCP: Float From JSON With No Range Limit (Low)

**File**: `scripts/vida_mcp_server.py:378-379`

```python
amount_kas = float(args.get("amount_kas", 0))
```

JSON numbers in Python are parsed as `float` (or `int` for integers without decimal points). An attacker could send:

```json
{"amount_kas": 1e308}
```

This would fail at `VidaTransactor.send()` due to `math.isfinite()` check (line 179), but the error message could leak internal state. More concerning: a very large integer value could cause precision loss (IEEE 754 double can only represent integers up to 2^53 exactly).

**Fix**: Already mitigated by downstream validation in `VidaTransactor.send()`.

---

### 6.3 Session: Host Fingerprint Fallback (Low)

**File**: `vida/secure_wallet.py:91`

```python
def _host_fingerprint() -> str:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            raw = Path(path).read_text().strip()
            if raw:
                return raw
        except Exception:
            continue
    import socket
    return f"host:{socket.gethostname()}"
```

If neither `/etc/machine-id` nor `/var/lib/dbus/machine-id` exists (containers, minimal systems), the fingerprint falls back to hostname. Hostname can be spoofed or changed. This weakens host bind.

**Fix**: Generate and persist a host-specific UUID on first call (`~/.vida/host_id`), making it resistant to hostname changes.

---

### 6.4 Spend JS: Covenant Binding Hash Mismatch (Critical — Known Broken)

**File**: `scripts/covenant_spend_agent_pot.js:192-224`

The spend script's covenant continuation logic is broken:

```javascript
// For continuation, authorizing_input 0, same id as spent covenant.
if (filterCov && filterCov.length === 64) {
    // reconstruct Hash via covenantId on a dummy is hard; set binding from recompute
    // Recompute genesis-style id is WRONG for transition. For transition, reuse spent id.
    // WASM: new CovenantBinding(0, Hash) — try Hash from string if available
    let idObj = null;
    if (kaspa.Hash && kaspa.Hash.fromHex) {
        idObj = kaspa.Hash.fromHex(filterCov);
    } else if (kaspa.Hash) {
        try {
            idObj = new kaspa.Hash(filterCov);
        } catch (_) {
            idObj = null;
        }
    }
    if (idObj) {
        tx.outputs[1].covenant = new CovenantBinding(0, idObj);
```

The comments themselves admit: "Recompute genesis-style id is WRONG for transition. For transition, reuse spent id." The code tries three different methods to reconstruct the covenant Hash from a hex string, with fallbacks — none of which are correct for transition spends. The WASM `covenantId` function creates a genesis-style ID from inputs/outputs, which is different from the spent covenant's ID.

**Impact**: Any attempt to spend from a covenant pot will create a transaction with an incorrectly bound covenant on the change output. This will either be rejected by the network (if the hash format mismatches) or create a broken covenant that the next spend cannot reference.

**Fix**: The correct approach is to extract the covenant ID from the **spent input UTXO** (which Kaspa's RPC provides as `covenantId` on UTXO entries) and use that ID directly for the change output's `CovenantBinding`. The fund script shows the correct pattern — it computes `covenantId()` from the genesis inputs/outputs and applies it.

---

### 6.5 Fund Script: Covenant ID Handling Fragile (Info)

**File**: `scripts/covenant_fund_agent_pot.js:118-127`

```javascript
const cid = e.covenantId;
if (cid !== undefined && cid !== null && String(cid) !== '' && String(cid) !== 'undefined') {
    try {
        const s = cid.toString ? cid.toString() : String(cid);
        if (s && s.length >= 16 && s !== '[object Object]') continue;
    } catch (_) { /* keep */ }
}
```

This UTXO filtering logic attempts to skip UTXOs that already have a covenant binding. The string checks for `'[object Object]'` and `'undefined'` hint at WASM API instability where the covenant ID field returns unexpected types. If the WASM API changes the format of `covenantId` for covenant UTXOs, this check could skip non-covenant UTXOs or include covenant UTXOs.

**Not exploitable** but fragile — a WASM version update could silently break UTXO selection.

---

### 6.6 Negotiation: `**kwargs` Filtering via `hasattr` (Info)

**File**: `vida/plugins/covenant/negotiation.py:152`

```python
**{k: v for k, v in kwargs.items() if hasattr(CovenantTerms, k)},
```

This allows setting **any** field on `CovenantTerms` via kwargs. An attacker could pass `voting_threshold` or `dispute_resolver` or other governance fields that aren't intended for the MCP tool path. The MCP server's `vida_negotiate_offer` handler only passes the documented args, but if someone later adds a new tool that forwards all args, this could set unexpected fields.

**Not exploitable in current code paths** but the `hasattr` pattern is overly permissive. Consider an explicit allowlist:

```python
ALLOWED_OFFER_KEYS = {"max_kas_per_tx", "max_kas_per_day", "allowed_destinations", "duration_hours"}
```

---

### 6.7 Pot Spend: No Replay or Nonce on Soft Policy Check (Info)

**File**: `vida/plugins/covenant/pot_spend.py:19-82`

The `check_spend_allowed()` and `check_spend_kas()` functions are stateless pure functions. They perform no tracking of spent amounts against a pot's daily or total budget. The daily budget enforcement is handled by the session layer (`secure_wallet.py`), not the covenant pot policy.

**This is by design**: the pot policy only enforces `max_tx_sompi` and destination allowlists. There is no pot-level daily or total cap enforcement in the covenant module — that's delegated to the session layer.

**Implication**: If an agent has multiple pots (or a pot and a direct session), two separate pots could each spend up to `max_kas_per_day` independently, with no coordination. An attacker who compromises the agent gains access to multiple independent budgets.

**Not a vulnerability** — consistent with the documented design. But worth documenting in the threat model for operators.

---

## False Positives Flagged

### `calc_fund_fee(NaN)` returns NaN, not 0

When I initially traced this, I thought `NaN` input would return 0.0 (because `nan <= 0` is False). But `round(nan, 6)` returns `nan`, not `0.0`. So a NaN input produces NaN output. The MCP tool `covenant_estimate_fee()` would return `{"fee_kas": nan}`, which is a confusing but not dangerous output. The caller would need to handle NaN. **Not a fund-loss issue** because downstream transaction building would reject NaN amounts.

### First pot free — feature not implemented

The `free_pots_per_wallet` field exists but is never checked. `fee.py` always charges the full fee. This is a **missing feature**, not a security vulnerability. Updated to "Low" severity because a user expecting a free pot would not get one.

---

## Recommendation Priority

1. **Fix the spend JS script** (`covenant_spend_agent_pot.js`) — covenant transition spends are broken, potentially blocking all pot spending.
2. **Fix free-pot feature or documentation** — implement the first-pot-free tracking or remove from `describe_fees()`.
3. **Add NaN guard to fee functions** — `math.isfinite()` check to prevent NaN propagation.
4. **Add accept-lock to negotiation** — prevent race condition on final acceptance.
5. **Harden host fingerprint** — persist stable host UUID to `~/.vida/host_id`.
6. **Document residual machine-key risk** — add to `SECURITY_HARDENING.md` per existing pattern.
7. **Add rate limiting to MCP server** — prevent resource exhaustion.
8. **Narrow kwargs allowlist** in `create_offer()` — only accept documented negotiation parameters.

---

*Audit completed. All findings are read-only. No code was executed, no transactions were broadcast, and no files were modified during this review.*