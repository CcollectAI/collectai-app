#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

SRC_DIR="$PROJECT_ROOT/src"
SRC_COMPONENTS_DIR="$SRC_DIR/components"
ROOT_COMPONENTS_FILE="$PROJECT_ROOT/components/UpcomingEventsBanner.tsx"
TARGET_FILE="$SRC_COMPONENTS_DIR/UpcomingEventsBanner.tsx"

if [ ! -f "$ROOT_COMPONENTS_FILE" ]; then
  echo "ERROR: $ROOT_COMPONENTS_FILE not found."
  echo "If you already moved it manually, you can ignore this script."
  exit 1
fi

mkdir -p "$SRC_COMPONENTS_DIR"

cp "$ROOT_COMPONENTS_FILE" "$TARGET_FILE"
echo "📦 Copied:"
echo "  $ROOT_COMPONENTS_FILE"
echo "    -> $TARGET_FILE"

# Keep original as backup but you can delete it later if you want
echo "You can delete the root-level components/UpcomingEventsBanner.tsx once you're happy."

