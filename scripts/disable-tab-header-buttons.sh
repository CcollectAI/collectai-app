#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/_layout.tsx"

if [ ! -f "$FILE" ]; then
  echo "Tab layout not found at $FILE"
  exit 1
fi

cp "$FILE" "${FILE}.bak.no-header-buttons-$(date +%s)" || true

# Rename headerRight/headerLeft keys so React Navigation ignores them.
perl -pi -e '
  s/\bheaderRight\s*:/headerRightDisabled:/g;
  s/\bheaderLeft\s*:/headerLeftDisabled:/g;
' "$FILE"

echo "Patched $FILE (headerRight/headerLeft disabled). Backup kept."
