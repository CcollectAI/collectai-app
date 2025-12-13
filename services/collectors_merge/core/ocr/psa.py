from __future__ import annotations

import re

from .image_io import normalize_photo

try:
    import pytesseract
    from PIL import Image
except Exception:
    pytesseract = None

LINE = re.compile(r"[^\S\r\n]*")  # collapse whitespace

CERT_RE = re.compile(r"\b(\d{6,12})\b")
GRADE_RE = re.compile(
    r"\b(PSA)\s*([0-9]{1,2})(?:\s*[(\- ]?(?:OC|MC|ST|MK|Q)?)?\b", re.I
)
SET_RE = re.compile(
    r"(?i)\b(Set|Series|Base|1st Edition|Unlimited|Shadowless|Neo|Fossil|Jungle)\b"
)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _clean(s: str) -> str:
    return LINE.sub(" ", (s or "").strip())


def ocr_psa_bytes(raw: bytes, filename: str) -> dict:
    if pytesseract is None:
        return {"ok": False, "error": "pytesseract not installed"}
    # normalize (EXIF transpose, HEIC->JPEG)
    jpeg, norm_name = normalize_photo(raw, filename)
    img = Image.open(__import__("io").BytesIO(jpeg))

    text = pytesseract.image_to_string(img)
    text_c = _clean(text)

    cert = None
    m = CERT_RE.search(text_c)
    if m:
        cert = m.group(1)

    grade = None
    m = GRADE_RE.search(text_c)
    if m:
        grade = f"PSA {m.group(2)}"

    # naive guesses
    year = None
    my = YEAR_RE.search(text_c)
    if my:
        year = my.group(0)

    has_set = bool(SET_RE.search(text_c))

    return {
        "ok": True,
        "filename": norm_name,
        "raw_text": text,
        "fields": {
            "cert": cert,
            "grade": grade,
            "year_hint": year,
            "has_set_word": has_set,
        },
    }
