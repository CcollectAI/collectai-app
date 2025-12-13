#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

TABS_DIR="app/(tabs)"
INDEX_FILE="$TABS_DIR/index.tsx"
PORTFOLIO_IMPL="$TABS_DIR/portfolio_impl.tsx"
PORTFOLIO_WRAPPER="$TABS_DIR/portfolio.tsx"
ARCHIVE_DIR="$TABS_DIR/__archived__"

echo "=== Step 1: Restore original portfolio implementation from backup ==="

LATEST_BACKUP="$(ls -1t "$TABS_DIR"/index.tsx.bak_portfolio_robinhood_* 2>/dev/null | head -n 1 || true)"

if [ -z "$LATEST_BACKUP" ]; then
  echo "❌ Could not find any index.tsx.bak_portfolio_robinhood_* backup."
  echo "   Skipping restore; your current index.tsx will not be modified."
else
  if [ -f "$PORTFOLIO_IMPL" ]; then
    BAK_IMPL="${PORTFOLIO_IMPL}.bak_before_restore_$(date +%Y%m%d-%H%M%S)"
    mv "$PORTFOLIO_IMPL" "$BAK_IMPL"
    echo "📦 Existing $PORTFOLIO_IMPL moved to:"
    echo "   $BAK_IMPL"
  fi

  cp "$LATEST_BACKUP" "$PORTFOLIO_IMPL"
  echo "✅ Restored portfolio implementation from:"
  echo "   $LATEST_BACKUP"
  echo "   -> $PORTFOLIO_IMPL"
fi

echo
echo "=== Step 2: Update portfolio.tsx to import from ./portfolio_impl instead of ./index ==="

if [ -f "$PORTFOLIO_WRAPPER" ]; then
  WRAPPER_BAK="${PORTFOLIO_WRAPPER}.bak_portfolio_import_$(date +%Y%m%d-%H%M%S)"
  cp "$PORTFOLIO_WRAPPER" "$WRAPPER_BAK"
  echo "📦 Backed up portfolio wrapper to:"
  echo "   $WRAPPER_BAK"

  python3 <<PYCODE
from pathlib import Path

wrapper = Path("$PORTFOLIO_WRAPPER")
text = wrapper.read_text(encoding="utf-8")

original_text = text

text = text.replace('./index"', './portfolio_impl"')
text = text.replace("./index'", "./portfolio_impl'")

if text != original_text:
    wrapper.write_text(text, encoding="utf-8")
    print("✅ Updated imports in", wrapper)
else:
    print("ℹ️ No './index' import string found in", wrapper)
PYCODE
else
  echo "⚠️ $PORTFOLIO_WRAPPER not found; cannot update import."
fi

echo
echo "=== Step 3: Archive app/(tabs)/index.tsx so it no longer exists as a route ==="

mkdir -p "$ARCHIVE_DIR"

if [ -f "$INDEX_FILE" ]; then
  ARCHIVED="$ARCHIVE_DIR/index.tsx.orphan_$(date +%Y%m%d-%H%M%S)"
  mv "$INDEX_FILE" "$ARCHIVED"
  echo "🔒 Moved stray $INDEX_FILE -> $ARCHIVED"
else
  echo "ℹ️ No $INDEX_FILE present (already archived)."
fi

echo
echo "Files now under app/(tabs):"
ls -1 "$TABS_DIR"

echo
echo "✅ Original portfolio implementation restored as portfolio_impl.tsx,"
echo "   portfolio.tsx points to it, and index.tsx is archived (no stray index tab)."
