#!/usr/bin/env bash
set -euo pipefail

# Always run from repo root
cd "$(dirname "$0")/.."

# The backup from 28/11 you mentioned
SRC='app/(tabs)/add.tsx.bak.restore.1764197382'
DST='app/(tabs)/add.tsx'

echo "Source backup: $SRC"
echo "Destination:   $DST"

if [ ! -f "$SRC" ]; then
  echo "⚠️ Backup not found at: $SRC"
  echo "Available add.tsx backups:"
  ls -ltr app/(tabs)/add.tsx.bak.*
  exit 1
fi

if [ -f "$DST" ]; then
  echo "Backing up current add.tsx to add.tsx.bak.v3.$(date +%s)"
  cp "$DST" "$DST.bak.v3.$(date +%s)" || true
fi

echo "Restoring Add tab from 28/11 backup..."
cp "$SRC" "$DST"

echo "✅ Done: app/(tabs)/add.tsx restored from $SRC"
