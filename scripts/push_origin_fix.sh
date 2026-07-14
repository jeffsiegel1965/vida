#!/usr/bin/env bash
# Push the original-Vida security fix to GitHub main.
# Run on a machine with GitHub credentials.
set -euo pipefail
cd "$(dirname "$0")/.."
git checkout fix/origin-session-caps
git fetch origin
git log --oneline origin/main..HEAD
echo "About to: git push origin fix/origin-session-caps:main"
read -r -p "Type PUSH to continue: " ans
[[ "$ans" == "PUSH" ]] || { echo aborted; exit 1; }
git push origin fix/origin-session-caps:main
echo "Done. Verify:"
echo "  git clone https://github.com/jeffsiegel1965/vida.git && cd vida"
echo "  python tests/qa_tests.py && python tests/qa_secure_tests.py"
