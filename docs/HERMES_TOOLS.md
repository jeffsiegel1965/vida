# Hermes / agent tool surface — Vida

**Not standalone:** Vida is the wallet rail Hermes (or OpenClaw) drives.  
You choose **COMMAND / HYBRID / FULL** + caps — from “I approve every move” to full agentic use inside limits.  
See [HERMES_INTEGRATION.md](HERMES_INTEGRATION.md).


## Product rule

| Tool | Needs session? | confirm? | Password arg? |
|------|----------------|----------|---------------|
| `vida_tao_status` | No | No | **Never** |
| `vida_tao_balance` | No | No | **Never** |
| `vida_tao_delegate` | **Yes** | **Yes** | **Never** |
| `vida_tao_undelegate` | **Yes** | **Yes** | **Never** |
| `vida_tao_transfer` | **Yes** | **Yes** | **Never** |
| `vida_tao_optimize (emission-aware auto-stake plan/execute)` (plan) | No | No | **Never** |
| `vida_tao_optimize` (execute) | **Yes** | **Yes** | **Never** |

Password unlock is **owner scripts only** (`grant_*`, `provision_*`).  
Agent chat must not receive passwords or seeds.

## Setup (owner)

```bash
# Kaspa
python scripts/setup_owner_wallet.py
python scripts/grant_session.py --hours 8 --max-per-tx 5 --max-per-day 20 \
  --dest kaspa:qq...

# TAO
python scripts/provision_tao_account.py   # owner mnemonic path
python scripts/grant_tao_session.py --wallet-id my-tao \
  --hours 8 --max-per-tx 0.05 --max-per-day 0.1 --subnets 1
export VIDA_TAO_SESSION=/path/to/tao_agent_session.json

# Optional hygiene
python scripts/wipe_plaintext_secrets.py --dir data/tao_live_e2e
```

## Agent env

```bash
export VIDA_TAO_SESSION=...
# Kaspa: agent uses SecureVida(..., _session_file=agent_session.json)
# and VidaTransactor.send(..., confirm=True)
```

## Python import

```python
from vida.plugins.tao.tools import (
    HERMES_TOOLS,
    vida_tao_status,
    vida_tao_balance,
    vida_tao_delegate,
    vida_tao_transfer,
    vida_tao_optimize,
)
```

## Status dashboard

```bash
python scripts/vida_status.py --tao-wallet live-e2e
```

## Security notes

See `docs/SECURITY_HARDENING.md` and `docs/COMPETITIVE_POSITION.md`.
