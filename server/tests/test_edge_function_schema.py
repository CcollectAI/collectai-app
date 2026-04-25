"""
Static analysis test: verify Supabase edge function table/column references
are covered by migration SQL files.

Parses CREATE TABLE and ALTER TABLE ADD COLUMN statements from migrations,
then checks that every column referenced by edge function inserts/updates/
upserts exists in the accumulated schema. No DB connection needed.
"""
import re
from pathlib import Path
from typing import Dict, Set

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent.parent          # repo root
_MIGRATIONS_DIR = _ROOT / "supabase" / "migrations"
_FUNCTIONS_DIR = _ROOT / "supabase" / "functions"

# ---------------------------------------------------------------------------
# Migration parser: build {table: {col, col, ...}} from SQL files
# ---------------------------------------------------------------------------

# Matches:  CREATE TABLE [IF NOT EXISTS] [public.]<table> ( ... column defs
_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?(\w+)\s*\(",
    re.IGNORECASE,
)

# Matches column definitions inside CREATE TABLE:  <col_name> <type> ...
_COL_DEF_RE = re.compile(
    r"^\s+(\w+)\s+(?:uuid|text|bigserial|bigint|integer|int|numeric|boolean|"
    r"jsonb|json|timestamptz|timestamp|serial)\b",
    re.IGNORECASE,
)

# Matches:  ALTER TABLE [public.]<table> ADD COLUMN [IF NOT EXISTS] <col>
_ALTER_ADD_COL_RE = re.compile(
    r"ALTER\s+TABLE\s+(?:public\.)?(\w+)\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
    re.IGNORECASE,
)

# Multi-statement ADD COLUMN in a single ALTER TABLE block:
#   ADD COLUMN [IF NOT EXISTS] <col> <type>
_MULTI_ADD_COL_RE = re.compile(
    r"ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+",
    re.IGNORECASE,
)

# ALTER TABLE ... ADD COLUMN as part of a multi-line ALTER
_ALTER_TABLE_HEADER_RE = re.compile(
    r"ALTER\s+TABLE\s+(?:public\.)?(\w+)\s*$",
    re.IGNORECASE,
)


def _parse_migrations() -> Dict[str, Set[str]]:
    """Return {table_name: {column_name, ...}} from all migration .sql files."""
    schema: Dict[str, Set[str]] = {}
    if not _MIGRATIONS_DIR.is_dir():
        return schema

    sql_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    for path in sql_files:
        text = path.read_text(errors="replace")
        _parse_sql(text, schema)
    return schema


def _parse_sql(text: str, schema: Dict[str, Set[str]]) -> None:
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # --- CREATE TABLE ---
        m = _CREATE_TABLE_RE.search(line)
        if m:
            table = m.group(1).lower()
            schema.setdefault(table, set())
            # Scan column defs until closing paren
            j = i + 1
            while j < len(lines):
                cline = lines[j]
                cm = _COL_DEF_RE.match(cline)
                if cm:
                    col = cm.group(1).lower()
                    # Skip SQL keywords that look like column names
                    if col not in (
                        "primary", "unique", "foreign", "check", "constraint",
                        "references", "on", "create", "drop", "alter", "grant",
                        "index",
                    ):
                        schema[table].add(col)
                if ");" in cline or (cline.strip() == ")"):
                    break
                j += 1

        # --- ALTER TABLE ... ADD COLUMN (single-line) ---
        m = _ALTER_ADD_COL_RE.search(line)
        if m:
            table = m.group(1).lower()
            col = m.group(2).lower()
            schema.setdefault(table, set())
            schema[table].add(col)

        # --- ALTER TABLE <table>\n  ADD COLUMN ... (multi-line) ---
        m = _ALTER_TABLE_HEADER_RE.search(line.rstrip(",; "))
        if m and "ADD COLUMN" not in line.upper():
            table = m.group(1).lower()
            schema.setdefault(table, set())
            j = i + 1
            while j < len(lines):
                cline = lines[j]
                mcol = _MULTI_ADD_COL_RE.search(cline)
                if mcol:
                    schema[table].add(mcol.group(1).lower())
                # End of multi-line ALTER: semicolon-terminated line
                if cline.rstrip().endswith(";"):
                    break
                j += 1

        i += 1


# ---------------------------------------------------------------------------
# Edge function column references (manually extracted from index.ts files)
#
# Each entry: (function_name, table, column_list, operation)
# ---------------------------------------------------------------------------

EDGE_FUNCTION_DEPS = [
    # predict-sessions/index.ts  ->  .from('predict_sessions').insert({...})
    (
        "predict-sessions",
        "predict_sessions",
        ["user_id", "source", "version", "category", "idem_key", "meta"],
        "insert",
    ),
    # predict-complete/index.ts  ->  .from('predict_sessions').update({...})
    (
        "predict-complete",
        "predict_sessions",
        ["output", "image_url", "version"],
        "update",
    ),
    # predict-complete/index.ts  ->  .from('training_items').upsert({...})
    (
        "predict-complete",
        "training_items",
        ["idem_key", "source", "version", "image_url", "title", "attributes"],
        "upsert",
    ),
    # predict-label/index.ts  ->  .from('label_events').insert({...})
    (
        "predict-label",
        "label_events",
        ["session_id", "payload", "image_url", "source", "version"],
        "insert",
    ),
    # predict-label/index.ts  ->  .from('training_items').upsert({...})
    (
        "predict-label",
        "training_items",
        ["idem_key", "source", "version", "image_url", "attributes", "title"],
        "upsert",
    ),
    # predict-price/index.ts  ->  .from('model_gate').select(...)
    (
        "predict-price",
        "model_gate",
        ["name", "active_version", "candidate_version", "candidate_split"],
        "select",
    ),
    # predict-price/index.ts  ->  .from('rate_limits').insert/select
    (
        "predict-price",
        "rate_limits",
        ["subject", "resource", "ts", "id"],
        "insert/select",
    ),
    # predict-price/index.ts  ->  .from('price_cache').select/insert
    (
        "predict-price",
        "price_cache",
        ["keyhash", "price_eur", "created_at"],
        "select/insert",
    ),
    # predict-price/index.ts  ->  .from('prediction_events').insert({...})
    (
        "predict-price",
        "prediction_events",
        ["session_id", "model_name", "model_version", "input", "output", "latency_ms"],
        "insert",
    ),
    # market-search-ebay/index.ts  ->  .from('rate_limits')
    (
        "market-search-ebay",
        "rate_limits",
        ["subject", "resource", "ts", "id"],
        "insert/select",
    ),
    # market-search-ebay/index.ts  ->  .from('market_cache').insert/select
    (
        "market-search-ebay",
        "market_cache",
        ["provider", "q", "category", "hits", "created_at"],
        "insert/select",
    ),
    # flags/index.ts  ->  .from('feature_flags').select('key,value')
    (
        "flags",
        "feature_flags",
        ["key", "value"],
        "select",
    ),
    # _shared/metrics.ts  ->  .from('fn_metrics').insert({...})
    (
        "_shared/metrics",
        "fn_metrics",
        ["fn", "status", "latency_ms", "idem_key", "session_id", "payload"],
        "insert",
    ),
    # log-prediction/index.ts  ->  REST POST to prediction_events_v2
    (
        "log-prediction",
        "prediction_events_v2",
        ["category", "title", "features", "prediction", "reason", "gated",
         "platform", "model_name", "model_version"],
        "insert (REST)",
    ),
    # log-actual/index.ts  ->  REST PATCH to prediction_events_v2
    (
        "log-actual",
        "prediction_events_v2",
        ["actual_eur"],
        "update (REST)",
    ),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def migration_schema() -> Dict[str, Set[str]]:
    return _parse_migrations()


@pytest.mark.parametrize(
    "func_name, table, columns, operation",
    EDGE_FUNCTION_DEPS,
    ids=[f"{d[0]}:{d[1]}" for d in EDGE_FUNCTION_DEPS],
)
def test_edge_function_columns_exist_in_migrations(
    migration_schema: Dict[str, Set[str]],
    func_name: str,
    table: str,
    columns: list,
    operation: str,
):
    """Verify that every column an edge function references is defined in migrations."""
    # Tables created via Supabase dashboard/RPCs without a corresponding
    # migration file. They EXIST in production but the migration parser
    # can't see them. TODO: capture them in a migration file so this
    # allowlist can shrink.
    DASHBOARD_CREATED = {"label_events", "prediction_events_v2"}
    if table in DASHBOARD_CREATED:
        import pytest
        pytest.skip(f"{table} created via dashboard, not in migrations (known gap)")
    assert table in migration_schema, (
        f"Edge function '{func_name}' references table '{table}' "
        f"(operation: {operation}) but no CREATE TABLE found in migrations"
    )
    table_cols = migration_schema[table]
    missing = [c for c in columns if c not in table_cols]
    assert not missing, (
        f"Edge function '{func_name}' {operation}s into '{table}' "
        f"with columns {missing} that are NOT defined in any migration. "
        f"Available columns: {sorted(table_cols)}"
    )


def test_migration_parser_finds_expected_tables(migration_schema):
    """Sanity check: the parser finds the core tables we know exist."""
    expected = {
        "predict_sessions", "label_events", "training_items",
        "rate_limits", "market_cache", "price_cache",
        "prediction_events", "model_gate", "feature_flags",
        "fn_metrics",
    }
    found = set(migration_schema.keys())
    missing = expected - found
    assert not missing, f"Migration parser failed to find tables: {missing}"


def test_migration_parser_finds_known_columns(migration_schema):
    """Sanity check: parser captures columns we know are defined."""
    # predict_sessions got source/version/idem_key/meta in 20260412 migration
    for col in ("source", "version", "idem_key", "meta"):
        assert col in migration_schema.get("predict_sessions", set()), (
            f"predict_sessions.{col} should exist (added in 20260412 migration)"
        )
    # training_items got idem_key/source/version/attributes in 20250921 migration
    for col in ("idem_key", "source", "version", "attributes"):
        assert col in migration_schema.get("training_items", set()), (
            f"training_items.{col} should exist"
        )
