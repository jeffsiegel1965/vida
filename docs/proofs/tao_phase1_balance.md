# TAO Phase 1 — Provisioned account balance proof

**When:** 2026-07-09T00:08:22Z
**Network:** finney
**Address (test vector coldkey):** `5EPCUjPxiHAcNooYipQFWr9NmmXJKpNG5RhcntXwbtUySrgH`
**Elapsed:** 1.26s

## What this proves

1. Owner provision derives deterministic SS58 from mnemonic
2. Secrets encrypted at rest (agent status has no private keys)
3. Agent `provision_from_seed` remains blocked
4. Live Finney `status()` returns free/reserved TAO via System.Account

## Result

```json
{
  "ok": true,
  "wallet_id": "proof-abandon",
  "ss58_address": "5EPCUjPxiHAcNooYipQFWr9NmmXJKpNG5RhcntXwbtUySrgH",
  "hotkey_ss58": "5DUfE6odm5zHq9GqArraUFKDny34ormTU5FPLAhgKnSWUd8y",
  "provisioned": true,
  "client": {
    "ok": true,
    "endpoint": "wss://entrypoint-finney.opentensor.ai:443",
    "block_number": 8579999,
    "chain_name": "Bittensor",
    "error": null
  },
  "balance": {
    "ok": true,
    "free_tao": "0",
    "reserved_tao": "0",
    "unit": "TAO",
    "error": null,
    "meta": {
      "endpoint": "wss://entrypoint-finney.opentensor.ai:443",
      "unit": "TAO",
      "rao_per_tao": "1000000000"
    }
  },
  "elapsed_sec": 1.26,
  "agent_provision_blocked": true,
  "note": "Address is BIP39 test vector abandon\u2026about \u2014 not a funded Vida owner wallet. Proves provision \u2192 status \u2192 System.Account balance path on Finney."
}
```

## Not claimed

- This address is the public BIP39 test mnemonic — **do not send real funds**
- No staking / transfer extrinsics (Phase 1B)
- Not a production owner wallet proof (that uses your real seed offline)

## Re-run

```bash
kaspa-suite/venv/bin/python scripts/tao_balance_proof.py
```
