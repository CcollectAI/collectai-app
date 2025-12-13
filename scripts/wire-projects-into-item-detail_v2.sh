#!/usr/bin/env bash
set -euo pipefail

FILE="app/item/[id].tsx"

if [ ! -f "$FILE" ]; then
  echo "Item detail file not found at $FILE"
  exit 1
fi

cp "$FILE" "${FILE}.bak.projects-link-v2-$(date +%s)" || true

python << 'PY'
from pathlib import Path

path = Path("app/item/[id].tsx")
text = path.read_text()

# 1) Ensure Link import
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

# 2) Inject "Track as project (beta)" card before </ScrollView>
insert_block = """
        <View style={{ marginTop: spacing.lg }}>
          <Link
            href="/projects"
            style={{
              borderRadius: radii.lg,
              padding: spacing.md,
              backgroundColor: colors.card,
            }}
          >
            <Text
              style={{
                fontSize: 14,
                fontWeight: '600',
                color: colors.text,
                marginBottom: spacing.xs,
              }}
            >
              Track as project (beta)
            </Text>
            <Text
              style={{
                fontSize: 13,
                color: colors.mutedText,
              }}
            >
              Later this will create a project for this specific item. For now it opens your projects log.
            </Text>
          </Link>
        </View>
"""

marker = "</ScrollView>"
idx = text.rfind(marker)
if idx == -1:
    raise SystemExit("Could not find </ScrollView> in app/item/[id].tsx")

text = text[:idx] + insert_block + "\n\n    " + text[idx:]

path.write_text(text)
PY

echo "Patched app/item/[id].tsx with a 'Track as project (beta)' card. Backup created."
