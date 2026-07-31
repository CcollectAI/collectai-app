#!/bin/bash
# Render the store screenshots in one go.
#
# Usage:
#   cd collectai-admin/video && bash scripts/render-screenshots.sh          # App Store (iOS)
#   cd collectai-admin/video && bash scripts/render-screenshots.sh --play   # Google Play (Android)
#
# The two sets differ in size and device chrome, not in copy:
#   iOS  1320x2868, iPhone frame + Dynamic Island
#   Play 1440x2560, Android frame + punch-hole camera
#
# Play rejects screenshots whose longest side is more than 2x the shortest, so
# the iOS masters (ratio 2.173) cannot be reused as-is. After rendering --play,
# run scripts/prepare_play_assets.py from the repo root to copy them into
# android/fastlane/metadata/ as 24-bit PNGs and verify them against Play's limits.
set -euo pipefail

if [[ "${1:-}" == "--play" ]]; then
  OUT="out/play-screenshots"
  LABEL="Google Play"
  RESOLUTION="1440x2560 (9:16, Android device chrome)"
  COMPOSITIONS=(
    "Play-1-Home"
    "Play-2-QuickScan"
    "Play-3-ItemDetail"
    "Play-4-Collection"
    "Play-5-Marketplace"
    "Play-6-Deals"
  )
  # prepare_play_assets.py maps these to 1.png..6.png by filename.
  RENAME_TO_INDEX=1
else
  OUT="out/screenshots"
  LABEL="App Store"
  RESOLUTION="1320x2868 (iPhone 16 Pro Max 6.9\")"
  COMPOSITIONS=(
    "Screenshot-1-Home"
    "Screenshot-2-QuickScan"
    "Screenshot-3-ItemDetail"
    "Screenshot-4-Collection"
    "Screenshot-5-Marketplace"
    "Screenshot-6-Deals"
  )
  RENAME_TO_INDEX=0
fi

mkdir -p "$OUT"

echo "Rendering ${#COMPOSITIONS[@]} $LABEL screenshots..."

for comp in "${COMPOSITIONS[@]}"; do
  echo "  → $comp"
  if [[ "$RENAME_TO_INDEX" == "1" ]]; then
    # "Play-3-ItemDetail" -> "3.png"
    index="$(echo "$comp" | cut -d- -f2)"
    npx remotion still "$comp" --output="$OUT/${index}.png" 2>/dev/null
  else
    npx remotion still "$comp" --output="$OUT/${comp}.png" 2>/dev/null
  fi
done

echo ""
echo "Done! Screenshots saved to $OUT/"
echo "  Resolution: $RESOLUTION"
ls -lh "$OUT"/*.png

if [[ "$RENAME_TO_INDEX" == "1" ]]; then
  echo ""
  echo "Next: from the repo root, run"
  echo "  python3 scripts/prepare_play_assets.py"
fi
