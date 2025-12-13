#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

for base in "index.tsx" "items.tsx" "add.tsx" "marketplace.tsx"; do
  target="app/(tabs)/$base"
  echo
  echo "=============================="
  echo "Tab file: $target"
  echo "=============================="

  if [ ! -f "$target" ]; then
    echo "  (no current file, skipping)"
    continue
  fi

  baks=$(ls -1 "$target".bak.* 2>/dev/null || true)
  if [ -z "$baks" ]; then
    echo "  (no backups found)"
    continue
  fi

  for bak in $baks; do
    # Quick compare
    if diff -q "$target" "$bak" >/dev/null 2>&1; then
      echo "  IDENTICAL: $bak"
    else
      echo "  DIFFERS  : $bak"
    fi
  done
done
