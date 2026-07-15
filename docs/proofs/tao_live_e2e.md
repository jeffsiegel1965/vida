# TAO Live E2E

**When:** 2026-07-13T13:49:07Z
**Network:** finney
**Address:** `5CFfynEhaVb71fbJAaoQ75FeE1R2yrVnj6NbEdYUx9bf3QMJ`
**Free TAO:** 0.1

## Steps

```json
[
  {
    "step": "health",
    "ok": true,
    "endpoint": "wss://entrypoint-finney.opentensor.ai:443",
    "chain": "Bittensor",
    "block": 8612898,
    "error": null
  },
  {
    "step": "mnemonic",
    "ok": true,
    "source": "reuse_file",
    "path": "<repo>/data/tao_live_e2e/[redacted local path — never commit]"
  },
  {
    "step": "provision",
    "ok": true,
    "ss58_address": "5CFfynEhaVb71fbJAaoQ75FeE1R2yrVnj6NbEdYUx9bf3QMJ",
    "hotkey_ss58": "5EqwA6gzcmmwMTnbkaKXkdXQkov8gj4fyanDyfAzVuXUswhZ",
    "error": null
  },
  {
    "step": "agent_provision_blocked",
    "ok": true,
    "error": "agent path blocked \u2014 owner must run scripts/provision_tao_account.py or TaoPlugin.owner_provision(...)"
  },
  {
    "step": "balance",
    "ok": true,
    "ss58_address": "5CFfynEhaVb71fbJAaoQ75FeE1R2yrVnj6NbEdYUx9bf3QMJ",
    "free_tao": "0.1",
    "reserved_tao": "0",
    "block": 8612898,
    "error": null
  },
  {
    "step": "stake",
    "ok": true,
    "extrinsic_hash": "0xdc2cd82212b0d2e8ed35ec9d4004697e5ebe60257dccffd04a0e16cf119c62c0",
    "action": "delegate",
    "netuid": 1,
    "amount_tao": "0.05",
    "hotkey": "5Dsdf6vRMYSv8odiVPGgN86VN4WmrSjpSAHZAYC8Z3Zy4QK6",
    "call": "SubtensorModule.add_stake"
  }
]
```

## Stake

Attempted: `{'ok': True, 'extrinsic_hash': '0xdc2cd82212b0d2e8ed35ec9d4004697e5ebe60257dccffd04a0e16cf119c62c0', 'action': 'delegate', 'netuid': 1, 'amount_tao': '0.05', 'hotkey': '5Dsdf6vRMYSv8odiVPGgN86VN4WmrSjpSAHZAYC8Z3Zy4QK6', 'endpoint': 'wss://entrypoint-finney.opentensor.ai:443', 'call': 'SubtensorModule.add_stake'}`

Mnemonic is **not** in this proof (stays in 0600 workdir file).
