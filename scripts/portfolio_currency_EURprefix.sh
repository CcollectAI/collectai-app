#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/index.tsx"
[ -f "$FILE" ] || { echo "❌ Missing $FILE"; exit 1; }

TS=$(date +%Y%m%d_%H%M%S)
cp "$FILE" "$FILE.bak_eurprefix_${TS}"
echo "✅ Backup: $FILE.bak_eurprefix_${TS}"

# Insert formatter near top (after imports) if not present
python3 - <<'PY'
import re, pathlib
p = pathlib.Path("app/(tabs)/index.tsx")
s = p.read_text()

if "function formatEURPrefix" in s:
    print("✅ Formatter already present.")
else:
    # insert after last import line
    m = list(re.finditer(r'^\s*import .*?;\s*$', s, flags=re.M))
    if not m:
        raise SystemExit("❌ Could not find import block to insert formatter.")
    insert_at = m[-1].end()
    formatter = """

function formatEURPrefix(v: number) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "EUR—";
  return "EUR" + n.toLocaleString("en-US", { maximumFractionDigits: 0 });
}
"""
    s = s[:insert_at] + formatter + s[insert_at:]
    p.write_text(s)
    print("✅ Inserted formatEURPrefix().")
PY

echo "✅ Currency helper added. Now you must use formatEURPrefix(value) in the header total."
echo "🛑 SANITY CHECK NOW: npx expo start --tunnel"
