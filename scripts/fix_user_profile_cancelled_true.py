from pathlib import Path
from datetime import datetime
import re

p = Path("app/users/[userId].tsx")
s = p.read_text(encoding="utf-8")

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
bak = p.with_suffix(p.suffix + f".bak.{ts}")
bak.write_text(s, encoding="utf-8")

# Replace "cancelled = True as any" with valid JS boolean
s2 = re.sub(r"\bcancelled\s*=\s*True\s+as\s+any\s*;", "cancelled = true;", s)

# If that exact string isn't present, also catch "True;" generally in that file (very conservative)
if s2 == s:
    s2 = re.sub(r"\bTrue\b", "true", s)

p.write_text(s2, encoding="utf-8")
print(f"OK: patched {p} (backup: {bak.name})")
