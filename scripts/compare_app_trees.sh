#!/usr/bin/env bash
set -euo pipefail

A="app/(tabs)"
B="src/app/(tabs)"

echo "==> EXISTENCE"
[ -d "$A" ] && echo "✅ $A exists" || echo "❌ $A missing"
[ -d "$B" ] && echo "✅ $B exists" || echo "❌ $B missing"
echo

echo "==> FILE COUNTS"
for D in "$A" "$B"; do
  if [ -d "$D" ]; then
    echo "--- $D"
    find "$D" -type f \( -name '*.ts' -o -name '*.tsx' \) | wc -l | awk '{print "TS/TSX files:", $1}'
    find "$D" -type f | wc -l | awk '{print "All files:", $1}'
  fi
done
echo

echo "==> TOTAL LINES (TS/TSX only)"
for D in "$A" "$B"; do
  if [ -d "$D" ]; then
    echo "--- $D"
    find "$D" -type f \( -name '*.ts' -o -name '*.tsx' \) -print0 \
      | xargs -0 cat 2>/dev/null \
      | wc -l | awk '{print "Total lines:", $1}'
  fi
done
echo

echo "==> TOP 10 LARGEST TSX FILES (by bytes)"
for D in "$A" "$B"; do
  if [ -d "$D" ]; then
    echo "--- $D"
    find "$D" -type f -name '*.tsx' -printf '%s\t%p\n' | sort -nr | head -n 10
  fi
done
echo

echo "==> MOST RECENTLY MODIFIED (top 10, TS/TSX)"
for D in "$A" "$B"; do
  if [ -d "$D" ]; then
    echo "--- $D"
    find "$D" -type f \( -name '*.ts' -o -name '*.tsx' \) -printf '%T@\t%p\n' \
      | sort -nr | head -n 10 | awk '{print $2}'
  fi
done
echo

echo "==> IMPORTANT NOTE"
echo "Since your red stamp appears, the running app is using: app/(tabs)"
echo "So even if src/app/(tabs) is 'bigger', it is NOT the active UI tree unless you reconfigure routing."
