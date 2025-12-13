#!/usr/bin/env python3
import hashlib
import sys


def tail(path, n=50):
    from collections import deque

    dq = deque(maxlen=n)
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            dq.append(line.rstrip("\n"))
    for line in dq:
        print(line)


def dedupe(src, dst):
    seen = set()
    out = open(dst, "w", encoding="utf-8")
    with open(src, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            h = hashlib.md5(line.encode()).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            out.write(line + "\n")
    out.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "usage: jsonl_tools.py tail <path> [n]  |  jsonl_tools.py dedupe <src> <dst>"
        )
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "tail":
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 50
        tail(sys.argv[2], n)
    elif cmd == "dedupe":
        dedupe(sys.argv[2], sys.argv[3])
    else:
        print("unknown command")
        sys.exit(2)
