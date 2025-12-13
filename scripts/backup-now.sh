#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="${PROJECT_DIR:-$HOME/collectors-merge-recovered}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
RETENTION="${RETENTION:-7}"
mkdir -p "$BACKUP_DIR"
ts="$(date -u +%Y%m%d-%H%M%S)"
tarball="$BACKUP_DIR/collectors-merge-$ts.tar.gz"
tar -C "$PROJECT_DIR" --exclude=node_modules --exclude=.expo -czf "$tarball" .
echo "✓ Backup: $tarball"
(ls -1t "$BACKUP_DIR"/collectors-merge-*.tar.gz 2>/dev/null | sed -n "$((RETENTION+1)),999p" | xargs -r rm -f) || true
