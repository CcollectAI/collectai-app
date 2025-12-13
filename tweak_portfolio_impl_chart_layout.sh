#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

FILE="app/(tabs)/portfolio_impl.tsx"

echo "=== Gently tweaking portfolio_impl.tsx layout to reduce chart edge bleed ==="

if [ ! -f "$FILE" ]; then
  echo "❌ $FILE not found. Nothing to tweak."
  exit 0
fi

python3 <<PYCODE
from pathlib import Path
import re

path = Path("$FILE")
text = path.read_text(encoding="utf-8")

backup = path.with_suffix(path.suffix + ".bak_chartLayout")
backup.write_text(text, encoding="utf-8")
print("📦 Backed up original portfolio_impl.tsx to", backup)

original = text

# 1) Remove negative horizontal margins like marginHorizontal: -16
text = re.sub(r"marginHorizontal:\s*-\d+", "marginHorizontal: 0", text)

# 2) Remove negative left/right margins (common trick to edge charts)
text = re.sub(r"marginLeft:\s*-\d+", "marginLeft: 0", text)
text = re.sub(r"marginRight:\s*-\d+", "marginRight: 0", text)

# 3) Replace width: Dimensions.get('window').width patterns with flex-based width
text = re.sub(
    r"width:\s*Dimensions\.get\(['\"]window['\"]\)\.width",
    "width: '100%'",
    text,
)

if text == original:
    print("ℹ️ No matching margin/width patterns found; no layout changes applied.")
else:
    path.write_text(text, encoding="utf-8")
    print("✅ Applied layout tweaks to margin/width to reduce edge bleed.")
PYCODE
