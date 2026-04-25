#!/usr/bin/env python3
"""Vision text re-classifier — the only model in the vision loop we OWN.

Trains a small TF-IDF + LogisticRegression text classifier on user
`scan_corrections` mapping `(suggested_name + condition + attribute_text)`
to `corrected_category`. At inference time, `openai_vision.identify` calls
into this model AFTER the OpenAI vision call. If the text classifier
disagrees with the vision-predicted category AND has high confidence in
its own answer, the category is overridden.

Why this is a real learning loop:
  - OpenAI does not yet expose vision-model fine-tuning, so we cannot
    train GPT-4o-mini directly on our corrections.
  - The vision model returns a `suggested_name` that's typically clean
    text (e.g., "Charizard - Base Set 4/102"). That text is very
    discriminating — we can train a small text classifier ourselves.
  - This worker writes a reusable joblib artifact to
    `artifacts/_vision_reclassifier/active/model.pkl`. Loader reads from
    disk just like Ridge models.

Gates:
  - MIN_TRAIN_SAMPLES (default 1000) — does nothing useful below this.
    Currently scan_corrections has 0 rows; this worker is preparation.
  - MIN_PER_CATEGORY (default 5) — drops categories with too few samples
    so the model isn't dragged toward the noisy long tail.

Cycle interval: weekly (matches model_retrain_worker — same training
cadence; same data freshness assumptions).
"""

from __future__ import annotations

import asyncio
import logging
import os
import pickle
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

from app.worker_registry import record_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [vision_reclassifier] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")
LOOKBACK_DAYS = int(os.getenv("VISION_RECLASSIFIER_LOOKBACK_DAYS", "180"))
MIN_TRAIN_SAMPLES = int(os.getenv("VISION_RECLASSIFIER_MIN_SAMPLES", "1000"))
MIN_PER_CATEGORY = int(os.getenv("VISION_RECLASSIFIER_MIN_PER_CAT", "5"))

# Disk slot where the active reclassifier pickle lives.
_ARTIFACT_DIR = Path("/opt/collectors/server/artifacts/_vision_reclassifier")


async def run_once() -> dict[str, int]:
    if not DSN:
        logger.warning("DB_DSN not set — skipping")
        record_run("vision_reclassifier_worker", "error")
        return {"trained": 0}

    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            """
            SELECT
                sc.corrected_category AS label,
                sc.corrected_name AS name,
                sc.corrected_condition AS condition,
                ps.output AS predict_output
            FROM public.scan_corrections sc
            LEFT JOIN public.predict_sessions ps
              ON ps.uuid_id::text = sc.scan_session_id
                 OR ps.id::text = sc.scan_session_id
            WHERE sc.corrected_category IS NOT NULL
              AND sc.corrected_name IS NOT NULL
              AND sc.created_at >= now() - ($1 || ' days')::interval
            """,
            str(LOOKBACK_DAYS),
        )
    finally:
        await conn.close()

    if len(rows) < MIN_TRAIN_SAMPLES:
        logger.info(
            "Only %d scan_corrections in last %dd (need %d) — skipping train",
            len(rows), LOOKBACK_DAYS, MIN_TRAIN_SAMPLES,
        )
        record_run("vision_reclassifier_worker", "ok")
        return {"trained": 0, "samples": len(rows)}

    # Per-category min count — drop noisy categories
    by_cat: dict[str, list] = {}
    for r in rows:
        by_cat.setdefault(r["label"], []).append(r)
    eligible_cats = {c for c, recs in by_cat.items() if len(recs) >= MIN_PER_CATEGORY}
    filtered = [r for r in rows if r["label"] in eligible_cats]

    if len(filtered) < MIN_TRAIN_SAMPLES:
        logger.info(
            "After per-category filter, %d samples remain (need %d) — skipping train",
            len(filtered), MIN_TRAIN_SAMPLES,
        )
        record_run("vision_reclassifier_worker", "ok")
        return {"trained": 0, "samples_after_filter": len(filtered)}

    # Build text inputs + labels
    texts: list[str] = []
    labels: list[str] = []
    for r in filtered:
        # Compose feature text: corrected_name + condition + a few prediction
        # attributes if available. Keeps the classifier discriminative on the
        # text the user actually saw + corrected.
        attrs_text = ""
        if isinstance(r["predict_output"], dict):
            attrs = r["predict_output"].get("attributes") or {}
            if isinstance(attrs, dict):
                attrs_text = " ".join(f"{k}:{v}" for k, v in list(attrs.items())[:8] if isinstance(v, (str, int, float)))
        texts.append(
            f"{r['name'] or ''} {r['condition'] or ''} {attrs_text}".strip()
        )
        labels.append(r["label"])

    # Train
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score
    except ImportError as e:
        logger.error("sklearn not available: %s", e)
        record_run("vision_reclassifier_worker", "error")
        return {"trained": 0}

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels,
    )

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2), max_features=10_000, lowercase=True,
            min_df=2, sublinear_tf=True,
        )),
        ("clf", LogisticRegression(
            max_iter=500, C=1.0, multi_class="auto", n_jobs=-1,
        )),
    ])
    pipeline.fit(X_train, y_train)
    holdout_pred = pipeline.predict(X_test)
    accuracy = accuracy_score(y_test, holdout_pred)

    logger.info(
        "Trained reclassifier: train_n=%d test_n=%d holdout_accuracy=%.3f",
        len(X_train), len(X_test), accuracy,
    )

    # Persist atomically
    version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = _ARTIFACT_DIR / version
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pkl = out_dir / "model.pkl"
    out_meta = out_dir / "meta.json"

    fd, tmp = tempfile.mkstemp(suffix=".pkl", dir=str(out_dir))
    try:
        with os.fdopen(fd, "wb") as f:
            pickle.dump({
                "pipeline": pipeline,
                "version": version,
                "holdout_accuracy": accuracy,
                "train_size": len(X_train),
                "categories": sorted(eligible_cats),
            }, f)
        os.replace(tmp, str(out_pkl))
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise

    import json
    out_meta.write_text(json.dumps({
        "version": version, "holdout_accuracy": accuracy,
        "train_size": len(X_train), "test_size": len(X_test),
        "categories": sorted(eligible_cats),
    }, indent=2))

    # Atomically swap the active symlink
    active_link = _ARTIFACT_DIR / "active"
    if active_link.exists() or active_link.is_symlink():
        active_link.unlink()
    active_link.symlink_to(version)

    logger.info("Reclassifier promoted: version=%s active -> %s", version, version)
    record_run("vision_reclassifier_worker", "ok")
    return {"trained": 1, "samples": len(filtered), "accuracy": accuracy}


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("vision_reclassifier_worker", "error")
        logger.exception("vision_reclassifier_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
