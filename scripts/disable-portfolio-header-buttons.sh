#!/usr/bin/env bash
set -euo pipefail

TARGETS=(
  "app/(tabs)/portfolio.tsx"
  "app/(tabs)/index.tsx"
)

for FILE in "${TARGETS[@]}"; do
  if [ ! -f "$FILE" ]; then
    echo "Skipping $FILE (not found)"
    continue
  fi

  echo "Patching $FILE ..."
  cp "$FILE" "${FILE}.bak.no-header-buttons-$(date +%s)" || true

  # Rename headerRight/headerLeft keys so React Navigation ignores them,
  # but the code still compiles and stays in the file.
  perl -pi -e '
    s/\bheaderRight\s*:/_headerRightDisabled:/g;
    s/\bheaderLeft\s*:/_headerLeftDisabled:/g;
  ' "$FILE"

  echo "  -> Done. Backup: ${FILE}.bak.no-header-buttons-*"
done

echo "All portfolio-like tab files processed."
