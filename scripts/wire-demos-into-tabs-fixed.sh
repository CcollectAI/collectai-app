#!/usr/bin/env bash
set -euo pipefail

insert_demo_link() {
  local FILE="$1"
  local HREF="$2"
  local LABEL="$3"

  if [ ! -f "$FILE" ]; then
    echo "Skipping: $FILE not found"
    return
  fi

  cp "$FILE" "$FILE.bak.demo-$(date +%s)" || true

  python <<PY
from pathlib import Path

file_path = Path("$FILE")
text = file_path.read_text()

# Ensure Link import
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

# Block to insert
block = f"""
        <View style={{ marginTop: 16, marginBottom: 8 }}>
          <Link href=\\"$HREF\\">
            <Text>$LABEL</Text>
          </Link>
        </View>
"""

marker = "</ScrollView>"
idx = text.rfind(marker)

if idx == -1:
    print(f"[WARN] No </ScrollView> found in {file_path}. No link inserted.")
else:
    if "$LABEL" in text:
        print(f"[SKIP] Label already present in {file_path}")
    else:
        text = text[:idx] + block + "\\n    " + text[idx:]
        print(f"[OK] Inserted demo link into {file_path}")

file_path.write_text(text)
PY
}

insert_demo_link "app/(tabs)/portfolio.tsx" "/portfolio-v2-demo" "Try new portfolio (demo)"
insert_demo_link "app/(tabs)/add.tsx" "/add-v2-demo" "Try new add flow (demo)"

echo "Done wiring demo links."
