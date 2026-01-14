#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re, sys

TARGET = Path("app/events/[eventId].tsx")

def die(msg: str):
    print("[fix_events_add_useEffect_import] ERROR:", msg, file=sys.stderr)
    sys.exit(1)

def backup(p: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = Path(str(p) + ".bak_" + ts)
    bak.write_text(p.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    return bak

def add_to_named_import(src: str, name: str) -> str:
    # import React, { ... } from "react";
    m = re.search(r'^(import\s+React\s*,\s*\{)([^}]*)\}(\s*from\s*["\']react["\']\s*;)\s*$',
                  src, flags=re.M)
    if m:
        inside = m.group(2)
        parts = [p.strip() for p in inside.split(",") if p.strip()]
        if name not in parts:
            parts.append(name)
        new_inside = ", ".join(parts)
        return src[:m.start()] + m.group(1) + new_inside + "}" + m.group(3) + "\n" + src[m.end():]

    # import { ... } from "react";
    m = re.search(r'^(import\s*\{)([^}]*)\}(\s*from\s*["\']react["\']\s*;)\s*$',
                  src, flags=re.M)
    if m:
        inside = m.group(2)
        parts = [p.strip() for p in inside.split(",") if p.strip()]
        if name not in parts:
            parts.append(name)
        new_inside = ", ".join(parts)
        return src[:m.start()] + m.group(1) + new_inside + "}" + m.group(3) + "\n" + src[m.end():]

    return src

def main():
    if not TARGET.exists():
        die(f"File not found: {TARGET}")

    src = TARGET.read_text(encoding="utf-8", errors="ignore")

    # If file already uses React.useEffect, nothing to do.
    if "React.useEffect" in src:
        print("[fix_events_add_useEffect_import] File uses React.useEffect already; no changes made.")
        return

    # If useEffect already imported, nothing to do.
    if re.search(r'import\s*\{[^}]*\buseEffect\b[^}]*\}\s*from\s*["\']react["\']', src):
        print("[fix_events_add_useEffect_import] useEffect already imported; no changes made.")
        return

    bak = backup(TARGET)
    print("[fix_events_add_useEffect_import] Backup:", bak)

    out = src

    # Ensure we have at least one React import. If not, add one at top.
    if not re.search(r'^\s*import\b.*from\s*["\']react["\']', out, flags=re.M):
        out = 'import React, { useEffect, useState } from "react";\n' + out
    else:
        # Add useEffect and useState to existing named import(s) if needed
        out = add_to_named_import(out, "useEffect")
        # also ensure useState exists because file uses it too
        if "React.useState" not in out and not re.search(r'import\s*\{[^}]*\buseState\b[^}]*\}\s*from\s*["\']react["\']', out):
            out = add_to_named_import(out, "useState")

        # If React is imported without braces (import React from "react";), add separate named import
        if re.search(r'^\s*import\s+React\s+from\s+["\']react["\']\s*;\s*$', out, flags=re.M) and \
           not re.search(r'^\s*import\s*\{[^}]*\}\s*from\s*["\']react["\']\s*;\s*$', out, flags=re.M):
            out = re.sub(r'^(import\s+React\s+from\s+["\']react["\']\s*;\s*)$',
                         r'\1\nimport { useEffect, useState } from "react";\n',
                         out, flags=re.M, count=1)

    TARGET.write_text(out, encoding="utf-8")
    print("[fix_events_add_useEffect_import] Patched:", TARGET)

if __name__ == "__main__":
    main()
