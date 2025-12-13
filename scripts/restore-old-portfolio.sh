#!/usr/bin/env bash
set -euo pipefail

TARGET="app/(tabs)/portfolio.tsx"

if [ ! -f "$TARGET" ]; then
  echo "Portfolio file not found at $TARGET"
fi

# Find the most recent backup for portfolio.tsx
latest_backup="$(ls -t app/(tabs)/portfolio.tsx.bak* 2>/dev/null | head -n 1 || true)"

if [ -z "$latest_backup" ]; then
  echo "No backup portfolio.tsx.bak* files found. Nothing restored."
  exit 1
fi

echo "Restoring portfolio from backup: $latest_backup"
cp "$latest_backup" "$TARGET"

echo "Done. Old portfolio implementation has been restored to $TARGET"
