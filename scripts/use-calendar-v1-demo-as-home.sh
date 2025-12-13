#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_DIR="$ROOT_DIR/app"
INDEX_FILE="$APP_DIR/index.tsx"
CAL_FILE="$APP_DIR/calendar-v1-demo.tsx"

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: app/ directory not found at $APP_DIR"
  exit 1
fi

if [ ! -f "$CAL_FILE" ]; then
  echo "ERROR: Calendar demo screen not found at $CAL_FILE"
  exit 1
fi

if [ ! -f "$INDEX_FILE" ]; then
  echo "ERROR: $INDEX_FILE not found."
  echo "If your root file is different (e.g. app/index.jsx), adjust this script."
  exit 1
fi

# Backup existing index.tsx
BACKUP_FILE="${INDEX_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$INDEX_FILE" "$BACKUP_FILE"
echo "Backed up existing app/index.tsx to:"
echo "  $BACKUP_FILE"

# Overwrite index.tsx to directly render the calendar V1 demo screen
cat > "$INDEX_FILE" <<'TSX'
import React from "react";
import CalendarV1DemoScreen from "./calendar-v1-demo";

export default function Index() {
  // Directly render the Calendar v1 demo screen as the home screen
  return <CalendarV1DemoScreen />;
}
TSX

echo "Replaced app/index.tsx to render CalendarV1DemoScreen as the home screen."
