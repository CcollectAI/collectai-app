"""GATE: a key the app sends that the server model does not declare.

Pydantic ignores unknown keys, so a client key the model has no field for is
dropped and answered **200** — invisible to `tsc` (the client's own type declares
it) and to any test that mocks the API. `submitVerifiedSale` sent `sale_date`
and `marketplace` where the model says `sold_at` and `platform`, so the date and
venue of every verified sale were discarded in silence (class V, 2026-09-19).

Two ways to fail:

1. **A mismatch** — a proven payload carries a key its route's model lacks.
2. **A NEW unreadable endpoint** — a write whose payload cannot be proven at any
   layer and is not in ALLOWLIST. Without this the gate is dodged by typing a
   payload `Record<string, unknown>`, which is what the three grandfathered
   endpoints do.

`--report` prints the full coverage breakdown instead of the gate verdict.
Baseline when this landed: 57 endpoints proven, 3 allowlisted, 0 findings.

Class V, second run: read the wrapper's payload TYPE, not the call expression.

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
# BOTH layers. `src/api` holds the thin wrappers, but for anything routed
# through `dataProvider` the WIRE payload is built inside the provider —
# `eventsProvider.createEvent` posts a 19-key snake_case literal, while the
# wrapper it calls takes `Record<string, unknown>`. Scanning only `src/api`
# reported those as unreadable when the keys were one directory away.
API_DIRS = [ROOT / 'src/api', ROOT / 'src/data/providers', ROOT / 'src/data']
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

seen_files = set()
api_files = []
for d in API_DIRS:
    for f in sorted(d.glob('*.ts')):
        if f.resolve() not in seen_files:
            seen_files.add(f.resolve()); api_files.append(f)
for f in api_files:
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
        # (c) a body built as a LOCAL: `const body = {...}` or `body.x = ...`.
        # Providers construct the wire payload this way — `updateSponsorCompany`
        # assigns body.name / body.logo_url / body.contact_email one at a time —
        # so the keys are in the enclosing function, not at the call.
        if ident:
            name = ident.group(1)
            decl = max(src.rfind('export async function', 0, m.start()),
                       src.rfind('export function', 0, m.start()),
                       src.rfind('export const', 0, m.start()))
            scope = src[decl if decl > 0 else 0:m.start()]
            keys = set(re.findall(rf'\b{re.escape(name)}\.([A-Za-z_$][\w$]*)\s*=(?!=)', scope))
            keys |= set(re.findall(rf'\b{re.escape(name)}\[["\']([A-Za-z_$][\w$]*)["\']\]\s*=(?!=)', scope))
            dm = re.search(rf'(?:const|let|var)\s+{re.escape(name)}\b[^=]*=\s*\{{', scope)
            if dm:
                o = scope.index('{', dm.end() - 1)
                c = balanced(scope, o, '{', '}')
                if c > o:
                    keys |= set(re.findall(r'(?:^|,)\s*([A-Za-z_$][\w$]*)\s*(?:[,:}]|$)', scope[o+1:c]))
            if keys:
                calls.append((f.name, verb, path, sorted(keys), 'local-body'))
                continue

        unreadable.append((f.name, verb, path, body[:40]))

# ── server: route -> bound Pydantic model fields ─────────────────────────────
# Keyed by (file, class) — NOT by bare name. `ListingCreate` is declared in BOTH
# marketplace_listing_router.py and p2p_listing_router.py with different fields,
# so a name-keyed dict let the second overwrite the first and reported
# `marketplace_id` and `format` as undeclared when the bound model declares both.
# (directory, router variable) -> prefix.
#
# The prefix is NOT always in the file that declares the routes.
# `app/features/events/_router.py` holds `router = APIRouter(prefix="/events")`
# and `events_core.py` imports that same object and decorates it — so a
# per-file lookup saw no prefix, resolved `POST ""` to the empty path, and
# never matched `POST /events` to a route at all. Nine endpoints were read and
# never compared while the gate reported them as agreeing with their model.
# Keyed by FILE first. A directory-keyed map is the models mistake one level
# up: `app/features/` holds dozens of modules that each name their router
# `router`, so the last one scanned overwrote the rest and 58 of 64 endpoints
# stopped matching. The package fallback is used only when a directory agrees
# with itself — which is the `events/_router.py` case it exists for.
# `[^)]*` stops at the first `)`, so an `APIRouter(prefix=..., dependencies=[Depends(x)])`
# would truncate and lose the prefix. Checked 2026-09-19: no APIRouter call in
# this tree has a nested paren. If one appears, the endpoint silently stops
# matching a route rather than mis-matching — the report's "path matched no
# server route" count is where that would show.
ROUTER_DEF = re.compile(r'(\w+)\s*=\s*APIRouter\(([^)]*)\)', re.S)
file_prefix: dict[tuple[str, str], str] = {}
dir_candidates: dict[tuple[str, str], set[str]] = {}
for f in SERVER.rglob('*.py'):
    try:
        text = f.read_text(encoding='utf-8')
    except OSError:
        continue
    for var, args in ROUTER_DEF.findall(text):
        m = re.search(r'prefix\s*=\s*["\']([^"\']*)["\']', args)
        pfx = m.group(1) if m else ''
        file_prefix[(str(f), var)] = pfx
        dir_candidates.setdefault((str(f.parent), var), set()).add(pfx)
dir_prefix = {k: next(iter(v)) for k, v in dir_candidates.items() if len(v) == 1}
# Third fallback, by DIRECTORY alone: the routes in `events/events_core.py`
# decorate `core_router`, an ALIAS of the shared `router` defined in
# `events/_router.py`, so neither the file nor the (dir, var) lookup resolves
# it. Used only when every APIRouter declared in that package agrees on one
# prefix — otherwise the directory says nothing and the endpoint stays
# unmatched, which is the honest outcome.
_by_dir: dict[str, set[str]] = {}
for (d, _v), pfxs in dir_candidates.items():
    _by_dir.setdefault(d, set()).update(pfxs)
dir_any = {d: next(iter(v)) for d, v in _by_dir.items() if len(v) == 1 and next(iter(v))}

models: dict[tuple[str, str], set[str]] = {}
routes = []
for f in sorted(SERVER.rglob('*.py')):
    try:
        text = f.read_text(encoding='utf-8')
        tree = ast.parse(text)
    except SyntaxError:
        continue
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
                rvar = call.value.id if isinstance(call.value, ast.Name) else 'router'
                prefix = file_prefix.get((str(f), rvar))
                if prefix is None:
                    prefix = dir_prefix.get((str(f.parent), rvar))
                if prefix is None:
                    prefix = dir_any.get(str(f.parent), '')
                path = dec.args[0].value if (isinstance(dec, ast.Call) and dec.args
                                             and isinstance(dec.args[0], ast.Constant)) else ''
                annos = [a.annotation.id for a in node.args.args
                         if isinstance(getattr(a, 'annotation', None), ast.Name)]
                routes.append((str(f.relative_to(ROOT)), node.name,
                               (prefix + path) if path.startswith('/') else prefix, annos))


def norm(p: str) -> str:
    return re.sub(r'\{[^}]*\}', '{}', p).split('?')[0].rstrip('/')


findings, matched, unmatched_route, no_model = [], 0, 0, 0
compared_eps: set[tuple[str, str]] = set()
no_model_eps: set[tuple[str, str]] = set()
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
        no_model_eps.add((verb, tail))
        continue
    matched += 1
    compared_eps.add((verb, tail))
    unknown = [k for k in keys if k not in fields]
    if unknown:
        findings.append((fname, verb, path, unknown, fn, sfile, how))

# Endpoints whose payload cannot be proven at ANY layer. Each carries a reason
# and each was checked BY HAND when added. A new entry is a deliberate opt-out
# of this gate and should be argued for, not added quietly.
ALLOWLIST = {
    ("patch", "/purchase/mandates/{}"):
        "Record<string, unknown>. Hand-checked 2026-09-19: create-mandate.tsx "
        "sends 8 keys and MandateUpdate declares all 8.",
    ("put", "/notifications/preferences"):
        "Record<string, boolean> with a COMPUTED key ({ [key]: value }), so the "
        "real contract is the toggle list. Hand-checked 2026-09-19: all 7 toggle "
        "keys are declared by NotificationPreferencesUpdate.",
    ("patch", "/marketplace/listings/{}"):
        "`patch as Record<string, unknown>` erases Partial<MarketplaceListing>. "
        "Behind SELLING_ENABLED=false; resolve when selling is switched on.",
}

proven_eps = {(v, pth) for _f, v, pth, _k, _h in calls}
unread_eps = {(v, pth) for _f, v, pth, _b in unreadable}
unproven = sorted(unread_eps - proven_eps)
unallowed = [e for e in unproven if e not in ALLOWLIST]
stale_allow = [e for e in ALLOWLIST if e not in unproven]

if "--report" not in sys.argv:
    ok = True
    if findings:
        ok = False
        print(f"FAIL  {len(findings)} payload(s) carry a key the server model does not declare:")
        for fname, verb, path, unknown, fn, sfile, how in findings:
            print(f"   {fname}: {verb.upper()} {path}")
            print(f"      sends {unknown} — {fn}() in {sfile} declares no such field")
    if unallowed:
        ok = False
        print(f"FAIL  {len(unallowed)} write endpoint(s) whose payload cannot be proven at any layer:")
        for v, pth in unallowed:
            print(f"   {v.upper()} {pth}")
        print("   Type the payload, or add it to ALLOWLIST with a reason you checked by hand.")
    if stale_allow:
        print(f"note  {len(stale_allow)} ALLOWLIST entr(ies) no longer needed:")
        for v, pth in stale_allow:
            print(f"   {v.upper()} {pth}")
    if ok:
        # COMPARED, not merely read. `proven_eps` includes endpoints whose route
        # binds no Pydantic model, where there is nothing to disagree with — and
        # a PASS line that counts those claims more than the gate checked.
        print(f"PASS  dropped fields — {len(compared_eps)} endpoint payload(s) compared "
              f"against their model, 0 mismatches; {len(no_model_eps)} route(s) bind no model; "
              f"{len(ALLOWLIST)} allowlisted.")
        sys.exit(0)
    sys.exit(1)

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
# Per-ENDPOINT, not per-call-site. A thin `src/api` wrapper taking
# Record<string, unknown> is a pass-through whose body the PROVIDER builds, so
# the same (verb, path) appears twice — once unreadable at the wrapper, once
# proven at the provider. Counting call sites double-counts those.
proven_eps = {(v, pth) for _f, v, pth, _k, _h in calls}
unread_eps = {(v, pth) for _f, v, pth, _b in unreadable}
only_unread = sorted(unread_eps - proven_eps)
print(f"\n  DISTINCT ENDPOINTS with a proven payload  : {len(proven_eps)}")
print(f"  endpoints unreadable at EVERY layer       : {len(only_unread)}")
for v, pth in only_unread:
    print(f"    {v.upper():<6} {pth}")

if unreadable:
    print("\n  Still unreadable (the honest gap):")
    for fname, verb, path, body in unreadable:
        print(f"    {fname}: {verb.upper()} {path}  <- {body!r}")
