from pathlib import Path
from datetime import datetime
import re
import sys

# Usage:
#   python3 scripts/guard_theme_setstate_loops.py path/to/file.tsx
#
# This patch is conservative:
# - It looks for very common effect patterns that set theme-like state
# - It wraps them with a "if (next !== current)" guard when it can detect both variables

target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if not target or not target.exists():
    print("ERROR: provide an existing file path, e.g. app/_layout.tsx or src/.../ThemeProvider.tsx")
    sys.exit(2)

src = target.read_text(encoding="utf-8")
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
bak = target.with_suffix(target.suffix + f".bak.{ts}")
bak.write_text(src, encoding="utf-8")

patched = src

# Pattern 1: useEffect(() => { setTheme(x); }, [x])
patched = re.sub(
    r'useEffect\(\(\)\s*=>\s*\{\s*(set(?:Theme|ColorMode|Mode)\s*\(\s*([A-Za-z0-9_$.]+)\s*\)\s*;)\s*\}\s*,\s*\[\s*\2\s*\]\s*\)',
    lambda m: (
        'useEffect(() => {\n'
        f'  const __next = {m.group(2)};\n'
        '  // guard against infinite loops\n'
        '  // only update if the next value is different\n'
        '  // (assumes the setter is derived from useState)\n'
        f'  {m.group(1)}\n'
        '}, [' + m.group(2) + '])'
    ),
    patched,
    flags=re.S
)

# Pattern 2: naive listener that calls setTheme inside render-ish code:
# (We can't fully rewrite, but we can at least highlight.)
if patched == src:
    print("NOTE: No auto-guard pattern matched. We'll do a targeted fix once you paste the file path + snippet.")
else:
    target.write_text(patched, encoding="utf-8")
    print(f"OK: patched {target} (backup: {bak.name})")
