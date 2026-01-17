from pathlib import Path
from datetime import datetime
import re

FILES = [
    Path("src/state/colorModeStore.ts"),
    Path("src/theme/colors.ts"),
]

ts = datetime.now().strftime("%Y%m%d_%H%M%S")

def backup(p: Path, text: str):
    bak = p.with_suffix(p.suffix + f".bak.{ts}")
    bak.write_text(text, encoding="utf-8")
    return bak

def patch_text(text: str) -> str:
    out = text

    # 1) Force a stable default to light if we see common patterns
    # Examples: let currentMode = "dark";  or let currentMode: ColorMode = ...
    out = re.sub(
        r'(\blet\s+currentMode\b[^=]*=\s*)(["\'])(light|dark)(["\'])\s*;',
        r'\1"light";',
        out
    )
    out = re.sub(
        r'(\bconst\s+currentMode\b[^=]*=\s*)(["\'])(light|dark)(["\'])\s*;',
        r'\1"light";',
        out
    )

    # 2) Disable the dangerous auto-toggle line (the exact pattern you hit)
    # setColorMode(currentMode === "light" ? "dark" : "light");
    out = re.sub(
        r'^\s*setColorMode\(\s*currentMode\s*===\s*["\']light["\']\s*\?\s*["\']dark["\']\s*:\s*["\']light["\']\s*\)\s*;\s*$',
        lambda m: "// DISABLED: was auto-toggling color mode and could cause infinite re-render loops\n"
                  "// " + m.group(0).lstrip(),
        out,
        flags=re.M
    )

    # 3) Comment out any top-level toggleColorMode() calls (rare but deadly if present)
    # This is a conservative pass: if a line is exactly "toggleColorMode();" we comment it.
    out = re.sub(
        r'^\s*toggleColorMode\(\s*\)\s*;\s*$',
        lambda m: "// DISABLED: top-level toggleColorMode() (can cause infinite loops)\n"
                  "// " + m.group(0).lstrip(),
        out,
        flags=re.M
    )

    return out

changed_any = False

for p in FILES:
    if not p.exists():
        print(f"SKIP: {p} (missing)")
        continue
    original = p.read_text(encoding="utf-8")
    patched = patch_text(original)
    if patched != original:
        bak = backup(p, original)
        p.write_text(patched, encoding="utf-8")
        print(f"OK: patched {p} (backup: {bak.name})")
        changed_any = True
    else:
        print(f"NOTE: no changes needed in {p}")

if not changed_any:
    print("NOTE: Nothing changed. If loop persists, it's in a different file (we'll target it next).")
