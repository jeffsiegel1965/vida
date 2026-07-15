**SUPERSEDED for live status:** live Finney stake + session stake + P2P transfer are proven — see `tao_phase1b_extrinsic.md`, `tao_agent_session_live.md`, `tao_p2p_and_optimizer.md`, `tao_qa_report.md`.

# TAO Phase 1B — Policy-gated stake (mock path proven)

**When:** 2026-07-09  
**Status:** Mock/policy path (this file). **Live Finney stake is proven elsewhere** — see superseded banner above.

## What works

| Gate | Result |
|------|--------|
| `confirm=True` required | yes |
| COMMAND mode blocks auto stake | yes |
| FULL within caps allows | yes |
| Subnet allowlist | yes |
| Session revoked | deny |
| Negative amount | deny |
| Daily cap | deny |
| Wrong password unlock | deny |
| Mock delegate/undelegate hash | yes |

## Tests

```text
tests/test_tao_stake.py → 13 OK
(+ prior Phase 0/1 suites still green)
```

## Live extrinsic

Not claimed. To produce a real hash you need:

1. Owner-provision a wallet with a **funded** Finney coldkey (not the abandon test vector)
2. Call `delegate(..., confirm=True, password=...)` with tiny amount
3. Save extrinsic hash to this file

Until then, Phase 1B is **policy + signing path proven offline**; on-chain stake remains unproven.

## API surface

```python
plugin.delegate(ctx, amount_tao=0.1, netuid=1, confirm=True, password="...")
plugin.undelegate(ctx, amount_tao=0.1, netuid=1, confirm=True, password="...")
# Hermes helpers: vida_tao_delegate / vida_tao_undelegate
```

Capabilities: `status`, `balance`, `delegate`, `undelegate`
