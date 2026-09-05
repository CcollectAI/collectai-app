"""Audit PostgREST calls for `select=` / filter columns that do not exist.

The blind spot this closes
--------------------------
`audit_router_sql_drift.py` parses triple-quoted SQL handed to asyncpg. It is
blind to the OTHER way this codebase talks to the database: an httpx call to
`{SUPABASE_URL}/rest/v1/<table>` whose column list lives in a
`params={"select": "..."}` dict. There is no SQL text to parse, so a renamed
column there is invisible to every existing gate.

It stayed invisible for 199 days. `pipelines/train_price.py` asked for
`items.grade` and `items.attributes_json` — the real columns are
`condition_grade` and `attrs` — since 2026-02-19 (69fc4e9). PostgREST answers
400, the caller checks only `if resp.status_code == 200`, and the run logs
"Loaded 0 feedback samples". Zero and "the query was rejected" render
identically. The only reason anyone found out is that the first `sale_price`
feedback row arrived on 2026-08-29, which made the query actually fire, and
the watchdog saw 36 Postgres ERRORs/day — one per trained category.

What it checks
--------------
For every `client.get/post(...)` whose URL contains `/rest/v1/<table>` and
whose `params=` is a dict literal:
  * every column named in `select=` exists on <table>
  * every filter key (`"category": "eq.x"`) exists on <table>
  * every column named in `order=` exists on <table>
  * <table> itself exists

Run it on EC2, where DB_DSN_DIRECT points at prod:

    cd /opt/collectors/server && \
    sudo -E -u ubuntu /opt/collectors/.venv/bin/python scripts/audit_postgrest_selects.py

The daily watchdog runs it (server/scripts/watchdog.py, "PostgREST select
drift"). Exit 2 there is reported as "could not run", never as clean.

Exit 0 clean, 1 on findings, 2 if it could not ask (a checker that cannot
reach the DB must never print "clean" — see docs/WATCHDOG.md).
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import os
import re
import sys
from pathlib import Path

try:
    import asyncpg
except ImportError:  # --schema-json mode needs no driver
    asyncpg = None  # type: ignore[assignment]

# Scan roots, relative to the server/ directory.
SCAN_DIRS = ["app", "pipelines", "workers", "scripts"]

# PostgREST reserved query parameters — keys that are NOT column filters.
RESERVED_PARAMS = frozenset({
    "select", "order", "limit", "offset", "on_conflict", "columns",
    "or", "and", "not.or", "not.and",
})

REST_RE = re.compile(r"/rest/v1/([a-zA-Z_][a-zA-Z0-9_]*)")

# `alias:column`, `column::cast`, `column->>'k'`, `column->k`
_STRIP_RE = re.compile(r"(::[a-zA-Z_]+|->>?.*$)")


def _url_table(node: ast.AST) -> str | None:
    """Return the PostgREST table an f-string/str URL targets, else None."""
    parts: list[str] = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        parts.append(node.value)
    elif isinstance(node, ast.JoinedStr):
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            else:
                parts.append("\x00")  # an interpolation; cannot be a table name
    else:
        return None
    m = REST_RE.search("".join(parts))
    if not m:
        return None
    table = m.group(1)
    return None if table == "rpc" else table


def _split_select(sel: str) -> list[tuple[str, str | None]]:
    """Split a PostgREST select= list into (column, embedded_table) pairs.

    An embed `listings(id,title)` yields ("id", "listings") and
    ("title", "listings"); its own name is returned as ("listings", None) so
    the relationship still has to resolve to something.
    """
    out: list[tuple[str, str | None]] = []
    depth = 0
    buf = ""
    items: list[str] = []
    for ch in sel:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            items.append(buf)
            buf = ""
            continue
        buf += ch
    if buf.strip():
        items.append(buf)

    for raw in items:
        item = raw.strip()
        if not item or item == "*":
            continue
        if "(" in item and item.endswith(")"):
            head, inner = item.split("(", 1)
            inner = inner[:-1]
            embed = head.split(":")[-1].strip()
            out.append((embed, None))
            for col, sub in _split_select(inner):
                out.append((col, sub or embed))
            continue
        if ":" in item:                      # alias:column
            item = item.split(":", 1)[1]
        item = _STRIP_RE.sub("", item).strip()
        if item and item != "*":
            out.append((item, None))
    return out


def _order_columns(val: str) -> list[str]:
    cols = []
    for part in val.split(","):
        col = part.strip().split(".")[0]
        if col:
            cols.append(col)
    return cols


def scan_file(path: Path) -> list[dict]:
    """Return one record per PostgREST call site with a literal params dict."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    hits: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        params = next((kw.value for kw in node.keywords if kw.arg == "params"), None)
        if not isinstance(params, ast.Dict):
            continue

        table = None
        for arg in list(node.args) + [kw.value for kw in node.keywords if kw.arg == "url"]:
            table = _url_table(arg)
            if table:
                break
        if not table:
            continue

        select_val = None
        filters: list[str] = []
        order_val = None
        for k, v in zip(params.keys, params.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            key = k.value
            if key == "select":
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    select_val = v.value
            elif key == "order":
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    order_val = v.value
            elif key in RESERVED_PARAMS or key.startswith("not."):
                continue
            else:
                filters.append(key.split("->")[0])

        hits.append({
            "file": str(path),
            "line": node.lineno,
            "table": table,
            "select": select_val,
            "filters": filters,
            "order": order_val,
        })
    return hits


async def fetch_schema(dsn: str) -> tuple[set[str], dict[str, set[str]]]:
    if asyncpg is None:
        raise RuntimeError("asyncpg not installed; use --schema-json")
    conn = await asyncpg.connect(dsn, timeout=30)
    try:
        rows = await conn.fetch(
            """
            SELECT c.relname AS t, a.attname AS c
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
              JOIN pg_attribute a ON a.attrelid = c.oid
             WHERE n.nspname = 'public'
               AND c.relkind IN ('r', 'v', 'm', 'p', 'f')
               AND a.attnum > 0
               AND NOT a.attisdropped
            """
        )
    finally:
        await conn.close()
    cols: dict[str, set[str]] = {}
    for r in rows:
        cols.setdefault(r["t"], set()).add(r["c"])
    return set(cols), cols


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]),
                    help="server/ directory to scan (default: this script's parent)")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any finding")
    ap.add_argument("--schema-json", default="",
                    help="path to a {table: [columns]} JSON snapshot, for running "
                         "without DB access (dump it with --dump-schema on EC2)")
    ap.add_argument("--dump-schema", default="",
                    help="write the live schema to this path as JSON and exit")
    args = ap.parse_args()

    if args.schema_json:
        try:
            raw = json.loads(Path(args.schema_json).read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"POSTGREST SELECT AUDIT: COULD NOT RUN — schema snapshot unreadable: {e!r}")
            return 2
        columns = {t: set(cs) for t, cs in raw.items()}
        tables = set(columns)
    else:
        dsn = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN") or ""
        if not dsn:
            # A checker that cannot ask must not print "clean".
            print("POSTGREST SELECT AUDIT: COULD NOT RUN — DB_DSN_DIRECT/DB_DSN unset.")
            return 2
        try:
            tables, columns = await fetch_schema(dsn)
        except Exception as e:  # noqa: BLE001
            print(f"POSTGREST SELECT AUDIT: COULD NOT RUN — schema fetch failed: {e!r}")
            return 2
        if args.dump_schema:
            Path(args.dump_schema).write_text(
                json.dumps({t: sorted(cs) for t, cs in columns.items()}, indent=0),
                encoding="utf-8")
            print(f"schema snapshot written to {args.dump_schema} ({len(columns)} relations)")
            return 0

    root = Path(args.root)
    hits: list[dict] = []
    for d in SCAN_DIRS:
        base = root / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.py")):
            if "/tests/" in str(p) or p.name.startswith("test_"):
                continue
            hits.extend(scan_file(p))

    findings: list[str] = []
    for h in hits:
        t = h["table"]
        if t not in tables:
            findings.append(f"{h['file']}:{h['line']}: TABLE_MISSING {t}")
            continue
        own = columns[t]
        for col, embed in _split_select(h["select"] or ""):
            target = embed or t
            if embed is None and col not in own and col not in tables:
                findings.append(f"{h['file']}:{h['line']}: COLUMN_MISSING {t}.{col} (in select=)")
            elif embed is not None:
                if target in columns and col not in columns[target]:
                    findings.append(
                        f"{h['file']}:{h['line']}: COLUMN_MISSING {target}.{col} (embedded select=)")
        for col in h["filters"]:
            if col not in own:
                findings.append(f"{h['file']}:{h['line']}: COLUMN_MISSING {t}.{col} (filter)")
        for col in _order_columns(h["order"] or ""):
            if col not in own:
                findings.append(f"{h['file']}:{h['line']}: COLUMN_MISSING {t}.{col} (order=)")

    print(f"POSTGREST SELECT AUDIT: scanned {len(hits)} call site(s) with literal params")
    if not findings:
        print("AUDIT COMPLETE — no drift.")
        return 0
    for f in findings:
        print("  " + f)
    print(f"AUDIT COMPLETE — {len(findings)} finding(s).")
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
