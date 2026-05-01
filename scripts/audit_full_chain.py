"""Unified FE → BE → DB chain audit.

For every FE httpClient call: confirm the (method, path) exists in api.lock
AND tell which BE handler receives it. For every FE Supabase REST table-op:
confirm the table/column exists in schema.lock AND tell whether any BE
handler queries the same table.

Output: docs/full-chain-audit.md — one row per FE call, with the BE handler
file:line and the DB tables it touches.

Reads only the locks (no DB / no live server). Run after audit_*_drift.py to
get the chain view.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
API_LOCK = json.loads((ROOT / "scripts" / "api.lock.json").read_text())
RPC_LOCK = json.loads((ROOT / "scripts" / "rpc.lock.json").read_text())
SCHEMA_LOCK = json.loads((ROOT / "scripts" / "schema.lock.json").read_text())
MATRIX = json.loads((ROOT / "docs" / "schema-lock-matrix.json").read_text())

OUT = ROOT / "docs" / "full-chain-audit.md"

FE_DIRS = [ROOT / "src", ROOT / "app"]
BE_DIRS = [ROOT / "server" / "app"]
EXCLUDE = {"node_modules", ".expo", ".next", "dist", "build", "ios", "web"}

# Same normalization as audit_fe_api_drift so we match the working scanner.
PLACEHOLDER_RE = re.compile(r"""\$\{[^}]+\}|\{[^}]+\}""")
TRAILING_QUERY_STAR_RE = re.compile(r"([^/])\*+$")
def normalize_path(p: str) -> str:
    p = p.split("?", 1)[0]
    p = PLACEHOLDER_RE.sub("*", p)
    p = TRAILING_QUERY_STAR_RE.sub(r"\1", p)
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p

def collapse_substitutions(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        if text[i:i+2] == "${":
            depth = 1
            i += 2
            while i < len(text) and depth > 0:
                if text[i:i+2] == "${":
                    depth += 1; i += 2
                elif text[i] == "}":
                    depth -= 1; i += 1
                else:
                    i += 1
            out.append("*")
        else:
            out.append(text[i]); i += 1
    return "".join(out)

# --- regex from existing scanners (pulled from audit_fe_api_drift.py) ---
HC_RE = re.compile(
    r"""\b(get|post|put|patch|del|postMultipart)\s*(?:<[^>]*>)?\s*\(\s*([`'"])(\/[^`'"]*)\2""",
    re.IGNORECASE,
)
RPC_RE = re.compile(
    r"""supabase\.rpc\(\s*['"]([a-z_][a-z0-9_]*)['"]"""
)
FROM_SELECT_RE = re.compile(
    r"""\.from\(\s*['"]([a-z_][a-z0-9_]*)['"]\s*\)\s*\.select\("""
)
FROM_WRITE_RE = re.compile(
    r"""\.from\(\s*['"]([a-z_][a-z0-9_]*)['"]\s*\)\s*\.(insert|update|upsert|delete)"""
)

def iter_files(dirs, suffixes):
    for d in dirs:
        if not d.exists(): continue
        for p in d.rglob("*"):
            if any(part in EXCLUDE for part in p.parts): continue
            if p.is_file() and p.suffix in suffixes: yield p

# --- index BE handlers from api.lock so we can map (method, path) -> file:line ---
api_to_handler = {}
for entry in API_LOCK.get("routes", []):
    key = f"{entry['method']} {normalize_path(entry['path'])}"
    api_to_handler[key] = f"{entry.get('file', '?')}:{entry.get('line', '?')}"

# --- count BE SQL operations per table (from MATRIX) ---
be_tables_with_writes = {t for t, v in MATRIX["tables"].items() if v.get("be_write_files")}
be_tables_with_reads = {t for t, v in MATRIX["tables"].items() if v.get("be_read_files")}

# --- scan FE for every call ---
fe_http_calls = []   # (method, path, file:line)
fe_rpc_calls = []    # (rpc_name, file:line)
fe_rest_reads = []   # (table, file:line)
fe_rest_writes = []  # (table, op, file:line)

METHOD_MAP = {"get":"GET","post":"POST","put":"PUT","patch":"PATCH","del":"DELETE","postmultipart":"POST"}

for path in iter_files(FE_DIRS, {".ts", ".tsx"}):
    try:
        raw = path.read_text(errors="ignore")
    except Exception: continue
    text = collapse_substitutions(raw)
    rel = str(path.relative_to(ROOT))
    for m in HC_RE.finditer(text):
        method = METHOD_MAP[m.group(1).lower()]
        url_norm = normalize_path(m.group(3))
        line = text[:m.start()].count("\n") + 1
        fe_http_calls.append((method, m.group(3), url_norm, f"{rel}:{line}"))
    for m in RPC_RE.finditer(text):
        line = text[:m.start()].count("\n") + 1
        fe_rpc_calls.append((m.group(1), f"{rel}:{line}"))
    for m in FROM_SELECT_RE.finditer(text):
        line = text[:m.start()].count("\n") + 1
        fe_rest_reads.append((m.group(1), f"{rel}:{line}"))
    for m in FROM_WRITE_RE.finditer(text):
        line = text[:m.start()].count("\n") + 1
        fe_rest_writes.append((m.group(1), m.group(2), f"{rel}:{line}"))

# --- match http calls to api.lock entries (best-effort) ---
api_lock_keys = list(api_to_handler.keys())
def find_handler(method, url_norm):
    target = f"{method} {url_norm}"
    return api_to_handler.get(target)

# Build summary
md = [
    "# FE → BE → DB chain audit",
    "",
    "For every frontend call, traces the full chain: FE call site → BE handler",
    "(if applicable) → DB tables touched. Generated by `scripts/audit_full_chain.py`.",
    "",
    f"## Summary",
    "",
    f"- **FE httpClient calls** (get/post/put/patch/del/postMultipart): {len(fe_http_calls)}",
    f"- **FE Supabase RPC calls** (supabase.rpc): {len(fe_rpc_calls)}",
    f"- **FE Supabase REST reads** (.from().select): {len(fe_rest_reads)}",
    f"- **FE Supabase REST writes** (.from().insert/update/upsert/delete): {len(fe_rest_writes)}",
    f"- **BE routes registered** (api.lock): {len(API_LOCK.get('routes', []))}",
    f"- **BE Supabase RPCs** (rpc.lock): {len(rpc_lock_funcs) if 'rpc_lock_funcs' in dir() else len(RPC_LOCK.get('functions', {}))}",
    f"- **DB tables in schema.lock**: {len(SCHEMA_LOCK['tables'])}",
    f"- **DB tables touched by BE writes**: {len(be_tables_with_writes)}",
    f"- **DB tables touched by BE reads**: {len(be_tables_with_reads)}",
    "",
    "## FE httpClient → BE route resolution",
    "",
    "For each unique (method, path) called from the FE: does a BE handler exist?",
    "",
    "| FE method | FE path | BE handler | resolved? |",
    "|---|---|---|---|",
]

# Dedupe FE http calls by (method, url_norm)
seen = {}
for method, url, url_norm, ref in fe_http_calls:
    key = (method, url_norm)
    seen.setdefault(key, []).append(ref)

for (method, url_norm), refs in sorted(seen.items()):
    handler = find_handler(method, url_norm)
    ok = "✓" if handler else "✗ NO HANDLER"
    handler_short = (handler or "—")[:60]
    md.append(f"| {method} | `{url_norm}` | `{handler_short}` | {ok} |")

# RPC chain
md += [
    "",
    "## FE RPC calls → DB function resolution",
    "",
    "| FE rpc | params expected by lock | resolved? |",
    "|---|---|---|",
]
# rpc.lock.json shape: {"functions": {"name": ["p_x", "p_y"]}, ...}
rpc_lock_funcs = RPC_LOCK.get("functions", {}) if isinstance(RPC_LOCK.get("functions"), dict) else {}
seen_rpc = {}
for rpc_name, ref in fe_rpc_calls:
    seen_rpc.setdefault(rpc_name, []).append(ref)
for rpc_name, refs in sorted(seen_rpc.items()):
    if rpc_name in rpc_lock_funcs:
        params = ", ".join(rpc_lock_funcs[rpc_name])
        md.append(f"| `{rpc_name}` | `{params}` | ✓ |")
    else:
        md.append(f"| `{rpc_name}` | — | ✗ MISSING |")

# Supabase REST chain
md += [
    "",
    "## FE Supabase REST → DB tables",
    "",
    "Direct .from(table).select / .from(table).insert/update/upsert/delete calls.",
    "",
    "| op | table | n call sites | in schema.lock? |",
    "|---|---|---|---|",
]
read_counts = defaultdict(int)
write_counts = defaultdict(lambda: defaultdict(int))  # table -> op -> count
for t, ref in fe_rest_reads: read_counts[t] += 1
for t, op, ref in fe_rest_writes: write_counts[t][op] += 1
for t in sorted(set(read_counts) | set(write_counts)):
    in_lock = "✓" if t in SCHEMA_LOCK["tables"] else "✗ STRAY"
    if read_counts.get(t):
        md.append(f"| select | `{t}` | {read_counts[t]} | {in_lock} |")
    for op, n in sorted(write_counts.get(t, {}).items()):
        md.append(f"| {op} | `{t}` | {n} | {in_lock} |")

# Untouched-by-BE tables that FE writes (broken contract candidates)
md += [
    "",
    "## ⚠️ FE writes a table that no BE writes",
    "",
    "These are tables the frontend pushes data into via Supabase REST that no",
    "server-side handler also writes. RLS-enforced direct writes are normal",
    "for some flows, but a FE-write with NO server-side validation is worth a look.",
    "",
]
fe_write_tables = {t for t, _, _ in fe_rest_writes}
suspicious = sorted(fe_write_tables - be_tables_with_writes)
if not suspicious:
    md.append("_None — every FE-written table also has BE writes._")
else:
    md.append("| table |")
    md.append("|---|")
    for t in suspicious:
        if t in SCHEMA_LOCK["tables"]:
            md.append(f"| `{t}` |")

OUT.write_text("\n".join(md) + "\n")
print(f"Wrote {OUT}")
print(f"  FE http calls: {len(fe_http_calls)}, unique (method,path): {len(seen)}")
print(f"  FE RPC calls: {len(fe_rpc_calls)}, unique: {len(seen_rpc)}")
print(f"  FE REST reads: {len(fe_rest_reads)} on {len(read_counts)} tables")
print(f"  FE REST writes: {len(fe_rest_writes)} on {len(write_counts)} tables")
unresolved = [(m, u) for (m, u), _ in seen.items() if not find_handler(m, u)]
print(f"  HTTP calls with no BE handler: {len(unresolved)}")
print(f"  RPC calls with no DB function: {sum(1 for n in seen_rpc if n not in rpc_lock_funcs)}")
print(f"  REST tables not in schema: {sum(1 for t in (set(read_counts) | set(write_counts)) if t not in SCHEMA_LOCK['tables'])}")
