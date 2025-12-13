#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/add.tsx"

if [ ! -f "$FILE" ]; then
  echo "Add tab file not found at $FILE"
  exit 0
fi

cp "$FILE" "${FILE}.bak.useAppTheme-strong-$(date +%s)" || true

# 1) Ensure we import useAppTheme from the hook, if not already present
if ! grep -q "useAppTheme" "$FILE"; then
  perl -0pi -e 's/^(import\s+React[^\n]*\n)/$1import { useAppTheme } from '\''@\/hooks\/useAppTheme'\'';\n/' "$FILE"
fi

# 2) Replace all uses of useTheme with useAppTheme
perl -pi -e 's/\buseTheme\b/useAppTheme/g' "$FILE"

echo "Patched $FILE: all useTheme -> useAppTheme and import added. Backup kept."
