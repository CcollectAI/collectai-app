#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

FILE="app/(tabs)/portfolio_impl.tsx"

echo "=== Wiring PortfolioChartRobinhood into $FILE ==="

if [ ! -f "$FILE" ]; then
  echo "❌ $FILE not found. Cannot wire chart."
  exit 1
fi

# Backup first
BAK="${FILE}.bak_wire_robinhood_$(date +%Y%m%d-%H%M%S)"
cp "$FILE" "$BAK"
echo "📦 Backed up original portfolio_impl.tsx to:"
echo "   $BAK"

python3 <<'PYCODE'
from pathlib import Path

path = Path("app/(tabs)/portfolio_impl.tsx")
text = path.read_text(encoding="utf-8")

original = text

# 1) Add import if missing
import_line = 'import PortfolioChartRobinhood, { PortfolioPoint } from "@/components/PortfolioChartRobinhood";\n'

if "PortfolioChartRobinhood" not in text:
    # Insert after the last import line
    lines = text.splitlines()
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("import "):
            last_import_idx = i
    if last_import_idx >= 0:
        lines.insert(last_import_idx + 1, import_line.rstrip("\n"))
        text = "\n".join(lines)
        print("✅ Inserted PortfolioChartRobinhood import.")
    else:
        text = import_line + text
        print("✅ Inserted PortfolioChartRobinhood import at top (no imports found).")
else:
    print("ℹ️ PortfolioChartRobinhood already imported; skipping import insertion.")

# 2) Add MOCK_POINTS definition if not present
if "const MOCK_POINTS:" not in text and "PortfolioPoint[]" not in text:
    mock_block = """
const MOCK_POINTS: PortfolioPoint[] = [
  { label: "09:30", value: 1220 },
  { label: "10:15", value: 1240 },
  { label: "11:00", value: 1230 },
  { label: "12:30", value: 1255 },
  { label: "14:00", value: 1275 },
  { label: "15:30", value: 1265 },
  { label: "16:00", value: 1282 },
];
"""
    # Insert after imports & before component definition
    idx = text.find("export default")
    if idx != -1:
        # crude but safe: insert before first 'export default'
        text = text[:idx] + mock_block + "\n" + text[idx:]
        print("✅ Inserted MOCK_POINTS definition.")
    else:
        # fallback: append to end
        text = text + "\n" + mock_block
        print("✅ Appended MOCK_POINTS definition at end (no 'export default' found).")
else:
    print("ℹ️ MOCK_POINTS or PortfolioPoint[] already defined; skipping mock definition.")

# 3) Inject <PortfolioChartRobinhood ... /> before the 'Collection' section header
if "PortfolioChartRobinhood" in text:
    injection = "      <PortfolioChartRobinhood data={MOCK_POINTS} />\n"

    if "Collection" in text and "PortfolioChartRobinhood data={MOCK_POINTS}" not in text:
        marker = '<Text style={styles.sectionTitle}>Collection</Text>'
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx] + injection + text[idx:]
            print("✅ Injected <PortfolioChartRobinhood data={MOCK_POINTS} /> before 'Collection' header.")
        else:
            # fallback: before first occurrence of 'Collection' string
            idx = text.find("Collection")
            if idx != -1:
                text = text[:idx] + injection + text[idx:]
                print("✅ Injected chart before first 'Collection' occurrence (fallback).")
            else:
                print("⚠️ Could not find 'Collection' marker; no chart injection done.")
    else:
        print("ℹ️ Chart injection already present or 'Collection' not found; skipping injection.")
else:
    print("⚠️ PortfolioChartRobinhood import not found in final text; chart not injected.")

if text != original:
    path.write_text(text, encoding="utf-8")
    print("💾 Saved updated portfolio_impl.tsx.")
else:
    print("ℹ️ No changes made to portfolio_impl.tsx; it may already be wired.")
PYCODE

