"""Scan TS/TSX for `supabase.from('table').select(...)` /update/insert
patterns and cross-check column names against a live schema dump.

Limited but pragmatic — handles literal selects, literal filters, and
literal update payload keys. Skips dynamic patches and template-literal
column lists.
"""
import json, re, sys
from pathlib import Path

ROOT = Path("/Users/merle/GitHub/CcollectAI")
SCAN_DIRS = [ROOT / "src", ROOT / "app"]
EXCLUDE = {"node_modules", ".expo", ".next", "dist", "build", "ios", "web"}

FROM_RE = re.compile(
    r"""\.from\(\s*['"]([a-z_][a-z0-9_]*)['"]\s*\)([\s\S]{0,800}?)(?=\.from\(|\n\s*\}|\n\s*export |\n\s*function |\n\s*const |$)""",
    re.IGNORECASE,
)
SELECT_RE = re.compile(r"""\.select\(\s*['"]([^'"]+)['"]""", re.IGNORECASE)
FILTER_RE = re.compile(r"""\.(?:eq|neq|gt|gte|lt|lte|like|ilike|is|in|contains|order|filter)\(\s*['"]([a-z_][a-z0-9_]*)['"]""", re.IGNORECASE)
UPDATE_RE = re.compile(r"""\.(?:update|insert|upsert)\(\s*\{([^}]{0,400})\}""", re.IGNORECASE)
KEY_RE = re.compile(r"""(?:^|[\s,{])([a-z_][a-z0-9_]*)\s*:""")

def walk_files():
    for base in SCAN_DIRS:
        for p in base.rglob("*"):
            if not p.is_file(): continue
            if p.suffix not in {".ts", ".tsx"}: continue
            if any(part in EXCLUDE for part in p.parts): continue
            yield p

def parse_columns(select_str: str):
    out, depth, cur = [], 0, ""
    for ch in select_str + ",":
        if ch == "(": depth += 1
        elif ch == ")": depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            tok = cur.strip()
            if tok and tok != "*":
                bare = re.split(r"->|::", tok, 1)[0].strip()
                if re.fullmatch(r"[a-z_][a-z0-9_]*", bare):
                    out.append(bare)
            cur = ""
        else: cur += ch
    return out

def main():
    cols = json.loads(Path("/tmp/schema.json").read_text())
    cols = {k: set(v) for k, v in cols.items()}
    print(f"loaded schema: {len(cols)} tables")
    findings = []
    n_files = 0
    for f in walk_files():
        n_files += 1
        text = f.read_text()
        for fm in FROM_RE.finditer(text):
            table = fm.group(1)
            window = fm.group(2)
            if table not in cols:
                continue
            schema_cols = cols[table]
            line = text[: fm.start()].count("\n") + 1
            for sm in SELECT_RE.finditer(window):
                for c in parse_columns(sm.group(1)):
                    if c not in schema_cols and c not in cols:
                        findings.append((str(f.relative_to(ROOT)), line, table, "select", c))
            for fm2 in FILTER_RE.finditer(window):
                c = fm2.group(1)
                if c not in schema_cols:
                    findings.append((str(f.relative_to(ROOT)), line, table, "filter", c))
            for um in UPDATE_RE.finditer(window):
                for c in KEY_RE.findall(um.group(1)):
                    if c not in schema_cols:
                        findings.append((str(f.relative_to(ROOT)), line, table, "update/insert", c))
    print(f"scanned: {n_files} TS/TSX files")
    print(f"findings: {len(findings)}")
    findings.sort()
    last_file = None
    for path, line, table, kind, col in findings:
        if path != last_file:
            print(f"\n## {path}")
            last_file = path
        print(f"  L{line} {kind} on `{table}`: column `{col}` not on table")

main()
