"""Audit router .py files for SQL that references missing tables/views/RPCs/columns.

Surfaces the class of drift that mocked unit tests can't see — column renames,
ghost tables, missing RPCs, FK targets pointing at the wrong table — by parsing
every triple-quoted SQL block in routers and cross-checking against the live DB.

Run on EC2 (or anywhere with DB_DSN_DIRECT pointed at prod):

    cd /opt/collectors/server && \\
    sudo -E -u ubuntu /opt/collectors/.venv/bin/python /tmp/audit_router_sql_drift.py

Output: prints a markdown report. Pipe to a file if you want.

Caveats / known false-positive sources:
- Bare unqualified column refs are NOT checked (would be a false-positive nuclear).
- Only `alias.column` form is matched against schema.
- Common SQL keywords + detected CTE names are filtered out from table-ref check.
- ILIKE / dynamic SQL inside f-strings may or may not match; report it manually.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Iterable

import asyncpg


# Router directories to scan
ROUTER_DIRS = [
    Path("/opt/collectors/server/app/routes"),
    Path("/opt/collectors/server/app/features"),
    Path("/opt/collectors/server/app/agents"),
]

# Match SQL strings passed to asyncpg call sites only — eliminates the
# docstring/dataclass/JSON-template noise that a generic """ scan picks up.
# Covers: await conn.execute("""..."""), conn.fetch(...), conn.fetchrow(...),
# conn.fetchval(...), pool.execute(...), and the f-string variants.
SQL_BLOCK_RE = re.compile(
    r'(?:conn|pool|cur|cursor|tx|txn|c)\s*\.\s*'
    r'(?:execute|fetch|fetchrow|fetchval|fetchmany|executemany)\s*\(\s*'
    r'(?:f|r|rb|fr|rf)?"""(.*?)"""',
    re.DOTALL | re.IGNORECASE,
)
SQL_VERB_RE = re.compile(r'\b(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE)\b', re.IGNORECASE)

# table refs: FROM/INTO/JOIN/UPDATE <name> — possibly with a schema prefix.
# Schema-qualified refs to auth/information_schema/pg_catalog are valid SQL
# but not in our public-schema scan, so they're matched and then skipped.
TABLE_REF_RE = re.compile(
    r'\b(?:FROM|INTO|JOIN|UPDATE)\s+(?:(auth|public|information_schema|pg_catalog)\.)?([a-z_][a-z0-9_]*)',
    re.IGNORECASE,
)
# EXTRACT(... FROM x) is a SQL-builtin pattern that confuses TABLE_REF_RE —
# strip these spans before matching.
EXTRACT_FROM_RE = re.compile(r'\bEXTRACT\s*\(\s*\w+\s+FROM\s+[^)]+\)', re.IGNORECASE)

# Alias mapping: FROM/JOIN <table> [AS] <alias>
ALIAS_RE = re.compile(
    r'\b(?:FROM|JOIN|UPDATE)\s+(?:public\.)?([a-z_][a-z0-9_]*)\s+(?:AS\s+)?([a-z_][a-z0-9_]*)\b',
    re.IGNORECASE,
)

# Qualified column refs in SQL: alias.column (lowercase only — SQL convention)
QUALIFIED_COL_RE = re.compile(r'\b([a-z][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b')

# RPC calls: rpc_<name>(
RPC_CALL_RE = re.compile(r'\b(rpc_[a-z0-9_]+)\s*\(', re.IGNORECASE)

# CTE detection — both first and chained CTEs
CTE_FIRST_RE = re.compile(r'\bWITH\s+([a-z_][a-z0-9_]*)\s+AS\s*\(', re.IGNORECASE)
CTE_CHAIN_RE = re.compile(r'\)\s*,\s*([a-z_][a-z0-9_]*)\s+AS\s*\(', re.IGNORECASE)

# SQL keywords / common false-positive identifiers to suppress in table-ref check.
SQL_KEYWORDS = frozenset({
    "select", "where", "from", "into", "update", "join", "left", "right", "inner",
    "outer", "on", "and", "or", "not", "as", "is", "null", "true", "false", "case",
    "when", "then", "else", "end", "group", "order", "by", "limit", "offset",
    "having", "union", "all", "distinct", "with", "exists", "in", "for", "default",
    "now", "lateral", "values", "returning", "set", "using", "primary", "key",
    "foreign", "references", "cascade", "do", "update", "nothing",
    # Built-in / extension functions that look like table names in regex
    "unnest", "generate_series", "jsonb_build_object", "jsonb_set", "to_jsonb",
    "coalesce", "greatest", "least", "row_number", "row", "extract", "date_trunc",
    "split_part", "array_agg", "string_agg", "json_agg", "jsonb_agg", "count",
    "sum", "avg", "min", "max",
})

# Reserved alias-prefixes to skip in the column-check (Python attribute access
# inside SQL strings is impossible, but `auth.uid()` etc. are valid SQL).
SQL_BUILTIN_NAMESPACES = frozenset({"auth", "pg_catalog", "information_schema", "now"})


async def fetch_schema(dsn: str) -> tuple[set[str], dict[str, set[str]], set[str]]:
    """Pull tables+views+matviews, columns per table, and function names."""
    conn = await asyncpg.connect(dsn, timeout=30)
    try:
        # All tables/views/matviews under public
        rows = await conn.fetch(
            """
            SELECT table_name AS n FROM information_schema.tables WHERE table_schema = 'public'
            UNION
            SELECT table_name AS n FROM information_schema.views WHERE table_schema = 'public'
            UNION
            SELECT matviewname AS n FROM pg_matviews WHERE schemaname = 'public'
            """
        )
        tables = {r["n"] for r in rows}

        # Columns per public table
        col_rows = await conn.fetch(
            """
            SELECT table_name AS t, column_name AS c
            FROM information_schema.columns
            WHERE table_schema = 'public'
            """
        )
        columns: dict[str, set[str]] = {}
        for r in col_rows:
            columns.setdefault(r["t"], set()).add(r["c"])

        # Public functions
        func_rows = await conn.fetch(
            """
            SELECT proname AS p
            FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'public'
            """
        )
        funcs = {r["p"] for r in func_rows}
    finally:
        await conn.close()
    return tables, columns, funcs


SQL_LINE_COMMENT_RE = re.compile(r"--[^\n]*")


def _strip_sql_comments(sql: str) -> str:
    """Remove `-- …` line comments so words inside them aren't audited."""
    return SQL_LINE_COMMENT_RE.sub("", sql)


def iter_sql_blocks(text: str) -> Iterable[tuple[int, str]]:
    """Yield (line_number, sql_text) for every triple-quoted SQL-shaped block.

    Body is returned with `-- …` line comments stripped so prose inside SQL
    comments doesn't get audited as table/column references.
    """
    for m in SQL_BLOCK_RE.finditer(text):
        body = _strip_sql_comments(m.group(1))
        if not SQL_VERB_RE.search(body):
            continue
        line = text[: m.start()].count("\n") + 1
        yield line, body


def collect_aliases(sql: str) -> dict[str, str]:
    """Return alias→table mapping for FROM/JOIN/UPDATE clauses in this SQL."""
    out: dict[str, str] = {}
    for m in ALIAS_RE.finditer(sql):
        table = m.group(1).lower()
        alias = m.group(2).lower()
        if alias in SQL_KEYWORDS:
            continue
        out[alias] = table
        # The table name itself can also be used as an "alias" in unaliased queries.
        out.setdefault(table, table)
    return out


def collect_ctes(sql: str) -> set[str]:
    """Return the set of CTE names declared with WITH … AS (…)."""
    names: set[str] = set()
    for m in CTE_FIRST_RE.finditer(sql):
        names.add(m.group(1).lower())
    for m in CTE_CHAIN_RE.finditer(sql):
        names.add(m.group(1).lower())
    return names


def audit_file(
    path: Path,
    tables: set[str],
    columns: dict[str, set[str]],
    funcs: set[str],
) -> list[tuple[int, str, str]]:
    """Return list of (line, kind, detail) drift entries for this file."""
    text = path.read_text()
    drift: list[tuple[int, str, str]] = []

    for line, sql in iter_sql_blocks(text):
        ctes = collect_ctes(sql)
        aliases = collect_aliases(sql)

        # Table refs — strip EXTRACT(unit FROM expr) spans first (they
        # contain a literal FROM that isn't a table reference).
        sql_for_tables = EXTRACT_FROM_RE.sub("", sql)
        for m in TABLE_REF_RE.finditer(sql_for_tables):
            schema = (m.group(1) or "").lower()
            name = m.group(2).lower()
            # Skip cross-schema references — we only audit `public.*`.
            if schema in {"auth", "information_schema", "pg_catalog"}:
                continue
            if name in SQL_KEYWORDS or name in ctes:
                continue
            if name not in tables:
                drift.append((line, "TABLE_MISSING", name))

        # RPC refs
        for m in RPC_CALL_RE.finditer(sql):
            name = m.group(1).lower()
            if name not in funcs:
                drift.append((line, "RPC_MISSING", name))

        # Column refs (alias.column form only)
        for m in QUALIFIED_COL_RE.finditer(sql):
            alias = m.group(1).lower()
            col = m.group(2).lower()
            if alias in SQL_BUILTIN_NAMESPACES or alias in ctes:
                continue
            table = aliases.get(alias)
            if not table or table not in columns:
                continue
            if col not in columns[table] and col not in SQL_KEYWORDS:
                drift.append((line, "COLUMN_MISSING", f"{table}.{col} (used as {alias}.{col})"))

    return drift


async def main() -> int:
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("ERROR: DB_DSN_DIRECT or DB_DSN must be set", file=sys.stderr)
        return 1

    tables, columns, funcs = await fetch_schema(dsn)

    file_drift: dict[str, list[tuple[int, str, str]]] = {}
    for d in ROUTER_DIRS:
        if not d.exists():
            continue
        for f in d.rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            entries = audit_file(f, tables, columns, funcs)
            if entries:
                # Use repo-relative path for readability
                key = str(f).replace("/opt/collectors/server/", "")
                file_drift[key] = sorted(entries)

    # Markdown report
    print("# Router SQL Drift Report")
    print()
    print(f"- Schema source: live DB ({len(tables)} tables/views/matviews, {len(funcs)} public functions)")
    print(f"- Files scanned: {sum(1 for d in ROUTER_DIRS if d.exists() for _ in d.rglob('*.py'))}")
    total = sum(len(v) for v in file_drift.values())
    print(f"- Total potential drift entries: **{total}** across {len(file_drift)} files")
    print()

    # Sorted by file path
    for fname in sorted(file_drift):
        entries = file_drift[fname]
        print(f"\n## `{fname}` ({len(entries)})")
        for line, kind, detail in entries:
            print(f"  - L{line} **{kind}**: `{detail}`")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
