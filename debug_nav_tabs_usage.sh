#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

echo "=== All _layout.tsx files ==="
find app -name "_layout.tsx" -print
echo

echo "=== Files containing 'Tabs.Screen' or '<Tabs' ==="
grep -R --line-number "Tabs.Screen" app || echo "(no Tabs.Screen found)"
echo
grep -R --line-number "<Tabs" app || echo "(no <Tabs found)"
