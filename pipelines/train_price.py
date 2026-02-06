"""
Self-contained Ridge regression trainer for all 36 collectible categories.

Usage:
    python -m pipelines.train_price --category pokemon
    python -m pipelines.train_price --all
    python -m pipelines.train_price --category funko --version v1 --register

Features:
    - Trains Ridge regression models for median (q50), q10, and q90 quantiles
    - Dynamically extracts all numeric features from training data
    - Always uses core 3 features: condition_score, rarity_score, edition_score
    - Standardizes features (zero mean, unit variance) before regression
    - Outputs JSON model artifacts to artifacts/{category}/{version}/model.json
    - Symlinks artifacts/{category}/active to latest version
    - Synthetic fallback: generates 200 samples if no training data exists
    - Optional --register flag to upsert model metadata to Supabase

Model Output Format:
    {
        "model_type": "ridge_v1",
        "category": "pokemon",
        "version": "20260206_120000",
        "features": ["condition_score", "rarity_score", "edition_score"],
        "standardizer": {"mean": [...], "std": [...]},
        "ridge": {"coef": [...], "intercept": 0.0},
        "ridge_q10": {"coef": [...], "intercept": 0.0},
        "ridge_q90": {"coef": [...], "intercept": 0.0},
        "uncertainty_scale": 1.0,
        "train_size": 59,
        "mae": 12.5,
        "created_at": "2026-02-06T12:00:00Z"
    }
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error

# ---------------------------------------------------------------------------
# All 36 Supported Categories
# ---------------------------------------------------------------------------

ALL_CATEGORIES = [
    "pokemon", "mtg", "yugioh", "lorcana", "funko", "designer_toys", "anime_figures",
    "hot_toys", "lego", "gunpla", "scale_models", "warhammer", "retro_games", "manga",
    "bluray_steelbook", "anime_bluray", "anime_soundtrack", "anime_ost_vinyl", "kpop_merch",
    "taylor_swift", "pop_fandom", "kpop_lightsticks", "disney", "theme_park", "ghibli",
    "bandai_premium", "jp_magazine", "jp_event", "nintendo_merch", "retro_pokemon",
    "one_piece", "vtuber", "keycaps", "loungefly", "diecast", "sportscards"
]

# Core features present in ALL categories
CORE_FEATURES = ["condition_score", "rarity_score", "edition_score"]

# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

def load_training_data(category: str) -> tuple[list[dict], list[float]]:
    """
    Load training data from data/{category}/train.jsonl.

    Each line is: {"features": {...}, "price": 45.0}

    If file doesn't exist or is empty, generates 200 synthetic observations
    using the 3 core features.

    Returns:
        (features_list, prices_list)
    """
    data_path = Path(f"data/{category}/train.jsonl")

    if data_path.exists():
        features_list = []
        prices_list = []

        with open(data_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    features_list.append(record["features"])
                    prices_list.append(float(record["price"]))
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    print(f"  WARNING: Skipping invalid line: {e}")
                    continue

        if features_list and prices_list:
            return features_list, prices_list

    # No training data found - generate synthetic fallback
    print(f"  No training data found for {category}, generating 200 synthetic samples...")
    return generate_synthetic_data(category, n=200)


def generate_synthetic_data(category: str, n: int = 200) -> tuple[list[dict], list[float]]:
    """
    Generate synthetic training data using the 3 core features.

    Simple linear model: price = 50 + 80*condition + 40*rarity + 30*edition + noise

    This bootstraps all 36 categories with reasonable baseline data.
    """
    rng = np.random.default_rng(42)
    features_list = []
    prices_list = []

    for _ in range(n):
        condition_score = float(np.clip(rng.normal(0.7, 0.2), 0, 1))
        rarity_score = float(np.clip(rng.normal(0.5, 0.25), 0, 1))
        edition_score = float(np.clip(rng.normal(0.4, 0.2), 0, 1))

        # Simple linear price model
        base_price = (
            50.0
            + 80.0 * condition_score
            + 40.0 * rarity_score
            + 30.0 * edition_score
        )

        # Add noise (proportional to base price)
        noise = rng.normal(0, base_price * 0.15)
        price = max(5.0, base_price + noise)

        features = {
            "condition_score": condition_score,
            "rarity_score": rarity_score,
            "edition_score": edition_score,
        }

        features_list.append(features)
        prices_list.append(float(price))

    return features_list, prices_list


# ---------------------------------------------------------------------------
# Feature Extraction
# ---------------------------------------------------------------------------

def extract_feature_names(features_list: list[dict]) -> list[str]:
    """
    Extract all unique numeric feature names from the dataset.

    Always includes the 3 core features first, then adds any extra numeric features.
    """
    # Start with core features
    feature_names = CORE_FEATURES.copy()

    # Find all additional numeric features
    extra_features = set()
    for features in features_list:
        for key, value in features.items():
            if key not in CORE_FEATURES and isinstance(value, (int, float)):
                extra_features.add(key)

    # Add extra features in sorted order
    feature_names.extend(sorted(extra_features))

    return feature_names


def build_feature_matrix(
    features_list: list[dict],
    feature_names: list[str]
) -> np.ndarray:
    """
    Convert list of feature dicts to numpy matrix.

    Missing features are filled with 0.0.
    """
    n_samples = len(features_list)
    n_features = len(feature_names)

    X = np.zeros((n_samples, n_features), dtype=np.float64)

    for i, features in enumerate(features_list):
        for j, name in enumerate(feature_names):
            value = features.get(name, 0.0)
            if isinstance(value, (int, float)):
                X[i, j] = float(value)
            else:
                X[i, j] = 0.0

    return X


# ---------------------------------------------------------------------------
# Ridge Regression Training
# ---------------------------------------------------------------------------

class RidgeModelPack:
    """Trained Ridge regression models with standardization."""

    def __init__(
        self,
        category: str,
        version: str,
        feature_names: list[str],
        mean: np.ndarray,
        std: np.ndarray,
        ridge_q50: Ridge,
        ridge_q10: Ridge,
        ridge_q90: Ridge,
        train_size: int,
        mae: float,
    ):
        self.category = category
        self.version = version
        self.feature_names = feature_names
        self.mean = mean
        self.std = std
        self.ridge_q50 = ridge_q50
        self.ridge_q10 = ridge_q10
        self.ridge_q90 = ridge_q90
        self.train_size = train_size
        self.mae = mae
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> dict:
        """Serialize model to JSON-compatible dict."""
        return {
            "model_type": "ridge_v1",
            "category": self.category,
            "version": self.version,
            "features": self.feature_names,
            "standardizer": {
                "mean": self.mean.tolist(),
                "std": self.std.tolist(),
            },
            "ridge": {
                "coef": self.ridge_q50.coef_.tolist(),
                "intercept": float(self.ridge_q50.intercept_),
            },
            "ridge_q10": {
                "coef": self.ridge_q10.coef_.tolist(),
                "intercept": float(self.ridge_q10.intercept_),
            },
            "ridge_q90": {
                "coef": self.ridge_q90.coef_.tolist(),
                "intercept": float(self.ridge_q90.intercept_),
            },
            "uncertainty_scale": 1.0,
            "train_size": self.train_size,
            "mae": round(self.mae, 2),
            "created_at": self.created_at,
        }


def train_ridge_model(
    category: str,
    features_list: list[dict],
    prices: list[float],
    version: str,
    alpha: float = 1.0,
) -> RidgeModelPack:
    """
    Train Ridge regression models for q50, q10, q90.

    Steps:
        1. Extract feature names (core 3 + extras)
        2. Build feature matrix
        3. Standardize features (zero mean, unit variance)
        4. Train Ridge for median (q50)
        5. Train Ridge for q10 using price * 0.7 targets
        6. Train Ridge for q90 using price * 1.4 targets
        7. Compute MAE on q50 predictions

    Returns:
        RidgeModelPack with all models and metadata
    """
    # Extract features
    feature_names = extract_feature_names(features_list)
    X = build_feature_matrix(features_list, feature_names)
    y = np.array(prices, dtype=np.float64)

    # Standardize features
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0  # Avoid division by zero
    X_scaled = (X - mean) / std

    # Train median model (q50)
    ridge_q50 = Ridge(alpha=alpha, random_state=42)
    ridge_q50.fit(X_scaled, y)

    # Train q10 model (conservative lower bound)
    y_q10 = y * 0.7
    ridge_q10 = Ridge(alpha=alpha, random_state=42)
    ridge_q10.fit(X_scaled, y_q10)

    # Train q90 model (optimistic upper bound)
    y_q90 = y * 1.4
    ridge_q90 = Ridge(alpha=alpha, random_state=42)
    ridge_q90.fit(X_scaled, y_q90)

    # Compute MAE
    y_pred = ridge_q50.predict(X_scaled)
    mae = mean_absolute_error(y, y_pred)

    return RidgeModelPack(
        category=category,
        version=version,
        feature_names=feature_names,
        mean=mean,
        std=std,
        ridge_q50=ridge_q50,
        ridge_q10=ridge_q10,
        ridge_q90=ridge_q90,
        train_size=len(y),
        mae=mae,
    )


# ---------------------------------------------------------------------------
# Model Persistence
# ---------------------------------------------------------------------------

def save_model(model: RidgeModelPack, output_dir: Path) -> Path:
    """
    Save model to artifacts/{category}/{version}/model.json.

    Also creates symlink artifacts/{category}/active -> {version}.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / "model.json"
    with open(model_path, "w") as f:
        json.dump(model.to_json(), f, indent=2)

    # Update "active" symlink
    active_link = output_dir.parent / "active"
    if active_link.exists() or active_link.is_symlink():
        active_link.unlink()
    active_link.symlink_to(output_dir.name)

    return model_path


# ---------------------------------------------------------------------------
# Supabase Registration
# ---------------------------------------------------------------------------

def register_model_to_supabase(model: RidgeModelPack, model_path: Path) -> bool:
    """
    Upsert model metadata to Supabase model_registry table.

    Uses PostgREST API pattern from import_common.py.

    Table schema:
        - category: text
        - version: text
        - model_type: text
        - artifact_path: text
        - train_size: int
        - mae: float
        - created_at: timestamp

    Returns True if successful, False otherwise.
    """
    import httpx

    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not supabase_key:
        print("  ERROR: SUPABASE_URL or SUPABASE_SERVICE_KEY not set")
        return False

    # Prepare row
    row = {
        "category": model.category,
        "version": model.version,
        "model_type": "ridge_v1",
        "artifact_path": str(model_path.absolute()),
        "train_size": model.train_size,
        "mae": round(model.mae, 2),
        "created_at": model.created_at,
    }

    # Upsert to model_registry table
    try:
        client = httpx.Client(timeout=30.0)
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }

        response = client.post(
            f"{supabase_url}/rest/v1/model_registry",
            headers=headers,
            json=[row],
        )

        if response.status_code in (200, 201):
            print(f"  Registered model to Supabase: {model.category}/{model.version}")
            return True
        else:
            print(f"  ERROR: Supabase registration failed: {response.status_code}")
            print(f"         {response.text[:200]}")
            return False

    except Exception as e:
        print(f"  ERROR: Supabase registration failed: {e}")
        return False

    finally:
        client.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def train_category(
    category: str,
    version: str | None = None,
    register: bool = False,
) -> dict:
    """
    Train Ridge model for a single category.

    Returns summary dict with category, version, train_size, mae, output_path.
    """
    if version is None:
        version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    print(f"\n[{category}] Loading training data...")
    features_list, prices = load_training_data(category)

    print(f"[{category}] Training Ridge regression (n={len(prices)})...")
    model = train_ridge_model(category, features_list, prices, version)

    print(f"[{category}] Saving model artifact...")
    output_dir = Path(f"artifacts/{category}/{version}")
    model_path = save_model(model, output_dir)

    # Optional Supabase registration
    if register:
        print(f"[{category}] Registering model to Supabase...")
        register_model_to_supabase(model, model_path)

    summary = {
        "category": category,
        "version": version,
        "train_size": model.train_size,
        "mae": round(model.mae, 2),
        "features": model.feature_names,
        "output_path": str(model_path.absolute()),
    }

    print(f"[{category}] Done! MAE={model.mae:.2f}, n={model.train_size}, path={model_path}")

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Train Ridge regression models for collectible price prediction"
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Category slug (e.g. pokemon, funko, mtg). Required unless --all is used.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Train all 36 categories that have training data (or generate synthetic data)",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Version string (default: YYYYMMDD_HHMMSS timestamp)",
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Register model metadata to Supabase model_registry table",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all and not args.category:
        parser.error("Either --category or --all is required")

    if args.all and args.category:
        parser.error("Cannot use both --category and --all")

    # Determine categories to train
    if args.all:
        categories = ALL_CATEGORIES
    else:
        categories = [args.category]

    # Train each category
    summaries = []
    for category in categories:
        try:
            summary = train_category(
                category=category,
                version=args.version,
                register=args.register,
            )
            summaries.append(summary)
        except Exception as e:
            print(f"\n[{category}] ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Print final summary
    print("\n" + "=" * 80)
    print("TRAINING SUMMARY")
    print("=" * 80)

    if not summaries:
        print("No models trained.")
        return

    for summary in summaries:
        print(f"\n{summary['category']:20s} | "
              f"n={summary['train_size']:4d} | "
              f"MAE={summary['mae']:6.2f} | "
              f"features={len(summary['features'])}")

    print(f"\nTotal: {len(summaries)} models trained")
    print("\nModel artifacts saved to: artifacts/<category>/<version>/model.json")
    print("Active symlinks: artifacts/<category>/active -> <version>")


if __name__ == "__main__":
    main()
