#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import sys
import re

TARGET = Path("app/analytics.tsx")
BG = "#F0F2F5"  # light grey

def die(msg: str):
    print("[patch_analytics_bg_light_grey] ERROR: " + msg, file=sys.stderr)
    sys.exit(1)

def backup(path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = Path(str(path) + ".bak_" + ts)
    bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return bak

def main():
    if not TARGET.exists():
        die(f"File not found: {TARGET}")

    src = TARGET.read_text(encoding="utf-8")

    bak = backup(TARGET)
    print("[patch_analytics_bg_light_grey] Backup:", bak)

    lines = src.splitlines(True)

    # Find the first return( in the main component and then patch the first top-level <View or <ScrollView
    return_idx = None
    for i, line in enumerate(lines):
        if re.search(r"^\s*return\s*\(", line):
            return_idx = i
            break
    if return_idx is None:
        die("Could not find `return (` in file.")

    # Scan forward for the first JSX container tag line
    tag_idx = None
    for i in range(return_idx, min(len(lines), return_idx + 80)):
        if "<ScrollView" in lines[i] or "<View" in lines[i]:
            tag_idx = i
            break
    if tag_idx is None:
        die("Could not find a <View> or <ScrollView> near the return().")

    tag_line = lines[tag_idx]

    # Case 1: style={{ ... }} exists on same line, add/replace backgroundColor
    if "style={{" in tag_line:
        # If backgroundColor already exists in that inline object, replace its value
        if "backgroundColor" in tag_line:
            tag_line = re.sub(r"backgroundColor\s*:\s*[^,}]+", f'backgroundColor: "{BG}"', tag_line)
        else:
            # Insert backgroundColor right after the opening {{
            tag_line = tag_line.replace("style={{", f'style={{ backgroundColor: "{BG}", ')
        lines[tag_idx] = tag_line

    # Case 2: style= exists but not style={{ ... }} on same line (e.g., style={styles.container} or style={[...]}
    elif "style=" in tag_line:
        # Wrap existing style into an array with our bg first
        # style={X}  -> style={[{ flex: 1, backgroundColor: "..." }, X]}
        tag_line = re.sub(
            r"style=\{\s*([^}]+)\s*\}",
            r'style={[{ flex: 1, backgroundColor: "' + BG + r'" }, \1]}',
            tag_line
        )
        lines[tag_idx] = tag_line

    # Case 3: no style prop at all on the container line; add one
    else:
        # Add style prop before the closing > (same line)
        if ">" in tag_line:
            tag_line = tag_line.replace(">", f' style={{ flex: 1, backgroundColor: "{BG}" }}>')
            lines[tag_idx] = tag_line
        else:
            # If the tag is split across lines, insert a new style line right after it
            lines.insert(tag_idx + 1, f'        style={{ flex: 1, backgroundColor: "{BG}" }}\n')

    out = "".join(lines)
    TARGET.write_text(out, encoding="utf-8")
    print("[patch_analytics_bg_light_grey] Patched:", TARGET)
    print("[patch_analytics_bg_light_grey] Restart Expo.")

if __name__ == "__main__":
    main()
