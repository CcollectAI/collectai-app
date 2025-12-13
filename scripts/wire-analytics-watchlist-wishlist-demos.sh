#!/usr/bin/env bash
set -euo pipefail

FILE="app/analytics.tsx"

if [ ! -f "$FILE" ]; then
  echo "Analytics screen not found at $FILE"
  exit 1
fi

cp "$FILE" "$FILE.bak.watch-wish-demo-$(date +%s)" || true

python << 'PY'
from pathlib import Path

path = Path("app/analytics.tsx")
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

# 2) Insert watchlist + wishlist links above last </ScrollView>
if "Open watchlist (demo)" in text or "Open wishlist (demo)" in text:
    print("Watchlist/Wishlist demo links already present in analytics.tsx; skipping.")
else:
    block = """
        <View style={{ marginTop: 16, gap: 4 }}>
          <Link href="/watchlist-v1-demo">
            <Text>Open watchlist (demo)</Text>
          </Link>
          <Link href="/wishlist-v1-demo">
            <Text>Open wishlist (demo)</Text>
          </Link>
        </View>
"""
    marker = "</ScrollView>"
    idx = text.rfind(marker)
    if idx == -1:
        print("Warning: </ScrollView> not found in analytics.tsx; no block inserted.")
    else:
        text = text[:idx] + block + "\n    " + text[idx:]
        print("Inserted watchlist/wishlist demo links into analytics.tsx.")

path.write_text(text)
PY

echo "Patched analytics screen with Watchlist/Wishlist demo links (backup created)."
