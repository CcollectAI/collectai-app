#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

echo "=== Listing candidate app snapshots/backups under $PROJECT_ROOT ==="
echo

# Common snapshot patterns you already have (e.g. app_full_20251126, app_full_backup, etc.)
ls -d app_full* 2>/dev/null || echo "(no app_full* directories found)"

echo
echo "=== Listing app/index.tsx backups (if any) ==="
echo

find app -maxdepth 1 -type f -name 'index.tsx.bak*' -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' 2>/dev/null \
  | sort || echo "(no index.tsx.bak* files found)"

echo
echo "Pick the snapshot directory that matches the time you trust most (e.g. work from 00:15),"
echo "then use restore_app_from_snapshot.sh with that directory name."
