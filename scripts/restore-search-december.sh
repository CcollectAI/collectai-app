#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/search.tsx"

if [ ! -f "$FILE" ]; then
  echo "ERROR: $FILE not found"
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
cp "$FILE" "${FILE}.pre_restore_${TS}"

# Prefer the Dec 13 17:11 backup (you listed it)
if [ -f "app/(tabs)/search.tsx.bak.20251213_171154" ]; then
  cp "app/(tabs)/search.tsx.bak.20251213_171154" "$FILE"
  echo "OK: restored Search from search.tsx.bak.20251213_171154"
elif [ -f "app/(tabs)/search.tsx.bak_20251213_145358" ]; then
  cp "app/(tabs)/search.tsx.bak_20251213_145358" "$FILE"
  echo "OK: restored Search from search.tsx.bak_20251213_145358"
else
  echo "ERROR: No December search backup found."
  exit 1
fi

echo "Backup kept at: ${FILE}.pre_restore_${TS}"
