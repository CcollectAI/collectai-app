"""Class AA stage 1: which functions write MORE THAN ONE table for one event?

⚠️ The first version of this stripped every triple-quoted string as a
"docstring". All SQL in this repo lives in triple-quoted strings, so it deleted
exactly what it was searching for: it returned 5 candidates, 4 of them regex
noise ('set' from `UPDATE ... SET`), and MISSED the one instance already known.
Only `#` comments are stripped now. A docstring that merely mentions a table
can false-positive; that is the cheap direction to be wrong in, and the method
says verify by reading anyway.

Deliberately over-inclusive: writing two tables is normal. The class is the
subset where the SAME FACT lands in two tables something later COMBINES.
"""
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path("server")
WRITE = re.compile(r"\b(?:INSERT\s+INTO|UPDATE)\s+(?:public\.)?([a-z_][a-z0-9_]*)\b", re.I)
# helpers whose whole job is to write a row somewhere else
HELPER = re.compile(r"\bawait\s+(record_price_ground_truth|log_provenance_event|"
                    r"_log_provenance_event|record_value_provenance)\s*\(")
DEF = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)")
NOT_A_TABLE = {"set", "fields", "values", "where", "from", "select", "table"}


def strip_hash_comments(src: str) -> str:
    return "\n".join(re.sub(r"(?<!['\"])#.*$", "", l) for l in src.split("\n"))


def enumerate_writers():
    hits = {}
    for f in sorted(ROOT.rglob("*.py")):
        if "__pycache__" in str(f) or "/tests/" in str(f):
            continue
        lines = strip_hash_comments(f.read_text(encoding="utf-8", errors="ignore")).split("\n")
        starts = [i for i, l in enumerate(lines) if DEF.match(l)]
        for idx, start in enumerate(starts):
            end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
            body = "\n".join(lines[start:end])
            tables = {t.lower() for t in WRITE.findall(body)} - NOT_A_TABLE
            helpers = set(HELPER.findall(body))
            if len(tables) + len(helpers) >= 2 and tables:
                hits[(str(f), DEF.match(lines[start]).group(1), start + 1)] = (
                    sorted(tables), sorted(helpers))
    return hits


if __name__ == "__main__":
    hits = enumerate_writers()
    # CONTROL: the one instance we already fixed must appear, or the enumerator
    # is blind and every "no findings" below is meaningless.
    known = [k for k in hits if k[1] == "submit_verified_sale"]
    assert known, "BLIND: the known class-AA instance (submit_verified_sale) was not found"
    print(f"control OK — known instance found at {known[0][0]}:{known[0][2]}\n")
    print(f"functions writing 2+ tables (candidates, unfiltered): {len(hits)}\n")
    for (f, name, ln), (tables, helpers) in sorted(hits.items()):
        extra = f" + helper:{helpers}" if helpers else ""
        print(f"  {f}:{ln}  {name}()")
        print(f"      {tables}{extra}")
