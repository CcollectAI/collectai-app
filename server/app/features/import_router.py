"""
CSV / Excel collection import router.

Provides a downloadable CSV template and an upload endpoint that parses
CSV or Excel files and inserts rows into the Supabase ``items`` table.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid as _uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.auth import get_current_user_id
from app.errors import error_response
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/api/imports", tags=["Imports"])

_import_limit = per_user_rate_limit(5, window_seconds=3600, scope="collection_import")

_logger = logging.getLogger(__name__)

# ---- Import template columns ----
IMPORT_COLUMNS = [
    "name", "category", "condition", "grade", "graded_by",
    "sealed", "estimated_value", "notes",
]

IMPORT_COLUMN_EXAMPLES = {
    "name": "Charizard Base Set Holo 1st Edition",
    "category": "pokemon",
    "condition": "Near Mint",
    "grade": "PSA 9",
    "graded_by": "PSA",
    "sealed": "no",
    "estimated_value": "350.00",
    "notes": "My favourite card",
}


# ---- Endpoints ----

@router.get("/template")
async def import_template() -> StreamingResponse:
    """Return a CSV template with headers + one example row."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(IMPORT_COLUMNS)
    writer.writerow([IMPORT_COLUMN_EXAMPLES.get(c, "") for c in IMPORT_COLUMNS])
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=collectai_import_template.csv"},
    )


@router.post("/collection")
async def import_collection(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_import_limit),
) -> Dict[str, Any]:
    """
    Accept a CSV or Excel file, parse it, and insert valid rows into
    the Supabase ``items`` table. Returns a summary with counts.
    """
    filename = file.filename or "upload"
    content = await file.read()

    if not content:
        raise error_response(400, "Empty file")

    if len(content) > 50 * 1024 * 1024:  # 50 MB max for CSV/Excel
        raise error_response(413, "File too large (max 50 MB)")

    # Decide how to parse based on extension
    lower_name = filename.lower()
    rows: List[Dict[str, Any]] = []

    try:
        if lower_name.endswith(".csv"):
            text = content.decode("utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
        elif lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
            try:
                import pandas as pd  # type: ignore
            except ImportError:
                raise error_response(500, "Excel support is not installed. Please install pandas and openpyxl.")
            df = pd.read_excel(io.BytesIO(content))
            rows = df.to_dict(orient="records")
        else:
            raise error_response(400, "Unsupported file type. Please upload a CSV or Excel file.")
    except HTTPException:
        raise
    except Exception as e:
        _logger.warning("Failed to parse uploaded file: %s", e)
        raise error_response(400, "Failed to parse file")

    # Normalize keys (lowercase, strip spaces)
    norm_rows: List[Dict[str, Any]] = []
    for row in rows:
        norm: Dict[str, Any] = {}
        for k, v in row.items():
            if k is None:
                continue
            norm_key = str(k).strip().lower().replace(" ", "_")
            norm[norm_key] = v
        norm_rows.append(norm)

    total = len(norm_rows)
    inserted = 0
    skipped = 0
    errors: List[Dict[str, Any]] = []

    # Try to get DB pool for actual inserts
    pool = None
    try:
        from app.db import get_pool
        pool = get_pool()
    except (ImportError, RuntimeError, OSError) as e:
        _logger.debug("[import] DB pool unavailable, using in-memory fallback: %s", e)

    for idx, r in enumerate(norm_rows, start=1):
        name = r.get("name") or r.get("title")
        if not name or str(name).strip() == "":
            skipped += 1
            errors.append({"row": idx, "message": "Missing required 'name' column"})
            continue

        title = str(name).strip()
        category = str(r.get("category", "") or "").strip() or None
        condition = str(r.get("condition", "") or "").strip() or None
        grade = str(r.get("grade", "") or "").strip() or None
        graded_by = str(r.get("graded_by", "") or "").strip() or None
        sealed_raw = str(r.get("sealed", "") or "").strip().lower()
        sealed = sealed_raw in ("yes", "true", "1", "y")

        # Build attributes JSON for extra fields
        attrs: Dict[str, Any] = {}
        est_val = r.get("estimated_value") or r.get("price") or r.get("value")
        if est_val is not None:
            try:
                attrs["estimated_value"] = float(str(est_val).replace(",", ".").strip())
            except (ValueError, TypeError) as e:
                _logger.debug("[import] estimated_value parse failed: %s", e)
        notes = r.get("notes")
        if notes:
            attrs["notes"] = str(notes).strip()

        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO items (id, user_id, title, category, condition, grade, graded_by, sealed, attributes_json)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        """,
                        str(_uuid.uuid4()),
                        user_id,
                        title,
                        category,
                        condition,
                        grade,
                        graded_by,
                        sealed,
                        json.dumps(attrs) if attrs else None,
                    )
                inserted += 1
            except Exception as e:
                skipped += 1
                errors.append({"row": idx, "message": f"DB insert failed: {e}"})
        else:
            # No DB — count as inserted (parse-only mode)
            inserted += 1

    return {
        "total_rows": total,
        "inserted_count": inserted,
        "skipped_count": skipped,
        "errors": errors,
        "columns_detected": sorted(list(norm_rows[0].keys())) if norm_rows else [],
        "db_mode": "live" if pool else "parse_only",
    }
