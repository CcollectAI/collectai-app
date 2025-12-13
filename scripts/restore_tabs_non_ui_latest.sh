#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

restore_tab() {
  local target="$1"

  if [ ! -f "$target" ]; then
    echo "⚠️ Target $target does not exist, skipping."
    return
  fi

  local pattern="${target}.bak.*"
  local latest

  # Pick the most recent backup that does NOT contain 'ui_' in its name
  latest=$(ls -t $pattern 2>/dev/null | grep -v 'ui_' | head -1 || true)

  if [ -z "$latest" ]; then
    echo "⚠️ No non-ui backups found for $target (pattern: $pattern)."
    return
  fi

  echo "Restoring $target from backup: $latest"
  cp "$latest" "$target"
}

echo "🔄 Restoring tab screens from latest non-ui backups (likely 28/11)..."

restore_tab "app/(tabs)/index.tsx"        # Portfolio
restore_tab "app/(tabs)/items.tsx"        # Items
restore_tab "app/(tabs)/add.tsx"          # Add
restore_tab "app/(tabs)/marketplace.tsx"  # Marketplace

echo "✅ Restore finished. Restart Expo to see the reverted UI."
