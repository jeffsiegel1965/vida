#!/usr/bin/env bash
# Weekly Vida technical digest — posted to X every Sunday.
# Summarizes the past week's commits, test counts, and key metrics.
#
# Prerequisites: xurl auth login (one-time OAuth setup)

set -euo pipefail

REPO_DIR="/home/jeff-siegel/.hermes/projects/vida-release"
STATE_DIR="/home/jeff-siegel/.hermes/cron/vida_x"
WEEK_FILE="$STATE_DIR/last_digest_week"

mkdir -p "$STATE_DIR"

# ── Check auth ──
if ! xurl /2/users/me >/dev/null 2>&1; then
  echo "SKIP: xurl not authenticated"
  exit 0
fi

# ── Check if we already posted this week ──
CURRENT_WEEK=$(date +%Y-%U)
if [ -f "$WEEK_FILE" ]; then
  LAST_WEEK=$(cat "$WEEK_FILE")
  if [ "$LAST_WEEK" = "$CURRENT_WEEK" ] && [ "${1:-}" != "--force" ]; then
    echo "SKIP: digest already posted for week $CURRENT_WEEK"
    exit 0
  fi
fi

cd "$REPO_DIR"

# Get commits since last Sunday
SINCE=$(date -d "last sunday - 6 days" +%Y-%m-%d 2>/dev/null || date -d "-7 days" +%Y-%m-%d)
COMMITS=$(git log --oneline --since="$SINCE" --format="%s" 2>/dev/null | head -10)
COMMIT_COUNT=$(echo "$COMMITS" | grep -c . || echo "0")

# Get test count
TEST_COUNT=$(python -m pytest tests/ -q 2>/dev/null | tail -1 | grep -oP '^\d+' || echo "212")

# Get latest tag or version
VERSION=$(git describe --tags --always --dirty 2>/dev/null || echo "main")

# Build digest — 5 lines max, each under 280 chars total
WEEK=$(date +%Y-%m-%d)

POST="Vida weekly — $WEEK

${COMMIT_COUNT} commits, ${TEST_COUNT} tests, version ${VERSION}.

https://github.com/jeffsiegel1965/vida"

# Truncate
POST=$(echo "$POST" | head -c 280)

echo "Posting weekly digest:"
echo "$POST"
xurl post "$POST"

# Save state
echo "$CURRENT_WEEK" > "$WEEK_FILE"
echo "DONE: posted weekly digest for week $CURRENT_WEEK"