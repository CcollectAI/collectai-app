#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

ROOT_INDEX="app/index.tsx"

echo "=== Normalizing app/index.tsx to just redirect into (tabs) ==="

if [ -f "$ROOT_INDEX" ]; then
  BAK="${ROOT_INDEX}.bak_rootIndex_$(date +%Y%m%d-%H%M%S)"
  cp "$ROOT_INDEX" "$BAK"
  echo "📦 Backed up existing app/index.tsx to:"
  echo "   $BAK"
else
  echo "ℹ️ app/index.tsx did not exist; it will be created."
fi

cat > "$ROOT_INDEX" <<'TSX'
import React from "react";
import { Redirect } from "expo-router";

/**
 * Root entry point.
 *
 * We keep this extremely simple: always go straight into the (tabs) group,
 * where the bottom nav (Portfolio / Items / Add / Search) lives.
 */
export default function RootIndex() {
  return <Redirect href="/(tabs)" />;
}
TSX

echo "✅ app/index.tsx now only redirects to '/(tabs)'."
