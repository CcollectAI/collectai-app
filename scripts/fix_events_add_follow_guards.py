#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re, sys

TARGET = Path("app/events/[eventId].tsx")

def die(msg: str):
    print("[fix_events_add_follow_guards] ERROR:", msg, file=sys.stderr)
    sys.exit(1)

def backup(p: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = Path(str(p) + ".bak_" + ts)
    bak.write_text(p.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    return bak

def declared(src: str, name: str) -> bool:
    return re.search(rf"\b(const|let|var|function)\s+{re.escape(name)}\b", src) is not None

def main():
    if not TARGET.exists():
        die(f"File not found: {TARGET}")

    src = TARGET.read_text(encoding="utf-8", errors="ignore")

    need_isFollowing = not declared(src, "isFollowing")
    need_toggleFollow = not declared(src, "toggleFollow")
    need_savingAction = not declared(src, "savingAction")
    need_isAttending = not declared(src, "isAttending")
    need_toggleAttend = not declared(src, "toggleAttend")

    if not any([need_isFollowing, need_toggleFollow, need_savingAction, need_isAttending, need_toggleAttend]):
        print("[fix_events_add_follow_guards] Guards already present; no changes made.")
        return

    lines = src.splitlines(True)

    # Insert after last import
    last_import = -1
    for i, line in enumerate(lines):
        if line.lstrip().startswith("import "):
            last_import = i
    if last_import == -1:
        die("No import lines found; refusing to patch blindly.")

    bak = backup(TARGET)
    print("[fix_events_add_follow_guards] Backup:", bak)

    inject = []
    inject.append("\n")
    inject.append("// TEMP STABILITY GUARDS (remove once EventDetailScreen state is cleaned up)\n")
    if need_isFollowing:
        inject.append("const isFollowing: boolean = false;\n")
    if need_isAttending:
        inject.append("const isAttending: boolean = false;\n")
    if need_savingAction:
        inject.append("const savingAction: boolean = false;\n")
    if need_toggleFollow:
        inject.append("const toggleFollow = () => {};\n")
    if need_toggleAttend:
        inject.append("const toggleAttend = () => {};\n")

    out = "".join(lines[:last_import+1] + inject + lines[last_import+1:])
    TARGET.write_text(out, encoding="utf-8")
    print("[fix_events_add_follow_guards] Patched:", TARGET)

if __name__ == "__main__":
    main()
