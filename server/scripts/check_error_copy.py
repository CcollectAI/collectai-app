#!/usr/bin/env python3
"""An exception's text is not member copy.

`src/lib/userErrorMessage.ts` shows **the server's own sentence** when the
server wrote one — that is deliberate, and it is why `detail` is UI. So a
handler that answers with `str(e)` or `f"...{e}"` ships a library's wording to
a member, and sometimes internals with it:

    # before 2026-09-17
    raise HTTPException(status_code=500, detail=f"db_error: {e}")      # asyncpg names tables
    raise error_response(500, f"Failed to remove MFA factor: {exc}")   # GoTrue's wording
    raise error_response(502, f"eBay publish failed: {e!s}")           # upstream's wording
    raise ValueError(f"Cannot decode image: {exc}")                    # "<_io.BytesIO object at 0x…>"

The client has `check-raw-error-copy` for the same class on its own side; this
is the half it cannot see.

A FINDING is a route handler that puts the caught exception into the response —
`return`ed or `raise`d — with no written reason.

NOT a finding:
  * a payload that carries OUR OWN validator's sentence, marked
    `# raw-error-ok: <why this text is written for a person>`. Real examples in
    this repo: `app/ssrf.validate_url` ("URL points to a private/internal IP
    address"), `s3_storage` ("content_type not allowed: image/tiff"),
    `warm_tier` ("limit too high — split into chunks").
  * an operator-only endpoint that exists for debugging, marked the same way.

The whole contiguous comment block above the statement is read, so a reason can
run to three or four lines.

Exit codes: 0 clean, 1 findings.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "server" / "app"
MARKERS = ("raw-error-ok:", "best-effort:")
HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def is_route(fn: ast.AST) -> bool:
    for dec in getattr(fn, "decorator_list", []):
        call = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(call, ast.Attribute) and call.attr in HTTP_METHODS:
            owner = call.value
            name = getattr(owner, "id", None) or getattr(owner, "attr", "")
            if "router" in str(name).lower():
                return True
    return False


def embeds(node: ast.AST, names: set[str]) -> bool:
    """`str(e)`, `f"...{e}"`, or `{e!s}` anywhere in this expression."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "str":
            if n.args and isinstance(n.args[0], ast.Name) and n.args[0].id in names:
                return True
        if isinstance(n, ast.JoinedStr):
            for value in n.values:
                if isinstance(value, ast.FormattedValue):
                    # `{e}`, `{e!s}`, and `{e.args[0]}` all carry the text.
                    for sub in ast.walk(value.value):
                        if isinstance(sub, ast.Name) and sub.id in names:
                            return True
    return False


def reason_above(lines: list[str], lineno: int) -> bool:
    i = lineno - 2
    block: list[str] = []
    while i >= 0:
        stripped = lines[i].strip()
        if not stripped:
            if block:
                break
            i -= 1
            continue
        if not stripped.startswith("#"):
            break
        block.append(stripped)
        i -= 1
    return any(m in "\n".join(block) for m in MARKERS)


def main() -> int:
    findings: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        lines = text.splitlines()
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or not is_route(fn):
                continue
            for node in ast.walk(fn):
                if not isinstance(node, ast.Try):
                    continue
                for handler in node.handlers:
                    if not handler.name:
                        continue  # `except Exception:` binds nothing to leak
                    names = {handler.name}
                    for inner in ast.walk(handler):
                        target = None
                        if isinstance(inner, ast.Return) and inner.value is not None:
                            target = inner.value
                        elif isinstance(inner, ast.Raise) and inner.exc is not None:
                            target = inner.exc
                        if target is None or not embeds(target, names):
                            continue
                        if reason_above(lines, inner.lineno):
                            continue
                        rel = path.relative_to(ROOT)
                        findings.append(f"{rel}:{inner.lineno}  {fn.name}()")

    if findings:
        print(f"[error-copy] FAIL — {len(findings)} handler(s) put a caught exception's text in the response:\n")
        for f in findings:
            print(f"  - {f}")
        print(
            "\n  The app shows `detail` to the member (src/lib/userErrorMessage.ts), so write a\n"
            "  sentence and keep the exception in the log — or, if the text IS ours and written\n"
            "  for a person, say so: `# raw-error-ok: <why>` above the line."
        )
        return 1
    print("[error-copy] PASS — no handler ships a caught exception's text to the caller.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
