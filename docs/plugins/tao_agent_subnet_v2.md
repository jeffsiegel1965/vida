# TAO Plugin — Agent Subnet Operations (v2)

## Vision
The TAO plugin becomes a full subnet-operations platform for agents, not just a wallet.

## Capabilities

| Tier | What the agent can do | Status |
|------|----------------------|--------|
| **Wallet** | Hold, send, stake, unstake TAO | ✅ Shipped |
| **Subnet scout** | Discover subnets, read emissions, score validators, plan optimize | ✅ Shipped (plan) |
| **Validator interface** | Set weights, query subnet APIs, serve inference requests | ❌ v2 |
| **Subnet participant** | Register as miner/validator, submit work, collect rewards | ❌ v2 |
| **Subnode services** | Route agent traffic through subnet-specific endpoints | ❌ v2 |

## Why this matters

The agent economy needs agents that **participate**, not just transact. A TAO agent that can:
- Query a subnet's inference API to complete tasks
- Set weights based on its own evaluation
- Register and serve work on subnets
- Earn TAO autonomously

...is an agent that generates value, not just spends it. This aligns with Vida's positioning: **"Powering the agent economy."**

## Design sketch

```python
# Agent discovers subnets
subnets = tao_list_subnets()
best = max(subnets, key=lambda s: s.emission)

# Agent queries a subnet API directly
result = tao_subnet_query(subnet_uid=best.uid, endpoint="/inference", payload={...})

# Agent sets weights based on evaluation
tao_set_weights(subnet_uid=best.uid, uids=[1,2,3], weights=[0.5, 0.3, 0.2])

# Agent serves work on a subnet
tao_register_miner(subnet_uid=best.uid, hotkey=session_hotkey)
tao_serve(subnet_uid=best.uid, endpoint="/serve", model="...")
```

All operations are session-gated — agent never sees the seed.

## Blockers

1. Subnet API discovery — each subnet has its own API shape. Need a registry or convention.
2. Weight setting requires hotkey registration — agent would need a session-level hotkey.
3. Inference serving requires uptime — background process pattern.

## Priority

Post-MVP. Ship the covenant module first. TAO v2 is the next growth lever.