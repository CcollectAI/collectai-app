"""
Server-side image optimization for CollectAI.

Provides:
- optimize_image: Resize, strip EXIF, convert to JPEG q85
- generate_blurhash: Generate a compact placeholder string for progressive image loading

Uses Pillow (already in requirements.txt).  For blurhash we attempt to use the
`blurhash` library (pure-Python).  If unavailable, we fall back to a simple
dominant-colour placeholder string that the frontend can decode into a solid
colour swatch (format: "C:<hex>:<w>:<h>").
"""

from __future__ import annotations

import io
import logging
import struct
import math
from typing import Tuple

from PIL import Image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# optimize_image
# ---------------------------------------------------------------------------


def optimize_image(
    image_bytes: bytes,
    max_edge: int = 1200,
    quality: int = 85,
) -> Tuple[bytes, int, int]:
    """
    Resize an image so its longest edge is at most *max_edge* pixels, convert
    to JPEG at the given quality, and strip all EXIF / metadata.

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, WebP, etc.).
        max_edge: Maximum dimension on the longest side (default 1200).
        quality: JPEG compression quality 1-95 (default 85).

    Returns:
        Tuple of (optimized_jpeg_bytes, width, height).

    Raises:
        ValueError: If the input bytes cannot be decoded as an image.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as exc:
        raise ValueError(f"Cannot decode image: {exc}") from exc

    # Apply EXIF orientation before stripping metadata
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass  # If EXIF orientation fails, continue with original orientation

    # Convert palette / RGBA -> RGB for JPEG output
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize if necessary (preserve aspect ratio)
    w, h = img.size
    if max(w, h) > max_edge:
        scale = max_edge / max(w, h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        logger.debug(
            "[image_optimizer] Resized %dx%d -> %dx%d (scale %.2f)",
            w, h, new_w, new_h, scale,
        )
    else:
        new_w, new_h = w, h

    # Encode to JPEG (no EXIF, no ICC profile)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    optimized = buf.getvalue()

    logger.info(
        "[image_optimizer] Optimized image: %d bytes -> %d bytes (%dx%d)",
        len(image_bytes), len(optimized), new_w, new_h,
    )

    return optimized, new_w, new_h


# ---------------------------------------------------------------------------
# Blurhash — try real library first, then fallback
# ---------------------------------------------------------------------------

_BLURHASH_AVAILABLE: bool | None = None


def _check_blurhash_lib() -> bool:
    """Check whether the `blurhash` package is importable."""
    global _BLURHASH_AVAILABLE
    if _BLURHASH_AVAILABLE is None:
        try:
            import blurhash as _bh  # noqa: F401
            _BLURHASH_AVAILABLE = True
        except ImportError:
            _BLURHASH_AVAILABLE = False
            logger.info(
                "[image_optimizer] blurhash library not available; "
                "using fallback dominant-colour placeholder"
            )
    return _BLURHASH_AVAILABLE


# -- Minimal inline blurhash encoder (pure Python) -------------------------
# Based on the Wolt blurhash algorithm specification.
# Encodes a tiny thumbnail into a compact ~20-30 char base83 string.
#
# This avoids a hard dependency on the blurhash-python package while still
# producing valid blurhash strings that expo-image can decode natively.

_BASE83_CHARS = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~"
)


def _base83_encode(value: int, length: int) -> str:
    """Encode an integer into a base83 string of *length* characters."""
    result = []
    for i in range(1, length + 1):
        digit = (value // (83 ** (length - i))) % 83
        result.append(_BASE83_CHARS[digit])
    return "".join(result)


def _srgb_to_linear(value: int) -> float:
    v = value / 255.0
    if v <= 0.04045:
        return v / 12.92
    return math.pow((v + 0.055) / 1.055, 2.4)


def _linear_to_srgb(value: float) -> int:
    v = max(0.0, min(1.0, value))
    if v <= 0.0031308:
        return min(255, max(0, int(v * 12.92 * 255 + 0.5)))
    return min(255, max(0, int((1.055 * math.pow(v, 1.0 / 2.4) - 0.055) * 255 + 0.5)))


def _sign_pow(val: float, exp: float) -> float:
    return math.copysign(math.pow(abs(val), exp), val)


def _encode_dc(r: float, g: float, b: float) -> int:
    return (_linear_to_srgb(r) << 16) + (_linear_to_srgb(g) << 8) + _linear_to_srgb(b)


def _encode_ac(r: float, g: float, b: float, max_val: float) -> int:
    def _quantise(v: float) -> int:
        return max(0, min(18, int(math.floor(_sign_pow(v / max_val, 0.5) * 9 + 9.5))))
    return _quantise(r) * 19 * 19 + _quantise(g) * 19 + _quantise(b)


def _blurhash_encode_pixels(
    pixels: list,  # list of (r, g, b) in linear float
    width: int,
    height: int,
    x_comp: int,
    y_comp: int,
) -> str:
    """Encode pixel data (linear RGB floats) into a blurhash string."""
    components = []
    for j in range(y_comp):
        for i in range(x_comp):
            r_sum = g_sum = b_sum = 0.0
            for y in range(height):
                for x in range(width):
                    basis = (
                        math.cos((math.pi * i * x) / width)
                        * math.cos((math.pi * j * y) / height)
                    )
                    idx = y * width + x
                    pr, pg, pb = pixels[idx]
                    r_sum += basis * pr
                    g_sum += basis * pg
                    b_sum += basis * pb
            scale = 1.0 / (width * height) if (i == 0 and j == 0) else 2.0 / (width * height)
            components.append((r_sum * scale, g_sum * scale, b_sum * scale))

    # Size flag
    size_flag = (x_comp - 1) + (y_comp - 1) * 9
    result = _base83_encode(size_flag, 1)

    # Quantised maximum AC value
    if len(components) > 1:
        actual_max = max(
            max(abs(c[0]), abs(c[1]), abs(c[2]))
            for c in components[1:]
        )
        quantised_max = max(0, min(82, int(math.floor(actual_max * 166 - 0.5))))
        max_val = (quantised_max + 1) / 166.0
    else:
        quantised_max = 0
        max_val = 1.0

    result += _base83_encode(quantised_max, 1)

    # DC component
    dc = components[0]
    result += _base83_encode(_encode_dc(*dc), 4)

    # AC components
    for comp in components[1:]:
        result += _base83_encode(_encode_ac(*comp, max_val), 2)

    return result


def generate_blurhash(
    image_bytes: bytes,
    x_components: int = 4,
    y_components: int = 4,
) -> str:
    """
    Generate a blurhash string from image bytes.

    The blurhash is a compact (~20-30 char) representation of a blurred
    version of the image, suitable for use as a placeholder while the full
    image loads.  expo-image supports blurhash natively.

    Args:
        image_bytes: Raw image bytes.
        x_components: Horizontal detail level (1-9, default 4).
        y_components: Vertical detail level (1-9, default 4).

    Returns:
        Blurhash string, or a fallback "C:<hex>:<w>:<h>" colour string if
        encoding fails.
    """
    x_components = max(1, min(9, x_components))
    y_components = max(1, min(9, y_components))

    try:
        # Try the blurhash library first (faster C extension)
        if _check_blurhash_lib():
            import blurhash as bh
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            # Downscale for speed (blurhash is lossy anyway)
            thumb = img.resize((32, 32), Image.LANCZOS)
            return bh.encode(thumb, x_components, y_components)
    except Exception as exc:
        logger.debug("[image_optimizer] blurhash library encode failed: %s", exc)

    # Inline pure-Python encoder on a tiny thumbnail
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        # Use a very small thumbnail for the pure-Python encoder (performance)
        thumb_size = 20
        thumb = img.resize((thumb_size, thumb_size), Image.LANCZOS)
        raw = list(thumb.getdata())  # list of (R, G, B) tuples 0-255

        # Convert to linear RGB floats
        linear_pixels = [
            (_srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b))
            for r, g, b in raw
        ]

        bh_str = _blurhash_encode_pixels(
            linear_pixels, thumb_size, thumb_size, x_components, y_components,
        )
        logger.debug("[image_optimizer] Generated blurhash (inline): %s", bh_str)
        return bh_str

    except Exception as exc:
        logger.warning("[image_optimizer] Blurhash encoding failed: %s", exc)

    # Last-resort fallback: dominant colour string
    return _dominant_colour_fallback(image_bytes)


def _dominant_colour_fallback(image_bytes: bytes) -> str:
    """
    Fallback when blurhash encoding is not possible.
    Returns a string like "C:81D8D0:800:600" (colour, width, height)
    that the frontend can parse to show a solid-colour placeholder.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        thumb = img.resize((1, 1), Image.LANCZOS)
        r, g, b = thumb.getpixel((0, 0))
        hex_colour = f"{r:02X}{g:02X}{b:02X}"
        return f"C:{hex_colour}:{w}:{h}"
    except Exception:
        return "C:808080:0:0"
