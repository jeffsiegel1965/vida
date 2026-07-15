# TAO agent session — live proof

**When:** 2026-07-13  
**Network:** Finney  

## What happened

1. Owner granted a 24h FULL session (password used only at grant time)
2. Agent path staked **0.02 TAO** with **no password** (`unlock_via: session`)
3. Caps: max 0.03/tx, 0.05/day, subnet 1 only

## Extrinsic
```
0x44c9b9a5c61fcd5998b8b0012568d4db5bdfbd98d7f9c2d73b02c9df7ca39a87
```

## Balances
- Before session stake free ≈ `0.04838` TAO  
- After free ≈ `0.02676` TAO  

## Address
`5CFfynEhaVb71fbJAaoQ75FeE1R2yrVnj6NbEdYUx9bf3QMJ`

## Tests
`tests/test_tao_session.py` — 5/5 OK (grant, stake without password, subnet cap, revoke, expiry burn, tamper AAD)

## Owner controls
- Grant: `scripts/grant_tao_session.py`
- Revoke: `scripts/grant_tao_session.py --revoke`
- Env for agent: `VIDA_TAO_SESSION=/path/to/agent_session.json`
