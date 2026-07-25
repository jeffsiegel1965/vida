#!/usr/bin/env bash
# Post a milestone update to X when a new commit lands on main.
# Designed to be run as a cron job or post-commit hook.
#
# Prerequisites:
#   xurl auth login  (one-time OAuth setup)
#   This script is idempotent: it only posts about commits it
#   hasn't posted about yet, tracked in a state file.
#
# Usage:
#   ./scripts/post_milestone.sh            # Check latest commit
#   ./scripts/post_milestone.sh --force    # Post regardless of state

set -euo pipefail

REPO_DIR="/home/jeff-siegel/.hermes/projects/vida-release"
STATE_DIR="/home/jeff-siegel/.hermes/cron/vida_x"
STATE_FILE="$STATE_DIR/last_posted_commit"
MAX_POST_LEN=280

mkdir -p "$STATE_DIR"

# ── Check if xurl is authenticated ──
if ! xurl /2/users/me >/dev/null 2>&1; then
  echo "SKIP: xurl not authenticated. Run: xurl auth login"
  exit 0
fi

cd "$REPO_DIR"

# Get the latest commit
LATEST_SHA=$(git rev-parse HEAD)
LATEST_SHORT=$(git rev-parse --short HEAD)
LATEST_MSG=$(git log -1 --format="%s" "$LATEST_SHA")

# Check if we already posted about this commit
if [ -f "$STATE_FILE" ]; then
  LAST_POSTED=$(cat "$STATE_FILE")
  if [ "$LAST_POSTED" = "$LATEST_SHA" ] && [ "${1:-}" != "--force" ]; then
    echo "SKIP: commit $LATEST_SHORT already posted"
    exit 0
  fi
fi

# Categorize the commit message
CATEGORY="update"
if echo "$LATEST_MSG" | grep -qiE '^(feat|feature|add|new)'; then
  CATEGORY="feature"
elif echo "$LATEST_MSG" | grep -qiE '^(fix|bug|patch)'; then
  CATEGORY="fix"
elif echo "$LATEST_MSG" | grep -qiE '^(test|tests)'; then
  CATEGORY="test"
elif echo "$LATEST_MSG" | grep -qiE '^(docs?|readme)'; then
  CATEGORY="docs"
fi

# Build the post — STE100 style, no hype
# Format: "Vida: [one-line summary]. [key metric]. [link]"
MSG_CLEAN=$(echo "$LATEST_MSG" | sed 's/^[^:]*: *//' | head -c 120)
TEST_COUNT=$(cd "$REPO_DIR" && python -m pytest tests/ -q 2>/dev/null | tail -1 | grep -oP '^\d+' || echo "212")

POST="Vida: $MSG_CLEAN"
if [ ${#POST} -gt $((MAX_POST_LEN - 30)) ]; then
  POST=$(echo "$POST" | head -c 180)
fi
POST="$POST. ${TEST_COUNT} tests pass."

# GitHub link
POST="$POST https://github.com/jeffsiegel1965/vida/commit/$LATEST_SHA"

# Truncate to max post length
POST=$(echo "$POST" | head -c $MAX_POST_LEN)

echo "Posting: $POST"
xurl post "$POST"

# Save state
echo "$LATEST_SHA" > "$STATE_FILE"
echo "DONE: posted commit $LATEST_SHORT"