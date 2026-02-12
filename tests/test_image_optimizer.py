"""
Tests for app/lib/image_optimizer.py — image optimization and blurhash.

Covers:
  - optimize_image() with a real small PNG
  - optimize_image() with RGBA -> RGB conversion
  - optimize_image() with oversized image (resize)
  - optimize_image() with invalid image bytes (error path)
  - generate_blurhash() with real image
  - _base83_encode() unit test
  - _srgb_to_linear() / _linear_to_srgb() round-trip
  - _dominant_colour_fallback()
"""

from __future__ import annotations

import io
import os

import pytest
from PIL import Image

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_png(width: int = 100, height: int = 80, mode: str = "RGB", color=(129, 216, 208)) -> bytes:
    """Create a small in-memory PNG image."""
    img = Image.new(mode, (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_rgba_png(width: int = 50, height: int = 50) -> bytes:
    """Create a small RGBA PNG with transparency."""
    img = Image.new("RGBA", (width, height), (255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_large_png(width: int = 3000, height: int = 2000) -> bytes:
    """Create a PNG larger than the default max_edge."""
    img = Image.new("RGB", (width, height), (50, 100, 150))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# optimize_image tests
# ---------------------------------------------------------------------------


class TestOptimizeImage:
    """Tests for optimize_image()."""

    def test_basic_optimization(self):
        from app.lib.image_optimizer import optimize_image

        png_bytes = _make_png(100, 80)
        optimized, w, h = optimize_image(png_bytes)

        assert isinstance(optimized, bytes)
        assert len(optimized) > 0
        assert w == 100
        assert h == 80

        # Should be JPEG
        result_img = Image.open(io.BytesIO(optimized))
        assert result_img.format == "JPEG"
        assert result_img.mode == "RGB"

    def test_rgba_to_rgb_conversion(self):
        from app.lib.image_optimizer import optimize_image

        rgba_bytes = _make_rgba_png()
        optimized, w, h = optimize_image(rgba_bytes)

        assert w == 50
        assert h == 50
        result_img = Image.open(io.BytesIO(optimized))
        assert result_img.mode == "RGB"

    def test_resize_large_image(self):
        from app.lib.image_optimizer import optimize_image

        large_bytes = _make_large_png(3000, 2000)
        optimized, w, h = optimize_image(large_bytes, max_edge=1200)

        assert max(w, h) <= 1200
        # Aspect ratio should be preserved
        ratio = w / h
        expected_ratio = 3000 / 2000
        assert abs(ratio - expected_ratio) < 0.05

    def test_small_image_not_resized(self):
        from app.lib.image_optimizer import optimize_image

        small_bytes = _make_png(200, 150)
        optimized, w, h = optimize_image(small_bytes, max_edge=1200)

        assert w == 200
        assert h == 150

    def test_custom_quality(self):
        from app.lib.image_optimizer import optimize_image

        png_bytes = _make_png(100, 80)
        high_q, _, _ = optimize_image(png_bytes, quality=95)
        low_q, _, _ = optimize_image(png_bytes, quality=20)

        # Higher quality should produce more bytes
        assert len(high_q) > len(low_q)

    def test_invalid_image_raises_value_error(self):
        from app.lib.image_optimizer import optimize_image

        with pytest.raises(ValueError, match="Cannot decode image"):
            optimize_image(b"not an image at all")

    def test_empty_bytes_raises_value_error(self):
        from app.lib.image_optimizer import optimize_image

        with pytest.raises(ValueError, match="Cannot decode image"):
            optimize_image(b"")

    def test_palette_mode_conversion(self):
        """Test P (palette) mode images are converted to RGB."""
        from app.lib.image_optimizer import optimize_image

        img = Image.new("P", (50, 50))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        p_bytes = buf.getvalue()

        optimized, w, h = optimize_image(p_bytes)
        result_img = Image.open(io.BytesIO(optimized))
        assert result_img.mode == "RGB"

    def test_grayscale_conversion(self):
        """Test L (grayscale) mode images are converted to RGB."""
        from app.lib.image_optimizer import optimize_image

        img = Image.new("L", (50, 50), 128)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        gray_bytes = buf.getvalue()

        optimized, w, h = optimize_image(gray_bytes)
        result_img = Image.open(io.BytesIO(optimized))
        assert result_img.mode == "RGB"


# ---------------------------------------------------------------------------
# generate_blurhash tests
# ---------------------------------------------------------------------------


class TestGenerateBlurhash:
    """Tests for generate_blurhash()."""

    def test_returns_string(self):
        from app.lib.image_optimizer import generate_blurhash

        png_bytes = _make_png(100, 80)
        result = generate_blurhash(png_bytes)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_blurhash_or_fallback_format(self):
        """Should return either a valid blurhash or C:<hex>:<w>:<h> fallback."""
        from app.lib.image_optimizer import generate_blurhash

        png_bytes = _make_png(100, 80)
        result = generate_blurhash(png_bytes)

        # Either a proper blurhash string (base83 chars) or fallback
        if result.startswith("C:"):
            parts = result.split(":")
            assert len(parts) == 4
        else:
            # Valid blurhash string
            assert len(result) >= 6

    def test_component_clamping(self):
        """x/y components should be clamped to 1-9."""
        from app.lib.image_optimizer import generate_blurhash

        png_bytes = _make_png(50, 50)
        # Should not raise even with extreme values
        result = generate_blurhash(png_bytes, x_components=0, y_components=100)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_different_images_different_hashes(self):
        from app.lib.image_optimizer import generate_blurhash

        red_png = _make_png(50, 50, color=(255, 0, 0))
        blue_png = _make_png(50, 50, color=(0, 0, 255))

        hash_red = generate_blurhash(red_png)
        hash_blue = generate_blurhash(blue_png)
        assert hash_red != hash_blue

    def test_invalid_image_returns_fallback(self):
        from app.lib.image_optimizer import generate_blurhash

        result = generate_blurhash(b"not-an-image")
        # Should return the grey fallback
        assert result.startswith("C:")


# ---------------------------------------------------------------------------
# Internal helper tests
# ---------------------------------------------------------------------------


class TestBase83Encode:
    """Tests for _base83_encode()."""

    def test_zero(self):
        from app.lib.image_optimizer import _base83_encode

        assert _base83_encode(0, 1) == "0"

    def test_single_char(self):
        from app.lib.image_optimizer import _base83_encode

        result = _base83_encode(1, 1)
        assert len(result) == 1

    def test_multi_char(self):
        from app.lib.image_optimizer import _base83_encode

        result = _base83_encode(100, 4)
        assert len(result) == 4


class TestSrgbLinearConversion:
    """Tests for _srgb_to_linear() and _linear_to_srgb() round-trip."""

    def test_black(self):
        from app.lib.image_optimizer import _srgb_to_linear, _linear_to_srgb

        linear = _srgb_to_linear(0)
        assert linear == 0.0
        assert _linear_to_srgb(linear) == 0

    def test_white(self):
        from app.lib.image_optimizer import _srgb_to_linear, _linear_to_srgb

        linear = _srgb_to_linear(255)
        assert linear == pytest.approx(1.0, abs=0.01)
        assert _linear_to_srgb(linear) == 255

    def test_midtone_round_trip(self):
        from app.lib.image_optimizer import _srgb_to_linear, _linear_to_srgb

        for val in (50, 100, 128, 200):
            linear = _srgb_to_linear(val)
            back = _linear_to_srgb(linear)
            assert abs(back - val) <= 1, f"Round-trip failed for {val}: got {back}"


class TestDominantColourFallback:
    """Tests for _dominant_colour_fallback()."""

    def test_returns_colour_string(self):
        from app.lib.image_optimizer import _dominant_colour_fallback

        png_bytes = _make_png(50, 50, color=(255, 0, 0))
        result = _dominant_colour_fallback(png_bytes)
        assert result.startswith("C:")
        parts = result.split(":")
        assert len(parts) == 4
        # Hex colour should be 6 chars
        assert len(parts[1]) == 6

    def test_tiffany_blue_detection(self):
        from app.lib.image_optimizer import _dominant_colour_fallback

        tiffany_blue = (129, 216, 208)
        png_bytes = _make_png(50, 50, color=tiffany_blue)
        result = _dominant_colour_fallback(png_bytes)
        # Dominant colour should be close to 81D8D0
        parts = result.split(":")
        hex_colour = parts[1]
        # Check it is in the right ballpark (Pillow resize may shift slightly)
        r = int(hex_colour[0:2], 16)
        g = int(hex_colour[2:4], 16)
        b = int(hex_colour[4:6], 16)
        assert abs(r - 129) < 10
        assert abs(g - 216) < 10
        assert abs(b - 208) < 10

    def test_invalid_image_returns_grey(self):
        from app.lib.image_optimizer import _dominant_colour_fallback

        result = _dominant_colour_fallback(b"bad data")
        assert result == "C:808080:0:0"

    def test_empty_bytes_returns_grey(self):
        from app.lib.image_optimizer import _dominant_colour_fallback

        result = _dominant_colour_fallback(b"")
        assert result == "C:808080:0:0"
