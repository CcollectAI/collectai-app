#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/index.tsx"

if [ ! -f "$FILE" ]; then
  echo "ERROR: $FILE not found"
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
cp "$FILE" "${FILE}.bak_remove_hoverchart_${TS}"

# 1) Remove import of PortfolioHoverChart (named import)
perl -pi -e 's/^\s*import\s+\{[^}]*PortfolioHoverChart[^}]*\}\s+from\s+["'\''][^"'\'']+["'\''];\s*$//g' "$FILE"

# 2) Remove import of PortfolioHoverChart (default import)
perl -pi -e 's/^\s*import\s+PortfolioHoverChart\s+from\s+["'\''][^"'\'']+["'\''];\s*$//g' "$FILE"

# 3) Replace JSX usage with a simple spacer View
perl -0777 -pi -e 's/<PortfolioHoverChart\b[\s\S]*?\/>/<View style={{ height: 220 }} \/>/g' "$FILE"

echo "OK: PortfolioHoverChart temporarily disabled"
echo "Backup created: ${FILE}.bak_remove_hoverchart_${TS}"
