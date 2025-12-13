#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

SRC="app/(tabs)/add.tsx.bak.restore.1764197382"
DST="app/(tabs)/add.tsx"

if [ ! -f "$SRC" ]; then
  echo "⚠️ Backup not found: $SRC"
  ls -ltr app/(tabs)/add.tsx.bak.*
  exit 1
fi

echo "Backing up current add.tsx"
cp "$DST" "$DST.bak.restore_28nov_again.$(date +%s)" || true

echo "Restoring Add tab from 28/11 backup: $SRC"
cp "$SRC" "$DST"

echo "✅ Add tab restored to 28/11 version."
