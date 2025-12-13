from __future__ import annotations

import re

try:
    import pytesseract
    from PIL import Image
except Exception:
    pytesseract = None


def tesseract_ocr(path: str) -> str:
    if not pytesseract:
        return ""
    img = Image.open(path)
    txt = pytesseract.image_to_string(img)
    return txt or ""


LEGO_RE = re.compile(r"\b(10\d{3}|7\d{4}|[1-9]\d{2,4})\b")  # simple catch; refine later
PSA_RE = re.compile(r"\b(?:Cert(?:ificate)?\s*#?:?\s*)?(\d{7,10})\b", re.I)
SKU_RE = re.compile(r"\b([A-Z0-9]{3,6}-?[A-Z0-9]{3,6})\b")  # sneakers, toys, misc


def extract_lego_set(text: str) -> str | None:
    m = LEGO_RE.search(text or "")
    return m.group(1) if m else None


def extract_psa_cert(text: str) -> str | None:
    m = PSA_RE.search(text or "")
    return m.group(1) if m else None


def extract_sku(text: str) -> str | None:
    m = SKU_RE.search(text or "")
    return m.group(1) if m else None
