"""Snapshot every FastAPI route in `server/` and write to
scripts/api.lock.json. Reads the source — no live server needed.

Captures: router prefix + decorator path → full route.
Skips: dynamic mounts (FastAPI.add_api_route(...)) — rare in this repo.

Two passes are needed because the events subpackage (and others) splits
the router across files: one module declares the APIRouter, sibling
modules import it via `from ._router import router as core_router` and
register decorators on the alias. Pass 1 builds a global router→prefix
table per-file (resolving import aliases); pass 2 walks decorators.
"""
from __future__ import annotations
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
OUT = ROOT / "scripts" / "api.lock.json"

DECORATOR_RE = re.compile(
    r"""@(\w+)\.(get|post|put|patch|delete|head|options)\(\s*["']([^"']*)["']""",
    re.IGNORECASE,
)
ROUTER_DECL_RE = re.compile(
    r"""(\w+)\s*=\s*APIRouter\(([^)]*)\)""", re.DOTALL,
)
PREFIX_KW_RE = re.compile(r"""prefix\s*=\s*["']([^"']*)["']""")
IMPORT_RE = re.compile(
    r"""^from\s+(\.{1,2}[\w.]*|[\w.]+)\s+import\s+([^\n]+)""", re.MULTILINE,
)


def _resolve_module(module: str, importer: Path) -> list[Path]:
    """Resolve a relative or absolute Python import to source files."""
    candidates: list[Path] = []
    if module.startswith("."):
        depth = len(module) - len(module.lstrip("."))
        rel = module.lstrip(".").replace(".", "/")
        base = importer.parent
        for _ in range(depth - 1):
            base = base.parent
        target = base / rel if rel else base
        candidates.append(target.with_suffix(".py"))
        candidates.append(target / "__init__.py")
    else:
        path = SERVER / module.replace(".", "/")
        candidates.append(path.with_suffix(".py"))
        candidates.append(path / "__init__.py")
    return [c for c in candidates if c.exists()]


def collect_router_prefixes() -> dict[Path, dict[str, str]]:
    """Per-file mapping {local_router_name: prefix}, including aliases
    resolved from `from X import router as Y` patterns."""
    decls: dict[Path, dict[str, str]] = {}
    for f in SERVER.rglob("*.py"):
        if "/.venv/" in str(f):
            continue
        text = f.read_text(errors="ignore")
        local: dict[str, str] = {}
        for m in ROUTER_DECL_RE.finditer(text):
            name, body = m.group(1), m.group(2)
            pm = PREFIX_KW_RE.search(body)
            local[name] = pm.group(1) if pm else ""
        if local:
            decls[f] = local

    resolved: dict[Path, dict[str, str]] = {}
    for f in SERVER.rglob("*.py"):
        if "/.venv/" in str(f):
            continue
        text = f.read_text(errors="ignore")
        local = dict(decls.get(f, {}))
        for m in IMPORT_RE.finditer(text):
            module, names = m.group(1), m.group(2)
            sources = _resolve_module(module, f)
            for src in sources:
                src_decls = decls.get(src)
                if not src_decls:
                    continue
                for raw in names.split(","):
                    raw = raw.strip().lstrip("(").rstrip(")")
                    if " as " in raw:
                        orig, alias = [x.strip() for x in raw.split(" as ", 1)]
                    else:
                        orig = alias = raw
                    if orig in src_decls:
                        local[alias] = src_decls[orig]
        resolved[f] = local
    return resolved


def scan_file(path: Path, router_prefixes: dict[str, str]) -> list[dict]:
    text = path.read_text(errors="ignore")
    out = []
    for m in DECORATOR_RE.finditer(text):
        router_name, method, route = m.group(1), m.group(2).upper(), m.group(3)
        prefix = router_prefixes.get(router_name, "")
        full = (prefix + route).rstrip("/") or "/"
        out.append({
            "method": method,
            "path": full,
            "file": str(path.relative_to(ROOT)),
            "line": text[: m.start()].count("\n") + 1,
        })
    return out


def main():
    routes = []
    prefixes_by_file = collect_router_prefixes()
    for f in SERVER.rglob("*.py"):
        if "/.venv/" in str(f):
            continue
        routes.extend(scan_file(f, prefixes_by_file.get(f, {})))
    routes.sort(key=lambda r: (r["method"], r["path"]))
    seen = set()
    deduped = []
    for r in routes:
        key = (r["method"], r["path"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    payload = {
        "_about": "Frozen FastAPI route table. Regenerated only after intentional route changes.",
        "routes": deduped,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT}: {len(deduped)} unique routes")


if __name__ == "__main__":
    main()
