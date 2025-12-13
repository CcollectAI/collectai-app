#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Decide which main file to use: prefer main.py, else app/main.py
if [ -f "main.py" ]; then
  MAIN_FILE="main.py"
elif [ -f "app/main.py" ]; then
  MAIN_FILE="app/main.py"
else
  echo "ERROR: Could not find main.py or app/main.py" >&2
  exit 1
fi

echo "Using main file: $MAIN_FILE"

# Backup with timestamp
cp "$MAIN_FILE" "$MAIN_FILE.bak.$(date +%s)"

python <<'PY'
from pathlib import Path

candidates = ["main.py", "app/main.py"]
main_path = None
for c in candidates:
    p = Path(c)
    if p.exists():
        main_path = p
        break

if main_path is None:
    raise SystemExit("No main file found.")

text = main_path.read_text()

import_line = "from app.features import alerts_feature_router\n"
include_line = "app.include_router(alerts_feature_router.router)\n"

# Add import if missing
if "alerts_feature_router" not in text:
    # Put import near the top
    text = import_line + text

# Add include_router if missing
if "app.include_router(alerts_feature_router.router)" not in text:
    if not text.endswith("\n"):
        text += "\n"
    text += "\n# Auto-wired alerts router\n" + include_line

main_path.write_text(text)
print(f"alerts_feature_router wired into {main_path}")
PY

echo "Done."
