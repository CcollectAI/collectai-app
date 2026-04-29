"""Scan TS/TSX for `supabase.rpc('rpc_name', { p_x: ..., p_y: ... })`
calls and verify each parameter key matches the live function signature.

Same class of bug as audit_fe_supabase_drift.py but for RPC params:
if the SQL function gets a parameter renamed (p_text → p_body) the FE
keeps calling the old name and Supabase silently returns null.

Reads scripts/rpc.lock.json (frozen function signature snapshot) so it
runs in CI without DB access. Regenerate the lock with
scripts/regen_rpc_lock.py after intentional function changes.

Exit codes:
  0 — no drift
  1 — drift found
  2 — lock missing
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "scripts" / "rpc.lock.json"
ALLOWLIST = ROOT / "scripts" / "rpc_drift_allowlist.txt"
SCAN_DIRS = [ROOT / "src", ROOT / "app"]
EXCLUDE = {"node_modules", ".expo", ".next", "dist", "build", "ios", "web"}

# supabase.rpc('rpc_name', { p_x: ..., p_y: ... })
# Captures function name then a brace block of up to 600 chars.
RPC_RE = re.compile(
    r"""\.rpc\(\s*['"]([a-z_][a-z0-9_]*)['"]\s*(?:,\s*\{([^}]{0,600})\})?""",
    re.IGNORECASE,
)
# Bare keys in an object literal: `p_text:`, `,p_text:`, `{ p_text:`
KEY_RE = re.compile(r"""(?:^|[\s,{])([a-z_][a-z0-9_]*)\s*:""")


def walk_files():
    for base in SCAN_DIRS:
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in {".ts", ".tsx"}:
                continue
            if any(part in EXCLUDE for part in p.parts):
                continue
            yield p


def main():
    if not LOCK.exists():
        print(f"ERROR: rpc lock not found at {LOCK}", file=sys.stderr)
        print("Run scripts/regen_rpc_lock.py to create it.", file=sys.stderr)
        sys.exit(2)
    payload = json.loads(LOCK.read_text())
    funcs = {k: set(v) for k, v in payload["functions"].items()}

    # Load allowlist: each non-comment line is `<file>:<KIND>:<detail>`,
    # matching the report format below. Use this to defer pre-existing
    # drift (e.g. functions never deployed server-side).
    allowed: set[str] = set()
    if ALLOWLIST.exists():
        for raw in ALLOWLIST.read_text().splitlines():
            s = raw.strip()
            if s and not s.startswith("#"):
                allowed.add(s)
    print(f"loaded rpc lock: {len(funcs)} functions  allowlist: {len(allowed)} entries")

    findings: list[tuple[str, int, str, str, str]] = []
    n_files = n_calls = 0
    for f in walk_files():
        n_files += 1
        text = f.read_text()
        for m in RPC_RE.finditer(text):
            name = m.group(1).lower()
            block = m.group(2) or ""
            if not name.startswith("rpc_"):
                continue
            n_calls += 1
            line = text[: m.start()].count("\n") + 1
            if name not in funcs:
                findings.append((str(f.relative_to(ROOT)), line, name, "MISSING_FN", ""))
                continue
            sig = funcs[name]
            for key in KEY_RE.findall(block):
                if key not in sig:
                    findings.append((str(f.relative_to(ROOT)), line, name, "BAD_PARAM", key))
    blocking: list = []
    informational: list = []
    for entry in findings:
        path, line, fn, kind, detail = entry
        key = f"{path}:{kind}:{fn}" if kind == "MISSING_FN" else f"{path}:{kind}:{fn}:{detail}"
        if key in allowed:
            informational.append(entry)
        else:
            blocking.append(entry)

    print(f"scanned: {n_files} TS/TSX files, {n_calls} rpc_* calls")
    print(f"findings: {len(findings)} ({len(blocking)} blocking, {len(informational)} allowlisted)")

    def emit(rows, label):
        if not rows:
            return
        print(f"\n--- {label} ---")
        rows.sort()
        last_file = None
        for path, line, fn, kind, detail in rows:
            if path != last_file:
                print(f"\n## {path}")
                last_file = path
            if kind == "MISSING_FN":
                print(f"  L{line} {kind}: rpc('{fn}') — function not in lock")
            else:
                print(f"  L{line} {kind}: rpc('{fn}') — param '{detail}' not in signature")

    emit(blocking, "blocking drift")
    emit(informational, "allowlisted (informational)")
    sys.exit(1 if blocking else 0)


main()
