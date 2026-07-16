# PR #1074 build report

**Date:** 2026-07-14  
**Source:** `git fetch origin pull/1074/head` → `08ccc37c2dd34d083013e8034fa9b312eb8c47c4`  
**Tree:** `~/.hermes/projects/toolchain/rusty-kaspa-pr1074`

---

## Built

| Artifact | Path |
|----------|------|
| Node WASM SDK (full `wasm32-sdk`) | `rusty-kaspa-pr1074/wasm/nodejs/kaspa/` |
| Files | `kaspa.js`, `kaspa_bg.wasm` (~11MB), `kaspa.d.ts`, `package.json` |

**Command:** `wasm/build-node` (`wasm-pack` → target `nodejs`, features `wasm32-sdk`)

**Tooling used:**
- rustc/cargo 1.97.0  
- wasm-pack 0.15.0  
- clang 18.1.8 (user-local; system had no clang/sudo)  
- libtinfo5 (user-local from Debian package)  

---

## Round-trip probe (Node)

```text
in-memory computeBudget → 10
toJSON has computeBudget → 10
reconstruct from JSON → computeBudget 10
PASS
```

Also exposes `ComputeCommit.fromComputeBudget(10)`.

**Compare:** PyPI Python `kaspa` 2.0.1 still **drops** `computeBudget` on `to_dict` (unchanged).

---

## What this does / does not unlock

| Item | Status |
|------|--------|
| Local #1074 WASM client | **Built** |
| `computeBudget` serialize (WASM/JS) | **PASS** |
| Python `kaspa` package updated | **No** (separate SDK; still 2.0.1) |
| TN10 deploy/spend from Vida Python | **Not yet** — need wire path that uses this WASM or a fixed Python SDK |
| #1074 merged upstream | **Still open** |

---

## How to use the build

```bash
# Node
node -e "const k=require('.../wasm/nodejs/kaspa'); ..."

# Optional npm link for projects
cd wasm/nodejs/kaspa && npm link
```

For Vida **C** (TN10 covenant): either  
1. drive deploy/spend via **Node + this package**, or  
2. wait for / build **Python** bindings that include the same fix.

---

## Disk note

Clone + target + clang tarball are large. Safe to delete `/tmp/clang-llvm.tar.xz` after install. Keep `rusty-kaspa-pr1074` for rebuilds.
