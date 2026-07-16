#!/usr/bin/env bash
# Wrapper: run kascov-lab against testnet-10 when the binary exists.
# Does NOT invent keys or print secrets. Key file: /tmp/kascov-lab-key.hex (0600).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# kascov-lab binary. Set VIDA_KASCOV_LAB to your local path.
LAB="${VIDA_KASCOV_LAB:-}"
KEY="${VIDA_KASCOV_KEY:-/tmp/kascov-lab-key.hex}"

cmd="${1:-help}"
shift || true

if [[ -z "$LAB" || ! -x "$LAB" ]]; then
  echo "kascov-lab not configured. Set VIDA_KASCOV_LAB=/path/to/kascov-lab"
  echo "Proof already recorded: docs/proofs/covenant_tn10_microproof.md"
  exit 2
fi

if [[ ! -f "$KEY" ]]; then
  echo "Key file missing: $KEY (generate or set VIDA_KASCOV_KEY)"
  exit 2
fi

case "$cmd" in
  help)
    echo "Usage: covenant_tn10_lab.sh <demo|fund|spend> [args]"
    echo ""
    echo "Commands:"
    echo "  demo [transitions=1]   Run genesis→N→burn lifecycle"
    echo "  fund                   Fund agent pot (delegates to JS helper)"
    echo "  spend                  Spend from agent pot (delegates to JS helper)"
    echo ""
    echo "Set VIDA_KASCOV_LAB to your kascov-lab binary path."
    echo "Set VIDA_KASCOV_KEY to your test key path."
    ;;
  demo)
    transitions="${1:-1}"
    exec "$LAB" demo --transitions "$transitions"
    ;;
  fund|spend)
    echo "Use the Python plugin via scripts/covenant_fund_agent_pot.js"
    echo "  node scripts/covenant_fund_agent_pot.js '<json>'"
    ;;
  *)
    exec "$LAB" "$cmd" "$@"
    ;;
esac