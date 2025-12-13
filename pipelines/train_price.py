from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np

from app.ml.features import ensure_known_category
from app.ml.model import fit_pack, save_pack


def _load_dataset(cat: str) -> tuple[list[dict], list[float]]:
    """
    Expected (if present): data/<cat>/train.jsonl with records:
      {"features": {...}, "price": 123.45}
    If missing, synthesize sane data to bootstrap.
    """
    p = Path(f"data/{cat}/train.jsonl")
    if p.exists():
        X, y = [], []
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            X.append(rec["features"])
            y.append(float(rec["price"]))
        if X and y:
            return X, y
    # synthesize
    cfg = ensure_known_category(cat)
    X, y = [], []
    rng = np.random.default_rng(42)
    for _ in range(800):
        if cat == "diecast":
            f = {
                "year": int(rng.integers(1990, 2024)),
                "package_condition_score": float(np.clip(rng.normal(0.7, 0.2), 0, 1)),
                "recent_sale_z": float(np.clip(rng.normal(0, 1), -2, 2)),
                "scale": rng.choice(["1:18", "1:24", "1:43"]),
                "material": rng.choice(["diecast", "resin"]),
                "maker": rng.choice(["AutoArt", "HotWheels", "Kyosho", "Minichamps"]),
            }
            base = (
                50
                + (f["year"] - 1990) * 0.8
                + 40 * (f["package_condition_score"])
                + 15 * (f["material"] == "diecast")
                + 10 * (f["scale"] == "1:18")
                + 5 * (f["maker"] == "AutoArt")
                + 8 * f["recent_sale_z"]
            )
            noise = rng.normal(0, 8)
            price = max(15, base + noise)
        else:
            f = {
                "piece_count": int(rng.integers(200, 4000)),
                "year": int(rng.integers(2000, 2024)),
                "theme_popularity": float(np.clip(rng.normal(0.6, 0.25), 0, 1)),
                "sealed": rng.choice([True, False]),
                "box_condition_score": float(np.clip(rng.normal(0.8, 0.15), 0, 1)),
                "recent_sale_z": float(np.clip(rng.normal(0, 1), -2, 2)),
            }
            base = (
                0.06 * f["piece_count"]
                + 2.0 * (f["year"] - 2000)
                + 60 * f["theme_popularity"]
                + (25 if f["sealed"] else 0)
                + 40 * f["box_condition_score"]
                + 10 * f["recent_sale_z"]
            )
            noise = rng.normal(0, 15)
            price = max(10, base + noise)
        X.append(f)
        y.append(float(price))
    return X, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", required=True, choices=["diecast", "lego"])
    ap.add_argument("--version", default=datetime.utcnow().strftime("%Y%m%d_%H%M%S"))
    args = ap.parse_args()

    X, y = _load_dataset(args.category)
    pack = fit_pack(args.category, X, y, args.version)
    out_dir = Path(f"artifacts/{args.category}/{args.version}")
    out_dir.mkdir(parents=True, exist_ok=True)
    save_pack(pack, out_dir / "model.pkl")
    # move "active" symlink
    (Path(f"artifacts/{args.category}/active").parent).mkdir(
        parents=True, exist_ok=True
    )
    tmp = Path(f"artifacts/{args.category}/active")
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    tmp.symlink_to(out_dir.resolve())
    print(
        json.dumps(
            {
                "category": args.category,
                "version": args.version,
                "out": str(out_dir / "model.pkl"),
                "train_size": pack.meta.train_size,
                "mae": pack.meta.mae,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
