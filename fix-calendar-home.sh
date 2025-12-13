#!/usr/bin/env bash
set -euo pipefail

# 1. Find the project that has app/calendar-v1-demo.tsx
ROOT_SCAN_DIR="$HOME"

echo "Scanning for calendar-v1-demo.tsx under $ROOT_SCAN_DIR ..."
CAL_FILE_PATH="$(find "$ROOT_SCAN_DIR" -maxdepth 6 -type f -name 'calendar-v1-demo.tsx' 2>/dev/null | head -n 1 || true)"

if [ -z "$CAL_FILE_PATH" ]; then
  echo "ERROR: Could not find any calendar-v1-demo.tsx under $ROOT_SCAN_DIR"
  echo "Run this from /home/ubuntu and make sure your project is in a subfolder like collectai/ or similar."
  exit 1
fi

echo "Found calendar demo file at:"
echo "  $CAL_FILE_PATH"
echo

# 2. Derive app/ and project root
APP_DIR="$(dirname "$CAL_FILE_PATH")"            # .../app
PROJECT_ROOT="$(dirname "$APP_DIR")"            # project root
INDEX_FILE="$APP_DIR/index.tsx"

echo "Assuming:"
echo "  PROJECT_ROOT = $PROJECT_ROOT"
echo "  APP_DIR      = $APP_DIR"
echo "  INDEX_FILE   = $INDEX_FILE"
echo

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: app/ directory not found at $APP_DIR"
  exit 1
fi

if [ ! -f "$INDEX_FILE" ]; then
  echo "ERROR: index.tsx not found at $INDEX_FILE"
  echo "If your root file is named differently (e.g. index.jsx), we can tweak the script."
  exit 1
fi

# 3. Backup index.tsx
BACKUP_FILE="${INDEX_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$INDEX_FILE" "$BACKUP_FILE"
echo "Backed up app/index.tsx to:"
echo "  $BACKUP_FILE"
echo

# 4. Overwrite index.tsx to render the calendar v1 demo as home
cat > "$INDEX_FILE" <<'TSX'
import React from "react";
import CalendarV1DemoScreen from "./calendar-v1-demo";

export default function Index() {
  // Directly render the Calendar v1 demo screen as the home screen
  return <CalendarV1DemoScreen />;
}
TSX

echo "✅ Replaced app/index.tsx to render CalendarV1DemoScreen as the home screen."
echo "Project root should be: $PROJECT_ROOT"
echo
echo "Next steps:"
echo "  1) cd \"$PROJECT_ROOT\""
echo "  2) Start Expo (e.g. npx expo start --tunnel --clear)"
