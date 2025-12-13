#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/portfolio.tsx"

if [ ! -f "$FILE" ]; then
  echo "Portfolio tab file not found at $FILE"
  exit 1
fi

# Backup the existing portfolio tab
cp "$FILE" "$FILE.bak.promote-v2-$(date +%s)" || true

# Replace implementation with a re-export of the v2 demo screen
cat > "$FILE" <<'TS'
export { default } from '../portfolio-v2-demo';
TS

echo "Portfolio tab now re-exports ../portfolio-v2-demo (backup created)."
