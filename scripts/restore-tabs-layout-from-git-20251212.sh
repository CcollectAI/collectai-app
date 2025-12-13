#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/_layout.tsx"

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

COMMIT="$(git rev-list -n 1 --before="2025-12-12 00:00:00 +0100" HEAD || true)"
if [ -z "$COMMIT" ]; then
  echo "ERROR: Could not find a commit before 2025-12-12 00:00 (+0100)."
  exit 1
fi

echo "Using commit: $COMMIT"
echo "Restoring $FILE from that commit..."

git checkout "$COMMIT" -- "$FILE"

echo "OK: Restored $FILE from git commit $COMMIT"
echo "Backup kept at: ${FILE}.pre_git_restore_${TS}"
