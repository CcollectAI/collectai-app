#!/usr/bin/env bash
set -euo pipefail

# Find likely search files
CANDIDATES=( "search.tsx" "chat.tsx" "marketplace.tsx" )

found=""
for f in "${CANDIDATES[@]}"; do
  if [ -f "app/(tabs)/$f" ]; then
    found="$f"
    break
  fi
done

if [ -z "$found" ]; then
  echo "No obvious Search file found (search.tsx/chat.tsx/marketplace.tsx)."
  echo "Run: ls -lah app/(tabs) and tell me which file is your Search screen."
  exit 0
fi

TS="$(date +%Y%m%d_%H%M%S)"
cp "app/(tabs)/$found" "app/(tabs)/$found.pre_restore_${TS}"

BAK="$(ls -1t app/\(tabs\)/${found}.bak_20251212_* 2>/dev/null | head -n 1 || true)"
if [ -z "$BAK" ]; then
  echo "No 20251212 backup found for $found"
  exit 0
fi

echo "Restoring $found from: $BAK"
cp "$BAK" "app/(tabs)/$found"
echo "OK: restored $found (backup kept at $found.pre_restore_${TS})"
