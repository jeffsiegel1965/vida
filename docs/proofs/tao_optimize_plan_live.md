# TAO yield optimizer — live **plan** (Finney)

**When:** 2026-07-14  
**Network:** Finney  
**Wallet:** `live-e2e` / `5CFfynEhaVb71fbJAaoQ75FeE1R2yrVnj6NbEdYUx9bf3QMJ`  
**Method:** `TaoPlugin.optimize_yield(..., execute=False)` via official Finney WSS

## Result

```json
{
  "ok": true,
  "action": "stake",
  "free_tao": "0.021589861",
  "reserve_tao": "0.01",
  "stake_amount": "0.011589861",
  "target_uid": 52,
  "target_hotkey": "5D1saVvssckE1XoPwPzdHrqYZtvBJ3vESsrPNxZ4zAxbKGs1",
  "reason": "stake 0.011589861 TAO to uid 52 (score 2560424068)",
  "balance_ok": true,
  "executed": false
}
```

Top candidate: uid 52, `validator_permit: true`, emission-based score.

## What this proves

1. Live `System.Account` balance path for the demo wallet  
2. Live `SubtensorModule` emission/permit/keys scoring on netuid 1  
3. Plan math: stake ≈ free − reserve when free > reserve + min_stake  

## What this does **not** prove

- Optimize **execute** (on-chain `add_stake` via optimizer) — needs owner password or agent session with spend material. Password/mnemonic files were wiped from `data/tao_live_e2e/` (correct hygiene). Use `scripts/tao_optimize_execute_proof.py` when unlock is available.

## Disclaimer

Emission/permit scoring is a **heuristic**, not guaranteed yield or APY.
