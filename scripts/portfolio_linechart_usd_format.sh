#!/usr/bin/env bash
set -e

FILE="src/components/PortfolioLineChart.tsx"
[ -f "$FILE" ] || { echo "❌ Missing $FILE"; exit 1; }

TS=$(date +%Y%m%d_%H%M%S)
cp "$FILE" "$FILE.bak_usd_$TS"
echo "✅ Backup: $FILE.bak_usd_$TS"

perl -0777 -i -pe 's/new Intl\.NumberFormat\(\x27de-DE\x27,\s*\{\s*style:\s*\x27currency\x27,\s*currency:\s*\x27EUR\x27,\s*maximumFractionDigits:\s*0,\s*\}\)/new Intl.NumberFormat(\x27en-US\x27, { style: \x27currency\x27, currency: \x27USD\x27, maximumFractionDigits: 0 })/gms' "$FILE"

echo "✅ Patched PortfolioLineChart currency formatter to en-US USD (0 decimals)."
echo "🛑 STOP & SANITY CHECK: npx expo start --tunnel"
