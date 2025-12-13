from __future__ import annotations

import re

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def normalize_photo(raw: bytes, filename: str) -> tuple[bytes, str]:
    """
    Dev-safe normalizer: return bytes unchanged, sanitize filename.
    (Later you can add EXIF autorotate / HEIC->JPEG here.)
    """
    name = filename or "upload.jpg"
    name = _SAFE.sub("_", name).strip("_") or "upload.jpg"
    return raw, name
