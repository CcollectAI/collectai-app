#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import sys, re

TARGET = Path("app/analytics.tsx")

def die(msg: str):
    print("[fix_analytics_scrollview_style_syntax] ERROR:", msg, file=sys.stderr)
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

    # Fix: style={{styles.page}  -> style={styles.page}
    # Keep everything else on the tag intact.
    pat = r'(<ScrollView\b[^>]*?)style=\{\{\s*styles\.page\s*\}\}(\s*contentContainerStyle=\{styles\.container\}[^>]*>)'
    m = re.search(pat, src)
    if not m:
        die("Did not find the exact broken <ScrollView style={{styles.page} ...> pattern.")

    bak = backup(TARGET)
    print("[fix_analytics_scrollview_style_syntax] Backup:", bak)

    out = re.sub(pat, r'\1style={styles.page}\2', src, count=1)
    TARGET.write_text(out, encoding="utf-8")
    print("[fix_analytics_scrollview_style_syntax] Patched:", TARGET)
    print("[fix_analytics_scrollview_style_syntax] Restart: npx expo start --tunnel --clear")

if __name__ == "__main__":
    main()
