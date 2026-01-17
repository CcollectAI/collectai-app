from pathlib import Path
from datetime import datetime
import re

p = Path("app/events/[eventId].tsx")
if not p.exists():
    raise SystemExit(f"Missing file: {p}")

src = p.read_text(encoding="utf-8")
bak = p.with_suffix(p.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
bak.write_text(src, encoding="utf-8")

text = src

# 1) Fix the exact broken cleanup line if present
text2 = re.sub(
    r"\)\s*=>\s*\{\s*mounted\s*=\s*false\s*;\s*\}\s*;",
    r"return () => { mounted = false; };",
    text
)

# 2) Also fix any accidental "mounted = True" (Pythonism) -> true
text2 = re.sub(r"\bmounted\s*=\s*True\b", "mounted = true", text2)

if text2 == src:
    print("WARN: no changes applied (pattern not found). You may have a slightly different corruption.")
else:
    p.write_text(text2, encoding="utf-8")
    print(f"OK: patched {p} (backup: {bak.name})")
