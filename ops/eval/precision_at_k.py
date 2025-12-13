import csv, json, sys

GOLD = {}
with open("ops/eval/gold_labels.csv", newline="") as f:
    for row in csv.DictReader(f):
        GOLD[row["sha256"]] = row["label_id"]

K = int(sys.argv[1]) if len(sys.argv) > 1 else 3
hits = total = 0

try:
    f = open("ops/spool/vision_predictions.jsonl", "r", encoding="utf-8")
except FileNotFoundError:
    print({"error":"predictions file missing","path":"ops/spool/vision_predictions.jsonl"})
    raise SystemExit(2)

for line in f:
    j = json.loads(line)
    sha = j.get("sha256")
    cats = j.get("categories") or []
    if sha in GOLD:
        total += 1
        topk = [c["id"] for c in cats[:K]]
        if GOLD[sha] in topk:
            hits += 1

print({"k":K, "total": total, "hits": hits, "precision_at_k": (hits/total if total else 0.0)})
