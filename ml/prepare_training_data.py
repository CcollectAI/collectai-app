from __future__ import annotations

import os

import numpy as np
import pandas as pd

os.makedirs("data", exist_ok=True)
np.random.seed(7)
n = 200
df = pd.DataFrame(
    {
        "y": np.random.lognormal(mean=5, sigma=0.4, size=n),
        "sealed": np.random.randint(0, 2, size=n),
        "grade10": np.random.randint(0, 2, size=n),
        "pieces": np.random.randint(200, 2000, size=n),
    }
)
df.to_parquet("data/train.parquet")
print("wrote data/train.parquet", df.shape)
