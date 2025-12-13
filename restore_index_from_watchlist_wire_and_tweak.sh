#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

TABS_DIR="app/(tabs)"
TARGET="$TABS_DIR/index.tsx"
SOURCE="$TABS_DIR/index.tsx.bak.watchlist_wire"

echo "=== Step 1: Restore index.tsx from watchlist_wire backup ==="

if [ ! -f "$SOURCE" ]; then
  echo "❌ Backup not found:"
  echo "   $SOURCE"
  echo "   Cannot restore watchlist wiring automatically."
  exit 1
fi

if [ -f "$TARGET" ]; then
  BAK="${TARGET}.bak_before_watchlist_restore_$(date +%Y%m%d-%H%M%S)"
  cp "$TARGET" "$BAK"
  echo "📦 Backed up current index.tsx to:"
  echo "   $BAK"
fi

cp "$SOURCE" "$TARGET"
echo "✅ Restored:"
echo "   $SOURCE"
echo "   -> $TARGET"

echo
echo "=== Step 2: Gently add horizontal padding to the main container (if present) ==="

python3 <<'PYCODE'
from pathlib import Path

path = Path("app/(tabs)/index.tsx")
text = path.read_text(encoding="utf-8")

backup = path.with_suffix(path.suffix + ".bak_containerPadding_watchlist")
backup.write_text(text, encoding="utf-8")
print("📦 Backed up restored index.tsx to", backup)

needle = "container: {"
idx = text.find(needle)

if idx == -1:
    print("ℹ️ No 'container: {' style found in index.tsx; no automatic padding tweaks applied.")
else:
    start = idx + len(needle)
    brace_level = 1
    i = start
    # Find end of this style object
    while i < len(text) and brace_level > 0:
        c = text[i]
        if c == "{":
            brace_level += 1
        elif c == "}":
            brace_level -= 1
        i += 1
    end = i

    block = text[start:end]
    if "paddingHorizontal" in block:
        print("ℹ️ 'paddingHorizontal' already present in container; leaving as-is.")
    else:
        injection = "\\n    paddingHorizontal: 16,"
        new_block = injection + block
        text = text[:start] + new_block + text[end:]
        path.write_text(text, encoding="utf-8")
        print("✅ Added paddingHorizontal: 16 to container style.")
PYCODE

echo
echo "Done. index.tsx now comes from watchlist_wire backup with optional padding tweak."
