#!/usr/bin/env bash
set -e

FILE="src/theme.ts"

if [ ! -f "$FILE" ]; then
  echo "❌ ERROR: $FILE not found"
  exit 1
fi

TS=$(date +%Y%m%d_%H%M%S)
cp "$FILE" "$FILE.bak_runtimefix_$TS"
echo "✅ Backup created: $FILE.bak_runtimefix_$TS"

cat > "$FILE" <<'TSX'
// SAFE THEME EXPORT
// This file must NEVER throw at import-time.

export type ThemeColors = {
  background?: string;
  tiffany?: string;
  navy?: string;
};

export type Theme = {
  colors?: ThemeColors;
};

// Default fallback theme (safe)
export const theme: Theme = {
  colors: {
    background: "#f3f4f6",
    tiffany: "#14b8a6",
    navy: "#0b1f3a",
  },
};

export default theme;
TSX

echo "✅ theme.ts patched to safe baseline."
