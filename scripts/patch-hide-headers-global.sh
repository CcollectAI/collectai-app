#!/usr/bin/env bash
set -euo pipefail

FILE="app/_layout.tsx"

if [ ! -f "$FILE" ]; then
  echo "ERROR: $FILE not found. Aborting."
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
cp "$FILE" "${FILE}.bak_${TS}"

# Replace the file with a minimal, safe Stack that hides headers everywhere.
# This avoids “title banner” across non-tab screens too.
cat > "$FILE" <<'TSX'
import React from "react";
import { Stack } from "expo-router";

export default function RootLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false, // remove title banner everywhere
      }}
    />
  );
}
TSX

echo "OK: Root headers disabled"
echo "Backup: ${FILE}.bak_${TS}"
