#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

restore_file() {
  local target="$1"

  if [ ! -f "$target" ]; then
    echo "⚠️  Target $target does not exist yet, skipping."
    return
  fi

  local pattern="${target}.bak.*"
  local latest

  latest=$(ls -t $pattern 2>/dev/null | head -1 || true)

  if [ -z "$latest" ]; then
    echo "⚠️  No backups found for $target (pattern: $pattern)."
    return
  fi

  echo "Restoring $target from backup: $latest"
  cp "$latest" "$target"
}

echo "🔄 Restoring tab screens from latest backups..."

restore_file "app/(tabs)/index.tsx"        # Portfolio
restore_file "app/(tabs)/items.tsx"        # Items
restore_file "app/(tabs)/add.tsx"          # Add
restore_file "app/(tabs)/marketplace.tsx"  # Marketplace

echo "✅ Restore script finished. Restart Expo to see the original UI."
