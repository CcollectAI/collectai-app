#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re, sys

TARGET = Path("app/events/[eventId].tsx")

def die(msg: str):
    print("[fix_events_guards] ERROR:", msg, file=sys.stderr)
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

    # If already declared (anywhere), don't redeclare.
    has_toggle = re.search(r"\b(const|let|var)\s+toggleAttend\b", src) is not None
    has_saving = re.search(r"\b(const|let|var)\s+savingAction\b", src) is not None
    has_att = re.search(r"\b(const|let|var)\s+isAttending\b", src) is not None

    lines = src.splitlines(True)

    # Insert right after last import
    last_import = -1
    for i, line in enumerate(lines):
        if line.lstrip().startswith("import "):
            last_import = i
    if last_import == -1:
        die("No import lines found; refusing to patch blindly.")

    inject = []
    inject.append("\n")
    inject.append("// TEMP STABILITY GUARDS (remove once EventDetailScreen is cleaned up)\n")
    if not has_att:
        inject.append("const isAttending: boolean = false;\n")
    if not has_saving:
        inject.append("const savingAction: boolean = false;\n")
    if not has_toggle:
        inject.append("const toggleAttend = () => {};\n")

    if len(inject) == 2:
        print("[fix_events_guards] Guards already exist; no changes made.")
        return

    bak = backup(TARGET)
    print("[fix_events_guards] Backup:", bak)

    out = "".join(lines[:last_import+1] + inject + lines[last_import+1:])
    TARGET.write_text(out, encoding="utf-8")
    print("[fix_events_guards] Patched:", TARGET)

if __name__ == "__main__":
    main()
