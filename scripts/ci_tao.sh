#!/usr/bin/env bash
# Local CI for TAO plugin + Kaspa secure suites. Exit non-zero on any failure.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -n "${VIDA_PYTHON:-}" && -x "${VIDA_PYTHON}" ]]; then
  PY="${VIDA_PYTHON}"
elif [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  PY="${VIRTUAL_ENV}/bin/python"
else
  PY=python3
fi

echo "Using: $PY"
echo "=== Kaspa secure ==="
"$PY" tests/qa_secure_tests.py
echo "=== Kaspa core ==="
"$PY" tests/qa_tests.py
echo "=== TAO unit suites ==="
for t in \
  tests/test_tao_session.py \
  tests/test_tao_stake.py \
  tests/test_tao_p2p_optimizer.py \
  tests/test_tao_robustness.py \
  tests/test_tao_balance.py \
  tests/test_tao_derive.py \
  tests/test_tao_infra.py \
  tests/test_tao_pq.py \
  tests/test_plugins_phase0.py \
  tests/test_covenant_scaffold.py
do
  echo "--- $t ---"
  "$PY" "$t"
done
echo "ALL GREEN"
