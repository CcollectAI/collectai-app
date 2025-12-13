#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/items.tsx"

if [ ! -f "$FILE" ]; then
  echo "Items tab not found at $FILE"
  exit 1
fi

cp "$FILE" "${FILE}.bak.theme-body-$(date +%s)" || true

python << 'PY'
from pathlib import Path

path = Path("app/(tabs)/items.tsx")
text = path.read_text()

# If we already destructure spacing from useAppTheme, do nothing
if "useAppTheme()" in text and "spacing, radii" in text:
    print("useAppTheme + spacing already present, nothing to do.")
    raise SystemExit(0)

lines = text.splitlines()

# Find the export default function line
func_idx = None
for i, line in enumerate(lines):
    if "export default function" in line and "{" in line:
        func_idx = i
        break

if func_idx is None:
    # Fallback: first function line
    for i, line in enumerate(lines):
        if "function" in line and "{" in line:
            func_idx = i
            break

if func_idx is None:
    raise SystemExit("Could not find component function in items.tsx")

# Insert the theme destructuring one line after the function definition
insert_line = "  const { colors, spacing, radii } = useAppTheme();"
# Avoid duplicate
if insert_line in lines:
    print("Theme destructuring already in file.")
    raise SystemExit(0)

lines.insert(func_idx + 1, insert_line)

path.write_text("\n".join(lines))
PY

echo "Inserted useAppTheme() destructuring inside Items component body. Backup created."
