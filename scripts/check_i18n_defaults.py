#!/usr/bin/env python3
"""Every t('key', { defaultValue: 'X' }) must agree with en.json.

WHY: translating a screen means editing code and seven locale files together,
usually from parallel arrays of keys and strings. A single misaligned entry
silently pairs the wrong English with the wrong key — and NO existing gate sees
it. `i18n:parity` only compares locale files to each other, so a consistent
mistake in all seven passes. `i18n:check` only asks whether a literal is
wrapped. `tsc` sees two strings.

The defaultValue is the one place the intended English is written next to the
key, so comparing it against en.json is the only cheap check that can catch a
shifted array.

It also flags a defaultValue that has drifted from en.json — which means the
code and the locale file disagree about what the user should read, and the
locale file wins at runtime for every locale including English.

    python3 scripts/check_i18n_defaults.py        # exit 0 clean, 1 mismatches
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EN = ROOT / "src/i18n/locales/en.json"
SCAN = ("app", "src")

# t('a.b', { defaultValue: '...' }) — single-quoted, the repo's own style.
CALL = re.compile(
    r"""t\(\s*'([A-Za-z0-9_.]+)'\s*,\s*\{[^{}]*?defaultValue:\s*'((?:[^'\\]|\\.)*)'""",
    re.S,
)


def lookup(tree: dict, dotted: str):
    cur = tree
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur if isinstance(cur, str) else None


def main() -> int:
    en = json.loads(EN.read_text(encoding="utf-8"))
    problems, checked = [], 0
    for base in SCAN:
        for path in sorted((ROOT / base).rglob("*.ts*")):
            if any(p in path.parts for p in ("node_modules", "__tests__")):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "defaultValue" not in text:
                continue
            for m in CALL.finditer(text):
                key, dv = m.group(1), m.group(2).replace("\\'", "'").replace('\\"', '"')
                checked += 1
                actual = lookup(en, key)
                line = text[: m.start()].count("\n") + 1
                rel = path.relative_to(ROOT)
                if actual is None:
                    problems.append(f"  {rel}:{line}  {key} — not in en.json")
                elif actual != dv:
                    problems.append(
                        f"  {rel}:{line}  {key}\n"
                        f"      en.json      : {actual!r}\n"
                        f"      defaultValue : {dv!r}"
                    )
    print(f"checked {checked} t() call(s) carrying a defaultValue")
    if problems:
        print(f"\nFAIL  {len(problems)} disagreement(s) with en.json:\n")
        print("\n".join(problems))
        print(
            "\n      A mismatch usually means a translation array shifted by one, or\n"
            "      the English was edited in one place and not the other. en.json\n"
            "      wins at runtime, so the defaultValue is the half that is wrong."
        )
        return 1
    print("PASS  every defaultValue matches en.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
