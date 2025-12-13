#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

INDEX_FILE="app/index.tsx"
BACKUP_FILE="${INDEX_FILE}.bak_entry_$(date +%s)"

if [ -f "$INDEX_FILE" ]; then
  cp "$INDEX_FILE" "$BACKUP_FILE"
  echo "📦 Backed up app/index.tsx to:"
  echo "  $BACKUP_FILE"
fi

cat > "$INDEX_FILE" <<'TSX'
import React from "react";
import { Redirect } from "expo-router";

/**
 * Root entry – send user into the tab navigator (Portfolio as default).
 */
export default function Index() {
  return <Redirect href="/(tabs)/portfolio" />;
}
TSX

echo "✅ app/index.tsx now redirects to /(tabs)/portfolio (tabs layout)."
