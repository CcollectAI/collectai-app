#!/usr/bin/env python3
import argparse, json, os, sys, glob, gzip, logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def iter_jsonl(path):
    """Robust JSONL reader that skips blanks/garbage, supports .gz."""
    open_fn = gzip.open if path.endswith(".gz") else open
    with open_fn(path, "rb") as fh:
        for i, raw in enumerate(fh, 1):
            try:
                s = raw.decode("utf-8", errors="replace").strip()
                if not s:            # skip blanks
                    continue
                # Handle accidental prefix noise (e.g., logs before a JSON dict)
                # If the line doesn't start with { or [, try to find the first { and slice.
                if s and s[0] not in "{[":
                    j = s.find("{")
                    if j > 0:
                        s = s[j:]
                yield json.loads(s)
            except Exception as e:
                # Skip but record once to stderr
                sys.stderr.write(f"[WARN] {os.path.basename(path)}:{i} skip line: {e}\n")
                continue

def extract_top_score(rec):
    """
    Try multiple shapes:
    - {"prediction":{"results":[{"score":...}]}}
    - {"results":[{"score":...}]}
    - {"neighbors":[{"score":...}]}
    - {"prediction":{"neighbors":[{"score":...}]}}
    Returns float or None.
    """
    def first_score(arr):
        if isinstance(arr, list) and arr and isinstance(arr[0], dict):
            s = arr[0].get("score")
            return float(s) if isinstance(s, (int, float)) else None
        return None

    if isinstance(rec, dict):
        pred = rec.get("prediction")
        if isinstance(pred, dict):
            for key in ("results", "neighbors"):
                val = pred.get(key)
                s = first_score(val)
                if s is not None: return s
        for key in ("results", "neighbors"):
            val = rec.get(key)
            s = first_score(val)
            if s is not None: return s
    return None

def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0: return None
    mid = n // 2
    return xs[mid] if n % 2 == 1 else (xs[mid-1] + xs[mid]) / 2.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", default="ops/vision", help="Dir to scan for predictions-*.jsonl[.gz]")
    ap.add_argument("--out", default="ops/metrics/model_metrics.jsonl")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    files = sorted(glob.glob(os.path.join(args.predictions, "predictions-*.jsonl*")))
    if not files:
        logger.info("No prediction files found; exiting 0.")
        return 0

    for f in files[-10:]:
        n=0; scores=[]
        for rec in iter_jsonl(f):
            n += 1
            s = extract_top_score(rec)
            if s is not None:
                scores.append(s)

        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "file": os.path.basename(f),
            "pred_count": n,
            "median_top1_score": median(scores),
            "note": "scaffold; replace with MAE/MAPE after market join"
        }
        with open(args.out, "a", encoding="utf-8") as w:
            w.write(json.dumps(payload, ensure_ascii=False) + "\n")
        logger.info("wrote metric: %s", payload)
    return 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
