"""Build a per-table column-flow matrix and write `docs/schema-lock.md`.

For each table in `scripts/schema.lock.json`:
  - FE_READ   — columns the frontend selects via Supabase REST `.from(table).select(...)`
  - FE_WRITE  — columns the frontend sends via .insert/.update/.upsert(...) bodies
  - BE_READ   — columns the server SELECTs from this table (best-effort regex)
  - BE_WRITE  — columns the server INSERTs / UPDATEs into this table

The point: "lockable per column" — a column is fully verified when FE_WRITE
matches BE_WRITE (round-trip matches the schema) and BE_READ matches FE_READ
(client gets back what it expects).

Output: docs/schema-lock.md. JSON sidecar: docs/schema-lock-matrix.json.

Caveats:
  - regex-based, not AST. False positives on string literals are possible;
    they're noted in the per-table notes column.
  - tables with zero observed FE/BE activity are listed under "untouched".
  - dynamic SELECT * / spread payload patterns are flagged.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_LOCK = ROOT / "scripts" / "schema.lock.json"
STRAY_ALLOWLIST = ROOT / "scripts" / "stray_drift_allowlist.txt"
OUT_MD = ROOT / "docs" / "schema-lock.md"
OUT_JSON = ROOT / "docs" / "schema-lock-matrix.json"


def load_stray_allowlist() -> set[tuple[str, str]]:
    """Parse stray_drift_allowlist.txt → {(table, col), ...}. Entries here
    are gated/dormant references — see learning_dont_allowlist_dead_assert_dead.md
    for the rule that every entry must trace a call chain in its comment block."""
    entries: set[tuple[str, str]] = set()
    if not STRAY_ALLOWLIST.exists():
        return entries
    for line in STRAY_ALLOWLIST.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        tbl, col = line.split(":", 1)
        entries.add((tbl.strip(), col.strip()))
    return entries

FE_DIRS = [ROOT / "src", ROOT / "app"]
BE_DIRS = [ROOT / "server" / "app"]
EXCLUDE = {"node_modules", ".expo", ".next", "dist", "build", "ios", "web"}

# --- FE patterns ---
# .from('table_name')  with single OR double quotes; capture the table.
FE_FROM_RE = re.compile(r"""\.from\(\s*['"]([a-z_][a-z0-9_]*)['"]\s*\)""")
# Match a .select('a, b, c') chain on the same statement (heuristic — same line
# or following whitespace). We pull from the entire statement up to a sentinel.
FE_SELECT_RE = re.compile(r"""\.select\(\s*['"]([^'"]+)['"]""")
# .insert({col: ..., col: ...}) / .update({...}) / .upsert({...}). Capture body.
# NOT DOTALL — body must end on the same logical statement, otherwise we sweep
# up trailing `// foo, so bar:` comment text and treat words as column keys.
FE_BODY_RE = re.compile(r"""\.(insert|update|upsert)\(\s*\{([^}]*)\}""")
# Body key extractor: `key:` or `key,` (shorthand). Anchored to whitespace+`:`
# so we don't match prose like "foo, so bar:" — only the `:` form is a real
# JS object key.
FE_KEY_RE = re.compile(r"""(?:^|,|\{|\s)\s*([a-z_][a-z0-9_]*)\s*:""")

# Common English / JS stop-words that show up in comments and prose. If a
# regex thinks one of these is a column name, it's almost certainly noise.
# Real column names use snake_case multi-letter; single-word english stops are
# excluded outright.
PROSE_STOPWORDS = frozenset({
    "so", "optionally", "below", "above", "note", "todo", "eg", "ie", "as",
    "to", "from", "is", "be", "of", "in", "on", "at", "or", "and", "the",
    "a", "an", "this", "that", "these", "those", "but", "if", "no", "not",
    "via", "vs", "etc", "ok", "x",
})

# --- BE patterns (best-effort) ---
# INSERT INTO table(col, col, col)  /  INTO public.table(col, col, col)
BE_INSERT_RE = re.compile(
    r"""INSERT\s+INTO\s+(?:public\.)?([a-z_][a-z0-9_]*)\s*\(([^)]+)\)""",
    re.IGNORECASE,
)
# UPDATE table SET col1 = $1, col2 = $2
BE_UPDATE_RE = re.compile(
    r"""UPDATE\s+(?:public\.)?([a-z_][a-z0-9_]*)\s+SET\s+(.+?)(?:WHERE|RETURNING|\Z)""",
    re.IGNORECASE | re.DOTALL,
)
# SELECT col1, col2 FROM (public.)?table — captures the column list before FROM.
BE_SELECT_RE = re.compile(
    r"""SELECT\s+([^;]+?)\s+FROM\s+(?:public\.)?([a-z_][a-z0-9_]*)""",
    re.IGNORECASE | re.DOTALL,
)

def iter_files(dirs, suffixes):
    for d in dirs:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if any(part in EXCLUDE for part in p.parts):
                continue
            if p.is_file() and p.suffix in suffixes:
                yield p


# Strip Python `#` line comments. Without this, BE_SELECT_RE happily matches
# inside `# Explicit column lists for SELECT (avoid SELECT *)` and then sweeps
# (DOTALL) across hundreds of lines until the next real `FROM <table>` —
# pulling docstring words like "raising" into the column list as bogus strays.
# Replace each `# ...` tail with same-length whitespace so file offsets stay
# stable for any callers that rely on them.
_PY_COMMENT_RE = re.compile(r"(^|\s)#[^\n]*")


def _strip_py_comments(text: str) -> str:
    return _PY_COMMENT_RE.sub(lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), text)

def parse_columns_from_select_clause(s: str) -> list[str]:
    """Split a SELECT col list, drop aliases / fn calls / *, return bare cols."""
    cols = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok or tok == "*":
            continue
        # Drop AS alias
        tok_no_alias = re.split(r"\s+AS\s+|\s+", tok, maxsplit=1, flags=re.IGNORECASE)[0]
        # Drop function calls / expressions — skip if has paren/operator
        if re.search(r"[()*+\-/<>!]", tok_no_alias):
            continue
        # Drop schema/table prefix
        bare = tok_no_alias.split(".")[-1].strip().strip('"')
        # Filter prose/stop-words and 1-char tokens (always noise; real cols ≥2 chars).
        if bare in PROSE_STOPWORDS or len(bare) < 2:
            continue
        if re.fullmatch(r"[a-z_][a-z0-9_]*", bare):
            cols.append(bare)
    return cols

def parse_set_columns(s: str) -> list[str]:
    """From an UPDATE ... SET clause, extract column names being assigned."""
    cols = []
    for tok in s.split(","):
        m = re.match(r"\s*([a-z_][a-z0-9_]*)\s*=", tok, re.IGNORECASE)
        if m:
            cols.append(m.group(1))
    return cols

def main():
    schema = json.loads(SCHEMA_LOCK.read_text())
    tables = schema["tables"]  # dict[table] -> list[col]

    # Aggregations
    fe_read: dict[str, set[tuple[str, str]]] = defaultdict(set)   # table -> {(col, file)}
    fe_write: dict[str, set[tuple[str, str]]] = defaultdict(set)
    be_read: dict[str, set[tuple[str, str]]] = defaultdict(set)
    be_write: dict[str, set[tuple[str, str]]] = defaultdict(set)
    notes: dict[str, list[str]] = defaultdict(list)

    # --- FE scan ---
    for path in iter_files(FE_DIRS, {".ts", ".tsx"}):
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        rel = str(path.relative_to(ROOT))
        for m in FE_FROM_RE.finditer(text):
            table = m.group(1)
            if table not in tables:
                continue
            # Look in the next ~600 chars for .select(...) or .insert/update/upsert(...)
            window = text[m.end(): m.end() + 600]
            for sm in FE_SELECT_RE.finditer(window):
                if sm.start() > 600: break
                # Strip nested-select bodies: select('id, profiles(name, avatar)')
                # shouldn't introduce profiles' inner cols as parent-table cols.
                clause = re.sub(r"\([^()]*\)", "", sm.group(1))
                for col in [c.strip() for c in clause.split(",") if c.strip()]:
                    bare = col.split(".")[-1].split(":")[0].strip()
                    # Skip prose stop-words and FE relation refs that have
                    # paren-children we already stripped (would leave dangling tokens).
                    if bare in PROSE_STOPWORDS:
                        continue
                    if re.fullmatch(r"[a-z_][a-z0-9_]*", bare) and len(bare) >= 2:
                        fe_read[table].add((bare, rel))
                    elif bare == "*":
                        notes[table].append(f"{rel}: select('*') — full row, can't enumerate")
            for bm in FE_BODY_RE.finditer(window):
                body = bm.group(2)
                for km in FE_KEY_RE.finditer(body):
                    bare = km.group(1)
                    if bare in PROSE_STOPWORDS:
                        continue
                    if re.fullmatch(r"[a-z_][a-z0-9_]*", bare) and len(bare) >= 2:
                        fe_write[table].add((bare, rel))
                # Detect spread / dynamic insert
                if "..." in body:
                    notes[table].append(f"{rel}: spread/dynamic body — not all keys captured")

    # --- BE scan ---
    for path in iter_files(BE_DIRS, {".py"}):
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        text = _strip_py_comments(text)
        rel = str(path.relative_to(ROOT))
        for m in BE_INSERT_RE.finditer(text):
            table, cols_str = m.group(1), m.group(2)
            if table not in tables:
                continue
            for col in [c.strip() for c in cols_str.split(",")]:
                bare = col.split(".")[-1].strip().strip('"')
                if re.fullmatch(r"[a-z_][a-z0-9_]*", bare):
                    be_write[table].add((bare, rel))
        for m in BE_UPDATE_RE.finditer(text):
            table, set_clause = m.group(1), m.group(2)
            if table not in tables:
                continue
            for col in parse_set_columns(set_clause):
                be_write[table].add((col, rel))
        for m in BE_SELECT_RE.finditer(text):
            cols_str, table = m.group(1), m.group(2)
            if table not in tables:
                continue
            for col in parse_columns_from_select_clause(cols_str):
                be_read[table].add((col, rel))

    # --- Build markdown ---
    out_json = {"_about": "FE/BE column-flow matrix derived from regex scan.",
                "tables": {}}

    md_lines = [
        "# Schema lock — column-flow matrix",
        "",
        "Generated by `scripts/build_column_flow_matrix.py`. For each table the columns",
        "are tagged with where they're touched:",
        "",
        "- **FE_R** = frontend `.from(table).select(col)` (Supabase REST read)",
        "- **FE_W** = frontend `.insert/.update/.upsert({col: ...})` (Supabase REST write)",
        "- **BE_R** = server SQL `SELECT col FROM table` literal",
        "- **BE_W** = server SQL `INSERT INTO table(col,...)` or `UPDATE table SET col=`",
        "",
        "A column with **all four tags** has been seen in both directions on both sides.",
        "Columns the schema knows about but no code touches are listed under _Untouched_.",
        "",
        "Limitations: regex-based, not AST. `select('*')` and spread payloads can't be",
        "enumerated and are reported as notes.",
        "",
    ]

    # Build a set of all known column names across the schema; used below to
    # filter out JOIN-introduced "strays" (columns that exist on a *different*
    # table — almost always a foreign-relation reference, not real drift).
    all_schema_cols: set[str] = set()
    for tbl_cols in tables.values():
        all_schema_cols.update(tbl_cols)

    stray_allowlist = load_stray_allowlist()

    # Sort: tables that have any activity first, then untouched.
    touched = []
    untouched = []
    for table, cols in sorted(tables.items()):
        any_activity = any(table in d for d in (fe_read, fe_write, be_read, be_write))
        (touched if any_activity else untouched).append(table)

    for table in touched:
        cols = tables[table]
        fr = {c for c, _ in fe_read.get(table, set())}
        fw = {c for c, _ in fe_write.get(table, set())}
        br = {c for c, _ in be_read.get(table, set())}
        bw = {c for c, _ in be_write.get(table, set())}
        all_seen_cols = fr | fw | br | bw

        md_lines.append(f"## `{table}`")
        md_lines.append("")
        md_lines.append("| column | FE_R | FE_W | BE_R | BE_W | locked? |")
        md_lines.append("|---|---|---|---|---|---|")
        per_col = {}
        for col in cols:
            tag_fr = "✓" if col in fr else "·"
            tag_fw = "✓" if col in fw else "·"
            tag_br = "✓" if col in br else "·"
            tag_bw = "✓" if col in bw else "·"
            locked = "🔒" if (col in all_seen_cols) and (
                # at minimum: write side matches OR read side matches
                (col in fw and col in bw) or (col in fr and col in br)
            ) else ""
            md_lines.append(f"| `{col}` | {tag_fr} | {tag_fw} | {tag_br} | {tag_bw} | {locked} |")
            per_col[col] = {"fe_r": col in fr, "fe_w": col in fw,
                            "be_r": col in br, "be_w": col in bw}
        # Stray columns referenced in code but NOT in schema (drift signal).
        # Filter out:
        # - cols that exist on ANY OTHER table — those are JOIN/FK references
        #   the regex picked up from a Supabase nested-select or BE JOIN
        # - 1-character tokens (always noise; real cols are 2+ chars)
        # - entries in scripts/stray_drift_allowlist.txt — gated/dormant refs
        #   that pass the "default-live" sniff test in their comment block.
        raw_stray = [c for c in all_seen_cols if c not in cols]
        candidate_stray = [
            c for c in raw_stray
            if len(c) >= 2 and c not in all_schema_cols
        ]
        stray = [c for c in candidate_stray if (table, c) not in stray_allowlist]
        allowlisted = sorted(set(candidate_stray) - set(stray))
        join_likely = sorted(set(raw_stray) - set(candidate_stray))
        if stray:
            md_lines.append("")
            md_lines.append(f"**Stray refs** (not in any schema table): `{', '.join(sorted(stray))}`")
        if allowlisted:
            md_lines.append("")
            md_lines.append(
                f"**Allowlisted strays** (gated/dormant — see `scripts/stray_drift_allowlist.txt`): "
                f"`{', '.join(allowlisted)}`"
            )
        if join_likely:
            md_lines.append("")
            md_lines.append(f"**JOIN/FK refs** (col exists on another table — likely from a JOIN): `{', '.join(join_likely)}`")
        if notes.get(table):
            md_lines.append("")
            md_lines.append(f"**Notes:** {'; '.join(sorted(set(notes[table])))}")
        md_lines.append("")
        out_json["tables"][table] = {
            "columns": per_col,
            "stray": stray,
            "stray_allowlisted": allowlisted,
            "fe_read_files": sorted({f for _, f in fe_read.get(table, set())}),
            "fe_write_files": sorted({f for _, f in fe_write.get(table, set())}),
            "be_read_files": sorted({f for _, f in be_read.get(table, set())}),
            "be_write_files": sorted({f for _, f in be_write.get(table, set())}),
        }

    md_lines.append("---")
    md_lines.append("")
    md_lines.append(f"## Untouched tables ({len(untouched)})")
    md_lines.append("")
    md_lines.append("Schema-known but no FE/BE code touches them. Often legacy or admin-only:")
    md_lines.append("")
    for t in untouched:
        md_lines.append(f"- `{t}` ({len(tables[t])} cols)")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(md_lines) + "\n")
    OUT_JSON.write_text(json.dumps(out_json, indent=2, sort_keys=True))

    print(f"Wrote {OUT_MD} ({len(touched)} touched, {len(untouched)} untouched).")
    print(f"Wrote {OUT_JSON}.")

if __name__ == "__main__":
    main()
