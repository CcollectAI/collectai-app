#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/items.tsx"

if [ ! -f "$FILE" ]; then
  echo "Items tab not found at $FILE"
  exit 1
fi

cp "$FILE" "${FILE}.bak.remove-projects-card-$(date +%s)" || true

python << 'PY'
from pathlib import Path

path = Path("app/(tabs)/items.tsx")
text = path.read_text()

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
              Build & paint projects
            </Text>
            <Text
              style={{
                fontSize: 13,
                color: colors.mutedText,
              }}
            >
              Open your long-running build and paint projects log.
            </Text>
          </Link>
        </View>
"""

if insert_block not in text:
    print("Projects card block not found in items.tsx; nothing to remove.")
else:
    text = text.replace(insert_block + "\n\n    ", "")
    text = text.replace(insert_block, "")
    print("Projects card block removed from items.tsx.")

path.write_text(text)
PY

echo "Cleaned projects card from Items tab. Backup created."
