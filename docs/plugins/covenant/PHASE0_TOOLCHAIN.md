# Covenant Phase 0 — Post-Toccata Toolchain Investigation

**Investigated (UTC):** 2026-07-14T15:42:56Z  
**Host:** Linux Spock `7.0.0-27-generic` x86_64  
**Scope:** This machine only. Verified facts with commands/paths. No transactions broadcast.  
**Do not claim live covenants work from this tree without our own accepted TN10 txids.**

---

## Verdict

| Goal | Status |
|------|--------|
| Live TN10 covenant deploy/spend from this machine **today** | **NO-GO** |
| Offline plugin scaffold / soft agent caps | Out of Phase 0 scope (see plugin README) |
| Network covenants exist on TN10 (third-party indexer) | Observed via kascov API (not our txs) |

**Blocker class:** Missing post-Toccata client that round-trips `computeBudget` / `ComputeCommit`. Installed SDKs are pre-fix wire shape.

---

## 1. Rust toolchain

| Check | Result | Command / evidence |
|-------|--------|--------------------|
| `rustc` | **Not installed** | `command -v rustc` / `type rustc` → not found |
| `cargo` | **Not installed** | `command -v cargo` / `type cargo` → not found |
| `rustup` | **Not installed** | `command -v rustup` → not found; `~/.cargo/bin` empty/absent |
| apt candidates (not installed) | `rustc` / `cargo` **1.93.1ubuntu1** available | `apt-cache policy rustc cargo` → Installed: (none) |
| snap | `rustup` 1.29.0 published | `snap find rust` lists `rustup` |

**No** local `rusty-kaspa` clone found:

```text
find <home> -maxdepth 6 -type d -name 'rusty-kaspa'  → (empty)
find <home> -name 'Cargo.toml' (maxdepth deep) → only
  <home>/Downloads/hermes-agent-main/apps/bootstrap-installer/src-tauri/Cargo.toml
```

---

## 2. PR #1074 fetchability (remote only; not built here)

| Field | Verified value |
|-------|----------------|
| URL | https://github.com/kaspanet/rusty-kaspa/pull/1074 |
| State | **open** (not merged) |
| Title | `compute commit, mass calculation and generator fixes` |
| Author | IzioDev |
| Head | `IzioDev:tmp/generator-changes` @ `08ccc37c2dd34d083013e8034fa9b312eb8c47c4` |
| Base | `kaspanet:master` |
| Mergeable | `true` / `mergeable_state: clean` (API snapshot 2026-07-14) |
| Draft | false |
| merged_at | null |

**Fetch refs (no clone performed):**

```text
git ls-remote https://github.com/kaspanet/rusty-kaspa.git 'refs/pull/1074/*'
  08ccc37c2dd34d083013e8034fa9b312eb8c47c4  refs/pull/1074/head
  1e74b54daa311194730528b91b56fbfa2e556759  refs/pull/1074/merge

git ls-remote https://github.com/IzioDev/rusty-kaspa.git 'refs/heads/tmp/generator-changes'
  08ccc37c2dd34d083013e8034fa9b312eb8c47c4  refs/heads/tmp/generator-changes
```

PR body (API) claims WASM wrapper for `ComputeCommit`, generator `compute_commit` + tx `version`, covenant support in wasm create-transaction, etc.

Related issue (still open): https://github.com/kaspanet/rusty-kaspa/issues/1073  
- Title: `v1 covenant transaction rejected on testnet-10: "script units exceeded" even with computeBudget set`
- State: **open**, comments: 5 (API 2026-07-14)

---

## 3. Python `kaspa` package (this machine)

| Item | Value |
|------|--------|
| Install location | `<kaspa-suite>/venv/lib/python3.11/site-packages/kaspa/` |
| Interpreter | `<kaspa-suite>/venv/bin/python` → **3.11.15** |
| PyPI version | **2.0.1** (`pip show kaspa`) |
| PyPI latest | **2.0.1** only newer line (`pip index versions kaspa`) |
| Upstream releases | `v2.0.1` published 2026-06-18 (`api.github.com/.../kaspanet/kaspa-python-sdk/releases`) |
| Extension | `kaspa/kaspa.cpython-311-x86_64-linux-gnu.so` (native PyO3) |
| Project URL | https://github.com/kaspanet/kaspa-python-sdk |
| `ComputeCommit` in stubs | **0** occurrences in `__init__.pyi` |

**Not installed in:**

- system `/usr/bin/python3`
- `<kaspa-suite>/.venv` (separate venv; no `kaspa`)

**Covenant-related symbols present on 2.0.1:** `CovenantBinding`, `GenesisCovenantGroup`, `covenant_id`  
**TransactionInput** attrs: `compute_budget`, `from_dict`, `previous_outpoint`, `sequence`, `sig_op_count`, `signature_script`, `to_dict`, `utxo`

### 3.1 Repro: `to_dict()` drops `computeBudget` (Knitser pattern)

Command (venv python):

```python
from kaspa import TransactionInput
import json

d_in = {
    "previousOutpoint": {"transactionId": "00"*32, "index": 0},
    "signatureScript": "",
    "sequence": 0,
    "sigOpCount": 1,
    "computeBudget": 10,
}
ti = TransactionInput.from_dict(d_in)
print("in-memory compute_budget:", ti.compute_budget)  # → 10
print("to_dict keys:", sorted(ti.to_dict().keys()))
print(json.dumps(ti.to_dict()))
```

**Observed 2026-07-14:**

| Step | Result |
|------|--------|
| `from_dict` with camel `computeBudget: 10` | in-memory `ti.compute_budget == 10` |
| `ti.to_dict()` keys | `['previousOutpoint', 'sequence', 'sigOpCount', 'signatureScript', 'utxo']` |
| `computeBudget` / `compute_budget` in `to_dict()` | **absent** |
| Set `ti.compute_budget = 10` after construct | memory=10; `to_dict()` still **no** budget field |
| `from_dict` snake_case keys | **FAIL** `KeyError: Key 'previousOutpoint' not present` |
| Default without budget | `compute_budget == 0`; same keys (sigOpCount only) |

**Implication (aligned with #1073 diagnosis):** serialization path still emits sigOpCount-era JSON; node can see effective budget 0 → free ~9999 script units → Schnorr CheckSig (~100000 units) fails with `used=100000, limit=9999`.

---

## 4. npm `kaspa-wasm` (this machine)

| Item | Value |
|------|--------|
| Local (kaspa-suite) | `<kaspa-suite>/node_modules/kaspa-wasm` **0.13.0** |
| Also under home | `<home>/node_modules/kaspa-wasm` **0.13.0** |
| npm registry latest | **0.13.0** (`npm view kaspa-wasm version`) |
| `package.json` dep | `"kaspa-wasm": "^0.13.0"` in kaspa-suite |

`kaspa_wasm.d.ts` class `TransactionInput` fields (lines ~1970–1996):

- `previousOutpoint`, `sequence`, `sigOpCount`, `signatureScript`
- **No** `computeBudget` / `compute_budget` / `ComputeCommit`

---

## 5. kascov / network observation (read-only)

| Check | Result |
|-------|--------|
| Repo | https://github.com/Knitser/kascov — remote `HEAD` reachable: `e9cc8ae62162f9c794100d3c44d459f3ee9b778a` |
| Local clone | **None** (`find … -name kascov` empty under home maxdepth 4) |
| Live feed | `GET https://kascov-explorer.web.app/data/testnet-10-live.json` → **HTTP 200** |
| Live stats (snapshot) | `network=testnet-10`, `stats.covenants=265272`, `active=17673`, `burned=247599`, `events=1217346` |
| Known-good spend debug | `GET https://kascov.io/data/testnet-10/debug/051288013eecf1cc3f890005236b96567f743423390a540650af65f50c4288b3` → **HTTP 200**, `ok: true`, `covenant_id: b4ade48e…`, outpoint txid `a9a7df1a…` (Knitser deploy reference) |
| Deploy debug alone | `…/debug/a9a7df1a…` returned `ok:false` reason “didn't spend any covenant state we track” (endpoint is spend-oriented) |

**Note:** Indexer activity proves **TN10 has covenants**; it does **not** prove this workstation can create/spend them with installed SDKs.

---

## 6. Related local trees (paths only)

| Path | Role |
|------|------|
| `<kaspa-suite>` | Main suite + venv with `kaspa==2.0.1` |
| `<kaspa-suite>/COVENANT_BLOCKER_STATUS.md` | Product/tech status re #1073 |
| `<repo>` | Release repo; this doc under `docs/plugins/covenant/` |
| `<repo>/docs/plugins/COVENANT_BLOCKER_STATUS.md` | Mirror status |
| Disk free | ~669G available on `/` (enough to clone/build) |

`node` present: `<home>/.local/bin/node` v22.23.1  
`gh` CLI: **not** installed  
Local `kaspad` / `kaspa-wallet` binaries: **not** on PATH

---

## 7. Go / No-Go for live TN10 **today**

### NO-GO reasons (all verified)

1. **No Rust toolchain** → cannot build rusty-kaspa PR #1074 WASM/Python bindings from source on this host without install.
2. **No rusty-kaspa clone** → nothing to check out / build.
3. **PyPI `kaspa==2.0.1` is latest** and **drops `computeBudget` in `to_dict()`** (repro above).
4. **npm `kaspa-wasm@0.13.0` has no computeBudget field** on `TransactionInput`.
5. **PR #1074 is open, not merged** — no published fixed wheel/npm package observed.
6. No local proof artifact (our own accepted deploy+spend txids) produced in this Phase 0 run.

### What is *not* claimed

- Not claiming TN10 lacks covenants (kascov shows heavy activity).
- Not claiming PR #1074 is broken or fixed beyond “exists, open, fetchable.”
- Not broadcasting or signing live txs in Phase 0.

---

## 8. Exact next install commands (when unblocking)

Prefer official Rust installer + PR fetch (do **not** use frozen PyPI 2.0.1 for v1 budget wire tests).

```bash
# 1) Rust toolchain (pick one)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# OR: sudo snap install rustup --classic && rustup default stable
# OR: sudo apt-get install -y rustc cargo   # distro 1.93.1ubuntu1 — may be older than project needs

# 2) Clone + fetch PR 1074
mkdir -p ~/src && cd ~/src
git clone --filter=blob:none --sparse https://github.com/kaspanet/rusty-kaspa.git
cd rusty-kaspa
git fetch origin pull/1074/head:pr-1074
git checkout pr-1074
# alternate head: git remote add izio https://github.com/IzioDev/rusty-kaspa.git
#                 git fetch izio tmp/generator-changes && git checkout 08ccc37c2dd34d083013e8034fa9b312eb8c47c4

# 3) Build client bindings per that tree’s wasm/python docs (exact crate targets depend on PR layout).
#    After build, install into a fresh venv; then prove:
#      ti.compute_budget = 10; assert 'computeBudget' in ti.to_dict()  # or PR’s ComputeCommit JSON key

# 4) Optional reference stack (MIT)
git clone https://github.com/Knitser/kascov.git ~/src/kascov
```

**Success gate before claiming live GO:**

1. Round-trip: input with budget 10–20 survives serialize/deserialize (JSON keys retained).  
2. Budget set **before** signing; every signing input (incl. fee/change) has budget.  
3. Own TN10 deploy + spend accepted txids recorded under `vida-release/docs/proofs/`.  
4. Prefer budgets ~10–20 (not 65535) per signing input once wire path works.

---

## 9. Command log (investigation)

```text
command -v rustc cargo rustup          # all missing
find … rusty-kaspa                     # none
git ls-remote … pull/1074/*            # head+merge present
git ls-remote IzioDev … tmp/generator-changes  # sha 08ccc37c…
curl api.github.com/.../pulls/1074     # open, mergeable clean
pip show / index kaspa in kaspa-suite/venv  # 2.0.1 / latest 2.0.1
Python TransactionInput.from_dict/to_dict repro  # budget dropped
npm view kaspa-wasm version            # 0.13.0
kascov live + debug endpoints          # HTTP 200
```

**End of Phase 0 report.**
