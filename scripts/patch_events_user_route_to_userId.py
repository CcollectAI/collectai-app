from pathlib import Path
from datetime import datetime
import re

p = Path("app/(tabs)/events.tsx")
s = p.read_text(encoding="utf-8")

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
bak = p.with_suffix(p.suffix + f".bak.{ts}")
bak.write_text(s, encoding="utf-8")

# Change pathname "/users/[id]" -> "/users/[userId]"
s2 = s.replace('pathname: "/users/[id]"', 'pathname: "/users/[userId]"')

# Also rename params key if present: { id: userId } -> { userId: userId }
# handles id: something
s2 = re.sub(r"\bparams:\s*\{\s*id\s*:\s*", "params: { userId: ", s2)

p.write_text(s2, encoding="utf-8")
print(f"OK: patched {p} (backup: {bak.name})")
