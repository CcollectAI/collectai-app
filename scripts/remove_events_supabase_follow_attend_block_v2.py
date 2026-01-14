#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import sys

TARGET = Path("app/events/[eventId].tsx")

def die(msg: str):
    print("[remove_events_supabase_follow_attend_block_v2] ERROR:", msg, file=sys.stderr)
    sys.exit(1)

def backup(p: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = Path(str(p) + ".bak_" + ts)
    bak.write_text(p.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    return bak

def main():
    if not TARGET.exists():
        die(f"File not found: {TARGET}")

    lines = TARGET.read_text(encoding="utf-8", errors="ignore").splitlines(True)

    start = None
    for i, line in enumerate(lines):
        if "SUPABASE_FOLLOW_ATTEND_V1" in line:
            start = i
            break
    if start is None:
        die("Marker SUPABASE_FOLLOW_ATTEND_V1 not found.")

    # Remove marker line itself + subsequent const COL_* lines (and optional comments immediately adjacent).
    end = start
    i = start + 1

    # Skip optional comment lines right after marker
    while i < len(lines) and lines[i].lstrip().startswith("//"):
        end = i
        i += 1

    # Remove consecutive const lines that define COL_*
    removed_any_col = False
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("const COL_"):
            removed_any_col = True
            end = i
            i += 1
            continue
        break

    if not removed_any_col:
        die("Found marker but no `const COL_...` lines after it; refusing to guess.")

    bak = backup(TARGET)
    print("[remove_events_supabase_follow_attend_block_v2] Backup:", bak)
    print("[remove_events_supabase_follow_attend_block_v2] Removing lines %d..%d" % (start+1, end+1))

    new_lines = lines[:start] + lines[end+1:]
    TARGET.write_text("".join(new_lines), encoding="utf-8")

    # Sanity: marker should be gone
    chk = TARGET.read_text(encoding="utf-8", errors="ignore")
    if "SUPABASE_FOLLOW_ATTEND_V1" in chk:
        die("Marker still present after removal (unexpected).")
    print("[remove_events_supabase_follow_attend_block_v2] OK: block removed.")

if __name__ == "__main__":
    main()
