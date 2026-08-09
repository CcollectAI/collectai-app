#!/usr/bin/env python3
"""
Regenerate the Google Play listing images from the iOS screenshot masters.

Why this exists
---------------
The Play Console rejects assets the App Store happily accepts, and the two
rules that bite us are easy to miss because the files *look* fine:

  1. "The maximum dimension of your screenshot can't be more than twice as long
     as the minimum dimension."  The iOS masters are 1320x2868 (iPhone 6.9"),
     a ratio of 2.173 -> rejected.
  2. Screenshots must be "JPEG or 24-bit PNG (no alpha)".  The masters are
     RGBA -> rejected.

  (The app icon is the opposite: Play wants a 32-bit PNG, so it keeps alpha.)

Rather than hand-editing images, this regenerates them from the masters every
time, so it is idempotent -- running it twice does not double-pad.

Padding strategy: the masters have a vertical gradient background, so a flat
pad colour leaves a visible seam.  Instead each row is extended outward using
its own edge pixel, which continues the gradient and reads as a wider capture.

Usage:
    python3 scripts/prepare_play_assets.py            # regenerate + verify
    python3 scripts/prepare_play_assets.py --verify   # verify only, no writes

Verification also runs standalone in scripts/preflight_android.mjs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import struct

# Pillow is needed to *rewrite* images, but not to check them. Verification
# reads the PNG header directly so `--verify` (and therefore the Android
# preflight) works on any machine — a checker that silently skips when a
# dependency is missing is the same class of bug it is meant to catch.
try:
    from PIL import Image
except ImportError:  # pragma: no cover - verification still works without it
    Image = None


# PNG colour-type byte -> (human name, has_alpha). Play wants no alpha on
# screenshots and the feature graphic, but requires it on the icon.
PNG_COLOR_TYPES = {
    0: ("grayscale", False),
    2: ("RGB", False),
    3: ("palette", False),
    4: ("grayscale+alpha", True),
    6: ("RGBA", True),
}


def read_png_header(path: Path) -> tuple[int, int, str, bool]:
    """Return (width, height, mode_name, has_alpha) by parsing the PNG IHDR.

    A PNG is an 8-byte signature followed by the IHDR chunk: 4-byte length,
    4-byte type, then width/height as big-endian uint32 and the bit depth and
    colour type as single bytes.
    """
    with open(path, "rb") as fh:
        signature = fh.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"{path} is not a PNG")
        fh.read(4)  # IHDR chunk length
        if fh.read(4) != b"IHDR":
            raise ValueError(f"{path} has no IHDR chunk")
        width, height = struct.unpack(">II", fh.read(8))
        fh.read(1)  # bit depth
        color_type = fh.read(1)[0]
    name, has_alpha = PNG_COLOR_TYPES.get(color_type, (f"colour-type-{color_type}", True))
    return width, height, name, has_alpha


def require_pillow() -> None:
    if Image is None:
        sys.exit(
            "Pillow is required to regenerate images (verification does not need it):\n"
            "  python3 -m venv .venv && .venv/bin/pip install pillow\n"
            "then run this script with .venv/bin/python"
        )

REPO = Path(__file__).resolve().parent.parent
VIDEO_OUT = REPO / "collectai-admin" / "video" / "out"
# Native Android renders (Play-* compositions, 1440x2560, Android device chrome).
PLAY_MASTERS = VIDEO_OUT / "play-screenshots"
# iOS masters (1320x2868, iPhone chrome) — only used if the Play renders are absent.
MASTERS = VIDEO_OUT / "screenshots"
PLAY_IMAGES = REPO / "android" / "fastlane" / "metadata" / "android" / "en-US" / "images"
PHONE_DIR = PLAY_IMAGES / "phoneScreenshots"
ICON = PLAY_IMAGES / "icon" / "icon.png"

# Play's hard limits for screenshots.
MIN_SIDE = 320
MAX_SIDE = 3840
MAX_RATIO = 2.0

# Play's "high-visibility recommendation" for portrait phone screenshots.
TARGET_RATIO = 9 / 16


def pad_to_ratio(im: Image.Image, ratio: float = TARGET_RATIO) -> Image.Image:
    """Widen `im` to width/height == ratio by extending each row's edge pixels.

    Only ever widens; a screenshot already at or wider than the target ratio is
    returned unchanged so this stays idempotent.
    """
    src = im.convert("RGB")
    w, h = src.size
    target_w = round(h * ratio)
    if target_w <= w:
        return src

    pad_left = (target_w - w) // 2
    out = Image.new("RGB", (target_w, h))
    out.paste(src, (pad_left, 0))

    # Extend each row outward with its own leftmost / rightmost pixel so the
    # background gradient continues instead of hitting a flat block of colour.
    left_col = src.crop((0, 0, 1, h))
    right_col = src.crop((w - 1, 0, w, h))
    if pad_left:
        out.paste(left_col.resize((pad_left, h), Image.NEAREST), (0, 0))
    pad_right = target_w - w - pad_left
    if pad_right:
        out.paste(right_col.resize((pad_right, h), Image.NEAREST), (pad_left + w, 0))
    return out


def regenerate() -> list[str]:
    """Rebuild the Play screenshots from the masters. Returns a change log."""
    changes: list[str] = []

    # Prefer the native Android renders. Falling back to the iOS masters keeps
    # this working without a Remotion render, but those show an iPhone frame —
    # Play discourages competitor hardware in listings, so it is a stopgap.
    play_masters = sorted(PLAY_MASTERS.glob("*.png"))
    if play_masters:
        masters = play_masters
    else:
        masters = sorted(MASTERS.glob("Screenshot-*.png"))
        if not masters:
            sys.exit(
                f"No screenshots found in {PLAY_MASTERS} or {MASTERS}.\n"
                "Render them with: cd collectai-admin/video && "
                "bash scripts/render-screenshots.sh --play"
            )
        print(
            "  WARNING: no Android renders in collectai-admin/video/out/play-screenshots;\n"
            "           falling back to the iPhone-framed iOS masters.\n"
            "           Render the Play-* compositions before publishing the listing."
        )

    PHONE_DIR.mkdir(parents=True, exist_ok=True)
    for master in masters:
        # "Screenshot-3-ItemDetail.png" -> "3.png"; the Play renders are "3.png".
        stem = master.stem
        index = stem.split("-")[1] if stem.startswith("Screenshot-") else stem
        dest = PHONE_DIR / f"{index}.png"
        with Image.open(master) as im:
            out = pad_to_ratio(im)
            out.save(dest, "PNG")
        changes.append(f"{master.name} -> {dest.relative_to(REPO)} {out.size} RGB")

    # The app icon is the one asset Play wants as a 32-bit PNG.
    if ICON.exists():
        with Image.open(ICON) as im:
            if im.mode != "RGBA":
                im.convert("RGBA").save(ICON, "PNG")
                changes.append(f"{ICON.relative_to(REPO)} -> RGBA (32-bit)")
    return changes


def verify() -> list[str]:
    """Check every Play image against the documented limits. Returns problems."""
    problems: list[str] = []

    shots = sorted(PHONE_DIR.glob("*.png"))
    if len(shots) < 2:
        problems.append(f"{PHONE_DIR.relative_to(REPO)}: Play requires at least 2 screenshots, found {len(shots)}")

    for p in shots:
        rel = p.relative_to(REPO)
        w, h, mode, has_alpha = read_png_header(p)
        if has_alpha:
            problems.append(f"{rel}: mode {mode} — Play requires 24-bit PNG with no alpha")
        lo, hi = min(w, h), max(w, h)
        if lo < MIN_SIDE or hi > MAX_SIDE:
            problems.append(f"{rel}: {w}x{h} — each side must be {MIN_SIDE}..{MAX_SIDE}px")
        if hi > lo * MAX_RATIO:
            problems.append(
                f"{rel}: {w}x{h} (ratio {hi / lo:.3f}) — longest side may not exceed {MAX_RATIO}x the shortest"
            )
        if p.stat().st_size > 8 * 1024 * 1024:
            problems.append(f"{rel}: over Play's 8MB per-screenshot limit")

    feature = PLAY_IMAGES / "featureGraphic" / "featureGraphic.png"
    if not feature.exists():
        problems.append("featureGraphic/featureGraphic.png is missing — Play requires it")
    else:
        w, h, mode, has_alpha = read_png_header(feature)
        if (w, h) != (1024, 500):
            problems.append(f"featureGraphic.png: {w}x{h} — Play requires exactly 1024x500")
        if has_alpha:
            problems.append(f"featureGraphic.png: mode {mode} — must be 24-bit PNG with no alpha")

    if not ICON.exists():
        problems.append("icon/icon.png is missing — Play requires a 512x512 icon")
    else:
        w, h, mode, has_alpha = read_png_header(ICON)
        if (w, h) != (512, 512):
            problems.append(f"icon.png: {w}x{h} — Play requires exactly 512x512")
        if not has_alpha:
            problems.append(f"icon.png: mode {mode} — Play requires a 32-bit PNG (with alpha)")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true", help="verify only, do not write")
    args = ap.parse_args()

    if not args.verify:
        require_pillow()
        for line in regenerate():
            print(f"  regenerated {line}")

    problems = verify()
    if problems:
        print("\nPlay asset problems:")
        for p in problems:
            print(f"  FAIL {p}")
        return 1
    print("\nAll Play listing images satisfy the Play Console limits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
