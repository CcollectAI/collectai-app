#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/portfolio.tsx"

if [ ! -f "$FILE" ]; then
  echo "Portfolio screen file not found at $FILE"
  exit 1
fi

# Backup with timestamp
cp "$FILE" "${FILE}.bak.no-header-$(date +%s)" || true

# Rename headerRight/headerLeft so React Navigation ignores them
perl -pi -e '
  s/\bheaderRight\s*:/_headerRightDisabled:/g;
  s/\bheaderLeft\s*:/_headerLeftDisabled:/g;
' "$FILE"

echo "Patched $FILE: headerRight/headerLeft disabled. Backup kept."
