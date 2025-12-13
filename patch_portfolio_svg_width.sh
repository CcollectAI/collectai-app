#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

FILE="app/(tabs)/index.tsx"

echo "=== Making Portfolio SVG chart responsive (width='100%' instead of 260px) ==="

if [ ! -f "$FILE" ]; then
  echo "❌ $FILE not found."
  exit 1
fi

python3 <<'PYCODE'
from pathlib import Path

path = Path("app/(tabs)/index.tsx")
text = path.read_text(encoding="utf-8")

backup = path.with_suffix(path.suffix + ".bak_svgWidth")
backup.write_text(text, encoding="utf-8")
print("📦 Backed up index.tsx to", backup)

old = '<Svg height={90} width={260}>'
new = '<Svg height={90} width="100%" preserveAspectRatio="none">'

if old not in text:
    print("ℹ️ Pattern '<Svg height={90} width={260}>' not found; no change applied.")
else:
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("✅ Replaced fixed width 260 with width=\"100%\" and preserveAspectRatio=\"none\" in SVG chart.")
PYCODE
