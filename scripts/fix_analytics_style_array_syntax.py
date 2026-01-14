#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import sys

TARGET = Path("app/analytics.tsx")

def die(msg: str):
    print("[fix_analytics_style_array_syntax] ERROR:", msg, file=sys.stderr)
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

    needle = 'style={{[styles.page, { alignItems: "center", justifyContent: "center" }]}}'
    if needle not in src:
        die("Exact broken style pattern not found. Paste lines 370-390 if it differs.")

    bak = backup(TARGET)
    print("[fix_analytics_style_array_syntax] Backup:", bak)

    out = src.replace(
        needle,
        'style={[styles.page, { alignItems: "center", justifyContent: "center" }]}'
    )

    TARGET.write_text(out, encoding="utf-8")
    print("[fix_analytics_style_array_syntax] Patched:", TARGET)
    print("[fix_analytics_style_array_syntax] Restart Expo: npx expo start --tunnel --clear")

if __name__ == "__main__":
    main()
