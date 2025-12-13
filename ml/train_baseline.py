from __future__ import annotations

import json
import os

import pandas as pd

# read the training data (parquet or csv fallback)
if os.path.exists("data/train.parquet"):
    df = pd.read_parquet("data/train.parquet")
elif os.path.exists("data/train.csv"):
    df = pd.read_csv("data/train.csv")
else:
    raise SystemExit("No training data found (data/train.parquet|csv)")

# trivial “model”: median price by (sealed, grade10)
group_raw = df.groupby(["sealed", "grade10"])["y"].median().to_dict()

# JSON-safe keys: "sealed=<v>|grade10=<v>"
group = {
    f"sealed={int(k[0])}|grade10={int(k[1])}": float(v) for k, v in group_raw.items()
}

os.makedirs("models", exist_ok=True)
with open("models/baseline.json", "w") as f:
    json.dump({"median_by_group": group}, f, indent=2)

print("trained baseline groups:", group)
