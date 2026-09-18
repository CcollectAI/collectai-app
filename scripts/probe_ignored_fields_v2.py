"""Class V, second run: read the wrapper's payload TYPE, not the call expression.

The first probe (`probe_ignored_fields.py`) matched only calls whose body is an
INLINE object literal and reached **11 of 87** write calls — 13% — and found
nothing, which is not the same as clean. Most wrappers take a TYPED PARAMETER
and pass it through, often with `as Record<string, unknown>` erasing it:

    export const updateAlertPreferences = (prefs: { price_drop_enabled?: boolean }) =>
      patch<…>("/settings/alert-preferences", prefs as Record<string, unknown>);

The keys live in the SIGNATURE. This reads them there, then diffs against the
Pydantic model bound by the matching FastAPI route. Pydantic ignores unknown
keys, so a dropped field is a 200 with nothing saved — invisible to `tsc` (the
client's own type says the field exists) and to any test that mocks the API.

Read-only. Reports COVERAGE as loudly as findings, because 0 findings over a
small denominator is the failure mode this class already hit once.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path('/Users/merle/GitHub/CcollectAI')
API = ROOT / 'src/api'
SERVER = ROOT / 'server/app'


def balanced(s: str, i: int, open_ch: str, close_ch: str) -> int:
    """Index just past the matching close, starting at an opener at i."""
    depth = 0
    while i < len(s):
        if s[i] == open_ch:
            depth += 1
        elif s[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def type_keys(block: str) -> list[str]:
    """Top-level property names of an inline object TYPE body."""
    keys, depth, i, cur = [], 0, 0, ''
    while i < len(block):
        c = block[i]
        if c in '{([<':
            depth += 1
        elif c in '})]>':
            depth -= 1
        if depth == 0 and c in ';,\n':
            m = re.match(r'\s*([A-Za-z_$][\w$]*)\s*\??\s*:', cur)
            if m:
                keys.append(m.group(1))
            cur = ''
        else:
            cur += c
        i += 1
    m = re.match(r'\s*([A-Za-z_$][\w$]*)\s*\??\s*:', cur)
    if m:
        keys.append(m.group(1))
    return keys


# ── named types declared anywhere under src/ (for `payload: SomeType`) ────────
named_types: dict[str, list[str]] = {}
for f in sorted((ROOT / 'src').rglob('*.ts')):
    src = f.read_text(encoding='utf-8')
    for m in re.finditer(r'\b(?:type\s+([A-Za-z_$][\w$]*)\s*=\s*|interface\s+([A-Za-z_$][\w$]*)\s*)\{', src):
        name = m.group(1) or m.group(2)
        open_i = src.index('{', m.end() - 1)
        close_i = balanced(src, open_i, '{', '}')
        if close_i > 0:
            named_types.setdefault(name, type_keys(src[open_i + 1:close_i]))

# ── client: every post/patch/put, with the keys we can prove it sends ─────────
VERB = re.compile(r'\b(post|patch|put)\s*(?:<[^;]*?>)?\s*\(')
calls = []          # (file, verb, path, keys, how)
no_body = 0
transports = 0
unreadable = []

for f in sorted(API.glob('*.ts')):
    src = f.read_text(encoding='utf-8')
    for m in VERB.finditer(src):
        verb = m.group(1)
        open_i = src.index('(', m.end() - 1)
        close_i = balanced(src, open_i, '(', ')')
        if close_i < 0:
            continue
        args_s = src[open_i + 1:close_i]
        # split top-level args
        # A template literal is DELIMITED by the same character at both ends, so
        # it cannot be counted like a bracket. The first version listed '`' in
        # both the opener and closer sets of an if/elif — the opener branch
        # always won, depth never returned to 0, and every call with a
        # `/items/${id}` style path was silently counted as having NO BODY.
        parts, depth, cur, in_tpl = [], 0, '', False
        for c in args_s:
            if c == '`':
                in_tpl = not in_tpl
            elif not in_tpl:
                if c in '{([':
                    depth += 1
                elif c in '})]':
                    depth -= 1
            if c == ',' and depth == 0 and not in_tpl:
                parts.append(cur); cur = ''
            else:
                cur += c
        parts.append(cur)
        if not parts or not parts[0].strip():
            continue
        raw0 = parts[0].strip()
        # A transport, not an endpoint: `post(path, body)` inside httpClient /
        # storageApi / collectorsApi takes the path as a PARAMETER. Six of the
        # 27 "unreadable" calls were these — counted as a gap when there is no
        # endpoint to compare against.
        if not (raw0.startswith('`') or raw0.startswith('"') or raw0.startswith("'")):
            transports += 1
            continue
        path_raw = raw0.strip('`"\'')
        path = re.sub(r'\$\{[^}]*\}', '{}', path_raw).split('?')[0].rstrip('/')
        if len(parts) < 2 or not parts[1].strip():
            no_body += 1
            continue
        body = parts[1].strip()
        # `{}` cannot lose a field. Seven of the 27 were these.
        if re.fullmatch(r'\{\s*\}', body):
            no_body += 1
            continue

        # (a) inline object literal at the call site
        if body.startswith('{'):
            inner = body[1:balanced(body, 0, '{', '}')]
            # `[,:}]` — shorthand `{ status }` ends the key with `}`, so a
            # pattern requiring ':' or ',' read six single-key payloads as
            # unreadable. `$` too, for a trailing key with no separator.
            keys = re.findall(r'(?:^|,)\s*([A-Za-z_$][\w$]*)\s*(?:[,:}]|$)', inner)
            if keys:
                calls.append((f.name, verb, path, sorted(set(keys)), 'inline'))
                continue

        # (b) an identifier (possibly `x as Record<...>`) -> the wrapper's param type
        ident = re.match(r'([A-Za-z_$][\w$]*)\s*(?:as\b|$)', body)
        if ident:
            name = ident.group(1)
            # Scope the lookup to the ENCLOSING wrapper. Searching all of
            # `head` took the LAST matching signature anywhere above, and
            # `\(\s*name` only matches a FIRST parameter — so
            # `updateMandate = (id, payload: Record<…>)` was skipped and the
            # call was credited with `createMandate`'s object type, reporting
            # POST keys against a PATCH route.
            decl = max(src.rfind('export const ', 0, m.start()),
                       src.rfind('export function ', 0, m.start()),
                       src.rfind('\nconst ', 0, m.start()))
            head = src[decl if decl > 0 else 0:m.start()]
            sig = None
            for pm in re.finditer(
                    rf'[(,]\s*{re.escape(name)}\s*\??\s*:\s*', head):
                sig = pm.end()
            if sig is not None:
                rest = head[sig:]
                if rest.lstrip().startswith('{'):
                    o = head.index('{', sig)
                    c = balanced(head, o, '{', '}')
                    keys = type_keys(head[o + 1:c])
                    if keys:
                        calls.append((f.name, verb, path, sorted(set(keys)), 'inline-param-type'))
                        continue
                else:
                    tm = re.match(r'\s*([A-Za-z_$][\w$]*)', rest)
                    if tm and tm.group(1) in named_types and named_types[tm.group(1)]:
                        calls.append((f.name, verb, path, sorted(set(named_types[tm.group(1)])),
                                      f'named:{tm.group(1)}'))
                        continue
        unreadable.append((f.name, verb, path, body[:40]))

# ── server: route -> bound Pydantic model fields ─────────────────────────────
# Keyed by (file, class) — NOT by bare name. `ListingCreate` is declared in BOTH
# marketplace_listing_router.py and p2p_listing_router.py with different fields,
# so a name-keyed dict let the second overwrite the first and reported
# `marketplace_id` and `format` as undeclared when the bound model declares both.
models: dict[tuple[str, str], set[str]] = {}
routes = []
for f in sorted(SERVER.rglob('*.py')):
    try:
        text = f.read_text(encoding='utf-8')
        tree = ast.parse(text)
    except SyntaxError:
        continue
    # The router PREFIX, or a route path matches the wrong file entirely:
    # `p2p_listing_router` is mounted at `/p2p` and declares `/listings`, so an
    # endswith test on the bare path claimed `POST /marketplace/listings` for
    # it. Both ends must be the full path before anything is reported.
    prefixes = re.findall(r'APIRouter\(\s*prefix\s*=\s*["\']([^"\']+)["\']', text)
    prefix = prefixes[0] if prefixes else ''
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            fields = {n.target.id for n in node.body
                      if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
            if fields:
                models[(str(f.relative_to(ROOT)), node.name)] = fields
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in getattr(node, 'decorator_list', []):
                call = dec.func if isinstance(dec, ast.Call) else dec
                if not (isinstance(call, ast.Attribute) and call.attr in ('post', 'patch', 'put')):
                    continue
                path = dec.args[0].value if (isinstance(dec, ast.Call) and dec.args
                                             and isinstance(dec.args[0], ast.Constant)) else ''
                annos = [a.annotation.id for a in node.args.args
                         if isinstance(getattr(a, 'annotation', None), ast.Name)]
                routes.append((str(f.relative_to(ROOT)), node.name,
                               (prefix + path) if path.startswith('/') else prefix, annos))


def norm(p: str) -> str:
    return re.sub(r'\{[^}]*\}', '{}', p).split('?')[0].rstrip('/')


findings, matched, unmatched_route, no_model = [], 0, 0, 0
for fname, verb, path, keys, how in calls:
    tail = norm(path)
    hit = None
    for sfile, fn, spath, annos in routes:
        if spath and norm(spath) and norm(spath) == tail:
            hit = (sfile, fn, annos)
            break
    if not hit:
        unmatched_route += 1
        continue
    sfile, fn, annos = hit
    fields: set[str] = set()
    for a in annos:
        # the route's OWN file first; only then anywhere else
        if (sfile, a) in models:
            fields |= models[(sfile, a)]
        else:
            for (mf, mn), mfields in models.items():
                if mn == a:
                    fields |= mfields
                    break
    if not fields:
        no_model += 1
        continue
    matched += 1
    unknown = [k for k in keys if k not in fields]
    if unknown:
        findings.append((fname, verb, path, unknown, fn, sfile, how))

print("=" * 78)
print("CLASS V, run 2 — the app sends a field the server drops on the floor")
print("=" * 78)
for fname, verb, path, unknown, fn, sfile, how in findings:
    print(f"\n  {fname}: {verb.upper()} {path}")
    print(f"      sends {unknown}")
    print(f"      bound to {fn}() in {sfile}, which declares no such field")
    print(f"      (payload read from: {how})")

total_writes = 87
print(f"\n{'-' * 78}")
print(f"  findings                                  : {len(findings)}")
print(f"  payloads READ (keys proven)               : {len(calls)}")
print(f"    of which from the call site (inline)    : {sum(1 for c in calls if c[4] == 'inline')}")
print(f"    of which from the SIGNATURE (new)       : {sum(1 for c in calls if c[4] != 'inline')}")
print(f"  calls with no body at all                 : {no_body}")
print(f"  payloads still unreadable                 : {len(unreadable)}")
print(f"  read payloads matched to a route+model    : {matched}")
print(f"    path matched no server route            : {unmatched_route}")
print(f"    route had no Pydantic body model        : {no_model}")
print(f"\n  COVERAGE: {matched} of ~{total_writes} write calls fully checked "
      f"({100 * matched // total_writes}%)")
if unreadable:
    print("\n  Still unreadable (the honest gap):")
    for fname, verb, path, body in unreadable:
        print(f"    {fname}: {verb.upper()} {path}  <- {body!r}")
