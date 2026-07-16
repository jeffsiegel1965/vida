# Vida covenant plugin

**Phase:** scaffold / offline only (2026-07-13)  
**Plugin name:** `covenant` · **Chain:** `kaspa`

## Status

| Capability | Ready? |
|------------|--------|
| Plugin registration / `status` / `describe` | Yes |
| Offline budget validation (`computeBudget` rules from #1073) | Yes |
| Timelock metadata sketch (no bytecode guarantee) | Yes |
| Soft policy preflight (`check_action`) | Yes — software only |
| Soft policy (agent sessions) | Yes — use Kaspa `secure_wallet` sessions |
| Go/no-go (A) | [`GO_NOGO.md`](GO_NOGO.md) — **NO-GO live** as of 2026-07-14 |
| Agent hard-cap design (B) | [`AGENT_HARD_CAP_DESIGN.md`](AGENT_HARD_CAP_DESIGN.md) |
| Live deploy / spend / broadcast (C) | **No** — see [`C_TN10_STATUS.md`](C_TN10_STATUS.md) |

## Honest limits

- **Now:** software session policy (FULL / HYBRID / COMMAND, max/tx, max/day). This is **not** an on-chain hard cap.
- **Live covenants:** blocked on post-Toccata SDK wire format (`computeBudget` must survive serialize/sign). See the product blocker write-up.
- `deploy()` / `spend()` **always return `ok: False`** in this scaffold. They never invent a txid or claim success.

## Why not live yet

Canonical status: [COVENANT_BLOCKER_STATUS.md](../COVENANT_BLOCKER_STATUS.md)  
Upstream: [rusty-kaspa#1073](https://github.com/kaspanet/rusty-kaspa/issues/1073) · fix path [PR #1074](https://github.com/kaspanet/rusty-kaspa/pull/1074)

Old SDKs drop `computeBudget` → node sees budget 0 → `used=100000, limit=9999`.

## Usage (offline)

```python
from vida.plugins import PluginRegistry
from vida.plugins.base import VidaPluginContext
from vida.plugins.covenant import CovenantPlugin, register_covenant_plugin

reg = PluginRegistry()
p = register_covenant_plugin(reg)
print(p.status(VidaPluginContext(wallet_id="demo", mode="COMMAND")))
print(p.validate_budget(10))
print(p.sketch_timelock(100))
print(p.deploy())  # always refuses until live wired
```

## Unit test

```bash
cd /path/to/vida-release
python3 tests/test_covenant_scaffold.py -v
```

No network, no node, no broadcast.

## Unblock (live phase later)

1. Post-Toccata client ([PR #1074](https://github.com/kaspanet/rusty-kaspa/pull/1074))
2. Deploy+spend TN10 with budget **10–20** per signing input (including change)
3. Record our own accepted txids under `docs/proofs/`
4. Then enable live methods on this plugin (still optional next to soft policy)
