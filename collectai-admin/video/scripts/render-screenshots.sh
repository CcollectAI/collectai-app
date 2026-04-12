#!/bin/bash
# Render all App Store screenshots in one go
# Usage: cd collectai-admin/video && bash scripts/render-screenshots.sh
set -euo pipefail

OUT="out/screenshots"
mkdir -p "$OUT"

COMPOSITIONS=(
  "Screenshot-1-Home"
  "Screenshot-2-QuickScan"
  "Screenshot-3-ItemDetail"
  "Screenshot-4-Collection"
  "Screenshot-5-Marketplace"
  "Screenshot-6-Deals"
)

echo "Rendering ${#COMPOSITIONS[@]} App Store screenshots..."

for comp in "${COMPOSITIONS[@]}"; do
  echo "  → $comp"
  npx remotion still "$comp" --output="$OUT/${comp}.png" 2>/dev/null
done

echo ""
echo "Done! Screenshots saved to $OUT/"
echo "  Resolution: 1320x2868 (iPhone 16 Pro Max 6.9\")"
ls -lh "$OUT"/*.png
