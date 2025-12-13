#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f main.py ]; then
  echo "ERROR: main.py not found" >&2
  exit 1
fi

cp main.py "main.py.bak.screenshotfix.$(date +%s)"

python <<'PY'
from pathlib import Path

path = Path("main.py")
text = path.read_text()

broken = r"\n\n# Auto-wired screenshot intel router\napp.include_router(screenshot_intel_router.router)"

if broken in text:
    text = text.replace(broken, "")
    print("Removed broken auto-wired screenshot intel include line.")
else:
    print("Broken screenshot intel include not found; nothing to remove.")

# Ensure we have a clean include line somewhere
if "app.include_router(screenshot_intel_router.router)" not in text:
    # Append a clean include at the end
    if not text.endswith("\n"):
        text += "\n"
    text += "\n# Screenshot intel router\napp.include_router(screenshot_intel_router.router)\n"
    print("Appended clean screenshot_intel_router include at end of main.py")

path.write_text(text)
PY
