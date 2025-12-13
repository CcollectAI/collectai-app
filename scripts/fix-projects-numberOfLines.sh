#!/usr/bin/env bash
set -euo pipefail

FILE="app/projects.tsx"

if [ ! -f "$FILE" ]; then
  echo "projects.tsx not found at $FILE"
  exit 1
fi

cp "$FILE" "${FILE}.bak.numberOfLines-$(date +%s)" || true

# Replace the invalid JSX prop "numberOfLines: {1}" with "numberOfLines={1}"
perl -pi -e 's/numberOfLines:\s*\{1\}/numberOfLines={1}/g' "$FILE"

echo "Patched $FILE (numberOfLines prop syntax fixed). Backup created."
