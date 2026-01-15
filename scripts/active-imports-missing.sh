#!/usr/bin/env bash
set -euo pipefail

echo "== Checking ACTIVE @/ imports resolve to src/* =="

# Extract @/import targets from ACTIVE routes (no shelf/backups)
mapfile -t mods < <(
  rg -n "from ['\"]@/|import\(['\"]@/" app \
    -g'*.tsx' \
    -g'!app/_shelf/**' \
    -g'!**/*.disabled*' \
    -g'!**/*.broken*' \
    -g'!**/*.pre_*' \
  | sed -nE "s/.*@\/([^'\")]+).*/\1/p" \
  | sort -u
)

missing=0
for m in "${mods[@]}"; do
  base="src/$m"
  ok=0
  for cand in \
    "${base}.ts" "${base}.tsx" \
    "${base}/index.ts" "${base}/index.tsx"
  do
    if [ -f "$cand" ]; then ok=1; break; fi
  done
  if [ "$ok" -eq 0 ]; then
    echo "MISSING: @/$m   (expected src/$m.(ts|tsx) or src/$m/index.(ts|tsx))"
    missing=$((missing+1))
  fi
done

echo "== Done. Missing count: $missing =="
exit 0
