#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Searching for likely Calendar files under ./app ==="

if [ ! -d "app" ]; then
  echo "ERROR: ./app directory not found. Are you in the Expo project root?"
  exit 1
fi

echo
echo "--- Step 1: Search for text markers in TSX files (My Events / Major Drops / Calendar) ---"
grep -Rni --include="*.tsx" --include="*.jsx" \
  -e "My Events" \
  -e "Major Drops" \
  -e "Calendar" \
  app || echo "(No obvious text matches, that's okay – continue)"

echo
echo "--- Step 2: Search for filenames containing 'calendar' under ./app ---"
# Using grouped -o in find is a bit verbose but safe
find app \( -iname "*calendar*.tsx" -o -iname "*calendar*.jsx" -o -iname "*calendar*.ts" -o -iname "*calendar*.js" \) -print || true

echo
echo "Look at the paths printed above. You want the one that corresponds to the"
echo "Calendar screen (the one with My Events / Major Drops / add-event UI)."
echo
echo "Example paths you might see:"
echo "  app/calendar/index.tsx"
echo "  app/(tabs)/calendar.tsx"
echo "  app/screens/calendar/CalendarScreen.tsx"
echo
echo "Once you know the correct file, you'll feed a *relative path from app/*"
echo "into the next script, like:"
echo "  ./scripts/wire-calendar-as-home.sh 'calendar/index'"
echo "or:"
echo "  ./scripts/wire-calendar-as-home.sh '(tabs)/calendar'"
