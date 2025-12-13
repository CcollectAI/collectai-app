#!/usr/bin/env bash
set -euo pipefail

FILE="app/analytics.tsx"

if [ ! -f "$FILE" ]; then
  echo "Analytics screen not found at $FILE"
  exit 1
fi

cp "$FILE" "$FILE.bak.calendar-link-$(date +%s)" || true

python << 'PY'
from pathlib import Path
import re

path = Path("app/analytics.tsx")
text = path.read_text()

# 1) Make sure Link is imported from expo-router, but don't duplicate it
pattern = re.compile(r"^import\s*\{\s*([^}]+)\}\s*from\s*['\"]expo-router['\"]\s*;\s*$", re.MULTILINE)
m = pattern.search(text)

if m:
    names = [n.strip() for n in m.group(1).split(",") if n.strip()]
    if "Link" not in names:
        names.append("Link")
        new_line = "import { " + ", ".join(sorted(set(names))) + " } from 'expo-router';"
        text = text[:m.start()] + new_line + text[m.end():]
        print("Updated expo-router import to include Link.")
    else:
        print("Link already present in expo-router import; leaving import as-is.")
else:
    # No named import for expo-router -> insert one after React import if needed
    if "Link" not in text:
        lines = text.splitlines()
        out = []
        inserted = False
        for line in lines:
            out.append(line)
            if not inserted and line.startswith("import React"):
                out.append("import { Link } from 'expo-router';")
                inserted = True
        if not inserted:
            out.insert(0, "import { Link } from 'expo-router';")
        text = "\n".join(out)
        print("Inserted new import { Link } from 'expo-router';")
    else:
        print("Some Link import already exists; skipping import insertion.")

# 2) Insert calendar link near the bottom of the ScrollView
if "/calendar-v1-demo" in text:
    print("Calendar link already present in analytics.tsx; skipping block insertion.")
else:
    block = """
        <View style={{ marginTop: 16 }}>
          <Link href="/calendar-v1-demo">
            <Text>Open events &amp; drops calendar</Text>
          </Link>
        </View>
"""

    marker = "</ScrollView>"
    idx = text.rfind(marker)
    if idx == -1:
        print("Warning: </ScrollView> not found in analytics.tsx; calendar link not inserted.")
    else:
        text = text[:idx] + block + "\\n    " + text[idx:]
        print("Inserted calendar link into analytics.tsx.")

path.write_text(text)
PY

echo "Patched analytics.tsx with calendar link (backup created)."
