#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
INDEX_FILE="$PROJECT_ROOT/app/index.tsx"
BACKUP_FILE="$PROJECT_ROOT/app/index.tsx.bak_calendar_demo"

cd "$PROJECT_ROOT"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERROR: Backup file not found at:"
  echo "  $BACKUP_FILE"
  echo "If you named it differently, adjust this script."
  exit 1
fi

cp "$BACKUP_FILE" "$INDEX_FILE"
echo "✅ Restored app/index.tsx from:"
echo "  $BACKUP_FILE"

