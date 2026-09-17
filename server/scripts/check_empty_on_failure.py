#!/usr/bin/env python3
"""A 200 with empty data is a claim. The server must not make it on a failure.

The client has policed this since 2026-09-15 (`check-silent-failures` rule F:
"a failed read is not 'none'"), but that rule can only see code it can read. A
route handler that catches its own exception and answers **200 with an empty
payload** is invisible to it: the client receives a well-formed, plausible
answer and renders it as fact.

Found 2026-09-17, sweeping the server for the same class:

    # portfolio_router.portfolio_overview
    except Exception as e:
        _logger.error("[portfolio/overview] DB error: %s", e)
        return {"total_value": 0, "item_count": 0, "items": []}

`total_value: 0, item_count: 0` is the sentence Home puts in its hero. The
member's collection had not emptied; the database was unreachable. Nine handlers
in `portfolio_router` did this, plus the alert history (whose `unread_count: 0`
also cleared the badge).

WHAT COUNTS AS A FINDING
    A function decorated with `@…router.get/post/put/patch/delete` that, inside
    an `except` block, returns an empty collection, 0, None, or a dict whose
    values are empty/zero. Returns inside NESTED functions are ignored — a
    helper returning None for a blank spreadsheet cell is not this bug (the
    first version of this scan reported `import_router`'s `_num()` and was
    wrong).

HOW TO SATISFY IT
    Raise instead:
        raise error_response(503, "Portfolio is unavailable", code="DB_UNAVAILABLE")
    …so the client's failure state can run, or write the reason in the comment
    block above the return:
        # empty-ok: <why this empty answer is the truth, or harmless>
    The whole contiguous comment block is read, not the last line — a reason
    worth writing runs to three or four lines.

Exit codes: 0 clean, 1 findings.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "server" / "app"
REASON_MARKERS = ("empty-ok:", "best-effort:")
HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def is_route(fn: ast.AST) -> bool:
    """True for a FastAPI route handler (decorated @<something>router.<method>)."""
    for dec in getattr(fn, "decorator_list", []):
        call = dec.func if isinstance(dec, ast.Call) else dec
        if not isinstance(call, ast.Attribute) or call.attr not in HTTP_METHODS:
            continue
        owner = call.value
        name = getattr(owner, "id", None) or getattr(owner, "attr", "")
        if "router" in str(name).lower():
            return True
    return False


def is_empty_literal(node: ast.AST) -> bool:
    """`[]`, `{}`, `0`, `None`, or a dict whose every value is one of those."""
    # `is None` / `== 0` / `is False` spelled out on purpose: `False in (None, 0)`
    # is True in Python (False == 0), so the tuple form silently folded booleans
    # in. Booleans ARE wanted here — a bare `return False` from a read is the
    # same empty answer — but by decision, not by accident.
    if isinstance(node, ast.Constant) and (node.value is None or node.value is False or node.value == 0):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)) and not node.elts:
        return True
    if isinstance(node, ast.Dict):
        if not node.keys:
            return True
        # A payload is "empty" when nothing in it carries information: every
        # value is an empty collection, 0, or None. `{"status": "error", …}`
        # therefore does NOT count — it says what happened.
        return all(is_empty_literal(v) for v in node.values)
    return False


def reason_above(lines: list[str], lineno: int) -> bool:
    """Read the whole contiguous `#` comment block above line `lineno`."""
    i = lineno - 2  # 0-based, line above
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
    text = "\n".join(block)
    return any(m in text for m in REASON_MARKERS)


def except_returns(fn: ast.AST):
    """Every `return <value>` inside an `except` block of this function.

    Nested defs are excluded by LINE RANGE in main() (`nested_spans`), not here:
    `continue` inside an ast.walk only skips that one node, never its children,
    which is how the first version still reported `import_router._num()`.
    """
    for node in ast.walk(fn):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                for inner in ast.walk(handler):
                    if isinstance(inner, ast.Return) and inner.value is not None:
                        yield inner


def nested_spans(fn: ast.AST) -> list[tuple[int, int]]:
    spans = []
    for node in ast.walk(fn):
        if node is fn:
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
    return spans


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
            skip = nested_spans(fn)
            for ret in except_returns(fn):
                if any(a <= ret.lineno <= b for a, b in skip):
                    continue
                if not is_empty_literal(ret.value):
                    continue
                if reason_above(lines, ret.lineno):
                    continue
                rel = path.relative_to(ROOT)
                snippet = (ast.get_source_segment(text, ret.value) or "").replace("\n", " ")[:60]
                findings.append(f"{rel}:{ret.lineno}  {fn.name}() returns {snippet}")

    if findings:
        print(f"[empty-on-failure] FAIL — {len(findings)} handler(s) answer 200 with empty data on a failure:\n")
        for f in findings:
            print(f"  - {f}")
        print(
            "\n  Raise instead — `raise error_response(503, ..., code=\"DB_UNAVAILABLE\")` —\n"
            "  so the client's failure state can run, or write `# empty-ok: <why>` above the return."
        )
        return 1
    print("[empty-on-failure] PASS — no route handler answers a failure with an empty payload.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
