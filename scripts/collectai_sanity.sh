#!/usr/bin/env bash
set -euo pipefail

echo "=== CollectAI sanity check ==="
echo

echo "1) Expected core files:"
for f in \
  "src/config/api.ts" \
  "src/services/collectorsClient.ts" \
  "app/(tabs)/index.tsx"
do
  if [ -f "$f" ]; then
    echo "  [FOUND]  $f"
  else
    echo "  [MISSING] $f"
  fi
done

echo
echo "2) Definitions of collectorsClient functions (check for duplicates):"
if command -v rg >/dev/null 2>&1; then
  rg -n "export function getPortfolioOverview|getPortfolioItems|getPortfolioTimeseries|scanAndAddItem" src app || echo "  (none found)"
else
  grep -RniE "export function getPortfolioOverview|export function getPortfolioItems|export function getPortfolioTimeseries|export function scanAndAddItem" src app || echo "  (none found)"
fi

echo
echo "3) Usage sites of portfolio client functions (to spot double wiring):"
if command -v rg >/dev/null 2>&1; then
  rg -n "getPortfolioOverview|getPortfolioItems|getPortfolioTimeseries" app src || echo "  (no usages)"
else
  grep -RniE "getPortfolioOverview|getPortfolioItems|getPortfolioTimeseries" app src || echo "  (no usages)"
fi

echo
echo "4) Components named PortfolioScreen (make sure we don't have two):"
if command -v rg >/dev/null 2>&1; then
  rg -n "function PortfolioScreen" app src || echo "  (no components named PortfolioScreen)"
else
  grep -Rni "function PortfolioScreen" app src || echo "  (no components named PortfolioScreen)"
fi

echo
echo "=== Done. Review for: (a) multiple definitions, (b) multiple PortfolioScreen components. ==="
