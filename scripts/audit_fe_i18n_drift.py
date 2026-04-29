r"""Scan TS/TSX for `t('key.path')` / `t("key.path")` / `t(\`key.path\`)`
and verify every key exists in src/i18n/locales/en.json (the canonical
locale). Reports drift in either direction:

  MISSING_KEY  — t('foo.bar') referenced but not defined in en.json
  UNUSED_KEY   — defined in en.json but no t() call references it
                 (informational only — won't fail the gate)

Exit codes:
  0 — no missing keys
  1 — missing keys found
  2 — en.json missing
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EN_JSON = ROOT / "src" / "i18n" / "locales" / "en.json"
ALLOWLIST = ROOT / "scripts" / "i18n_drift_allowlist.txt"
SCAN_DIRS = [ROOT / "src", ROOT / "app"]
EXCLUDE = {"node_modules", ".expo", ".next", "dist", "build", "ios", "web", "i18n"}

# Match `t('key.path')` / `t("key.path")` / `t(`key.path`)` — one positional
# string-literal arg. Skips dynamic keys (template literals with ${...}
# interpolation). Variant: t('key', { count: ... }) — same key extraction.
T_CALL_RE = re.compile(
    r"""\bt\(\s*(['"`])([a-zA-Z_][\w.]*)\1""", re.IGNORECASE,
)


def flatten(obj, prefix=""):
    """Flatten nested JSON to dotted keys whose leaves are strings."""
    out: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            sub = f"{prefix}.{k}" if prefix else k
            out |= flatten(v, sub)
    elif isinstance(obj, str):
        out.add(prefix)
    return out


def walk_files():
    for base in SCAN_DIRS:
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in {".ts", ".tsx"}:
                continue
            if any(part in EXCLUDE for part in p.parts):
                continue
            yield p


def main():
    if not EN_JSON.exists():
        print(f"ERROR: {EN_JSON} not found", file=sys.stderr)
        sys.exit(2)
    keys = flatten(json.loads(EN_JSON.read_text()))

    allowed: set[str] = set()
    if ALLOWLIST.exists():
        for raw in ALLOWLIST.read_text().splitlines():
            s = raw.strip()
            if s and not s.startswith("#"):
                allowed.add(s)

    missing: list[tuple[str, int, str]] = []
    used: set[str] = set()
    n_files = n_calls = 0
    for f in walk_files():
        n_files += 1
        text = f.read_text()
        for m in T_CALL_RE.finditer(text):
            key = m.group(2)
            n_calls += 1
            used.add(key)
            line = text[: m.start()].count("\n") + 1
            if key not in keys:
                missing.append((str(f.relative_to(ROOT)), line, key))

    blocking, informational = [], []
    for entry in missing:
        path, line, key = entry
        gate_key = f"{path}:MISSING_KEY:{key}"
        if gate_key in allowed:
            informational.append(entry)
        else:
            blocking.append(entry)

    unused = sorted(keys - used)

    print(f"loaded en.json: {len(keys)} keys  allowlist: {len(allowed)} entries")
    print(f"scanned: {n_files} TS/TSX files, {n_calls} t() calls")
    print(f"missing: {len(missing)} ({len(blocking)} blocking, {len(informational)} allowlisted)")
    print(f"unused (informational): {len(unused)} keys defined in en.json with no t() reference")

    def emit(rows, label):
        if not rows:
            return
        print(f"\n--- {label} ---")
        rows.sort()
        last_file = None
        for path, line, key in rows:
            if path != last_file:
                print(f"\n## {path}")
                last_file = path
            print(f"  L{line} t('{key}') — not in en.json")

    emit(blocking, "blocking missing keys")
    emit(informational, "allowlisted missing keys")
    sys.exit(1 if blocking else 0)


main()
