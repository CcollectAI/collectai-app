#!/usr/bin/env bash
set -euo pipefail

FILE="app/portfolio-v2-demo.tsx"

if [ ! -f "$FILE" ]; then
  echo "File not found: $FILE"
  exit 1
fi

cp "$FILE" "$FILE.bak.calendar-link-$(date +%s)" || true

python << 'PY'
from pathlib import Path

path = Path("app/portfolio-v2-demo.tsx")
text = path.read_text()

# Avoid duplicate insertion
if "/calendar-v1-demo" in text:
    print("Calendar link already present in portfolio-v2-demo.tsx; skipping.")
else:
    block = """
        <View style={{ marginTop: spacing.sm }}>
          <Link href="/calendar-v1-demo">
            <Text>Events &amp; drops calendar (demo)</Text>
          </Link>
        </View>
"""

    marker = "</ScrollView>"
    idx = text.rfind(marker)
    if idx == -1:
        print("Warning: </ScrollView> not found in portfolio-v2-demo.tsx; no block inserted.")
    else:
        text = text[:idx] + block + "\n    " + text[idx:]
        print("Inserted Calendar link into portfolio-v2-demo.tsx.")

    path.write_text(text)
PY

echo "Patched portfolio-v2-demo with Calendar link (backup created)."
