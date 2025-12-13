#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/items.tsx"

if [ ! -f "$FILE" ]; then
  echo "Items tab not found at $FILE"
  exit 1
fi

cp "$FILE" "${FILE}.bak.imports-v2-$(date +%s)" || true

python << 'PY'
from pathlib import Path

path = Path("app/(tabs)/items.tsx")
text = path.read_text()
lines = text.splitlines()

react_idx = None
for i, line in enumerate(lines):
    if "import React" in line:
        react_idx = i
        break

if react_idx is None:
    raise SystemExit("Could not find 'import React' in items.tsx")

new_block = [
    "import React, { useEffect, useMemo, useState } from 'react';",
    "import { useAppTheme } from '@/hooks/useAppTheme';",
]

# Replace the first 2 lines after the React import with a clean block
# (covers the broken line we created earlier)
end_idx = min(react_idx + 2, len(lines))
lines[react_idx:end_idx] = new_block

path.write_text("\n".join(lines))
PY

echo "Rewrote React/useAppTheme imports in app/(tabs)/items.tsx. Backup created."
