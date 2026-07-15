# TAO P2P + Yield Optimizer

**When:** 2026-07-13T13:59:18Z

## Kaspa parity (autonomy)
- Kaspa: agent session spends KAS without password under caps
- TAO: agent session stakes/transfers without password under caps (proven)

## Yield optimizer (plan on Finney)
```json
{
  "ok": true,
  "action": "stake",
  "free_tao": "0.0267599",
  "stake_amount": "0.0167599",
  "target_uid": 52,
  "target_hotkey": "5D1saVvssckE1XoPwPzdHrqYZtvBJ3vESsrPNxZ4zAxbKGs1",
  "reason": "stake 0.0167599 TAO to uid 52 (score 2527747185)"
}
```
Top candidates (truncated):
```json
[
  {
    "uid": 52,
    "hotkey": "5D1saVvssckE1XoPwPzdHrqYZtvBJ3vESsrPNxZ4zAxbKGs1",
    "emission": 2527747185,
    "validator_permit": true,
    "score": 2527747185.0
  },
  {
    "uid": 26,
    "hotkey": "5Ev5mQXPh6Ch22MmTQMTrZjj7a1atSSE5i8z8USZAW8Pnh9s",
    "emission": 2369656962,
    "validator_permit": true,
    "score": 2369656962.0
  },
  {
    "uid": 58,
    "hotkey": "5CsvRJXuR955WojnGMdok1hbhffZyB4N5ocrv82f3p5A2zVp",
    "emission": 603735649,
    "validator_permit": true,
    "score": 603735649.0
  }
]
```

## P2P payment (live)
- From: `5CFfynEhaVb71fbJAaoQ75FeE1R2yrVnj6NbEdYUx9bf3QMJ`
- To: `5Dtq8ZDhqtGuovQ8C6vCVXmgi6WQ4EGHo5AFXkKNYmPL1zSW`
- Amount: 0.005 TAO
- Result: `{"ok": true, "extrinsic_hash": "0xa0915ab92d83c170ce5d759f22d97ba1413fc54cc3700e2503137ca5011251ee", "action": "transfer", "dest": "5Dtq8ZDhqtGuovQ8C6vCVXmgi6WQ4EGHo5AFXkKNYmPL1zSW", "amount_tao": "0.005", "keep_alive": true, "endpoint": "wss://entrypoint-finney.opentensor.ai:443", "call": "Balances.transfer_keep_alive", "unlock_via": "session"}`

## Disclaimer
Optimizer uses emission/permit heuristics — not guaranteed APY.
**This proof documents plan-on-Finney + live P2P.** Optimize **execute** is code-path + session-gated; not claimed as a separate live receipt here.
