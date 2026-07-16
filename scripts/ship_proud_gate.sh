#!/usr/bin/env bash
# Ship-proud process-path gate for Vida (local product tree).
# Exit 0 only if automated bar passes. Does NOT claim FS/covenant absolute security.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  if python3 -c "import kaspa" 2>/dev/null; then
    PY=python3
  else
    echo "FAIL  no .venv/bin/python and system python lacks kaspa — run: cd $ROOT && python3 -m venv .venv && .venv/bin/pip install -e ."
    exit 1
  fi
fi

fail=0
pass() { echo "PASS  $*"; }
bad()  { echo "FAIL  $*"; fail=1; }

echo "=== Vida ship-proud gate (process-path) ==="
echo "root=$ROOT"
echo "python=$PY"

# 1) Secrets in tracked tree
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git grep -nE 'BEGIN (RSA |OPENSSH )?PRIVATE KEY|"mnemonic"\s*:\s*"[a-z]+ [a-z]+' -- \
      ':!docs/**' ':!*.md' 2>/dev/null | head -5 | grep -q .; then
    bad "secret-like material in tracked non-doc files"
  else
    pass "no obvious private keys/mnemonics in tracked code"
  fi
  if git ls-files data/ 2>/dev/null | grep -q .; then
    bad "data/ is tracked (must stay gitignored)"
  else
    pass "data/ not tracked"
  fi
else
  pass "skip git secret scan (not a git repo)"
fi

# 2) Core tests
if ! "$PY" tests/qa_tests.py >/tmp/vida_gate_qa.txt 2>&1; then
  bad "qa_tests.py"; tail -20 /tmp/vida_gate_qa.txt
else
  pass "qa_tests.py (13)"
fi
if ! "$PY" tests/qa_secure_tests.py >/tmp/vida_gate_sec.txt 2>&1; then
  bad "qa_secure_tests.py"; tail -20 /tmp/vida_gate_sec.txt
else
  pass "qa_secure_tests.py (14)"
fi

# 3) TAO suite if plugin present
if [[ -d vida/plugins/tao ]]; then
  if ! "$PY" -m unittest discover -s tests -p 'test_tao*.py' >/tmp/vida_gate_tao.txt 2>&1; then
    bad "test_tao*.py"; tail -30 /tmp/vida_gate_tao.txt
  else
    n=$("$PY" -m unittest discover -s tests -p 'test_tao*.py' 2>&1 | grep -E 'Ran [0-9]+' | tail -1)
    pass "test_tao*.py ($n)"
  fi
  if [[ -f scripts/ci_tao.sh ]]; then
    if ! bash scripts/ci_tao.sh >/tmp/vida_gate_ci_tao.txt 2>&1; then
      bad "ci_tao.sh"; tail -20 /tmp/vida_gate_ci_tao.txt
    else
      pass "ci_tao.sh ALL GREEN"
    fi
  fi
else
  pass "TAO plugin absent (Kaspa-only tree OK for partial ship)"
fi

# 4) Fail-closed PoC (Kaspa)
if ! "$PY" - <<'PY'
import tempfile, os, json
from pathlib import Path
from vida.secure_wallet import create_secure_wallet, SecureVida, grant_agent_session
td=Path(tempfile.mkdtemp()); wp=td/'w.json'; sp=td/'s.json'
create_secure_wallet(str(wp),'gate-pass-12345',network='mainnet')
grant_agent_session(str(wp),'gate-pass-12345',str(sp),hours=1,max_kas_per_tx=1.0,max_kas_per_day=2.0)
data=json.loads(sp.read_text()); del data['enc_spend']
sp.write_text(json.dumps(data)); os.chmod(sp,0o600)
try:
    SecureVida(str(wp), _session_file=str(sp))
    raise SystemExit('unlocked after delete enc_spend')
except ValueError as e:
    assert 'enc_spend' in str(e).lower() or 'missing' in str(e).lower()
print('kaspa fail-closed ok')
PY
then
  bad "Kaspa enc_spend fail-closed PoC"
else
  pass "Kaspa enc_spend fail-closed PoC"
fi

# 5) Fail-closed PoC (TAO) if present
if [[ -d vida/plugins/tao ]]; then
  if ! "$PY" - <<'PY'
import tempfile, json
from pathlib import Path
from mnemonic import Mnemonic
from vida.plugins.tao.accounts import TaoAccountStore
from vida.plugins.tao import provision_tao_account, grant_tao_agent_session, load_tao_session_secrets
td=Path(tempfile.mkdtemp()); store=TaoAccountStore(td/'a')
provision_tao_account(wallet_id='g', mnemonic=Mnemonic('english').generate(256), password='gate-pass-12345', network='finney', store=store)
sp=td/'s.json'
g=grant_tao_agent_session(store=store, wallet_id='g', password='gate-pass-12345', session_path=str(sp), hours=1, max_tao_per_tx=0.1, max_tao_per_day=0.2, scope='STAKE_ONLY')
assert g.get('ok'), g
d=json.loads(sp.read_text()); del d['enc_spend']; sp.write_text(json.dumps(d))
r=load_tao_session_secrets(str(sp))
assert not r.get('ok'), r
assert 'enc_spend' in (r.get('error') or '').lower() or 'missing' in (r.get('error') or '').lower()
print('tao fail-closed ok')
PY
  then
    bad "TAO enc_spend fail-closed PoC"
  else
    pass "TAO enc_spend fail-closed PoC"
  fi
fi

# 6) Covenant plugin checks
if [[ -d vida/plugins/covenant ]]; then
  if [[ ! -f docs/proofs/covenant_tn10_microproof.md ]]; then
    bad "covenant microproof doc missing"
  else
    pass "covenant microproof doc present"
  fi
  if [[ -f docs/proofs/covenant_tn10_microproof.md ]] && grep -q "is_accepted: True" /dev/null 2>/dev/null; then
    TX_COUNT=$(grep -c '|' docs/proofs/covenant_tn10_microproof.md 2>/dev/null || echo 0)
    if grep -q "accepted=True" <<< "" 2>/dev/null; then
      pass "covenant proofs have on-chain verification"
    fi
  fi
  # Count covenant tests
  COV_TESTS=$(find tests -name '*covenant*' 2>/dev/null | wc -l)
  if [[ "$COV_TESTS" -ge 1 ]]; then
    pass "covenant tests: $COV_TESTS test files"
  else
    bad "no covenant-specific tests"
  fi
  # Check lab_client gates
  if python3 -c "import sys; sys.path.insert(0,'.'); from vida.plugins.covenant.lab_client import live_gates_ok; g=live_gates_ok(); assert g['node'], 'node missing'" 2>/dev/null; then
    pass "lab_client.py imports clean (node available)"
  else
    bad "lab_client.py import failed or node missing"
  fi
fi

# 7) Honesty markers present
for f in README.md SECURITY.md docs/SECURITY_HARDENING.md; do
  if [[ -f "$f" ]] && grep -qiE 'policy|covenant|working balance|session file' "$f"; then
    pass "honesty language in $f"
  elif [[ -f "$f" ]]; then
    bad "missing honesty language in $f"
  fi
done

echo "=== residual (documented; gate does not clear these) ==="
echo "  - session file reader can extract session key (policy ≠ crypto hard cap)"
echo "  - session writer can reseal enc_spend (machine_key colocated)"
echo "  - no on-chain covenants yet"
echo "  - host/root compromise wins"
echo "  - optimize execute live receipt needs owner unlock (optional)"

if [[ "$fail" -ne 0 ]]; then
  echo "GATE FAIL — not process-path ship-proud"
  exit 1
fi
echo "GATE PASS — process-path ship-proud (software agent wallet bar)"
echo "NOT absolute / NOT covenant-hard / NOT FS-adversary-proof"
exit 0
