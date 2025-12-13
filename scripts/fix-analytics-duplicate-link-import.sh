#!/usr/bin/env bash
set -euo pipefail

FILE="app/analytics.tsx"

if [ ! -f "$FILE" ]; then
  echo "File not found: $FILE"
  exit 1
fi

# Backup before modifying
cp "$FILE" "$FILE.bak.fix-duplicate-link-$(date +%s)" || true

python << 'PY'
from pathlib import Path
import re

path = Path("app/analytics.tsx")
text = path.read_text()

# Pattern to match a standalone import { Link }...
standalone_link_import = re.compile(r"^\s*import\s*\{\s*Link\s*\}\s*from\s*['\"]expo-router['\"]\s*;\s*$", re.MULTILINE)

matches = standalone_link_import.findall(text)
if matches:
    print(f"Found and removing {len(matches)} duplicate standalone Link import(s).")
    text = standalone_link_import.sub("", text)
else:
    print("No duplicate standalone Link import found.")

# Clean extra blank lines caused by removal
text = re.sub(r"\n{3,}", "\n\n", text)

path.write_text(text)
PY

echo "Duplicate Link import fixed in analytics.tsx (backup created)."
