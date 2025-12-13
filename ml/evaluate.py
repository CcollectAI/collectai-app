from __future__ import annotations

import json

import numpy as np
import pandas as pd

df = pd.read_parquet("data/train.parquet")
y = df["y"].to_numpy()
q50 = np.median(y)
q10 = np.quantile(y, 0.10)
q90 = np.quantile(y, 0.90)
picp = float(np.mean((y >= q10) & (y <= q90)))
ace = float(np.mean(np.abs(q50 - y) / np.maximum(1.0, y)))
rep = {"coverage_q10_q90": round(picp, 4), "ace": round(ace, 4), "n": int(len(y))}
open("calibration_report.json", "w").write(json.dumps(rep, indent=2))
print("wrote calibration_report.json", rep)
