# Vida Plugin Build Tickets

**Execution order:** Phase 0 → Phase 1 → Phase 1B  
**Roadmap:** [PLUGIN_ROADMAP.md](./PLUGIN_ROADMAP.md)

Status legend: `TODO` | `DOING` | `DONE` | `BLOCKED`

---

## Phase 0 — Plugin seam

**Goal:** Chain-agnostic plugin surface in standalone Vida. No TAO/covenant chain logic yet.   (status: [COVENANT_BLOCKER_STATUS.md](docs/plugins/COVENANT_BLOCKER_STATUS.md))
**Exit criteria:**
- [ ] `vida.plugins` package exists with protocol + registry + policy types  
- [ ] Dummy plugin registers, lists, and is policy-gated  
- [ ] Unit tests pass without network  
- [ ] Existing Kaspa wallet/tests still pass  
- [ ] README roadmap links to plugin docs  

### T0.1 — Package layout
**Status:** TODO  
**Files:**
- `vida/plugins/__init__.py`
- `vida/plugins/base.py`
- `vida/plugins/registry.py`
- `vida/plugins/policy.py`
- `vida/plugins/dummy.py` (dev/test only)

**Done when:** imports work: `from vida.plugins import PluginRegistry, VidaPlugin, PolicyRequest`

### T0.2 — `VidaPlugin` protocol
**Status:** TODO  
**Required attributes/methods:**
- `name: str` — e.g. `"dummy"`, `"tao"`, `"kaspa"`
- `chain: str` — e.g. `"none"`, `"bittensor"`, `"kaspa"`
- `capabilities: list[str]` — e.g. `["status", "transfer", "delegate"]`
- `status(ctx) -> dict` — read-only  
- `describe() -> dict` — public metadata for Hermes/UI  

**Optional (later plugins):** `transfer`, `delegate`, `undelegate`, `deploy_covenant`  
**Rule:** plugins never receive raw seed/password; only a `VidaPluginContext`.

### T0.3 — `VidaPluginContext` + policy
**Status:** TODO  
**Types in `policy.py` / `base.py`:**
- `VidaPluginContext`: `wallet_id`, `network`, `session_id` (optional), `mode`, caps  
- `PolicyRequest`: `chain`, `action`, `amount`, `destination` (optional), `meta`  
- `PolicyDecision`: `allowed: bool`, `reason: str`, `needs_approval: bool`  
- `evaluate_policy(ctx, request) -> PolicyDecision`  
  - COMMAND → always `needs_approval=True` / not auto-allowed  
  - HYBRID → allow iff amount ≤ threshold and within daily cap  
  - FULL → allow within daily/per-tx caps  
  - negative / non-finite amounts → deny  

### T0.4 — `PluginRegistry`
**Status:** TODO  
**API:**
- `register(plugin)`  
- `get(name)`  
- `list_plugins() -> list[dict]`  
- `enabled names` config (env or simple list)  
- Reject duplicate names  

### T0.5 — Dummy plugin + tests
**Status:** TODO  
**Dummy:**
- `name="dummy"`, `chain="none"`, capabilities `["status"]`  
- `status()` returns fixed dict  
- Any spend-like action goes through `evaluate_policy` and is denied or needs approval per mode  

**Tests:** `tests/test_plugins_phase0.py`
- register + list  
- duplicate name fails  
- policy FULL under cap allows  
- policy COMMAND denies auto  
- policy rejects negative amount  
- dummy status works  

### T0.6 — Docs touch
**Status:** TODO  
- README roadmap: link Plugin Roadmap + note Phase 0 in progress  
- This ticket file statuses updated  

### Phase 0 acceptance
```bash
cd /path/to/vida-release
# existing
python tests/qa_tests.py
python tests/qa_secure_tests.py
# new
python -m pytest tests/test_plugins_phase0.py -q
# or a small runner if pytest not desired
```

---

## Phase 1 — TAO infrastructure → then identity/balance

**Goal:** Build TAO plugin rails **before** deriving addresses.  
**Depends on:** Phase 0 DONE  
**Order inside Phase 1:**
1. Infrastructure (T1.0.*) — config, client interface, account store, plugin skeleton  
2. Live client (T1.1) — real RPC health  
3. Derivation (T1.2) — owner-only seed → SS58  
4. Balance proof (T1.3–T1.4)  

**Exit criteria (full Phase 1):**
- [x] TAO plugin package + mock client + account schema (infra)
- [x] Live RPC health works
- [x] Address derived from owner seed (owner path only)
- [x] Live balance proof documented
- [x] Agent cannot export coldkey/seed

### T1.0 — Infrastructure (DO FIRST)
**Status:** DONE (2026-07-08)

| Sub | Work | Status |
|-----|------|--------|
| T1.0.1 | `docs/plugins/tao.md` infrastructure spec | DONE |
| T1.0.2 | `vida/plugins/tao/config.py` networks + env | DONE |
| T1.0.3 | `client.py` Protocol + MockTaoClient + live placeholder | DONE |
| T1.0.4 | `accounts.py` TaoAccountRecord + 0600 store | DONE |
| T1.0.5 | `plugin.py` TaoPlugin status/policy; derivation blocked | DONE |
| T1.0.6 | `requirements-tao.txt` (optional; not required for mock) | DONE |
| T1.0.7 | `tests/test_tao_infra.py` offline (15 tests) | DONE |

**Done when:** `python tests/test_tao_infra.py` green; `provision_from_seed` returns not-enabled.

### T1.1 — Live Substrate client (health only)
**Status:** DONE (2026-07-08)  
**Work done:**
- `vida/plugins/tao/substrate_client.py` — `SubstrateTaoClient` + `make_tao_client`
- `health()` live on Finney: chain **Bittensor**, block proven
- `get_balance()` System.Account path implemented (public address smoke OK)
- `scripts/tao_health_check.py` + `docs/proofs/tao_phase1_health.md`
- `requirements-tao.txt` pins substrate-interface
- No key derivation

### T1.2 — Seed → TAO account (owner path only)
**Status:** DONE (2026-07-08)  
**Work done:**
- `derive.py` — Substrate URI coldkey + `//hotkey` (deterministic test vector)
- `provision.py` — scrypt+AES-GCM encrypt secrets; public record only for agents
- `scripts/provision_tao_account.py` — owner-run (mnemonic from env/file, not argv)
- Agent `provision_from_seed` stays blocked; `owner_provision` for scripts only
- Tests: `tests/test_tao_derive.py` (5 OK with substrate-interface)

### T1.3 — Balance on provisioned account
**Status:** DONE (2026-07-08)  
- `status()` / `balance()` return free+reserved TAO
- capabilities: `["status", "balance"]`
- hotkey_ss58 surfaced from public meta

### T1.4 — Live balance proof doc
**Status:** DONE  
- `docs/proofs/tao_phase1_balance.md` — Finney provision→status→balance (test vector)
- `scripts/tao_balance_proof.py`

### T1.5 — Hermes tool (read-only)
**Status:** DONE  
- `vida/plugins/tao/tools.py` — `vida_tao_status`, `vida_tao_balance`  
- No mnemonic parameters

### T1.6 — Tests
**Status:** DONE (Phase 1 unit set)  
- infra 15 + derive 5 + balance 3 + phase0 16

### Phase 1 acceptance
- [x] Infra tests green
- [x] Live health + owner-provisioned balance path proven on Finney
- [x] Agent cannot export coldkey/seed / agent provision blocked
- [x] No stake extrinsics claimed

## Phase 1B — TAO act (policy-gated stake)

**Goal:** Agent can delegate/undelegate TAO only inside session policy.  
**Depends on:** Phase 1 DONE  
**Exit criteria:**
- [ ] Policy caps enforced before any extrinsic  
- [ ] FULL / HYBRID / COMMAND behavior matches Kaspa semantics  
- [ ] One live extrinsic hash verified  
- [ ] Tools require `confirm=True` for destructive ops  

### T1B.1 — Action policy for TAO
**Status:** DONE  
**Fields:**
- `max_tao_per_tx`, `max_tao_per_day`  
- `allowed_actions`: `delegate`, `undelegate`, (`transfer` if enabled)  
- optional `allowed_subnets: list[int]`  
- Wire through `evaluate_policy`  

### T1B.2 — Hotkey / session mapping
**Status:** DONE (hotkey from provision meta; session_revoked on ctx)  
**Work:**
- Coldkey = owner vault  
- Hotkey or stake authority = session-scoped material where possible  
- FULL: act within caps  
- HYBRID: auto under threshold  
- COMMAND: always needs owner approval path  
- Revoke session ⇒ no further TAO acts  

### T1B.3 — Delegate / undelegate implementation
**Status:** DONE (mock path proven; live substrate submit implemented, needs funded key)  
**Work:**
- Build, sign, submit extrinsics via pinned client  
- Return `{ok, extrinsic_hash, explorer_url?}`  
- On failure: structured error, no false success  

### T1B.4 — Hermes tools
**Status:** DONE (vida_tao_delegate / undelegate, confirm required)  
- `vida_tao_delegate(..., confirm=False)`  
- `vida_tao_undelegate(..., confirm=False)`  
- optional `vida_tao_transfer`  
- `vida_tao_positions`  

### T1B.5 — Live extrinsic proof
**Status:** DONE (2026-07-13)
- Extrinsic: `0xdc2cd82212b0d2e8ed35ec9d4004697e5ebe60257dccffd04a0e16cf119c62c0`
- `docs/proofs/tao_phase1b_extrinsic.md`  
- Tiny stake or unstake on real network  
- `docs/proofs/tao_phase1b_extrinsic.md` with hash + what was done  
- Same bar as Kaspa mainnet receipt  

### T1B.6 — Adversarial tests
**Status:** DONE (13 tests)  
- Over daily cap → deny  
- Disallowed subnet → deny  
- COMMAND mode → no auto stake  
- Negative amount → deny  
- Revoked session → deny  

### Phase 1B acceptance
```text
Policy deny paths tested
One live extrinsic verified on-chain
Docs updated: TAO plugin capabilities = status + stake
```

---

## Later tickets (not started)

| ID | Phase | Note |
|----|-------|------|
| T2.* | Portfolio KAS+TAO | After 1B |
| T3.* | Covenant offline | Parallel watch OK; no fake deploy |
| T4.* | Live covenants | Blocked on Kaspa protocol |
| T5.* | BTC / bridge | After TAO+covenant maturity |

---

## Current focus

**Active phase:** Phase 1B COMPLETE (live stake proven)

| Ticket | Status |
|--------|--------|
| Phase 0–1 | DONE |
| Phase 1B (incl. live extrinsic) | DONE |

Update this file as tickets move `TODO` → `DOING` → `DONE`.
