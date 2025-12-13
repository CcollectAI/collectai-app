#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

SRC="app/(tabs)/add.tsx.bak.restore.1764197382"
DST="app/(tabs)/add.tsx"

if [ ! -f "$SRC" ]; then
  echo "⚠️ Backup not found: $SRC"
  exit 1
fi

echo "Backing up current add.tsx"
cp "$DST" "$DST.bak.restore_28nov.$(date +%s)" || true

echo "Restoring Add tab from 28/11 backup: $SRC"
cp "$SRC" "$DST"

echo "✅ Add tab restored to older version."
