#!/usr/bin/env bash
set -euo pipefail

python << 'PY'
from pathlib import Path
import glob
import os

target = Path("app/(tabs)/portfolio.tsx")

if not target.exists():
    print("Portfolio file not found at", target)
    raise SystemExit(1)

backups = glob.glob("app/(tabs)/portfolio.tsx.bak*")
if not backups:
    print("No backup files found matching app/(tabs)/portfolio.tsx.bak*")
    raise SystemExit(1)

# Sort backups by modification time (newest first)
backups.sort(key=os.path.getmtime, reverse=True)
latest = backups[0]
print("Restoring portfolio from backup:", latest)

backup_path = Path(latest)
target.write_text(backup_path.read_text())
PY

echo "Old portfolio implementation restored to app/(tabs)/portfolio.tsx"
