#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

INDEX_FILE="app/index.tsx"
BACKUP_SRC="app/index.tsx.bak.20251204-001312"
INDEX_NOW_BACKUP="${INDEX_FILE}.bak_restore_$(date +%Y%m%d-%H%M%S)"

echo "=== Restoring app/index.tsx from 2025-12-04 00:13 backup ==="

if [ ! -f "$BACKUP_SRC" ]; then
  echo "ERROR: Backup file not found:"
  echo "  $BACKUP_SRC"
  exit 1
fi

if [ -f "$INDEX_FILE" ]; then
  cp "$INDEX_FILE" "$INDEX_NOW_BACKUP"
  echo "📦 Backed up current app/index.tsx to:"
  echo "  $INDEX_NOW_BACKUP"
fi

cp "$BACKUP_SRC" "$INDEX_FILE"
echo "✅ Restored app/index.tsx from:"
echo "  $BACKUP_SRC"
