#!/usr/bin/env bash
set -e

FILE="app/(tabs)/index.tsx"
[ -f "$FILE" ] || { echo "❌ Missing $FILE"; exit 1; }

TS=$(date +%Y%m%d_%H%M%S)
cp "$FILE" "$FILE.bak_bgwhite_$TS"
echo "✅ Backup: $FILE.bak_bgwhite_$TS"

perl -0777 -i -pe '
  s/backgroundColor:\s*"#f3f4f6"/backgroundColor: "#FFFFFF"/g;
' "$FILE"

echo "✅ Portfolio background set to white."
echo "🛑 SANITY CHECK: npx expo start --tunnel"
