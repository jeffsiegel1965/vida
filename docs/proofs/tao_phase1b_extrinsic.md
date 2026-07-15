# TAO Phase 1B — Live extrinsic proof

**When:** 2026-07-13T13:49:38Z  
**Network:** Finney (Bittensor mainnet)  
**Status:** **LIVE SUCCESS**

## Wallet
- Coldkey: `5CFfynEhaVb71fbJAaoQ75FeE1R2yrVnj6NbEdYUx9bf3QMJ`
- Action: `SubtensorModule.add_stake`
- Netuid: `1`
- Amount: `0.05` TAO
- Validator hotkey: `5Dsdf6vRMYSv8odiVPGgN86VN4WmrSjpSAHZAYC8Z3Zy4QK6` (subnet 1 uid 0)

## Extrinsic hash
```
0xdc2cd82212b0d2e8ed35ec9d4004697e5ebe60257dccffd04a0e16cf119c62c0
```

## Post-stake free balance (node read)
- free_tao: `0.04837995`
- reserved_tao: `0`
- block ~ `8612900`

## What this proves
1. Owner-provisioned Vida TAO wallet can unlock coldkey offline
2. Policy path + confirm can submit a real Finney extrinsic
3. `add_stake(hotkey, netuid, amount_staked)` works on current runtime

## Explorer
Search the hash or address on https://taostats.io

## Notes
- Seed stays on server in `data/tao_live_e2e/` (0600), not in this doc
- This is a tiny test stake, not an investment recommendation
