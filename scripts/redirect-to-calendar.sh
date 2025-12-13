#!/usr/bin/env bash
set -euo pipefail

# Go to project root (script is assumed to live in ./scripts)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

INDEX_FILE="$ROOT_DIR/app/index.tsx"

if [ ! -f "$INDEX_FILE" ]; then
  echo "ERROR: $INDEX_FILE not found."
  echo "If your root file is different (e.g. app/index.jsx), adjust this script."
  exit 1
fi

# Backup the existing file with timestamp
BACKUP_FILE="${INDEX_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$INDEX_FILE" "$BACKUP_FILE"
echo "Backed up existing app/index.tsx to:"
echo "  $BACKUP_FILE"

# Overwrite with a minimal redirect to /calendar
cat > "$INDEX_FILE" <<'TSX'
import { Redirect } from "expo-router";

export default function Index() {
  // Temporary: always boot straight into the Calendar route
  return <Redirect href="/calendar" />;
}
TSX

echo "Replaced app/index.tsx with a redirect to /calendar."
echo "Start Expo, and the app should open directly on the Calendar screen."
