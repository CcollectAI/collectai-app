#!/usr/bin/env bash
set -euo pipefail

TS="$(date +%Y%m%d_%H%M%S)"
git add -A
git commit -m "FREEZE: gold baseline ${TS}" || true
git tag -f gold-baseline
echo "✅ gold-baseline updated to current HEAD"
