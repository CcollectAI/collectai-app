"""Scan the FE for HTTP calls to the EC2 backend and verify each
(method, path) pair exists in scripts/api.lock.json.

Same class as the schema/rpc locks. Run in CI (no DB or live server
needed). Allowlist at scripts/api_drift_allowlist.txt for deferred
deletions (e.g. an EC2 route that was renamed and the FE migration
will land in a follow-up).

Exit codes:
  0 — no blocking drift
  1 — blocking drift
  2 — lock missing
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "scripts" / "api.lock.json"
ALLOWLIST = ROOT / "scripts" / "api_drift_allowlist.txt"
SCAN_DIRS = [ROOT / "src", ROOT / "app"]
EXCLUDE = {"node_modules", ".expo", ".next", "dist", "build", "ios", "web"}

# Match calls to httpClient helpers: get/post/put/patch/del/postMultipart
# with a single-quoted, double-quoted, or template-literal path that
# starts with "/". Captures the method, path text, and quote style.
#
# We scan the whole text and pick out call sites where the helper is
# referenced standalone (`get('/x')`) or as a member of an api object
# pattern. False positives on a `.get('/key')` of a Map are filtered
# out by requiring the path to start with "/".
CALL_RE = re.compile(
    r"""\b(get|post|put|patch|del|postMultipart)\s*<[^>]*>?\s*\(\s*([`'"])(\/[^`'"]*)\2""",
    re.IGNORECASE,
)
# Same but without a generic type parameter
CALL_RE_NO_GENERIC = re.compile(
    r"""\b(get|post|put|patch|del|postMultipart)\s*\(\s*([`'"])(\/[^`'"]*)\2""",
    re.IGNORECASE,
)

METHOD_MAP = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "patch": "PATCH",
    "del": "DELETE",
    "postmultipart": "POST",
}

# Replace any ${...} or {name} segment with * for matching.
PLACEHOLDER_RE = re.compile(r"""\$\{[^}]+\}|\{[^}]+\}""")
# Trailing `*` glued to a non-/ char is a query-string interpolation
# (e.g. `/x/y${query?'?...':''}` → `/x/y*`); the real path is `/x/y`.
TRAILING_QUERY_STAR_RE = re.compile(r"([^/])\*+$")
# Strip query strings — FastAPI matches by path only.
def normalize(p: str) -> str:
    p = p.split("?", 1)[0]
    p = PLACEHOLDER_RE.sub("*", p)
    p = TRAILING_QUERY_STAR_RE.sub(r"\1", p)
    # Strip trailing slash, unless root.
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


def walk_files():
    for base in SCAN_DIRS:
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in {".ts", ".tsx"}:
                continue
            if any(part in EXCLUDE for part in p.parts):
                continue
            yield p


def collapse_substitutions(text: str) -> str:
    """Replace every balanced `${...}` substitution with `*`. This makes
    template literals safe for the simple call-site regex even when they
    contain nested backticks (e.g. `/x/${a}/y${b ? `?${c}` : ""}`).
    Done at the file level — `${` outside template literals is rare.
    """
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i : i + 2] == "${":
            depth = 1
            i += 2
            while i < len(text) and depth > 0:
                if text[i : i + 2] == "${":
                    depth += 1
                    i += 2
                elif text[i] == "}":
                    depth -= 1
                    i += 1
                else:
                    i += 1
            out.append("*")
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def main():
    if not LOCK.exists():
        print(f"ERROR: api lock not found at {LOCK}", file=sys.stderr)
        sys.exit(2)
    payload = json.loads(LOCK.read_text())
    locked: set[tuple[str, str]] = set()
    for r in payload["routes"]:
        locked.add((r["method"], normalize(r["path"])))
    allowed: set[str] = set()
    if ALLOWLIST.exists():
        for raw in ALLOWLIST.read_text().splitlines():
            s = raw.strip()
            if s and not s.startswith("#"):
                allowed.add(s)
    print(f"loaded api lock: {len(locked)} (method, path) pairs  allowlist: {len(allowed)} entries")

    findings: list[tuple[str, int, str, str]] = []
    n_files = n_calls = 0
    seen_call: set = set()
    for f in walk_files():
        n_files += 1
        raw = f.read_text()
        text = collapse_substitutions(raw)
        # Try with-generic-type first, then without — dedupe by (start offset)
        for regex in (CALL_RE, CALL_RE_NO_GENERIC):
            for m in regex.finditer(text):
                start = m.start()
                # Dedup if both regex hit the same location
                key = (str(f), start)
                if key in seen_call:
                    continue
                seen_call.add(key)
                method_token = m.group(1).lower()
                path = m.group(3)
                norm = normalize(path)
                line = text[: start].count("\n") + 1
                method = METHOD_MAP[method_token]
                n_calls += 1
                if (method, norm) not in locked:
                    findings.append((str(f.relative_to(ROOT)), line, method, norm))

    blocking, informational = [], []
    for entry in findings:
        path, line, method, norm = entry
        key = f"{path}:{method} {norm}"
        if key in allowed:
            informational.append(entry)
        else:
            blocking.append(entry)

    print(f"scanned: {n_files} TS/TSX files, {n_calls} httpClient calls")
    print(f"findings: {len(findings)} ({len(blocking)} blocking, {len(informational)} allowlisted)")

    def emit(rows, label):
        if not rows:
            return
        print(f"\n--- {label} ---")
        rows.sort()
        last_file = None
        for path, line, method, norm in rows:
            if path != last_file:
                print(f"\n## {path}")
                last_file = path
            print(f"  L{line} {method} {norm}  — not in api lock")

    emit(blocking, "blocking drift")
    emit(informational, "allowlisted (informational)")
    sys.exit(1 if blocking else 0)


main()
