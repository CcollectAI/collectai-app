#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import sys
import re

TARGET = Path("app/events/[eventId].tsx")

def die(msg: str):
    print("[fix_events_define_isAttending_module_scope] ERROR:", msg, file=sys.stderr)
    sys.exit(1)

def backup(p: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = Path(str(p) + ".bak_" + ts)
    bak.write_text(p.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    return bak

def main():
    if not TARGET.exists():
        die(f"File not found: {TARGET}")

    src = TARGET.read_text(encoding="utf-8", errors="ignore")

    # If already declared somewhere, do nothing.
    if re.search(r"\b(const|let|var)\s+isAttending\b", src):
        print("[fix_events_define_isAttending_module_scope] isAttending already declared; no changes made.")
        return

    bak = backup(TARGET)
    print("[fix_events_define_isAttending_module_scope] Backup:", bak)

    lines = src.splitlines(True)

    # Insert right after the last import line.
    last_import = -1
    for i, line in enumerate(lines):
        if line.lstrip().startswith("import "):
            last_import = i

    if last_import == -1:
        die("No import lines found; refusing to patch blindly.")

    inject = []
    inject.append("\n")
    inject.append("// TEMP STABILITY GUARD: prevents runtime ReferenceError while file is being cleaned up\n")
    inject.append("const isAttending: boolean = false;\n")

    out = "".join(lines[:last_import+1] + inject + lines[last_import+1:])
    TARGET.write_text(out, encoding="utf-8")
    print("[fix_events_define_isAttending_module_scope] Patched:", TARGET)

if __name__ == "__main__":
    main()
