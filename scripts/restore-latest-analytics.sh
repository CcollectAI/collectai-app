#!/usr/bin/env bash
set -euo pipefail

python << 'PY'
from pathlib import Path
import glob, os

target = Path("app/analytics.tsx")
if not target.exists():
    print("analytics.tsx not found at", target)
    raise SystemExit(1)

backups = glob.glob("app/analytics.tsx.bak*")
if not backups:
    print("No analytics.tsx.bak* backups found.")
    raise SystemExit(1)

backups.sort(key=os.path.getmtime, reverse=True)
latest = backups[0]
print("Restoring analytics.tsx from backup:", latest)
Path(target).write_text(Path(latest).read_text())
PY

echo "analytics.tsx restored from latest backup."
