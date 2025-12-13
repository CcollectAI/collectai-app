#!/usr/bin/env bash
set -euo pipefail

SRC="src/app/(tabs)"
[ -d "$SRC" ] || { echo "✅ Nothing to shelf (missing $SRC)"; exit 0; }

TS="$(date +%Y%m%d_%H%M%S)"
DEST="_shelf/_legacy_src_app_tabs_${TS}"

mkdir -p "_shelf"
cp -a "$SRC" "$DEST"
echo "✅ Copied to: $DEST"

# remove from active tree (still recoverable from git + shelf copy)
rm -rf "$SRC"
echo "✅ Removed: $SRC"

git add -A
git commit -m "chore: shelf legacy src/app/(tabs) to ${DEST}" || true

echo "✅ Done."
