#!/usr/bin/env bash
set -euo pipefail

patch_file() {
  local FILE="$1"
  local HREF="$2"
  local LABEL="$3"

  if [ ! -f "$FILE" ]; then
    echo "Skipping ${FILE} (not found)"
    return
  fi

  cp "$FILE" "${FILE}.bak.demos-$(date +%s)" || true

  python << PY
from pathlib import Path

path = Path("${FILE}")
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

# 2) Insert a simple link block before the last </ScrollView>, if present
insert_block = f"""
        <View style={{ {{ marginTop: 16, marginBottom: 8 }} }}>
          <Link href=\\"{HREF}\\">
            <Text>{LABEL}</Text>
          </Link>
        </View>
"""

marker = "</ScrollView>"
idx = text.rfind(marker)
if idx == -1:
    print(f"Warning: could not find </ScrollView> in {path}, no block inserted.")
else:
    if LABEL in text:
        print(f"Link with label '{LABEL}' already present in {path}, skipping insertion.")
    else:
        text = text[:idx] + insert_block + "\\n\\n    " + text[idx:]
        print(f"Inserted demo link block into {path}.")

path.write_text(text)
PY
}

# Patch Portfolio tab -> portfolio-v2-demo
patch_file "app/(tabs)/portfolio.tsx" "/portfolio-v2-demo" "Try new portfolio (demo)"

# Patch Add tab -> add-v2-demo
patch_file "app/(tabs)/add.tsx" "/add-v2-demo" "Try new add flow (demo)"

echo "Finished wiring demo links into Portfolio and Add tabs (where files exist)."
