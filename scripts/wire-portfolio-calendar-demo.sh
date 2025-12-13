#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/portfolio.tsx"

if [ ! -f "$FILE" ]; then
  echo "Portfolio tab not found at $FILE"
  exit 1
fi

cp "$FILE" "$FILE.bak.calendar-demo-$(date +%s)" || true

python << 'PY'
from pathlib import Path

path = Path("app/(tabs)/portfolio.tsx")
text = path.read_text()

# 1) Ensure Link import is present
import_line = "import { Link } from 'expo-router';"
if import_line not in text:
    lines = text.splitlines()
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and line.startswith("import") and "React" in line:
            out.append(import_line)
            inserted = True
    if not inserted:
        out.insert(0, import_line)
    text = "\n".join(out)

# 2) Insert Calendar demo link above the last </ScrollView>
if "Events &amp; drops (demo)" in text:
    print("Calendar demo link already present in portfolio.tsx; skipping.")
else:
    block = """
        <View style={{ marginTop: 8 }}>
          <Link href="/calendar-v1-demo">
            <Text>Events &amp; drops (demo)</Text>
          </Link>
        </View>
"""
    marker = "</ScrollView>"
    idx = text.rfind(marker)
    if idx == -1:
        print("Warning: </ScrollView> not found in portfolio.tsx; no block inserted.")
    else:
        text = text[:idx] + block + "\n    " + text[idx:]
        print("Inserted Calendar demo link into portfolio.tsx.")

path.write_text(text)
PY

echo "Patched portfolio tab with Calendar demo link (backup created)."
