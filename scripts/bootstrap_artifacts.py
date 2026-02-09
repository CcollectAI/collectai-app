from __future__ import annotations

import json
import pathlib
import random
from datetime import datetime, timezone

import numpy as np
from joblib import dump
from sklearn.linear_model import LinearRegression

# Try to import your featurizers (we created these earlier)
try:
    from app.features.diecast import featurize as featurize_diecast

    HAVE_DIECAST = True
except Exception:
    HAVE_DIECAST = False
try:
    from app.features.lego import featurize as featurize_lego

    HAVE_LEGO = True
except Exception:
    HAVE_LEGO = False

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "artifacts"


def _mk_run_dir(cat: str) -> pathlib.Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    d = ART / cat / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fit_and_save(cat: str, X: list[dict[str, float]]):
    # ensure identical feature order
    keys = sorted({k for row in X for k in row.keys()})
    X_mat = np.array([[row.get(k, 0.0) for k in keys] for row in X], dtype=float)
    # synthetic target: simple weighted sum + noise
    rng = np.random.default_rng(42)
    w = rng.normal(0, 1, size=len(keys))
    y = X_mat @ w + rng.normal(0, 0.1, size=X_mat.shape[0])

    model = LinearRegression()
    model.fit(X_mat, y)

    run_dir = _mk_run_dir(cat)
    dump({"model": model, "feature_keys": keys}, run_dir / "model.pkl")
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "category": cat,
                "created_utc": datetime.now(timezone.utc).isoformat() + "Z",
                "n_samples": len(X),
                "n_features": len(keys),
                "feature_keys": keys,
                "bootstrap": True,
            },
            indent=2,
        )
    )
    # point active symlink
    active = ART / cat / "active"
    if active.is_symlink() or active.exists():
        active.unlink()
    active.symlink_to(run_dir, target_is_directory=True)
    return run_dir


def gen_diecast_payloads(n=200):
    scales = ["1:18", "1:24", "1:32", "1:43", "1:64"]
    mats = ["diecast", "metal", "plastic"]
    makers = [
        "AutoArt",
        "Greenlight",
        "Hot Wheels",
        "Matchbox",
        "Maisto",
        "Tomica",
        "Other",
    ]
    out = []
    for _ in range(n):
        out.append(
            {
                "scale": random.choice(scales),
                "material": random.choice(mats),
                "maker": random.choice(makers),
                "year": random.randint(1980, 2025),
                "package_condition_score": round(random.uniform(0.2, 1.0), 2),
                "recent_sale_z": round(random.uniform(-1.0, 2.0), 2),
            }
        )
    return out


def gen_lego_payloads(n=200):
    out = []
    for _ in range(n):
        out.append(
            {
                "piece_count": random.randint(100, 3000),
                "year": random.randint(1990, 2025),
                "theme_popularity": round(random.uniform(0.2, 1.0), 2),
                "sealed": random.choice([True, False]),
                "box_condition_score": round(random.uniform(0.2, 1.0), 2),
                "recent_sale_z": round(random.uniform(-1.0, 2.0), 2),
            }
        )
    return out


def build_cat(cat: str):
    if cat == "diecast":
        if not HAVE_DIECAST:
            raise RuntimeError(
                "diecast featurizer not importable (app.features.diecast)"
            )
        payloads = gen_diecast_payloads()
        feats = [featurize_diecast(p) for p in payloads]
        rd = _fit_and_save(cat, feats)
        print(f"[OK] diecast -> {rd}")
    elif cat == "lego":
        if not HAVE_LEGO:
            raise RuntimeError("lego featurizer not importable (app.features.lego)")
        payloads = gen_lego_payloads()
        feats = [featurize_lego(p) for p in payloads]
        rd = _fit_and_save(cat, feats)
        print(f"[OK] lego -> {rd}")
    else:
        raise ValueError(cat)


if __name__ == "__main__":
    built = []
    for cat in ("diecast", "lego"):
        try:
            build_cat(cat)
            built.append(cat)
        except Exception as e:
            print(f"[ERR] {cat}: {e}")
    if not built:
        raise SystemExit(2)
