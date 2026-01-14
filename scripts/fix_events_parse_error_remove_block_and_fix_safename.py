#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import sys
import re

TARGET = Path("app/events/[eventId].tsx")

def die(msg: str):
    print("[fix_events_parse_error] ERROR:", msg, file=sys.stderr)
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
    lines = src.splitlines(True)

    bak = backup(TARGET)
    print("[fix_events_parse_error] Backup:", bak)

    # --- (A) Remove SUPABASE_FOLLOW_ATTEND_V1 block exactly as shown ---
    start = None
    for i, line in enumerate(lines):
        if "SUPABASE_FOLLOW_ATTEND_V1" in line:
            start = i
            break
    if start is None:
        print("[fix_events_parse_error] Marker not found; skipping block removal.")
    else:
        end = start
        i = start + 1

        # eat comment lines after marker
        while i < len(lines) and lines[i].lstrip().startswith("//"):
            end = i
            i += 1

        # eat consecutive const COL_* lines
        removed_any = False
        while i < len(lines):
            if lines[i].strip().startswith("const COL_"):
                removed_any = True
                end = i
                i += 1
                continue
            break

        if removed_any:
            print("[fix_events_parse_error] Removing block lines %d..%d" % (start+1, end+1))
            lines = lines[:start] + lines[end+1:]
        else:
            print("[fix_events_parse_error] Marker found but no const COL_* lines after it; skipping block removal.")

    # --- (B) Fix the common parse-breaker: "const safeName =" with no RHS ---
    # Pattern: a line that ends with "=" (possibly with spaces) and is for safeName.
    fixed_safe = 0
    for idx in range(len(lines)):
        if re.match(r'^\s*const\s+safeName\s*=\s*$', lines[idx].rstrip("\n")):
            # Replace with a sane default
            indent = re.match(r'^(\s*)', lines[idx]).group(1)
            lines[idx] = indent + 'const safeName = (name || "").trim();\n'
            fixed_safe += 1

    if fixed_safe:
        print(f"[fix_events_parse_error] Fixed incomplete safeName assignment: {fixed_safe}")

    TARGET.write_text("".join(lines), encoding="utf-8")
    print("[fix_events_parse_error] Patched:", TARGET)

    # Quick sanity: marker should be gone
    chk = TARGET.read_text(encoding="utf-8", errors="ignore")
    if "SUPABASE_FOLLOW_ATTEND_V1" in chk:
        print("[fix_events_parse_error] WARNING: marker still present (unexpected).")

if __name__ == "__main__":
    main()
