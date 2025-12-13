#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/search.tsx"

if [ ! -d ".git" ]; then
  echo "ERROR: This folder is not a git repo (.git missing)."
  exit 1
fi

if [ ! -f "$FILE" ]; then
  echo "ERROR: $FILE not found."
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
cp "$FILE" "${FILE}.pre_git_restore_${TS}"

# Find the last commit BEFORE Dec 12, 2025 (i.e., “11/12 version” in your wording)
COMMIT="$(git rev-list -n 1 --before="2025-12-12 00:00:00 +0100" HEAD || true)"

if [ -z "$COMMIT" ]; then
  echo "ERROR: Could not find a commit before 2025-12-12 00:00 (+0100)."
  echo "Try widening the window or confirm the date you mean."
  exit 1
fi

echo "Using commit: $COMMIT"
echo "Restoring $FILE from that commit..."

git checkout "$COMMIT" -- "$FILE"

echo "OK: Restored $FILE from git commit $COMMIT"
echo "Backup kept at: ${FILE}.pre_git_restore_${TS}"

# Show a quick diff summary (non-fatal)
git --no-pager diff --stat || true
