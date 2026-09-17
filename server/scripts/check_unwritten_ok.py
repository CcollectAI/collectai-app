#!/usr/bin/env python3
"""A database that is not there did not save anything.

The narrow half of class S (`docs/CLASS_SWEEPS.md`). Six route handlers answered
**200 with a success payload** from a branch that had reached no database at
all:

    # items_router.update_item_attributes, before 2026-09-17
    pool = get_db_pool()
    if pool is None:
        return {"ok": True, "item_id": item_id}      # the app closes edit mode on `ok`

    # social_router.block_user
    if pool is None:
        return BlockResponse(success=True, message="User blocked (offline mode)")

    # alerts_feature_router.mark_trigger_read
    if not db_configured():
        return {"ok": True}

Every one sat behind an optimistic screen, so the member saw what they asked for
and the truth came back on the next fetch with nothing explaining it. Blocking
was the worst: "User blocked (offline mode)" is a safety claim.

WHAT COUNTS AS A FINDING
    Inside a route handler (`@…router.post/patch/put/delete` — GETs are reads
    and are class P's business, `check_empty_on_failure.py`), a `return` of a
    SUCCESS payload that is
      * lexically inside a branch testing DATABASE AVAILABILITY
        (`if pool is None`, `if not db_configured()`, `if conn is None`, …), and
      * in a branch body that contains no database call at all.

    A success payload is a dict with a truthy `ok`/`success`/`status: "ok"`, or a
    call like `BlockResponse(success=True, …)`. Deliberately not keyed on a list
    of response-class names: the SHAPE is `success=True` / `ok: True`, wherever
    it appears (learning_four_ways_a_new_gate_is_wrong, §1).

NOT A FINDING
    * a 503/404 raise — that is the fix;
    * a no-op that was never going to write anything, because it is not inside a
      db-availability branch (`if not merged: return {"ok": True}` in
      `update_item_attributes` is honest and stays);
    * a dev/in-memory fallback that REALLY performs the action without a
      database, e.g. `alerts_feature_router.create_alert` writing
      `_IN_MEMORY_ALERTS`. Those bodies contain the write, so they do not match
      — and if a future one does, say so with
      `# offline-ok: <what actually happens instead>` above the return. The
      whole contiguous comment block is read, so a reason can run to four lines.

Exit codes: 0 clean, 1 findings.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "server" / "app"
MARKERS = ("offline-ok:", "empty-ok:")
WRITE_METHODS = ("post", "patch", "put", "delete")
# Any of these on a branch's condition means "is the database reachable".
DB_NAMES = ("pool", "db_configured", "conn", "get_conn", "db_enabled", "_pool")
# Any await/attribute call on one of these is "it did reach the database".
DB_CALL_OWNERS = ("conn", "pool", "cur", "cursor", "session", "tx", "db")


def is_write_route(fn: ast.AST) -> bool:
    for dec in getattr(fn, "decorator_list", []):
        call = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(call, ast.Attribute) and call.attr in WRITE_METHODS:
            owner = call.value
            name = getattr(owner, "id", None) or getattr(owner, "attr", "")
            if "router" in str(name).lower():
                return True
    return False


def condition_is_db_availability(test: ast.AST) -> bool:
    """`pool is None`, `not db_configured()`, `conn is None`, `not pool` …"""
    for node in ast.walk(test):
        name = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        if name and any(d == name or d in name.lower() for d in DB_NAMES):
            return True
    return False


# Calls that are not work: logging, and building the response itself.
LOG_OWNERS = ("logger", "log", "logging", "_logger")
NOT_WORK = (
    "str", "int", "float", "bool", "len", "list", "dict", "set", "tuple",
    "error_response", "print", "HTTPException",
)


def touches_database(body: list[ast.AST]) -> bool:
    """True if this branch body does WORK — a db call, or a hand-off to anything.

    The RETURN statement's own value is skipped (2026-09-17). Walking it counted
    `BlockResponse(success=True, …)` as a possible hand-off, so the two
    `social_router` lies — the whole reason this gate exists — were not reported
    by its first version. Building the answer is not doing the work, and a
    mutation restoring all five real findings is what showed only 3 came back.
    """
    for stmt in body:
        nodes: list[ast.AST] = []
        if isinstance(stmt, ast.Return):
            continue  # the payload is the CLAIM, never the work
        nodes = list(ast.walk(stmt))
        for node in nodes:
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Attribute):
                    owner = f.value
                    owner_name = (getattr(owner, "id", None) or getattr(owner, "attr", "") or "").lower()
                    if any(o == owner_name for o in LOG_OWNERS):
                        continue
                    if any(o in owner_name for o in DB_CALL_OWNERS):
                        return True
                    # Some other object's method: could be a store or a service.
                    return True
                # A branch that calls ANY other function may be doing the work
                # elsewhere (the in-memory fallbacks do). Subscript assignment
                # into a module-level store counts too, below.
                if isinstance(f, ast.Name) and f.id not in NOT_WORK:
                    return True
            # `_IN_MEMORY_ALERTS[alert_id] = alert` — a real write, just not to
            # a database.
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Subscript):
                        return True
            if isinstance(node, ast.Delete):
                return True
    return False


def _truthy(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


# A payload may carry `ok: True` and still be honest when it SAYS nothing was
# written — the same principle as check_empty_on_failure ("a payload that says
# what happened is not a finding"). `notification_feedback_router` answers
# `{"ok": True, "stored": False}` with no database, which is a report, not a
# claim. Found by this gate's first run and judged, not silenced.
DISCLOSURE_KEYS = ("stored", "saved", "persisted", "written", "recorded")


def discloses_no_write(node: ast.Dict) -> bool:
    for key, value in zip(node.keys, node.values):
        if (
            isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and key.value.lower() in DISCLOSURE_KEYS
            and isinstance(value, ast.Constant)
            and value.value is False
        ):
            return True
    return False


def claims_success(node: ast.AST) -> bool:
    """A dict with a truthy ok/success, or any call passing success=True/ok=True."""
    if isinstance(node, ast.Dict):
        if discloses_no_write(node):
            return False
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                k = key.value.lower()
                if k in ("ok", "success", "succeeded") and _truthy(value):
                    return True
                if k == "status" and isinstance(value, ast.Constant) and value.value in ("ok", "success"):
                    return True
        return False
    if isinstance(node, ast.Call):
        for kw in node.keywords:
            if kw.arg in ("ok", "success", "succeeded") and _truthy(kw.value):
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
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or not is_write_route(fn):
                continue
            skip = nested_spans(fn)
            for node in ast.walk(fn):
                if not isinstance(node, ast.If) or not condition_is_db_availability(node.test):
                    continue
                if touches_database(node.body):
                    continue
                for inner in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                    if not isinstance(inner, ast.Return) or inner.value is None:
                        continue
                    if any(a <= inner.lineno <= b for a, b in skip):
                        continue
                    if not claims_success(inner.value):
                        continue
                    if reason_above(lines, inner.lineno):
                        continue
                    rel = path.relative_to(ROOT)
                    findings.append(f"{rel}:{inner.lineno}  {fn.name}()")

    if findings:
        print(
            f"[unwritten-ok] FAIL — {len(findings)} write handler(s) claim success "
            "from a branch that never reached the database:\n"
        )
        for f in findings:
            print(f"  - {f}")
        print(
            "\n  The app takes `ok`/`success` as saved — it closes edit mode, shows a toast,\n"
            "  and stops rolling its optimistic update back. Raise instead:\n"
            '      raise error_response(503, "<what the member should read>", code="DB_UNAVAILABLE")\n'
            "  or, if the branch really does perform the action without a database, say what it\n"
            "  does: `# offline-ok: <what happens instead>` above the return."
        )
        return 1
    print("[unwritten-ok] PASS — no write handler claims success without reaching the database.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
