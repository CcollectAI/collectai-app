#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

FILE="app/(tabs)/index.tsx"

echo "=== Tweaking app/(tabs)/index.tsx container padding (if 'container' style exists) ==="

if [ ! -f "$FILE" ]; then
  echo "❌ $FILE not found. Nothing to tweak."
  exit 0
fi

python3 <<'PYCODE'
from pathlib import Path
import re

path = Path("app/(tabs)/index.tsx")
text = path.read_text(encoding="utf-8")

backup = path.with_suffix(path.suffix + ".bak_containerPadding")
backup.write_text(text, encoding="utf-8")
print("📦 Backed up original index.tsx to", backup)

original = text

# Look for a style object named "container: {"
needle = "container: {"
idx = text.find(needle)

if idx == -1:
    print("ℹ️ No 'container: {' style found in index.tsx; no automatic tweaks applied.")
else:
    # Insert paddingHorizontal if not already present inside that object
    # We'll scan forward until the closing '}' that matches the container block.
    start = idx + len(needle)
    brace_level = 1
    i = start
    while i < len(text) and brace_level > 0:
        if text[i] == "{":
            brace_level += 1
        elif text[i] == "}":
            brace_level -= 1
        i += 1
    end = i  # position just after the closing brace

    block = text[start:end]
    if "paddingHorizontal" in block:
        print("ℹ️ 'paddingHorizontal' already present in container; no change applied.")
    else:
        injection = "\n    paddingHorizontal: 16,"
        new_block = injection + block
        text = text[:start] + new_block + text[end:]
        path.write_text(text, encoding="utf-8")
        print("✅ Added paddingHorizontal: 16 to container style.")
PYCODE
