from pathlib import Path
from datetime import datetime
import re

p = Path("app/events/[eventId].tsx")
if not p.exists():
    raise SystemExit(f"Missing: {p}")

src = p.read_text(encoding="utf-8")
bak = p.with_suffix(p.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
bak.write_text(src, encoding="utf-8")

# Fix the exact bad pattern:
# return (
#   {/* comment */}
#   <View ...>
pat = r"return\s*\(\s*\n(\s*)\{\s*/\*\s*Ingress:\s*Category\s*->\s*Category\s*Card\s*\*/\s*\}\s*\n\1<"
m = re.search(pat, src)
if not m:
    print("No matching bad ingress pattern found. No changes made.")
    raise SystemExit(0)

indent = m.group(1)

# 1) Insert fragment start right after "return ("
src2 = re.sub(r"return\s*\(\s*\n", "return (\n" + indent + "<>\n", src, count=1)

# 2) Ensure the ingress comment+View are indented under fragment
src2 = re.sub(
    r"\n" + re.escape(indent) + r"\{\s*/\*\s*Ingress:\s*Category\s*->\s*Category\s*Card\s*\*/\s*\}\s*\n" + re.escape(indent) + r"<",
    "\n" + indent + "  {/* Ingress: Category -> Category Card */}\n" + indent + "  <",
    src2,
    count=1,
)

# 3) Close fragment just before the FIRST ");" that closes this return
# (we insert before the first line that is exactly "<indent>);")
close_pat = r"\n" + re.escape(indent) + r"\);\s*$"
m2 = re.search(close_pat, src2, flags=re.M)
if not m2:
    print("Couldn't find return close line to insert </>. Reverting.")
    bak.write_text(src, encoding="utf-8")
    raise SystemExit(1)

src2 = re.sub(close_pat, "\n" + indent + "</>\n" + indent + ");", src2, count=1, flags=re.M)

p.write_text(src2, encoding="utf-8")
print(f"OK: patched {p} (backup: {bak.name})")
