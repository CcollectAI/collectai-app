#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <relative-calendar-path-from-app>"
  echo
  echo "Examples:"
  echo "  $0 'calendar/index'"
  echo "  $0 '(tabs)/calendar'"
  echo "  $0 'screens/calendar/CalendarScreen'"
  exit 1
fi

CAL_PATH="$1"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_DIR="$ROOT_DIR/app"
INDEX_FILE="$APP_DIR/index.tsx"

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: app/ directory not found at $APP_DIR"
  exit 1
fi

if [ ! -f "$INDEX_FILE" ]; then
  echo "ERROR: $INDEX_FILE not found."
  echo "If your root file is different (e.g. app/index.jsx), adjust this script."
  exit 1
fi

# Try to resolve the actual calendar file, trying TSX/JSX/TS/JS extensions.
CAL_FILE=""
for ext in tsx jsx ts js; do
  if [ -f "$APP_DIR/$CAL_PATH.$ext" ]; then
    CAL_FILE="$APP_DIR/$CAL_PATH.$ext"
    break
  fi
done

if [ -z "$CAL_FILE" ]; then
  echo "ERROR: Could not find a file at app/${CAL_PATH}.tsx/jsx/ts/js"
  echo "Double-check the path you passed matches what locate-calendar.sh printed."
  exit 1
fi

echo "Found Calendar screen file at: $CAL_FILE"

# Backup existing index.tsx
BACKUP_FILE="${INDEX_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$INDEX_FILE" "$BACKUP_FILE"
echo "Backed up existing app/index.tsx to:"
echo "  $BACKUP_FILE"

# Compute relative import path from app/index.tsx to the calendar file.
# Since both are under app/, and index.tsx is directly inside app/,
# we can import as "./<CAL_PATH>" (without extension).
REL_IMPORT="./${CAL_PATH}"

cat > "$INDEX_FILE" <<TSX
import React from "react";
import CalendarScreen from "${REL_IMPORT}";

export default function Index() {
  // Directly render the Calendar screen component as the home screen
  return <CalendarScreen />;
}
TSX

echo "Wired Calendar as the home screen via app/index.tsx."
echo "Next: start Expo (ideally in tunnel mode) and you should see the Calendar directly."
