#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

restore_one() {
  local src="$1"
  local dst="$2"

  if [ ! -f "$src" ]; then
    echo "⚠️ Backup not found: $src"
    return 1
  fi

  if [ ! -f "$dst" ]; then
    echo "⚠️ Target file does not exist yet, will create: $dst"
  fi

  echo "Restoring $dst from $src"
  cp "$src" "$dst"
}

echo "🔄 Restoring tabs to older baseline versions..."

# Portfolio: older reset version
restore_one "app/(tabs)/index.tsx.bak.portfolio_reset" "app/(tabs)/index.tsx"

# Items / Add / Marketplace: older 'restore' baselines
restore_one "app/(tabs)/items.tsx.bak.restore.1764197382" "app/(tabs)/items.tsx"
restore_one "app/(tabs)/add.tsx.bak.restore.1764197382" "app/(tabs)/add.tsx"
restore_one "app/(tabs)/marketplace.tsx.bak.restore.1764197382" "app/(tabs)/marketplace.tsx"

echo "✅ Done. Now restart Expo to see the reverted UI."
