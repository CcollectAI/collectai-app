#!/usr/bin/env bash
set -euo pipefail

echo "=== Listing existing expo/node/metro processes (if any) ==="
ps aux | egrep "expo|metro|node .*expo" | grep -v egrep || echo "(none)"

echo
echo "=== Killing expo/metro/node bundlers ==="
pkill -f "expo start" || true
pkill -f "node .*expo" || true
pkill -f "metro" || true

echo
echo "=== Remaining relevant processes (should be empty or just this grep) ==="
ps aux | egrep "expo|metro|node .*expo" | grep -v egrep || echo "(none)"

echo
echo "Done. You can now start a fresh expo instance from the correct project."
