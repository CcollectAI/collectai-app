#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/add.tsx"

if [ ! -f "$FILE" ]; then
  echo "Add tab file not found at $FILE"
  exit 0
fi

# Backup with timestamp
cp "$FILE" "${FILE}.bak.useAppTheme-$(date +%s)" || true

# 1) Replace import of useTheme with useAppTheme
perl -pi -e "
  s/import\\s+\\{\\s*useTheme\\s*\\}\\s+from\\s+['\"]@\\/theme['\"];?/import { useAppTheme } from '@\\/hooks\\/useAppTheme';/g;
  s/import\\s+useTheme\\s+from\\s+['\"]@\\/theme['\"];?/import { useAppTheme } from '@\\/hooks\\/useAppTheme';/g;
" "$FILE"

# 2) Replace useTheme() call with useAppTheme()
perl -pi -e "
  s/const\\s+\\{([^}]*)\\}\\s*=\\s*useTheme\\(\\);/const {$1} = useAppTheme();/g;
  s/\\buseTheme\\(\\)/useAppTheme()/g;
" "$FILE"

echo "Patched $FILE to use useAppTheme(). Backup kept."
