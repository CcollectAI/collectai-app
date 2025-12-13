#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p app
[ -f app/__init__.py ] || echo '"""App package init"""' > app/__init__.py

python <<'PY'
from pathlib import Path
import re
from typing import Any

main_path = Path("main.py")
if not main_path.exists():
    raise SystemExit("main.py not found in current directory")

text = main_path.read_text()

# Match lines like: from app.db import connect_pool, close_pool, db_configured
pattern = re.compile(r'^from\s+app\.([a-zA-Z0-9_\.]+)\s+import\s+(.+)$', re.MULTILINE)

modules: dict[str, set[str]] = {}

for m in pattern.finditer(text):
    mod = m.group(1)    # e.g. 'db' or 'routers.vision_commit'
    names_raw = m.group(2)
    names: list[str] = []

    for part in names_raw.split(','):
        part = part.strip()
        if not part:
            continue
        if ' as ' in part:
            src, _alias = part.split(' as ', 1)
            names.append(src.strip())
        else:
            names.append(part)

    modules.setdefault(mod, set()).update(names)

for mod, names in modules.items():
    parts = mod.split('.')
    pkg_parts = parts[:-1]
    leaf = parts[-1]

    base = Path("app")
    # Ensure intermediate packages exist with __init__.py
    for p in pkg_parts:
        base = base / p
        base.mkdir(exist_ok=True)
        init = base / "__init__.py"
        if not init.exists():
            init.write_text('"""auto-stub package"""\\n')

    if pkg_parts:
        file_path = base / f"{leaf}.py"
    else:
        file_path = Path("app") / f"{leaf}.py"

    if file_path.exists():
        print(f"Skipping existing module: {file_path}")
        continue

    print(f"Creating stub module: {file_path} for imports {names}")

    lines: list[str] = []
    lines.append('"""auto-generated stub module for main.py imports"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("from typing import Any")
    lines.append("try:")
    lines.append("    from fastapi import APIRouter")
    lines.append("except Exception:  # pragma: no cover")
    lines.append("    APIRouter = object  # type: ignore")
    lines.append("")

    for name in sorted(names):
        if name == "router":
            # For router imports, expose an empty APIRouter instance
            lines.append("router = APIRouter()  # type: ignore")
            lines.append("")
        else:
            # Generic async no-op function stub – works for startup hooks, middleware, etc.
            lines.append(f"async def {name}(*args: Any, **kwargs: Any) -> Any:  # type: ignore")
            lines.append("    return None")
            lines.append("")

    file_path.write_text("\\n".join(lines))

PY
