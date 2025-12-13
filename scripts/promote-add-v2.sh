#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/add.tsx"

if [ ! -f "$FILE" ]; then
  echo "Add tab file not found at $FILE"
  exit 1
fi

# Backup the existing Add tab implementation
cp "$FILE" "$FILE.bak.promote-v2-$(date +%s)" || true

# Replace with a re-export of the v2 Add demo screen
cat > "$FILE" <<'TS'
export { default } from '../add-v2-demo';
TS

echo "Add tab now re-exports ../add-v2-demo (backup created)."
