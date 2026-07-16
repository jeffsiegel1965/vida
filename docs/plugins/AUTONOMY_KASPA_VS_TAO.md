# Vida autonomy: Kaspa vs TAO

**Not standalone.** Hermes (or another local agent) is the control plane.  
Vida is the wallet. You dial autonomy from **owner-only** → **COMMAND** → **HYBRID** → **FULL agentic** (still capped; seed never to the agent).

See [HERMES_INTEGRATION.md](../HERMES_INTEGRATION.md) · [PRODUCT.md](../PRODUCT.md).

**Architecture:** Kaspa = Vida core. TAO = Vida **plugin rail** (not a second product).


## Confirmed — same model

| Feature | Kaspa | TAO |
|---------|-------|-----|
| You hold the seed | Yes | Yes |
| Owner password never given to agent | Yes | Yes |
| Time-boxed session file (0600) | Yes | Yes |
| Agent acts without password during session | Yes (spend KAS) | Yes (stake + **transfer TAO**) |
| FULL / HYBRID / COMMAND style limits | Yes | Yes |
| Caps per tx / per day | Yes | Yes |
| Revoke kills access | Yes | Yes |
| Mainnet proven | Yes (KAS sends) | Yes (stake + P2P transfer) |

## TAO as peer-to-peer AI currency

Agent can **pay** another address in TAO via `transfer` under session policy:

- Call: `Balances.transfer_keep_alive`
- Unlock: session (no password)
- Live hash example: see `docs/proofs/tao_p2p_and_optimizer.md`

That is the P2P currency rail for agents (pay for inference, tools, services).

## Yield optimizer (MVP)

- Scores validators on a subnet (emission + permit heuristic)
- Plans: keep reserve free, stake rest to top scorer
- Optional execute via existing `delegate` + session
- **Not** guaranteed APY

## What is still stronger on Kaspa today

- Longer battle-tested wallet UX + PQ identity on Kaspa path
- Transactor / mainnet receipt culture more mature in docs

TAO is now **capability-parity for agent money + stake**, not a full portfolio product.
