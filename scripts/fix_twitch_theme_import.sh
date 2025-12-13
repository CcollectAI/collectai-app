#!/usr/bin/env bash
set -euo pipefail

FILE="app/twitch.tsx"
[ -f "$FILE" ] || { echo "❌ app/twitch.tsx not found"; exit 1; }

TS="$(date +%Y%m%d_%H%M%S)"
cp "$FILE" "$FILE.bak_themefix_$TS"
echo "✅ Backup created: $FILE.bak_themefix_$TS"

# Replace any theme import with the correct hook
sed -i '' \
  -e 's|from "@/theme"|from "@/hooks/useAppTheme"|g' \
  -e 's|from "src/theme"|from "@/hooks/useAppTheme"|g' \
  "$FILE"

echo "✅ Twitch now uses useAppTheme from hooks"
echo "🛑 SANITY CHECK: npx expo start --tunnel"
