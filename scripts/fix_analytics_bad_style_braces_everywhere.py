#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re, sys

TARGET = Path("app/analytics.tsx")

def die(msg: str):
    print("[fix_analytics_bad_style_braces_everywhere] ERROR:", msg, file=sys.stderr)
    sys.exit(1)

def backup(p: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = Path(str(p) + ".bak_" + ts)
    bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    return bak

def main():
    if not TARGET.exists():
        die(f"File not found: {TARGET}")

    src = TARGET.read_text(encoding="utf-8")

    # Fix patterns like:
    #   style={ backgroundColor: "#F0F2F5",  alignItems: "center" }}
    # or style={ flex: 1, backgroundColor: "...", ... }}
    #
    # We target ONLY the specific broken form: style={ <key>: ... <maybe more> }}
    # i.e. "style={ ... }}" (note the double closing braces) or "style={ ... }" variants.
    patterns = [
        # style={ something: ..., somethingElse: ... }}
        (re.compile(r"style=\{\s*([a-zA-Z_]\w*\s*:\s*[^}]+?)\s*\}\}"), r"style={{ \1 }}"),
        # style={ something: ..., somethingElse: ... }
        (re.compile(r"style=\{\s*([a-zA-Z_]\w*\s*:\s*[^}]+?)\s*\}"), r"style={{ \1 }}"),
    ]

    out = src
    total = 0
    for rx, repl in patterns:
        out, n = rx.subn(repl, out)
        total += n

    if total == 0:
        die("No broken `style={ key: ... }` patterns found to fix (but bundler still errors).")

    bak = backup(TARGET)
    print("[fix_analytics_bad_style_braces_everywhere] Backup:", bak)
    print("[fix_analytics_bad_style_braces_everywhere] Fixed occurrences:", total)

    TARGET.write_text(out, encoding="utf-8")
    print("[fix_analytics_bad_style_braces_everywhere] Patched:", TARGET)
    print("[fix_analytics_bad_style_braces_everywhere] Now restart Expo.")

if __name__ == "__main__":
    main()
