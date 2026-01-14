#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import sys

TARGET = Path("app/analytics.tsx")

def die(msg: str):
    print("[fix_analytics_style_braces_linewise] ERROR:", msg, file=sys.stderr)
    sys.exit(1)

def backup(p: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = Path(str(p) + ".bak_" + ts)
    bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    return bak

def fix_line(line: str) -> tuple[str, bool]:
    # Fix only single-line JSX style props of the form:
    #   style={ ... }>
    # where ... is intended as an object, but braces are wrong.
    if "style={" not in line:
        return line, False
    if "style={{" in line:
        return line, False  # already correct

    new = line

    # Replace opening: style={  -> style={{
    new = new.replace("style={", "style={{", 1)

    # Ensure closing has double braces before the tag closes.
    # If line already contains "}}>" after this, it's fine.
    if "}}>" in new:
        return new, (new != line)

    # If it ends the attribute as "}>", change to "}}>"
    # Only change the FIRST occurrence, and only if we now have style={{ on this line.
    if "style={{" in new and "}>" in new:
        new = new.replace("}>", "}}>", 1)

    return new, (new != line)

def main():
    if not TARGET.exists():
        die(f"File not found: {TARGET}")

    src = TARGET.read_text(encoding="utf-8")
    lines = src.splitlines(True)

    changed_any = False
    fixed_count = 0

    out_lines = []
    for ln in lines:
        fixed, changed = fix_line(ln)
        out_lines.append(fixed)
        if changed:
            changed_any = True
            fixed_count += 1

    if not changed_any:
        die("No lines matched the broken `style={ ... }` pattern. (But bundler still errors.)")

    bak = backup(TARGET)
    print("[fix_analytics_style_braces_linewise] Backup:", bak)
    print("[fix_analytics_style_braces_linewise] Lines fixed:", fixed_count)

    TARGET.write_text("".join(out_lines), encoding="utf-8")
    print("[fix_analytics_style_braces_linewise] Patched:", TARGET)
    print("[fix_analytics_style_braces_linewise] Restart Expo now.")

if __name__ == "__main__":
    main()
