#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

TABS_DIR="app/(tabs)"
ARCHIVE_DIR="$TABS_DIR/__archived__"
PORTFOLIO_FILE="$TABS_DIR/portfolio.tsx"

echo "=== Restoring app/(tabs)/portfolio.tsx so /portfolio route works again ==="

if [ ! -d "$ARCHIVE_DIR" ]; then
  echo "❌ Archive dir not found:"
  echo "   $ARCHIVE_DIR"
  echo "   Cannot restore portfolio wrapper automatically."
  exit 1
fi

LATEST_PORTFOLIO="$(ls -1t "$ARCHIVE_DIR"/portfolio.tsx.hidden_* 2>/dev/null | head -n 1 || true)"

if [ -z "$LATEST_PORTFOLIO" ]; then
  echo "❌ No portfolio.tsx.hidden_* backup found under:"
  echo "   $ARCHIVE_DIR"
  echo "   Cannot restore automatically."
  exit 1
fi

if [ -f "$PORTFOLIO_FILE" ]; then
  BAK="${PORTFOLIO_FILE}.bak_before_restore_$(date +%Y%m%d-%H%M%S)"
  mv "$PORTFOLIO_FILE" "$BAK"
  echo "📦 Existing $PORTFOLIO_FILE moved to:"
  echo "   $BAK"
fi

mv "$LATEST_PORTFOLIO" "$PORTFOLIO_FILE"

echo "✅ Restored:"
echo "   $LATEST_PORTFOLIO"
echo "   -> $PORTFOLIO_FILE"

echo
echo "Files now under app/(tabs):"
ls -1 "$TABS_DIR"
