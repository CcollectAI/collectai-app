#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

FILE="app/(tabs)/portfolio_impl.tsx"

echo "=== Tweaking portfolio chart padding in $FILE (if chartContainer exists) ==="

if [ ! -f "$FILE" ]; then
  echo "❌ $FILE not found. Nothing to tweak."
  exit 0
fi

python3 <<PYCODE
from pathlib import Path

path = Path("$FILE")
text = path.read_text(encoding="utf-8")

if "chartContainer" not in text:
    print("ℹ️ 'chartContainer' style not found in portfolio_impl.tsx; no automatic tweaks applied.")
    raise SystemExit(0)

backup = path.with_suffix(path.suffix + ".bak_chartPadding")
backup.write_text(text, encoding="utf-8")
print("📦 Backed up original file to", backup)

# Very conservative: if there is a 'chartContainer: {' style object,
# inject marginHorizontal & paddingHorizontal near the top of that object.
needle = "chartContainer: {"
idx = text.find(needle)
if idx == -1:
    print("ℹ️ Could not find exact 'chartContainer: {' substring; no changes applied.")
    raise SystemExit(0)

insert_pos = idx + len(needle)
injection = "\\n    marginHorizontal: 0,\\n    paddingHorizontal: 0,\\n    overflow: 'hidden',"

if injection.strip() in text:
    print("ℹ️ Padding tweaks already present; nothing to change.")
    raise SystemExit(0)

new_text = text[:insert_pos] + injection + text[insert_pos:]
path.write_text(new_text, encoding="utf-8")

print("✅ Injected marginHorizontal / paddingHorizontal / overflow into chartContainer style.")
PYCODE
