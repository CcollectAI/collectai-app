#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import sys
import re

TARGET = Path("app/events/[eventId].tsx")

def die(msg: str):
    print("[fix_events_define_isAttending] ERROR:", msg, file=sys.stderr)
    sys.exit(1)

def backup(p: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = Path(str(p) + ".bak_" + ts)
    bak.write_text(p.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    return bak

def patch_react_import(src: str) -> str:
    # If file already uses React.useState, we don't need named import.
    if "React.useState" in src:
        return src

    # If useState already imported from react, nothing to do.
    if re.search(r'import\s*\{[^}]*\buseState\b[^}]*\}\s*from\s*["\']react["\']', src):
        return src

    # Patch existing react import:
    # import React, { useEffect } from "react";
    m = re.search(r'^\s*import\s+React\s*,\s*\{([^}]*)\}\s*from\s*["\']react["\']\s*;\s*$',
                  src, flags=re.M)
    if m:
        inside = m.group(1).strip()
        if inside:
            parts = [p.strip() for p in inside.split(",") if p.strip()]
        else:
            parts = []
        if "useState" not in parts:
            parts.append("useState")
        new_inside = ", ".join(parts)
        return src[:m.start()] + f'import React, {{ {new_inside} }} from "react";\n' + src[m.end():]

    # import { useEffect } from "react";
    m = re.search(r'^\s*import\s*\{([^}]*)\}\s*from\s*["\']react["\']\s*;\s*$',
                  src, flags=re.M)
    if m:
        inside = m.group(1).strip()
        parts = [p.strip() for p in inside.split(",") if p.strip()]
        if "useState" not in parts:
            parts.append("useState")
        new_inside = ", ".join(parts)
        return src[:m.start()] + f'import {{ {new_inside} }} from "react";\n' + src[m.end():]

    # import React from "react";
    m = re.search(r'^\s*import\s+React\s+from\s+["\']react["\']\s*;\s*$', src, flags=re.M)
    if m:
        insert_at = m.end()
        return src[:insert_at] + '\nimport { useState } from "react";\n' + src[insert_at:]

    # No react import line found; add safe one at top.
    return 'import React, { useState } from "react";\n' + src

def insert_state_in_event_detail(src: str) -> str:
    # If already declared anywhere, do nothing.
    if re.search(r'\bconst\s*\[\s*isAttending\s*,\s*setIsAttending\s*\]\s*=\s*(React\.)?useState\(', src):
        return src

    # Find EventDetailScreen start.
    m = re.search(r'(export\s+default\s+function\s+EventDetailScreen\s*\([^)]*\)\s*\{)', src)
    if not m:
        m = re.search(r'(\bfunction\s+EventDetailScreen\s*\([^)]*\)\s*\{)', src)
    if not m:
        die("Could not find `EventDetailScreen` function.")

    start = m.end()

    # Search a small window for an existing state line to anchor insertion
    window = src[start:start+6000]

    # Prefer after isFollowing state if present
    m_follow = re.search(r'^\s*const\s*\[\s*isFollowing\s*,\s*setIsFollowing\s*\]\s*=\s*(React\.)?useState\([^\)]*\)\s*;\s*$',
                         window, flags=re.M)
    if m_follow:
        ins_at = start + m_follow.end()
        state_ctor = "React.useState" if "React.useState" in src else "useState"
        inject = f'\n  const [isAttending, setIsAttending] = {state_ctor}(false);\n'
        return src[:ins_at] + inject + src[ins_at:]

    # Else after savingAction state if present
    m_save = re.search(r'^\s*const\s*\[\s*savingAction\s*,\s*setSavingAction\s*\]\s*=\s*(React\.)?useState\([^\)]*\)\s*;\s*$',
                       window, flags=re.M)
    if m_save:
        ins_at = start + m_save.end()
        state_ctor = "React.useState" if "React.useState" in src else "useState"
        inject = f'\n  const [isAttending, setIsAttending] = {state_ctor}(false);\n'
        return src[:ins_at] + inject + src[ins_at:]

    # Fallback: insert near top of component (right after opening brace)
    state_ctor = "React.useState" if "React.useState" in src else "useState"
    inject = f'\n  const [isAttending, setIsAttending] = {state_ctor}(false);\n'
    return src[:start] + inject + src[start:]

def main():
    if not TARGET.exists():
        die(f"File not found: {TARGET}")

    src = TARGET.read_text(encoding="utf-8", errors="ignore")
    bak = backup(TARGET)
    print("[fix_events_define_isAttending] Backup:", bak)

    # 1) Ensure useState available (unless using React.useState already)
    src2 = patch_react_import(src)

    # 2) Insert isAttending in EventDetailScreen scope
    src3 = insert_state_in_event_detail(src2)

    TARGET.write_text(src3, encoding="utf-8")
    print("[fix_events_define_isAttending] Patched:", TARGET)

    # Sanity check (no questions, just informative)
    chk = TARGET.read_text(encoding="utf-8", errors="ignore")
    ok = bool(re.search(r'\bconst\s*\[\s*isAttending\s*,\s*setIsAttending\s*\]\s*=\s*(React\.)?useState\(', chk))
    print("[fix_events_define_isAttending] isAttending state present:", "YES" if ok else "NO")

if __name__ == "__main__":
    main()
