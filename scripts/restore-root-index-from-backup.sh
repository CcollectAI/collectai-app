#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

INDEX_FILE="$ROOT_DIR/app/index.tsx"

BACKUP_CANDIDATE="$(ls -t "${INDEX_FILE}".bak.* 2>/dev/null | head -n 1 || true)"

if [ -z "$BACKUP_CANDIDATE" ]; then
  echo "No backup files found for app/index.tsx."
  exit 1
fi

cp "$BACKUP_CANDIDATE" "$INDEX_FILE"
echo "Restored app/index.tsx from:"
echo "  $BACKUP_CANDIDATE"
