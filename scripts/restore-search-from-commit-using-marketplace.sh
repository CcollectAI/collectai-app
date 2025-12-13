#!/usr/bin/env bash
set -euo pipefail

COMMIT="497c2396b924d0a6fe19abb53f8ba75414540b17"
OUT="app/(tabs)/search.tsx"
SRC="app/(tabs)/marketplace.tsx"

if [ ! -d ".git" ]; then
  echo "ERROR: .git missing (not a git repo)"
  exit 1
fi
if [ ! -f "$OUT" ]; then
  echo "ERROR: $OUT not found"
  exit 1
fi

# verify the source exists in that commit
git cat-file -e "${COMMIT}:${SRC}" 2>/dev/null || {
  echo "ERROR: ${SRC} not found in commit ${COMMIT}"
  exit 1
}

TS="$(date +%Y%m%d_%H%M%S)"
cp "$OUT" "${OUT}.pre_restore_${TS}"

echo "Restoring Search from ${COMMIT}:${SRC} -> ${OUT}"
git show "${COMMIT}:${SRC}" > "$OUT"

echo "OK: restored ${OUT}"
echo "Backup kept at: ${OUT}.pre_restore_${TS}"
