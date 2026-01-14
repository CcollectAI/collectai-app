#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re, sys

TARGET = Path("app/events/[eventId].tsx")

def die(msg: str):
    print("[fix_events_inject_isAttending_near_usage] ERROR:", msg, file=sys.stderr)
    sys.exit(1)

def backup(p: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = Path(str(p) + ".bak_" + ts)
    bak.write_text(p.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    return bak

def ensure_useState_import(src: str) -> str:
    # If already using React.useState, no import needed.
    if "React.useState" in src:
        return src

    # If already imports useState from react, ok.
    if re.search(r'import\s*\{[^}]*\buseState\b[^}]*\}\s*from\s*["\']react["\']', src):
        return src

    # Patch "import React, { ... } from 'react';"
    m = re.search(r'^(import\s+React\s*,\s*\{)([^}]*)(\}\s*from\s*["\']react["\']\s*;\s*)$',
                  src, flags=re.M)
    if m:
        inside = m.group(2)
        parts = [p.strip() for p in inside.split(",") if p.strip()]
        if "useState" not in parts:
            parts.append("useState")
        new_inside = ", ".join(parts)
        return src[:m.start()] + m.group(1) + new_inside + m.group(3) + src[m.end():]

    # Patch "import { ... } from 'react';"
    m = re.search(r'^(import\s*\{)([^}]*)(\}\s*from\s*["\']react["\']\s*;\s*)$',
                  src, flags=re.M)
    if m:
        inside = m.group(2)
        parts = [p.strip() for p in inside.split(",") if p.strip()]
        if "useState" not in parts:
            parts.append("useState")
        new_inside = ", ".join(parts)
        return src[:m.start()] + m.group(1) + new_inside + m.group(3) + src[m.end():]

    # Patch "import React from 'react';" -> add separate import
    m = re.search(r'^(import\s+React\s+from\s+["\']react["\']\s*;\s*)$',
                  src, flags=re.M)
    if m:
        insert_at = m.end()
        return src[:insert_at] + '\nimport { useState } from "react";\n' + src[insert_at:]

    # No react import found -> add at top
    return 'import React, { useState } from "react";\n' + src

def find_usage_line(lines: list[str]) -> int:
    # Find the JSX usage that causes the crash
    for i, line in enumerate(lines):
        if "isAttending" in line and "styles.actionCardOn" in line:
            return i
    # Fallback: any isAttending usage
    for i, line in enumerate(lines):
        if "isAttending" in line:
            return i
    return -1

def find_enclosing_component_start(lines: list[str], from_idx: int) -> int:
    # Walk upwards to find a likely component/function start line
    patterns = [
        r'^\s*export\s+default\s+function\s+\w+\s*\([^)]*\)\s*\{',
        r'^\s*function\s+\w+\s*\([^)]*\)\s*\{',
        r'^\s*const\s+\w+\s*=\s*\([^)]*\)\s*=>\s*\{',
        r'^\s*const\s+\w+\s*=\s*\w*\s*\([^)]*\)\s*=>\s*\{',  # typed arrow
    ]
    for j in range(from_idx, -1, -1):
        for pat in patterns:
            if re.search(pat, lines[j]):
                return j
    return -1

def already_declared_in_scope(window: str) -> bool:
    return bool(re.search(r'\bconst\s*\[\s*isAttending\s*,\s*setIsAttending\s*\]\s*=\s*(React\.)?useState\(', window)) \
        or bool(re.search(r'\bconst\s+isAttending\b', window))

def main():
    if not TARGET.exists():
        die(f"File not found: {TARGET}")

    src0 = TARGET.read_text(encoding="utf-8", errors="ignore")
    if "isAttending" not in src0:
        die("No `isAttending` found in file; this patch is not applicable.")

    # Ensure useState import is available (unless using React.useState).
    src = ensure_useState_import(src0)

    lines = src.splitlines(True)
    use_idx = find_usage_line(lines)
    if use_idx < 0:
        die("Could not locate any isAttending usage line to anchor patch.")

    comp_start = find_enclosing_component_start(lines, use_idx)
    if comp_start < 0:
        die("Could not find enclosing component/function above the isAttending usage.")

    # Determine insertion point: right after the opening brace line of that component
    insert_at = comp_start + 1

    # Create a scope window (from component start to usage) and ensure not already declared there
    window = "".join(lines[comp_start:use_idx+1])
    if already_declared_in_scope(window):
        print("[fix_events_inject_isAttending_near_usage] isAttending already declared in this scope. No changes made.")
        return

    bak = backup(TARGET)
    print("[fix_events_inject_isAttending_near_usage] Backup:", bak)
    print("[fix_events_inject_isAttending_near_usage] Injecting state near component starting at line", comp_start+1)

    state_ctor = "React.useState" if "React.useState" in src else "useState"
    inject = []
    inject.append("\n")
    inject.append("  // RSVP state (stops runtime ReferenceError; wire persistence later)\n")
    inject.append(f"  const [isAttending, setIsAttending] = {state_ctor}(false);\n")

    new_lines = lines[:insert_at] + inject + lines[insert_at:]
    TARGET.write_text("".join(new_lines), encoding="utf-8")
    print("[fix_events_inject_isAttending_near_usage] Patched:", TARGET)

if __name__ == "__main__":
    main()
