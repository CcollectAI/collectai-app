"""
Self-contained Ridge regression trainer for all 36 collectible categories.

Usage:
    python -m pipelines.train_price --category pokemon
    python -m pipelines.train_price --all
    python -m pipelines.train_price --category funko --version v1 --register
    python -m pipelines.train_price --all --include-feedback

Features:
    - Trains Ridge regression for median (q50) with cross-validated alpha tuning
    - Proper quantile regression for q10 and q90 bounds (not fixed multipliers)
    - 5-fold cross-validation with holdout MAE reporting
    - Dynamically extracts all numeric features from training data
    - Always uses core 3 features: condition_score, rarity_score, edition_score
    - Standardizes features (zero mean, unit variance) before regression
    - Merges user feedback (sale prices / corrections) into training data
    - Outputs JSON model artifacts to artifacts/{category}/{version}/model.json
    - Symlinks artifacts/{category}/active to latest version
    - Synthetic fallback: generates 200 samples if no training data exists
    - Optional --register flag to upsert model metadata to Supabase

Model Output Format:
    {
        "model_type": "ridge_v2",
        "category": "pokemon",
        "version": "20260206_120000",
        "features": ["condition_score", "rarity_score", "edition_score"],
        "standardizer": {"mean": [...], "std": [...]},
        "ridge": {"coef": [...], "intercept": 0.0},
        "ridge_q10": {"coef": [...], "intercept": 0.0},
        "ridge_q90": {"coef": [...], "intercept": 0.0},
        "best_alpha": 1.0,
        "cv_mae": 12.5,
        "train_mae": 10.2,
        "uncertainty_scale": 1.0,
        "train_size": 59,
        "created_at": "2026-02-06T12:00:00Z"
    }
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import KFold

logger = logging.getLogger("collectai.train_price")

# Try to import QuantileRegressor (scikit-learn >= 1.0)
try:
    from sklearn.linear_model import QuantileRegressor
    HAS_QUANTILE_REGRESSOR = True
except ImportError:
    HAS_QUANTILE_REGRESSOR = False
    logger.warning("QuantileRegressor not available; falling back to scaled Ridge for q10/q90")

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

# Alpha values for hyperparameter search (#6)
ALPHA_GRID = [0.01, 0.1, 1.0, 10.0, 100.0]

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
                    logger.warning(f"Skipping invalid line: {e}")
                    continue

        if features_list and prices_list:
            return features_list, prices_list

    # No training data found - generate synthetic fallback
    logger.info(f"No training data found for {category}, generating 200 synthetic samples...")
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
# User Feedback Integration (#12)
# ---------------------------------------------------------------------------

def load_user_feedback(category: str) -> tuple[list[dict], list[float]]:
    """
    Load user feedback events from Supabase and merge into training data.

    Queries user_feedback_events_v1 for:
    - feedback_type = 'sale_price' (user reported actual sale price)
    - feedback_type = 'price_correction' (user corrected model prediction)

    Returns additional (features_list, prices_list) to merge.
    """
    import httpx

    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not supabase_key:
        logger.info("Supabase not configured, skipping feedback integration")
        return [], []

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    features_list = []
    prices_list = []

    try:
        client = httpx.Client(timeout=15.0)

        # Fetch sale_price and price_correction feedback for this category
        # Join with items table to get category and attributes
        resp = client.get(
            f"{supabase_url}/rest/v1/user_feedback_events_v1",
            params={
                "select": "feedback_type,value_json,item_id,created_at",
                "feedback_type": "in.(sale_price,price_correction)",
                "order": "created_at.desc",
                "limit": "5000",
            },
            headers=headers,
        )

        if resp.status_code != 200:
            logger.warning(f"Failed to fetch feedback: {resp.status_code}")
            client.close()
            return [], []

        events = resp.json()

        # Also fetch the items to get category + attributes
        item_ids = list({e.get("item_id") for e in events if e.get("item_id")})
        if not item_ids:
            client.close()
            return [], []

        # Fetch items in batches of 100
        items_by_id: dict[str, dict] = {}
        for i in range(0, len(item_ids), 100):
            batch_ids = item_ids[i:i + 100]
            id_filter = ",".join(batch_ids)
            items_resp = client.get(
                f"{supabase_url}/rest/v1/items",
                params={
                    "select": "id,category,condition,grade,attributes_json",
                    "id": f"in.({id_filter})",
                    "category": f"eq.{category}",
                },
                headers=headers,
            )
            if items_resp.status_code == 200:
                for item in items_resp.json():
                    items_by_id[item["id"]] = item

        client.close()

        # Convert feedback events to training samples
        for event in events:
            item_id = event.get("item_id")
            item = items_by_id.get(item_id)
            if not item:
                continue

            value_json = event.get("value_json", {})
            if isinstance(value_json, str):
                try:
                    value_json = json.loads(value_json)
                except json.JSONDecodeError:
                    continue

            # Extract price from feedback
            price = value_json.get("price") or value_json.get("corrected_price")
            if not price or float(price) <= 0:
                continue

            # Build features from item attributes
            attrs = item.get("attributes_json", {})
            if isinstance(attrs, str):
                try:
                    attrs = json.loads(attrs)
                except json.JSONDecodeError:
                    attrs = {}

            features = {
                "condition_score": attrs.get("condition_score", 0.7),
                "rarity_score": attrs.get("rarity_score", 0.5),
                "edition_score": attrs.get("edition_score", 0.5),
            }
            # Copy any extra numeric attributes
            for k, v in attrs.items():
                if k not in features and isinstance(v, (int, float)):
                    features[k] = v

            features_list.append(features)
            prices_list.append(float(price))

        logger.info(f"Loaded {len(prices_list)} feedback samples for {category}")

    except Exception as e:
        logger.warning(f"Error loading feedback for {category}: {e}")

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
# Cross-Validated Hyperparameter Tuning (#6, #7)
# ---------------------------------------------------------------------------

def cross_validate_alpha(
    X: np.ndarray,
    y: np.ndarray,
    alphas: list[float] = ALPHA_GRID,
    n_folds: int = 5,
) -> tuple[float, float]:
    """
    Find the best Ridge alpha via k-fold cross-validation.

    Returns (best_alpha, best_cv_mae).
    """
    n_samples = len(y)

    # If too few samples for k-fold, skip CV and use alpha=1.0
    if n_samples < n_folds * 2:
        logger.info(f"Too few samples ({n_samples}) for {n_folds}-fold CV, using alpha=1.0")
        return 1.0, float("inf")

    kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)

    best_alpha = 1.0
    best_mae = float("inf")

    for alpha in alphas:
        fold_maes = []
        for train_idx, val_idx in kf.split(X):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            # Standardize per fold (to avoid data leakage)
            mean = X_train.mean(axis=0)
            std = X_train.std(axis=0)
            std[std == 0] = 1.0

            X_train_s = (X_train - mean) / std
            X_val_s = (X_val - mean) / std

            model = Ridge(alpha=alpha, random_state=42)
            model.fit(X_train_s, y_train)
            y_pred = model.predict(X_val_s)
            fold_maes.append(mean_absolute_error(y_val, y_pred))

        avg_mae = float(np.mean(fold_maes))
        if avg_mae < best_mae:
            best_mae = avg_mae
            best_alpha = alpha

    logger.info(f"Best alpha={best_alpha} with CV MAE={best_mae:.2f}")
    return best_alpha, best_mae


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
        ridge_q10: Any,  # Ridge or QuantileRegressor
        ridge_q90: Any,
        train_size: int,
        train_mae: float,
        cv_mae: float,
        best_alpha: float,
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
        self.train_mae = train_mae
        self.cv_mae = cv_mae
        self.best_alpha = best_alpha
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> dict:
        """Serialize model to JSON-compatible dict."""
        return {
            "model_type": "ridge_v2",
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
            "best_alpha": self.best_alpha,
            "cv_mae": round(self.cv_mae, 2) if self.cv_mae != float("inf") else None,
            "train_mae": round(self.train_mae, 2),
            "uncertainty_scale": 1.0,
            "train_size": self.train_size,
            "mae": round(self.cv_mae if self.cv_mae != float("inf") else self.train_mae, 2),
            "created_at": self.created_at,
        }


def train_ridge_model(
    category: str,
    features_list: list[dict],
    prices: list[float],
    version: str,
    alpha: float | None = None,
) -> RidgeModelPack:
    """
    Train Ridge regression models for q50, q10, q90.

    Steps:
        1. Extract feature names (core 3 + extras)
        2. Build feature matrix
        3. Cross-validate to find best alpha (#6, #7)
        4. Standardize features (zero mean, unit variance)
        5. Train Ridge for median (q50)
        6. Train QuantileRegressor for q10 and q90 (#3)
           (Falls back to scaled Ridge if QuantileRegressor unavailable)
        7. Compute holdout CV MAE + training MAE

    Returns:
        RidgeModelPack with all models and metadata
    """
    # Extract features
    feature_names = extract_feature_names(features_list)
    X = build_feature_matrix(features_list, feature_names)
    y = np.array(prices, dtype=np.float64)

    # Validate prices: reject non-positive, clip outliers at 99.5th percentile
    valid_mask = y > 0
    n_invalid = int(np.sum(~valid_mask))
    if n_invalid > 0:
        logger.warning(f"[{category}] Dropping {n_invalid} samples with non-positive price")
        X = X[valid_mask]
        y = y[valid_mask]

    if len(y) == 0:
        raise ValueError(f"No valid training samples for {category} after price validation")

    p995 = float(np.percentile(y, 99.5))
    n_clipped = int(np.sum(y > p995))
    if n_clipped > 0:
        logger.info(f"[{category}] Clipping {n_clipped} outlier prices above {p995:.2f}")
        y = np.clip(y, 0, p995)

    # Cross-validate alpha if not specified
    if alpha is None:
        best_alpha, cv_mae = cross_validate_alpha(X, y)
    else:
        best_alpha = alpha
        cv_mae = float("inf")

    # Standardize features (full dataset for final model)
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0  # Avoid division by zero
    X_scaled = (X - mean) / std

    # Train median model (q50)
    ridge_q50 = Ridge(alpha=best_alpha, random_state=42)
    ridge_q50.fit(X_scaled, y)

    # Train quantile models (#3)
    if HAS_QUANTILE_REGRESSOR and len(y) >= 30:
        # Proper quantile regression
        logger.info(f"[{category}] Using QuantileRegressor for q10/q90")
        try:
            ridge_q10 = QuantileRegressor(quantile=0.10, alpha=best_alpha, solver="highs")
            ridge_q10.fit(X_scaled, y)
        except Exception as e:
            logger.warning(f"QuantileRegressor q10 failed ({e}), falling back to scaled Ridge")
            ridge_q10 = Ridge(alpha=best_alpha, random_state=42)
            ridge_q10.fit(X_scaled, y * 0.7)

        try:
            ridge_q90 = QuantileRegressor(quantile=0.90, alpha=best_alpha, solver="highs")
            ridge_q90.fit(X_scaled, y)
        except Exception as e:
            logger.warning(f"QuantileRegressor q90 failed ({e}), falling back to scaled Ridge")
            ridge_q90 = Ridge(alpha=best_alpha, random_state=42)
            ridge_q90.fit(X_scaled, y * 1.4)
    else:
        # Fallback: scaled Ridge (for small datasets or missing dependency)
        if not HAS_QUANTILE_REGRESSOR:
            logger.info(f"[{category}] QuantileRegressor not available, using scaled Ridge")
        else:
            logger.info(f"[{category}] Too few samples ({len(y)}) for quantile regression, using scaled Ridge")
        ridge_q10 = Ridge(alpha=best_alpha, random_state=42)
        ridge_q10.fit(X_scaled, y * 0.7)
        ridge_q90 = Ridge(alpha=best_alpha, random_state=42)
        ridge_q90.fit(X_scaled, y * 1.4)

    # Compute training MAE
    y_pred = ridge_q50.predict(X_scaled)
    train_mae = mean_absolute_error(y, y_pred)

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
        train_mae=train_mae,
        cv_mae=cv_mae,
        best_alpha=best_alpha,
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

    # Atomic write: write to temp file in same dir, then rename
    fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=str(output_dir))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(model.to_json(), f, indent=2)
        os.replace(tmp_path, str(model_path))
    except BaseException:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

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

    Returns True if successful, False otherwise.
    """
    import httpx

    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not supabase_key:
        logger.error("SUPABASE_URL or SUPABASE_SERVICE_KEY not set")
        return False

    row = {
        "category": model.category,
        "version": model.version,
        "model_type": "ridge_v2",
        "artifact_path": str(model_path.absolute()),
        "artifact_json": json.dumps(model.to_json()),
        "train_size": model.train_size,
        "mae": round(model.cv_mae if model.cv_mae != float("inf") else model.train_mae, 2),
        "is_active": True,
        "created_at": model.created_at,
    }

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
            logger.info(f"Registered model to Supabase: {model.category}/{model.version}")
            return True
        else:
            logger.error(f"Supabase registration failed: {response.status_code}")
            logger.error(f"  {response.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"Supabase registration failed: {e}")
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
    include_feedback: bool = False,
) -> dict:
    """
    Train Ridge model for a single category.

    Returns summary dict with category, version, train_size, mae, output_path.
    """
    if version is None:
        version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    logger.info(f"[{category}] Loading training data...")
    features_list, prices = load_training_data(category)

    # Merge user feedback (#12)
    if include_feedback:
        logger.info(f"[{category}] Loading user feedback...")
        fb_features, fb_prices = load_user_feedback(category)
        if fb_features:
            features_list.extend(fb_features)
            prices.extend(fb_prices)
            logger.info(f"[{category}] Merged {len(fb_prices)} feedback samples "
                        f"(total: {len(prices)})")

    logger.info(f"[{category}] Training Ridge regression (n={len(prices)})...")
    model = train_ridge_model(category, features_list, prices, version)

    logger.info(f"[{category}] Saving model artifact...")
    output_dir = Path(f"artifacts/{category}/{version}")
    model_path = save_model(model, output_dir)

    # Optional Supabase registration
    if register:
        logger.info(f"[{category}] Registering model to Supabase...")
        register_model_to_supabase(model, model_path)

    summary = {
        "category": category,
        "version": version,
        "train_size": model.train_size,
        "train_mae": round(model.train_mae, 2),
        "cv_mae": round(model.cv_mae, 2) if model.cv_mae != float("inf") else None,
        "best_alpha": model.best_alpha,
        "features": model.feature_names,
        "output_path": str(model_path.absolute()),
    }

    report_mae = model.cv_mae if model.cv_mae != float("inf") else model.train_mae
    logger.info(f"[{category}] Done! MAE={report_mae:.2f} (alpha={model.best_alpha}), "
                f"n={model.train_size}, path={model_path}")

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
    parser.add_argument(
        "--include-feedback",
        action="store_true",
        help="Merge user feedback events into training data (#12)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

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
                include_feedback=args.include_feedback,
            )
            summaries.append(summary)
        except Exception as e:
            logger.error(f"[{category}] ERROR: {e}", exc_info=True)
            continue

    # Log final summary
    logger.info("=" * 80)
    logger.info("TRAINING SUMMARY")
    logger.info("=" * 80)

    if not summaries:
        logger.info("No models trained.")
        return

    for summary in summaries:
        mae_str = f"CV={summary['cv_mae']}" if summary['cv_mae'] else f"Train={summary['train_mae']}"
        logger.info(
            "%s | n=%5d | MAE: %10s | alpha=%6.2f | features=%d",
            summary['category'].ljust(20),
            summary['train_size'],
            mae_str,
            summary['best_alpha'],
            len(summary['features']),
        )

    logger.info("Total: %d models trained", len(summaries))
    logger.info("Model artifacts saved to: artifacts/<category>/<version>/model.json")
    logger.info("Active symlinks: artifacts/<category>/active -> <version>")


if __name__ == "__main__":
    main()
