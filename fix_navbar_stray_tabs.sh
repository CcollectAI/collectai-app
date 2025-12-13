#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

TABS_DIR="app/(tabs)"
ARCHIVE_DIR="$TABS_DIR/__archived__"

echo "=== Cleaning stray tab files (index/search) in $TABS_DIR ==="

mkdir -p "$ARCHIVE_DIR"

for fname in "index.tsx" "search.tsx"; do
  SRC="$TABS_DIR/$fname"
  if [ -f "$SRC" ]; then
    DEST="$ARCHIVE_DIR/${fname}.bak_stray_$(date +%Y%m%d-%H%M%S)"
    mv "$SRC" "$DEST"
    echo "  🔄 Moved stray $SRC -> $DEST"
  else
    echo "  ✓ No $SRC, nothing to move."
  fi
done

echo
echo "Remaining files in (tabs) directory:"
ls -1 "$TABS_DIR"

echo
echo "✅ Stray tab files archived. Only explicitly declared tabs in _layout.tsx should now appear."
