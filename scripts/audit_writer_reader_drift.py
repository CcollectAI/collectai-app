"""Writer/reader column-drift sweep.

Catches the bug class that's bitten CollectAI 3 times in 2 weeks:

  1. items.attrs writer vs items.attributes_json reader (2026-04-29)
  2. market_hits writer populates seen_at/provider; readers filter
     observed_at/source (2026-05-02)
  3. Same RPC also missed marketplace + source mirror (2026-05-02)

The pattern: a schema migration (partitioning, column rename, column add)
ships, writer paths get updated, reader paths don't. Nothing crashes —
queries silently return wrong/empty data, and the bug surfaces weeks
later as "the model's predictions are garbage" or "this filter shows
nothing".

This scanner regexes every INSERT INTO and every SELECT/WHERE/ORDER BY
across server/, then compares column sets per table:

  * **silent_null_columns**:    column read by code, never written by code
                                → every read returns NULL
  * **dead_column_writes**:     column written by code, never read by code
                                → wasted writes (e.g. valuation_worker
                                writes nk/model_version/comps_count that
                                no reader uses)
  * **partition_filter_misses**: queries against a partitioned table
                                that don't include the partition key in
                                WHERE → planner walks all partitions
                                (160ms→3ms speedup when fixed; see
                                docs/perf-maintenance-playbook.md)

This is regex, not AST — it misses dynamically-built SQL (f-strings,
format(), `_DEAL_COLUMNS = "..."` constants joined into queries). It
will produce false positives (e.g. column referenced in a comment) and
false negatives (e.g. column referenced via `*` selects). Treat the
output as a **review queue**, not a pass/fail gate. Fold confirmed false
positives into the IGNORE_* sets at the top.

Run from repo root:

    python3 scripts/audit_writer_reader_drift.py
    python3 scripts/audit_writer_reader_drift.py --json   # machine-readable
    python3 scripts/audit_writer_reader_drift.py --strict # exit 1 on any finding

CI integration: ci-min.yml runs this in --strict mode on PRs touching
server/ or scripts/schema.lock.json. To allow a known false positive,
add it to the IGNORE_* sets below with a one-line comment.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = [REPO_ROOT / "server"]
SCHEMA_LOCK = REPO_ROOT / "scripts" / "schema.lock.json"

# ---------------------------------------------------------------------------
# Partitioned tables — extra rules apply (filter on partition key required
# in hot loops to enable Subplans Removed pruning).
# ---------------------------------------------------------------------------
PARTITIONED: dict[str, str] = {
    "market_hits": "seen_at",
    "price_predictions": "generated_at",
    "price_history": "snapshot_at",
}

# ---------------------------------------------------------------------------
# Allowlists. Add narrowly-scoped entries with a comment so future
# maintainers know why each one is here.
# ---------------------------------------------------------------------------

# Tables we genuinely don't manage from app code (auth schema, supabase
# system tables, etc.) — drift findings on these are noise.
IGNORE_TABLES = {
    "auth.users",
    "users",          # auth.users alias from supabase
    "storage.objects",
    "spatial_ref_sys",
}

# Columns expected to be NULL most of the time — present in the schema
# for future use, intentionally not yet written. Adding here means "I
# verified this is intentional, not a bug".
IGNORE_SILENT_NULL: dict[str, set[str]] = {
    # Partition keys with DB-side DEFAULT now() — written by the partition
    # definition, not by app SQL. Scanner can't see DB defaults.
    # `user_id` on market_hits is by design — most rows are anonymous
    # crawl data; only user-saved comps populate it (rare path).
    "market_hits": {"seen_at", "user_id"},
    "price_predictions": {"generated_at"},
    "price_history": {"snapshot_at"},
}

# Columns written but intentionally not read (legacy, telemetry, future).
IGNORE_DEAD_WRITES: dict[str, set[str]] = {
    "price_predictions": {
        # Schema-extra columns left over from earlier model architectures
        # (R12 raw quantile dump, head-of-distribution, training-data
        # asof). Kept for historical rows; not used by the current
        # /predict/* endpoints. Confirmed inert 2026-05-02.
        "raw", "ts", "head", "training_data_asof",
    },
    "market_hits": {
        # All four are read via patterns the regex can't see:
        #   features_json — read via JSONB path ops (`->>'is_sold'`) in
        #     import_discogs.py and downstream training. Verified 2026-05-02.
        #   listing_id    — read inside the same INSERT's WHERE NOT EXISTS
        #     dedup clause. Regex doesn't tie WHERE to its own INSERT.
        #   marketplace   — analytics filter / FE Supabase REST consumer.
        #   shipping      — read via `shipping->>'ships_from'` in
        #     deal_discovery_agent.py:519. Same JSONB-op blind spot.
        "features_json", "listing_id", "marketplace", "shipping",
    },
}

# Files that build SQL dynamically and confuse the regex. Skip them
# entirely — manual review only.
IGNORE_FILES = {
    # Migration scripts — DDL, not app SQL.
    "server/migrations",
    "server/data",      # seed-only SQL; not a runtime contract
    "server/tests/sql_fixtures",
}

# ---------------------------------------------------------------------------
# Regexes — deliberately permissive; we'd rather over-flag than miss a
# bug. False positives can be allowlisted via the IGNORE_* sets.
# ---------------------------------------------------------------------------

# INSERT INTO [public.]table (col1, col2, col3, ...)
RE_INSERT = re.compile(
    r"INSERT\s+INTO\s+(?:public\.)?([a-z_][a-z0-9_]*)\s*\(\s*([^)]+?)\s*\)",
    re.IGNORECASE | re.DOTALL,
)

# UPDATE [public.]table SET col = ..., col2 = ...
RE_UPDATE = re.compile(
    r"UPDATE\s+(?:public\.)?([a-z_][a-z0-9_]*)\s+SET\s+(.+?)(?:\s+WHERE\b|\s*$|;)",
    re.IGNORECASE | re.DOTALL,
)
RE_UPDATE_COL = re.compile(r"\b([a-z_][a-z0-9_]*)\s*=", re.IGNORECASE)

# FROM [public.]table — captures every table referenced in a SELECT.
RE_FROM = re.compile(
    r"\bFROM\s+(?:public\.)?([a-z_][a-z0-9_]*)\b",
    re.IGNORECASE,
)

# Column references qualified by table alias or name. Catches
# `pp.generated_at`, `mh.observed_at`, `items.canonical_key`. We can't
# resolve aliases (would need full SQL parse), so we collect both
# table.col and bare-col references and match against schema columns.
RE_QUALIFIED_COL = re.compile(r"\b([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b")

# Bare-column references inside SELECT/WHERE/ORDER BY — much noisier,
# only used as fallback when qualified refs don't cover.
# Captures both the column list AND the source table in one match so we
# don't have to search for the FROM separately (the previous version did
# `RE_FROM.search(text, pos=m.end())` which overshot — `m.end()` was AFTER
# the consumed FROM, so it found the *next* FROM in the file).
RE_SELECT_LIST = re.compile(
    r"\bSELECT\s+(?:DISTINCT\s+(?:ON\s*\([^)]*\)\s+)?)?(.+?)\s+FROM\s+(?:public\.)?([a-z_][a-z0-9_]*)",
    re.IGNORECASE | re.DOTALL,
)
RE_WHERE_CLAUSE = re.compile(
    r"\bWHERE\s+(.+?)(?:\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|\bRETURNING\b|\bON\s+CONFLICT\b|\)|\s*;|\s*$)",
    re.IGNORECASE | re.DOTALL,
)

# Bare identifier — used inside SELECT lists and WHERE clauses to find
# columns that aren't qualified (e.g. `WHERE observed_at IS NULL`).
RE_IDENT = re.compile(r"\b([a-z_][a-z0-9_]+)\b")

# SQL-ish literal detector — strips whitespace and Python strings to
# avoid matching variable names that happen to share column names.
SQL_KEYWORDS = {
    "select", "from", "where", "and", "or", "not", "in", "is", "null", "true",
    "false", "on", "as", "by", "with", "having", "case", "when", "then", "else",
    "end", "group", "order", "limit", "offset", "asc", "desc", "join", "left",
    "right", "inner", "outer", "cross", "lateral", "using", "distinct", "all",
    "exists", "between", "like", "ilike", "any", "some", "values", "returning",
    "set", "into", "default", "interval", "now", "coalesce", "nullif", "cast",
    "extract", "count", "sum", "avg", "min", "max", "round", "abs", "lower",
    "upper", "concat", "char_length", "length", "trim", "substr", "position",
    "to_char", "to_date", "date_trunc", "now", "current_timestamp",
    "current_date", "filter", "over", "partition", "row_number", "rank",
    "dense_rank", "lag", "lead", "first_value", "last_value", "nth_value",
    "asc", "desc", "nulls", "first", "last", "asc", "desc",
    # Python noise
    "self", "cls", "args", "kwargs", "true", "false", "none",
}


@dataclass
class TableUsage:
    name: str
    schema_columns: set[str] = field(default_factory=set)
    written: set[str] = field(default_factory=set)
    read: set[str] = field(default_factory=set)
    write_sites: list[str] = field(default_factory=list)
    read_sites: list[str] = field(default_factory=list)
    # Per partitioned table only: WHERE/ORDER BY references that did NOT
    # include the partition key.
    partition_filter_misses: list[str] = field(default_factory=list)


def _load_schema_lock() -> dict[str, set[str]]:
    """Return {table_name: {col1, col2, ...}} from schema.lock.json."""
    if not SCHEMA_LOCK.exists():
        sys.stderr.write(f"schema.lock.json not found at {SCHEMA_LOCK}\n")
        sys.exit(2)
    raw = json.loads(SCHEMA_LOCK.read_text())
    tables = raw.get("tables") or raw  # tolerate either shape
    out: dict[str, set[str]] = {}
    for tname, meta in tables.items():
        if isinstance(meta, dict):
            cols = meta.get("columns") or meta.get("cols") or {}
            if isinstance(cols, dict):
                out[tname] = set(cols.keys())
            elif isinstance(cols, list):
                out[tname] = {c if isinstance(c, str) else c.get("name", "") for c in cols}
        elif isinstance(meta, list):
            out[tname] = set(meta)
    return out


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for d in SCAN_DIRS:
        for p in d.rglob("*.py"):
            rel = p.relative_to(REPO_ROOT).as_posix()
            if any(rel.startswith(prefix) for prefix in IGNORE_FILES):
                continue
            if "/__pycache__/" in rel or "/tests/" in rel:
                continue
            files.append(p)
    return files


def _split_columns(col_list: str) -> list[str]:
    """Split a comma-separated column-list expression into bare identifiers.

    Handles the common forms inside an INSERT column list:
      `(col1, col2,
        col3)`             → ['col1', 'col2', 'col3']
      `(col1, col2 -- inline comment\n)` → ignores comments
    """
    # Strip SQL line comments
    cleaned = re.sub(r"--[^\n]*", "", col_list)
    parts = [p.strip().split()[0] for p in cleaned.split(",") if p.strip()]
    return [p.lower() for p in parts if p and p.replace("_", "").isalnum()]


_RE_COL_CONSTANT = re.compile(
    r"""_(?:[A-Z_]*COLUMNS?|FIELDS?)\s*=\s*[("\']\s*([a-z0-9_,\s]+?)[)"\']""",
    re.IGNORECASE | re.DOTALL,
)


def _extract_writers(
    text: str, filename: str, usages: dict[str, TableUsage]
) -> None:
    """Walk INSERT and UPDATE statements, populate writer column sets.

    Also catches column-list constants (`_DEAL_COLUMNS = "id, user_id, ..."`)
    that get f-string'd into INSERT/SELECT statements — without this the
    scanner produces hundreds of false positives on every table that uses
    that pattern.
    """
    # Column-list constants apply to whatever table the file mostly uses.
    # Heuristic: associate the constant with every table that's written
    # in the same file. Less precise than per-statement parsing, but
    # eliminates the noise without missing real drift.
    constant_cols: set[str] = set()
    for m in _RE_COL_CONSTANT.finditer(text):
        for col in _split_columns(m.group(1)):
            constant_cols.add(col)

    file_writer_tables: set[str] = set()
    for m in RE_INSERT.finditer(text):
        table = m.group(1).lower()
        if table in IGNORE_TABLES:
            continue
        cols = _split_columns(m.group(2))
        usage = usages.setdefault(table, TableUsage(name=table))
        usage.written.update(cols)
        usage.write_sites.append(f"{filename}:{text[: m.start()].count(chr(10)) + 1}")
        file_writer_tables.add(table)

    for m in RE_UPDATE.finditer(text):
        table = m.group(1).lower()
        if table in IGNORE_TABLES:
            continue
        set_clause = m.group(2)
        cols = [c.lower() for c in RE_UPDATE_COL.findall(set_clause)]
        if not cols:
            continue
        usage = usages.setdefault(table, TableUsage(name=table))
        usage.written.update(cols)
        usage.write_sites.append(f"{filename}:{text[: m.start()].count(chr(10)) + 1}")
        file_writer_tables.add(table)

    # Apply column-list constants to every table this file writes to.
    for table in file_writer_tables:
        usages[table].written.update(constant_cols)


def _strip_nested_sql(text: str) -> str:
    """Remove FILTER aggregates and balanced-paren subqueries so the
    WHERE-clause regex sees only top-level WHEREs.

    Without this:
      - `COUNT(*) FILTER (WHERE col IS NULL)` matches as a top-level
        WHERE on the wrong table (the FROM further down). Caused 4 of
        the 12 reported partition_miss findings to be false positives.
      - `(SELECT canonical_key FROM items WHERE id = $1)` inside a
        WHERE clause confuses both the WHERE-end detection (early
        close-paren terminator) and the FROM-table attribution.

    Approach: balanced-paren walk, blanking out the contents of any
    `FILTER (...)` or `(SELECT ...)` group. Preserves byte positions
    (replaces with spaces) so line numbers in findings stay accurate.
    """
    out = list(text)
    n = len(text)
    i = 0
    while i < n:
        # Detect FILTER ( starting at this position (case-insensitive)
        is_filter = (i + 7 <= n and text[i:i+7].lower() == "filter ")
        is_subselect = (
            text[i] == "("
            and i + 8 <= n
            and re.match(r"\(\s*SELECT\s", text[i:i+50], re.IGNORECASE)
        )
        if is_filter:
            # Find the opening paren after `FILTER`
            j = i + 7
            while j < n and text[j] != "(":
                j += 1
            if j == n:
                i += 1
                continue
            depth = 1
            k = j + 1
            while k < n and depth > 0:
                if text[k] == "(":
                    depth += 1
                elif text[k] == ")":
                    depth -= 1
                k += 1
            for p in range(j + 1, k - 1):
                if text[p] != "\n":
                    out[p] = " "
            i = k
        elif is_subselect:
            depth = 1
            k = i + 1
            while k < n and depth > 0:
                if text[k] == "(":
                    depth += 1
                elif text[k] == ")":
                    depth -= 1
                k += 1
            for p in range(i + 1, k - 1):
                if text[p] != "\n":
                    out[p] = " "
            i = k
        else:
            i += 1
    return "".join(out)


def _extract_readers(
    text: str, filename: str, usages: dict[str, TableUsage]
) -> None:
    """Walk SELECT/WHERE/ORDER BY, populate reader column sets and (for
    partitioned tables) partition-filter misses."""
    # Strip FILTER and subquery contents BEFORE WHERE detection — but
    # keep the original text for column references and FROM resolution
    # (the column refs inside subqueries are still real reads).
    text_for_where = _strip_nested_sql(text)

    # Map alias -> table for qualified-column resolution.
    aliases: dict[str, str] = {}
    for m in re.finditer(
        r"FROM\s+(?:public\.)?([a-z_][a-z0-9_]*)(?:\s+(?:AS\s+)?([a-z_][a-z0-9_]*))?",
        text, re.IGNORECASE,
    ):
        table = m.group(1).lower()
        alias = (m.group(2) or table).lower()
        aliases[alias] = table

    for m in RE_FROM.finditer(text):
        table = m.group(1).lower()
        if table in IGNORE_TABLES:
            continue
        usages.setdefault(table, TableUsage(name=table))

    # Qualified column refs — most reliable signal.
    for m in RE_QUALIFIED_COL.finditer(text):
        alias_or_table = m.group(1).lower()
        col = m.group(2).lower()
        if col in SQL_KEYWORDS or col.isdigit():
            continue
        table = aliases.get(alias_or_table, alias_or_table)
        if table not in usages or table in IGNORE_TABLES:
            continue
        usages[table].read.add(col)

    # SELECT-list bare columns
    for m in RE_SELECT_LIST.finditer(text):
        select_list = m.group(1)
        table = m.group(2).lower()
        if table not in usages or table in IGNORE_TABLES:
            continue
        # Strip aggregates/aliases — keep only things that look like column names
        for ident in RE_IDENT.findall(select_list):
            ident = ident.lower()
            if ident in SQL_KEYWORDS or ident.isdigit() or ident == table:
                continue
            usages[table].read.add(ident)

    # WHERE-clause bare columns + partition-filter misses.
    # Run against the cleaned text (FILTER/subquery contents blanked)
    # so we only see TOP-LEVEL WHEREs. text_for_where preserves byte
    # positions so line numbers in findings remain accurate.
    for m in RE_WHERE_CLAUSE.finditer(text_for_where):
        where = m.group(1)
        # Find the FROM table for this statement (nearest preceding FROM)
        from_m = None
        for fm in RE_FROM.finditer(text_for_where, endpos=m.start()):
            from_m = fm
        if not from_m:
            continue
        table = from_m.group(1).lower()
        if table in IGNORE_TABLES:
            continue
        usage = usages.setdefault(table, TableUsage(name=table))
        for ident in RE_IDENT.findall(where):
            ident = ident.lower()
            if ident in SQL_KEYWORDS or ident.isdigit() or ident == table:
                continue
            usage.read.add(ident)

        # Partition-key check — also widen the lookahead beyond the
        # WHERE regex's terminator. The regex stops at `)`, but a
        # partition-key filter sometimes lives in a later AND clause
        # that the regex couldn't reach. Look in the next 800 chars
        # past the WHERE start for the partition key.
        if table in PARTITIONED:
            pkey = PARTITIONED[table]
            window = text_for_where[m.start():m.start() + 800].lower()
            if pkey not in window:
                line = text[: m.start()].count("\n") + 1
                usage.partition_filter_misses.append(f"{filename}:{line}")


def scan() -> dict[str, TableUsage]:
    schema = _load_schema_lock()
    usages: dict[str, TableUsage] = {}

    # Pre-populate schema columns for every table so we can compare even
    # when one side has zero hits in the regex.
    for tname, cols in schema.items():
        if tname in IGNORE_TABLES:
            continue
        u = usages.setdefault(tname, TableUsage(name=tname))
        u.schema_columns = cols

    for path in _iter_python_files():
        text = path.read_text(errors="replace")
        rel = path.relative_to(REPO_ROOT).as_posix()
        _extract_writers(text, rel, usages)
        _extract_readers(text, rel, usages)

    return usages


@dataclass
class Finding:
    table: str
    kind: str          # 'silent_null' | 'dead_write' | 'partition_miss'
    column: str | None
    detail: str


def diff(usages: dict[str, TableUsage], full: bool = False) -> list[Finding]:
    """Compute drift findings.

    `full=False` (default) restricts to partitioned tables — the class
    where all 3 known production bugs landed. The non-partitioned silent_null
    sweep produces ~180 findings, most of which are false positives caused
    by RPC writes, FE-via-Supabase-REST writes, materialized-view refreshes,
    and dynamically-built SQL the regex can't parse. Triage those manually
    behind `--full`.
    """
    findings: list[Finding] = []

    target_tables = (
        set(usages.keys()) if full else set(PARTITIONED.keys())
    )

    for tname in sorted(target_tables):
        u = usages.get(tname)
        if u is None or not u.schema_columns:
            continue

        # silent_null: read in code, never written
        ignore_silent = IGNORE_SILENT_NULL.get(tname, set())
        for col in sorted(u.read - u.written):
            if col not in u.schema_columns:
                continue
            if col in ignore_silent:
                continue
            if col in {"created_at", "updated_at", "id"}:
                continue  # framework-managed
            findings.append(Finding(
                table=tname, kind="silent_null", column=col,
                detail="column read by code but never written by code → reads return NULL",
            ))

        # dead_write: written but never read
        ignore_dead = IGNORE_DEAD_WRITES.get(tname, set())
        for col in sorted(u.written - u.read):
            if col not in u.schema_columns:
                continue
            if col in ignore_dead:
                continue
            if col in {"id", "created_at", "updated_at"}:
                continue
            findings.append(Finding(
                table=tname, kind="dead_write", column=col,
                detail="column written by code but never read by code → wasted writes",
            ))

        # partition filter misses (partitioned tables only — by definition)
        if tname in PARTITIONED and u.partition_filter_misses:
            for site in u.partition_filter_misses[:5]:  # cap noise per-table
                findings.append(Finding(
                    table=tname, kind="partition_miss", column=PARTITIONED[tname],
                    detail=f"WHERE without {PARTITIONED[tname]} → planner walks all partitions @ {site}",
                ))

    return findings


def render_markdown(findings: list[Finding], usages: dict[str, TableUsage]) -> str:
    if not findings:
        return "# Writer/reader drift — no findings\n\nAll partitioned tables filter on their partition key. No silent-NULL columns. No dead writes flagged.\n"

    lines = ["# Writer/reader drift report\n"]
    lines.append(
        "Categories:\n"
        "- **silent_null**: column read but never written → reads return NULL on every row\n"
        "- **dead_write**: column written but never read → wasted writes\n"
        "- **partition_miss**: query against a partitioned table without partition-key filter → planner walks all partitions\n",
    )

    # Group by kind, then by table
    by_kind: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_kind[f.kind].append(f)

    for kind in ("silent_null", "partition_miss", "dead_write"):
        items = by_kind.get(kind, [])
        if not items:
            continue
        lines.append(f"\n## {kind} ({len(items)})\n")
        lines.append("| table | column | detail |")
        lines.append("|---|---|---|")
        for f in items:
            lines.append(f"| `{f.table}` | `{f.column or ''}` | {f.detail} |")

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of markdown")
    ap.add_argument("--strict", action="store_true", help="Exit 1 if any findings")
    ap.add_argument("--out", help="Write report to file (default: stdout)")
    ap.add_argument(
        "--full", action="store_true",
        help="Scan ALL tables (default: partitioned tables only). Produces ~180 findings, most false positives — manual triage required.",
    )
    args = ap.parse_args()

    usages = scan()
    findings = diff(usages, full=args.full)

    if args.json:
        out = json.dumps(
            [{"table": f.table, "kind": f.kind, "column": f.column, "detail": f.detail} for f in findings],
            indent=2,
        )
    else:
        out = render_markdown(findings, usages)

    if args.out:
        Path(args.out).write_text(out)
    else:
        sys.stdout.write(out)

    return 1 if (args.strict and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
