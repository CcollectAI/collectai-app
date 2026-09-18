"""Class V probe: the app SENDS a field the server drops on the floor.

Pydantic ignores unknown keys by default, so a client that posts `{"foo": 1}`
to a model without `foo` gets a 200 and no `foo`. That is the same shape as
class T (server sends, client ignores) with the arrow reversed — and it is
worse, because the member THINKS they saved something.

Method: for every `post(...)`/`patch(...)`/`put(...)` in src/api/*.ts whose body
is an inline object literal, take its keys; find the route the path maps to and
the Pydantic model it binds; report keys the model has no field for.
"""
import ast, re, json
from pathlib import Path

ROOT = Path('/Users/merle/GitHub/CcollectAI')
API = ROOT / 'src/api'
SERVER = ROOT / 'server/app'

# --- 1. client: path -> body keys -----------------------------------------
calls = []
CALL = re.compile(r'\b(post|patch|put)\s*(?:<[^>]*>)?\s*\(\s*`([^`]+)`\s*,\s*\{([^}]*)\}', re.S)
for f in sorted(API.glob('*.ts')):
    src = f.read_text()
    for m in CALL.finditer(src):
        verb, path, body = m.group(1), m.group(2), m.group(3)
        keys = re.findall(r'^\s*([a-z_][A-Za-z0-9_]*)\s*[,:]', body, re.M)
        if not keys:
            continue
        clean = re.sub(r'\$\{[^}]*\}', '{id}', path)
        calls.append((f.name, verb, clean, sorted(set(keys))))

# --- 2. server: route -> model fields --------------------------------------
models = {}
routes = []
for f in sorted(SERVER.rglob('*.py')):
    try:
        tree = ast.parse(f.read_text())
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            fields = [n.target.id for n in node.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)]
            if fields:
                models[node.name] = set(fields)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in getattr(node, 'decorator_list', []):
                call = dec.func if isinstance(dec, ast.Call) else dec
                if not (isinstance(call, ast.Attribute) and call.attr in ('post', 'patch', 'put')):
                    continue
                path = ''
                if isinstance(dec, ast.Call) and dec.args and isinstance(dec.args[0], ast.Constant):
                    path = dec.args[0].value
                body_models = [a.annotation.id for a in node.args.args
                               if isinstance(getattr(a, 'annotation', None), ast.Name)
                               and a.annotation.id in models or False]
                routes.append((str(f.relative_to(ROOT)), node.name, path,
                               [a.annotation.id for a in node.args.args
                                if isinstance(getattr(a, 'annotation', None), ast.Name)]))

def norm(p):
    p = re.sub(r'\{[^}]*\}', '{}', p).rstrip('/')
    return p.split('?')[0]

findings = []
for fname, verb, path, keys in calls:
    tail = norm(path)
    match = None
    for sfile, fn, spath, annos in routes:
        if not spath:
            continue
        if tail.endswith(norm(spath)) and norm(spath) != '':
            match = (sfile, fn, annos)
            break
    if not match:
        continue
    sfile, fn, annos = match
    fields = set()
    for a in annos:
        fields |= models.get(a, set())
    if not fields:
        continue
    unknown = [k for k in keys if k not in fields]
    if unknown:
        findings.append(f"{fname}: {verb.upper()} {path} sends {unknown} — {fn}() in {sfile} has no such field(s)")

for f in findings:
    print(f)
print(f"\n{len(findings)} client payload(s) carrying a key the server model does not declare "
      f"(of {len(calls)} inline-body calls, {len(models)} models)")
