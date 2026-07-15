# TAO Phase 1 — Live health proof

**When:** 2026-07-09T00:05:26Z (health) / balance smoke same session  
**Network:** finney  
**Endpoint:** `wss://entrypoint-finney.opentensor.ai:443`  
**Chain:** Bittensor  
**Block:** 8579984 (health) / 8579986 (balance smoke)  
**Elapsed (health):** 1.54s  

No keys were used. No seed derivation. Infrastructure + live RPC only.

## Health

```json
{
  "ok": true,
  "network": "finney",
  "endpoint": "wss://entrypoint-finney.opentensor.ai:443",
  "chain_name": "Bittensor",
  "block_number": 8579984,
  "error": null,
  "elapsed_sec": 1.54,
  "ss58_prefix": 42
}
```

## Balance path smoke (public Substrate Alice address)

Address: `5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY`  
(Not a Vida wallet — only proves `System.Account` query shape.)

```json
{
  "ok": true,
  "free_tao": "0",
  "reserved_tao": "0",
  "error": null
}
```

## How to re-run

```bash
# use env with substrate-interface (e.g. kaspa-suite venv)
python scripts/tao_health_check.py --network finney --write-proof
python scripts/tao_health_check.py --network finney --address 5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY
```

## Not done yet

- Owner seed → TAO address (T1.2)
- Encrypted account provisioning
- Staking extrinsics (Phase 1B)
