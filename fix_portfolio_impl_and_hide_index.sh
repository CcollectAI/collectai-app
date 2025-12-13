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
  echo "❌ No index.tsx.bak_portfolio_robinhood_* backup found under $TABS_DIR."
  echo "   Cannot restore original portfolio implementation automatically."
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
echo "=== Step 2: Point portfolio.tsx at ./portfolio_impl instead of ./index ==="

if [ -f "$PORTFOLIO_WRAPPER" ]; then
  WRAPPER_BAK="${PORTFOLIO_WRAPPER}.bak_portfolio_import_$(date +%Y%m%d-%H%M%S)"
  cp "$PORTFOLIO_WRAPPER" "$WRAPPER_BAK"
  echo "📦 Backed up portfolio wrapper to:"
  echo "   $WRAPPER_BAK"

  python3 <<PYCODE
from pathlib import Path

wrapper = Path("$PORTFOLIO_WRAPPER")
text = wrapper.read_text(encoding="utf-8")
orig = text

text = text.replace('./index"', './portfolio_impl"')
text = text.replace("./index'", "./portfolio_impl'")

if text != orig:
    wrapper.write_text(text, encoding="utf-8")
    print("✅ Updated import in", wrapper)
else:
    print("ℹ️ No './index' import string found in", wrapper, "- nothing changed.")
PYCODE
else
  echo "⚠️ $PORTFOLIO_WRAPPER not found; cannot update import."
fi

echo
echo "=== Step 3: Move app/(tabs)/index.tsx out of the tab group (kills stray index tab) ==="

mkdir -p "$ARCHIVE_DIR"

if [ -f "$INDEX_FILE" ]; then
  ARCHIVED="$ARCHIVE_DIR/index.tsx.hidden_$(date +%Y%m%d-%H%M%S)"
  mv "$INDEX_FILE" "$ARCHIVED"
  echo "🔒 Moved $INDEX_FILE -> $ARCHIVED"
else
  echo "ℹ️ No $INDEX_FILE present (already moved or deleted)."
fi

echo
echo "Files currently under app/(tabs):"
ls -1 "$TABS_DIR"

echo
echo "✅ Portfolio now uses portfolio_impl.tsx, and index.tsx is no longer a route in (tabs),"
echo "   so the stray 'index' tab should disappear."
