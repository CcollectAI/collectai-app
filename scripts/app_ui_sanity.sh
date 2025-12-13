#!/usr/bin/env bash
set -euo pipefail

echo "=== App UI sanity check ==="
echo

echo "1) Key files:"
for f in \
  "src/config/api.ts" \
  "src/services/collectorsClient.ts" \
  "app/(tabs)/portfolio.tsx" \
  "app/(tabs)/items.tsx" \
  "app/(tabs)/add.tsx" \
  "app/(tabs)/marketplace.tsx" \
  "app/debug/eval.tsx"
do
  if [ -f "$f" ]; then
    echo "  [FOUND]  $f"
  else
    echo "  [MISSING] $f"
  fi
done

echo
echo "2) Client functions present:"
if command -v rg >/dev/null 2>&1; then
  rg -n "export function getPortfolioOverview|export function getPortfolioItems|export function getPortfolioTimeseries|export function scanAndAddItem|export function getMarketplaceListings|export function getEvalSummary" src/services/collectorsClient.ts || true
else
  grep -RniE "export function getPortfolioOverview|export function getPortfolioItems|export function getPortfolioTimeseries|export function scanAndAddItem|export function getMarketplaceListings|export function getEvalSummary" src/services/collectorsClient.ts || true
fi

echo
echo "3) Screen components present:"
if command -v rg >/dev/null 2>&1; then
  rg -n "function PortfolioScreen" app/(tabs)/portfolio.tsx || true
  rg -n "function ItemsScreen" app/(tabs)/items.tsx || true
  rg -n "function AddScreen" app/(tabs)/add.tsx || true
  rg -n "function MarketplaceScreen" app/(tabs)/marketplace.tsx || true
  rg -n "function EvalDebugScreen" app/debug/eval.tsx || true
else
  grep -n "function PortfolioScreen" app/(tabs)/portfolio.tsx || true
  grep -n "function ItemsScreen" app/(tabs)/items.tsx || true
  grep -n "function AddScreen" app/(tabs)/add.tsx || true
  grep -n "function MarketplaceScreen" app/(tabs)/marketplace.tsx || true
  grep -n "function EvalDebugScreen" app/debug/eval.tsx || true
fi

echo
echo "4) Imports of collectorsClient in screens:"
if command -v rg >/dev/null 2>&1; then
  rg -n "collectorsClient|getPortfolioOverview|getPortfolioItems|getPortfolioTimeseries|scanAndAddItem|getMarketplaceListings|getEvalSummary" app || true
else
  grep -RniE "collectorsClient|getPortfolioOverview|getPortfolioItems|getPortfolioTimeseries|scanAndAddItem|getMarketplaceListings|getEvalSummary" app || true
fi

echo
echo "=== Done. Fix any [MISSING] items above before running Expo. ==="

