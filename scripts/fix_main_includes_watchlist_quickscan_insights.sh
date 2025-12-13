#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f main.py ]; then
  echo "ERROR: main.py not found" >&2
  exit 1
fi

cp main.py "main.py.bak.fixincludes.$(date +%s)"

python <<'PY'
from pathlib import Path

path = Path("main.py")
text = path.read_text()

lines = text.splitlines()

bad_markers = [
    "Auto-wired watchlist router",
    "Auto-wired quickscan advanced router",
    "Auto-wired insights router",
    "app.include_router(watchlist_router.router)",
    "app.include_router(quickscan_advanced_router.router)",
    "app.include_router(insights_router.router)",
]

cleaned: list[str] = []
for line in lines:
    if any(marker in line for marker in bad_markers):
        # drop all auto-wired and broken lines
        continue
    cleaned.append(line)

# Now append clean include block at end
cleaned.append("")
cleaned.append("# Watchlist, QuickScan advanced, Insights routers")
cleaned.append("app.include_router(watchlist_router.router)")
cleaned.append("app.include_router(quickscan_advanced_router.router)")
cleaned.append("app.include_router(insights_router.router)")

path.write_text("\n".join(cleaned))
print("Rewrote main.py includes cleanly.")
PY
