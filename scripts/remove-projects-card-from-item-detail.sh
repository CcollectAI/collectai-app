#!/usr/bin/env bash
set -euo pipefail

FILE="app/item/[id].tsx"

if [ ! -f "$FILE" ]; then
  echo "Item detail file not found at $FILE"
  exit 1
fi

cp "$FILE" "${FILE}.bak.remove-projects-card-$(date +%s)" || true

python << 'PY'
from pathlib import Path

path = Path("app/item/[id].tsx")
text = path.read_text()

block = """
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

if "Track as project (beta)" not in text:
    print("No projects card found in item detail; nothing to remove.")
else:
    # Remove with or without the extra blank lines we might have added
    new_text = text.replace(block + "\n\n    ", "")
    new_text2 = new_text.replace(block, "")
    text = new_text2
    print("Removed 'Track as project (beta)' block from item detail.")

path.write_text(text)
PY

echo "Item detail cleaned of Projects card. Backup created."
