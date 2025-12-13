#!/usr/bin/env bash
set -euo pipefail

echo "=== CollectAI API wiring check ==="
echo

# Helper
check_file() {
  local path="$1"
  if [ -f "$path" ]; then
    echo "[FOUND] $path"
    echo "-------- head $path --------"
    head -n 20 "$path" || true
    echo "-----------------------------"
    echo
  else
    echo "[MISSING] $path"
    echo
  fi
}

echo "1) Checking config/api.ts..."
check_file "src/config/api.ts"

echo "2) Checking services/collectorsClient.ts..."
check_file "src/services/collectorsClient.ts"

echo "3) Checking Portfolio tab screen candidates..."
# Common locations
for path in \
  "app/(tabs)/index.tsx" \
  "app/(tabs)/portfolio.tsx" \
  "app/(tabs)/portfolio/index.tsx" \
  "src/screens/PortfolioScreen.tsx" \
  "src/screens/Portfolio/index.tsx"
do
  if [ -f "$path" ]; then
    echo "[FOUND] Possible Portfolio screen: $path"
    echo "   Imports mentioning 'collectorsClient' or 'portfolio' API:"
    rg -n "collectorsClient|getPortfolioOverview|getPortfolioItems|getPortfolioTimeseries" "$path" 2>/dev/null || echo "   (no matching imports in $path)"
    echo
  fi
done

echo "4) Global search for existing API client patterns..."
if command -v rg >/dev/null 2>&1; then
  rg -n "getPortfolioOverview|getPortfolioItems|getPortfolioTimeseries|scanAndAddItem" src app || echo "   (no existing references found)"
else
  echo "ripgrep (rg) not found, falling back to grep..."
  grep -RniE "getPortfolioOverview|getPortfolioItems|getPortfolioTimeseries|scanAndAddItem" src app || echo "   (no existing references found)"
fi

echo
echo "=== Done. Review FOUND sections above to see if you already have API wiring. ==="
