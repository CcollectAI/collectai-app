#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/portfolio.tsx"

if [ ! -f "$FILE" ]; then
  echo "Portfolio tab file not found at $FILE"
  exit 1
fi

# Backup current portfolio tab
cp "$FILE" "$FILE.bak.calendar-link-$(date +%s)" || true

python << 'PY'
from pathlib import Path
import re

path = Path("app/(tabs)/portfolio.tsx")
text = path.read_text()

# 1) Ensure Link is imported from expo-router without duplicating it
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
        print("Link already present in expo-router import.")
else:
    # No named import found for expo-router; add a simple one after React import
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
        print("Some Link import already exists; skipping import change.")

# 2) Insert calendar link block near bottom of ScrollView
if "/calendar-v1-demo" in text:
    print("Calendar link already present in portfolio.tsx; skipping insertion.")
else:
    block = """
        <View style={{ marginTop: 12 }}>
          <Link href="/calendar-v1-demo">
            <Text>Events &amp; drops calendar</Text>
          </Link>
        </View>
"""

    marker = "</ScrollView>"
    idx = text.rfind(marker)
    if idx == -1:
        print("Warning: </ScrollView> not found in portfolio.tsx; calendar link not inserted.")
    else:
        text = text[:idx] + block + "\\n    " + text[idx:]
        print("Inserted calendar link into portfolio.tsx.")

path.write_text(text)
PY

echo "Done wiring calendar link into Portfolio (backup created)."
