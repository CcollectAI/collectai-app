#!/usr/bin/env bash
set -euo pipefail

FILE="app/twitch.tsx"
[ -f "$FILE" ] || { echo "❌ app/twitch.tsx not found"; exit 1; }

TS="$(date +%Y%m%d_%H%M%S)"
cp "$FILE" "$FILE.bak_themefix_linux_$TS"
echo "✅ Backup: $FILE.bak_themefix_linux_$TS"

# Replace bad imports with correct one
sed -i \
  's|from "@/theme"|from "@/hooks/useAppTheme"|g;
   s|from "src/theme"|from "@/hooks/useAppTheme"|g' \
  "$FILE"

echo "✅ Twitch now uses the correct theme hook"
