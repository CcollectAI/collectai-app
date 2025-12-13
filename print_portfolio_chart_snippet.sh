#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/index.tsx"

echo "=== Showing lines in index.tsx that mention chart-related components ==="
if [ ! -f "$FILE" ]; then
  echo "❌ app/(tabs)/index.tsx not found."
  exit 1
fi

# Show imports that might be chart-related
echo
echo "--- Chart-related imports ---"
grep -nE "Svg|LineChart|InteractiveLineChart|PortfolioLineChart|react-native-svg" "$FILE" || echo "(no chart imports found)"

# Show JSX lines where chart components are rendered, with a bit of context
echo
echo "--- JSX usage (with context) ---"
nl -ba "$FILE" | grep -nE "LineChart|InteractiveLineChart|PortfolioLineChart|<Svg" | head -n 20 | cut -d: -f2-
