#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/items.tsx"

if [ ! -f "$FILE" ]; then
  echo "Items tab not found"
  exit 1
fi

cp "$FILE" "${FILE}.bak.fix-theme-$(date +%s)"

python << 'PY'
from pathlib import Path

path = Path("app/(tabs)/items.tsx")
text = path.read_text()

# Ensure import exists
if "useAppTheme" not in text:
    text = text.replace(
        "import React",
        "import React\nimport { useAppTheme } from '@/hooks/useAppTheme';"
    )

# Insert theme destructure inside the main component
# We look for the first `function` or `export default function`
lines = text.splitlines()
out = []
inserted = False

for line in lines:
    out.append(line)

    if not inserted and ("function" in line and "Items" in line):
        # Only insert the theme line if missing
        # Prevent duplicates
        if "useAppTheme()" not in text:
            out.append("  const { colors, spacing, radii } = useAppTheme();")
        inserted = True

text = "\n".join(out)
path.write_text(text)
PY

echo "Added useAppTheme() to Items tab safely."
