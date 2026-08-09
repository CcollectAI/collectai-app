"""Column-existence scanner — catches `column "X" does not exist` 42703 bombs.

The drift scanner caught writer/reader column-set differences. This one
catches a different class: SQL that REFERENCES a column that simply
isn't on the target table at all. These are pre-shipped 500-errors
waiting for the first request to hit them.

Bugs of this class found in production today (2026-05-02):
  - sell_timing_router.py: `EXTRACT(MONTH FROM created_at)` on
    market_hits — endpoint 500'd on every Premium call
  - trends_and_deepdive_router.py: same `created_at` bug
  - deal_discovery_agent.py: `WHERE normalized_key ILIKE` and
    `ORDER BY asof DESC` on price_predictions — both columns don't
    exist on that table; deal discovery fell through to category
    median fallback for months

Approach (regex, not AST — same caveats as audit_writer_reader_drift.py):

1. For each .py file in server/, find every SQL block (triple-quoted
   string containing FROM/INSERT INTO).
2. Walk each block: extract FROM-clause aliases (`FROM market_hits mh`
   → mh→market_hits), and for every `alias.col` or `table.col` ref,
   check if col exists in schema.lock.json[table].
3. Also walk INSERT INTO column lists.
4. Report mismatches.

Run:
    python3 scripts/audit_column_existence.py
    python3 scripts/audit_column_existence.py --json
    python3 scripts/audit_column_existence.py --strict   # exit 1 on any
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

# Skip patterns — same ones the drift scanner uses
IGNORE_FILE_PREFIXES = ("server/migrations", "server/data", "server/tests/")
IGNORE_TABLES = {
    "auth.users", "users", "storage.objects", "spatial_ref_sys",
    # PG / catalog
    "pg_proc", "pg_constraint", "pg_inherits", "pg_class", "pg_index",
    "pg_namespace", "pg_attribute", "pg_stat_activity",
    # information_schema
    "columns", "tables", "routines", "schemata",
}

# Common column references that aren't actually qualified table columns
# (CTEs, aggregates, json paths, function results) — skip these.
NON_TABLE_QUALIFIERS = {
    # CTEs / subquery aliases that shadow real tables
    "current_vals", "historical_vals", "latest_predictions",
    "historical_predictions", "latest_pred", "current_pred",
    # Function-result aliases
    "now", "extract", "coalesce", "json", "jsonb", "array", "string",
    # UUIDs that contain dashes
}

# Bare-word triple-quoted SQL block detector.
RE_SQL_BLOCK = re.compile(r'"""(.*?)"""', re.DOTALL)
RE_FROM_ALIAS = re.compile(
    r"\b(?:FROM|JOIN)\s+(?:public\.)?([a-z_][a-z0-9_]*)\s*(?:AS\s+)?([a-z_][a-z0-9_]*)?",
    re.IGNORECASE,
)
RE_QUALIFIED = re.compile(r"\b([a-z_][a-z0-9_]+)\.([a-z_][a-z0-9_]+)\b")
RE_INSERT_COLS = re.compile(
    r"INSERT\s+INTO\s+(?:public\.)?([a-z_][a-z0-9_]*)\s*\(\s*([^)]+?)\s*\)",
    re.IGNORECASE | re.DOTALL,
)
RE_BARE_IDENT = re.compile(r"\b([a-z_][a-z0-9_]+)\b")

# SQL/Postgres keywords + builtins. Identifiers matching these are NOT
# columns. Kept extensive to suppress false positives.
SQL_KEYWORDS_FULL = {
    "select", "distinct", "from", "where", "and", "or", "not", "in", "is", "null",
    "true", "false", "on", "as", "by", "with", "having", "case", "when", "then",
    "else", "end", "group", "order", "limit", "offset", "asc", "desc", "join",
    "left", "right", "inner", "outer", "cross", "lateral", "using", "all",
    "exists", "between", "like", "ilike", "any", "some", "values", "returning",
    "set", "into", "default", "interval", "filter", "over", "partition",
    "union", "intersect", "except", "rows", "range", "preceding", "following",
    "current", "row", "unbounded", "cast", "extract", "from",
    # Builtins & operators
    "now", "coalesce", "nullif", "count", "sum", "avg", "min", "max", "round",
    "abs", "lower", "upper", "concat", "char_length", "length", "trim", "substr",
    "substring", "position", "to_char", "to_date", "to_timestamp", "date_trunc",
    "current_timestamp", "current_date", "current_time", "current_user",
    "session_user", "user", "localtime", "localtimestamp", "age", "make_interval",
    "row_number", "rank", "dense_rank", "lag", "lead", "first_value",
    "last_value", "nth_value", "generate_series", "json_typeof", "jsonb_typeof",
    "json_build_object", "jsonb_build_object", "jsonb_set", "jsonb_array_length",
    "json_array_length", "to_jsonb", "json_to_jsonb", "jsonb_to_recordset",
    "regexp_replace", "regexp_match", "regexp_matches", "split_part",
    "percentile_cont", "percentile_disc", "stddev", "stddev_pop", "stddev_samp",
    "variance", "var_pop", "var_samp", "string_agg", "array_agg", "array_length",
    "unnest", "array_to_string", "string_to_array",
    "greatest", "least", "least", "ceil", "floor", "trunc", "div", "mod",
    "exp", "ln", "log", "power", "sqrt", "random",
    "left", "right", "lpad", "rpad", "btrim",
    # Types
    "text", "varchar", "char", "integer", "int", "bigint", "smallint",
    "numeric", "decimal", "float", "real", "boolean", "bool", "date",
    "timestamp", "timestamptz", "time", "uuid", "json", "jsonb",
    "bytea", "money", "tsrange", "tstzrange", "daterange",
    # Common
    "asc", "desc", "nulls", "first", "last",
    # PG-specific
    "do", "nothing", "conflict", "constraint", "primary", "foreign", "key",
    "references", "check", "unique", "if",
}

# Identifiers we KNOW aren't columns even though they match the pattern
NEVER_COLUMN = {
    "n", "p", "q", "r", "s", "t", "v", "x", "y", "z",
    "and", "or", "not", "is", "in",
    "days", "hours", "minutes", "seconds", "weeks", "months", "years",
    "month", "year", "day", "hour", "minute", "second",
}


@dataclass
class Finding:
    file: str
    line: int
    table: str
    column: str
    detail: str


def _load_schema() -> dict[str, set[str]]:
    raw = json.loads(SCHEMA_LOCK.read_text())
    tables = raw.get("tables") or raw
    out: dict[str, set[str]] = {}
    for tname, meta in tables.items():
        if isinstance(meta, dict):
            cols = meta.get("columns") or meta.get("cols") or {}
            if isinstance(cols, dict):
                out[tname] = set(cols.keys())
            elif isinstance(cols, list):
                out[tname] = {c if isinstance(c, str) else c.get("name", "") for c in cols}
    return out


def _scan_block(
    block: str, file_path: str, byte_offset: int, full_text: str,
    schema: dict[str, set[str]],
) -> list[Finding]:
    findings: list[Finding] = []
    if "FROM" not in block.upper() and "INSERT" not in block.upper():
        return findings

    # Build alias → table map for THIS block
    aliases: dict[str, str] = {}
    for m in RE_FROM_ALIAS.finditer(block):
        table = m.group(1).lower()
        alias = (m.group(2) or "").lower()
        if table in IGNORE_TABLES or table not in schema:
            continue
        # The table itself is a valid "alias" too
        aliases[table] = table
        if alias and alias not in NON_TABLE_QUALIFIERS:
            aliases[alias] = table

    # 1. Qualified column references
    seen: set[tuple[str, str]] = set()
    for m in RE_QUALIFIED.finditer(block):
        alias = m.group(1).lower()
        col = m.group(2).lower()
        if alias not in aliases:
            continue
        if col in NON_TABLE_QUALIFIERS or col.isdigit():
            continue
        table = aliases[alias]
        cols = schema.get(table)
        if not cols:
            continue
        if col in cols:
            continue
        if (table, col) in seen:
            continue
        seen.add((table, col))
        # Compute approximate line number
        absolute = byte_offset + m.start()
        line = full_text[:absolute].count("\n") + 1
        findings.append(Finding(
            file=file_path, line=line, table=table, column=col,
            detail=f"`{alias}.{col}` references column not on `{table}` (schema cols: {sorted(cols)[:5]}...)",
        ))

    # 1b. Bare-identifier columns for single-table queries.
    # When the SQL block has exactly ONE FROM table (no JOIN), every bare
    # identifier inside SELECT/WHERE/ORDER BY/GROUP BY that isn't a SQL
    # keyword should resolve to a column on that table. This catches
    # `EXTRACT(MONTH FROM created_at)` on market_hits where created_at
    # doesn't exist (the sell_timing/trends_and_deepdive bug from
    # 2026-05-02). False positives include CTE columns and AS aliases —
    # we filter those by stripping CTE WITH blocks first.
    from_tables = list({aliases[a] for a in aliases if a not in IGNORE_TABLES})
    if len(from_tables) == 1:
        table = from_tables[0]
        cols_on_table = schema.get(table, set())
        if cols_on_table:
            # Strip CTE WITH ... AS (...) blocks — their columns shadow
            # the FROM table. Crude: drop everything up to "FROM" if a
            # WITH appears.
            scan_text = block
            if re.search(r"\bWITH\b", scan_text, re.IGNORECASE):
                # Skip — too noisy. CTE columns confuse bare-ident match.
                pass
            else:
                # Skip the SELECT-list (lots of expressions, AS aliases).
                # Focus on WHERE / ORDER BY / GROUP BY where col refs are
                # cleaner.
                where_match = re.search(
                    r"\b(?:WHERE|ORDER\s+BY|GROUP\s+BY|HAVING)\b(.+)", block,
                    re.IGNORECASE | re.DOTALL,
                )
                if where_match:
                    where_section = where_match.group(1)
                    # Strip strings and parenthesised function calls
                    where_section = re.sub(r"'[^']*'", "", where_section)
                    where_section = re.sub(r"\$\d+", "", where_section)
                    for m in RE_BARE_IDENT.finditer(where_section):
                        ident = m.group(1).lower()
                        if ident in SQL_KEYWORDS_FULL or ident in NEVER_COLUMN:
                            continue
                        if ident in cols_on_table:
                            continue
                        if ident == table:
                            continue
                        # Skip anything that's an alias the user defined
                        if ident in aliases:
                            continue
                        if (table, ident) in seen:
                            continue
                        seen.add((table, ident))
                        absolute = byte_offset + m.start()
                        line = full_text[:absolute].count("\n") + 1
                        findings.append(Finding(
                            file=file_path, line=line, table=table, column=ident,
                            detail=f"bare `{ident}` in WHERE/ORDER BY/GROUP BY of single-table query on `{table}` — col not on table",
                        ))

    # 2. INSERT INTO column lists
    for m in RE_INSERT_COLS.finditer(block):
        table = m.group(1).lower()
        if table in IGNORE_TABLES or table not in schema:
            continue
        col_list = re.sub(r"--[^\n]*", "", m.group(2))
        cols_in_query = [c.strip().split()[0].lower() for c in col_list.split(",") if c.strip()]
        cols_in_query = [c for c in cols_in_query if c.replace("_", "").isalnum()]
        cols_on_table = schema.get(table, set())
        for col in cols_in_query:
            if col in cols_on_table:
                continue
            absolute = byte_offset + m.start()
            line = full_text[:absolute].count("\n") + 1
            findings.append(Finding(
                file=file_path, line=line, table=table, column=col,
                detail=f"INSERT INTO `{table}(...{col}...)` — column not on table",
            ))

    return findings


def scan() -> list[Finding]:
    schema = _load_schema()
    findings: list[Finding] = []
    for d in SCAN_DIRS:
        for path in d.rglob("*.py"):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if any(rel.startswith(p) for p in IGNORE_FILE_PREFIXES):
                continue
            if "/__pycache__/" in rel:
                continue
            text = path.read_text(errors="replace")
            for m in RE_SQL_BLOCK.finditer(text):
                findings.extend(_scan_block(m.group(1), rel, m.start(1), text, schema))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    findings = scan()
    # Dedup (same file+table+column from multiple SQL blocks is one bug)
    seen: set[tuple[str, str, str]] = set()
    unique: list[Finding] = []
    for f in findings:
        key = (f.file, f.table, f.column)
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)

    if args.json:
        sys.stdout.write(json.dumps(
            [{"file": f.file, "line": f.line, "table": f.table,
              "column": f.column, "detail": f.detail} for f in unique],
            indent=2,
        ))
    else:
        if not unique:
            print("# Column-existence audit — no findings")
            print("\nEvery qualified column reference in server/ resolves to a real schema column.")
        else:
            print(f"# Column-existence audit — {len(unique)} findings\n")
            print("Each is a 42703 `column does not exist` waiting for the first request.\n")
            print("| file:line | table | column | detail |")
            print("|---|---|---|---|")
            by_table: dict[str, list[Finding]] = defaultdict(list)
            for f in unique:
                by_table[f.table].append(f)
            for table in sorted(by_table.keys()):
                for f in sorted(by_table[table], key=lambda x: (x.file, x.line)):
                    print(f"| `{f.file}:{f.line}` | `{f.table}` | `{f.column}` | {f.detail} |")

    return 1 if (args.strict and unique) else 0


if __name__ == "__main__":
    sys.exit(main())
