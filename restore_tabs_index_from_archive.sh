#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

TABS_DIR="app/(tabs)"
ARCHIVE_DIR="$TABS_DIR/__archived__"

echo "=== Restoring app/(tabs)/index.tsx from archive (for PortfolioScreen import) ==="

if [ ! -d "$ARCHIVE_DIR" ]; then
  echo "  ❌ Archive directory not found:"
  echo "     $ARCHIVE_DIR"
  echo "  Nothing to restore."
  exit 1
fi

LATEST_INDEX="$(ls -1t "$ARCHIVE_DIR"/index.tsx.bak_stray_* 2>/dev/null | head -n 1 || true)"

if [ -z "$LATEST_INDEX" ]; then
  echo "  ❌ No archived index.tsx.bak_stray_* found in:"
  echo "     $ARCHIVE_DIR"
  echo "  Cannot restore; you'll need to show me app/(tabs)/portfolio.tsx later so we can inline it."
  exit 1
fi

TARGET="$TABS_DIR/index.tsx"

if [ -f "$TARGET" ]; then
  BAK="${TARGET}.bak_before_restore_$(date +%Y%m%d-%H%M%S)"
  mv "$TARGET" "$BAK"
  echo "  📦 Existing $TARGET moved to:"
  echo "     $BAK"
fi

cp "$LATEST_INDEX" "$TARGET"

echo "  ✅ Restored:"
echo "     $LATEST_INDEX"
echo "       -> $TARGET"

echo
echo "Files now under app/(tabs):"
ls -1 "$TABS_DIR"
