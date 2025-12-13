#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/items.tsx"

if [ ! -f "$FILE" ]; then
  echo "Items tab file not found at $FILE"
  exit 1
fi

cp "$FILE" "${FILE}.bak.projects-link-safe-$(date +%s)" || true

python << 'PY'
from pathlib import Path

path = Path("app/(tabs)/items.tsx")
text = path.read_text()

# 1) Ensure Link import from expo-router exists
import_line = "import { Link } from 'expo-router';"
if import_line not in text:
    lines = text.splitlines()
    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if not inserted and line.startswith("import React"):
            new_lines.append(import_line)
            inserted = True
    if not inserted:
        new_lines.insert(0, import_line)
    text = "\n".join(new_lines)

# 2) Insert a simple link block before the last </ScrollView>, with only numeric margins
insert_block = """
        <View style={{ marginTop: 16, marginBottom: 8 }}>
          <Link href="/projects">
            <Text>Build &amp; paint projects (beta)</Text>
          </Link>
        </View>
"""

marker = "</ScrollView>"
idx = text.rfind(marker)
if idx == -1:
    raise SystemExit("Could not find </ScrollView> in app/(tabs)/items.tsx")

# Avoid duplicate insertion if already present
if "Build &amp; paint projects (beta)" in text:
    print("Projects link already present in items.tsx; skipping insertion.")
else:
    text = text[:idx] + insert_block + "\n\n    " + text[idx:]
    print("Inserted Projects link block into items.tsx.")

path.write_text(text)
PY

echo "Patched app/(tabs)/items.tsx with a safe Projects link. Backup created."
