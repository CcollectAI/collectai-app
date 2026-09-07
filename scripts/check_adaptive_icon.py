#!/usr/bin/env python3
"""The Android adaptive icon's artwork must survive the launcher's mask.

WHY (2026-09-07): the shipped icon had the bird's beak clipped at the top and
the treasure chest clipped at the bottom on the Pixel launcher. Nothing caught
it: the asset is a valid 512x512 PNG, `preflight:android` checked that an
adaptive icon EXISTS, and every automated check passed while the launcher drew
a decapitated bird.

Android composites `foregroundImage` over `backgroundColor` on a 108dp layer,
then shows only the centre 72dp of it and masks that to the launcher's shape.
So content is only guaranteed visible inside the centre **66/108 = 61.1%**.
The old asset's artwork spanned 61-450 of 512 vertically — past the safe zone
at both ends, which is exactly the clipping that was reported.

Artwork bounds are found by colour, not alpha: the foreground is fully opaque
with an off-white field, so an alpha bounding box is the whole canvas and tells
you nothing. That is the trap this check exists to avoid re-walking.

Stdlib only (zlib + struct), same as prepare_play_assets.py — PIL is not
installed on the plain interpreter that CI and preflight use.

    python3 scripts/check_adaptive_icon.py           # exit 0 ok, 1 clipped
"""
from __future__ import annotations

import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Fraction of the layer Android guarantees to show: 66dp of a 108dp canvas.
SAFE_FRACTION = 66 / 108
# Colour distance at which a pixel counts as artwork rather than background.
TOLERANCE = 26


def load_rgba(path: Path):
    """Decode an 8-bit non-interlaced PNG to (w, h, [rows of (r,g,b,a)])."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    pos, idat, ihdr = 8, [], None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if ctype == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif ctype == b"IDAT":
            idat.append(body)
        elif ctype == b"IEND":
            break
        pos += 12 + length
    if ihdr is None:
        raise ValueError(f"{path} has no IHDR")
    w, h, depth, colour, _comp, _filt, interlace = ihdr
    # Fail closed on anything this decoder does not fully understand, rather
    # than guessing at the byte layout and reporting a confident wrong bbox.
    if depth != 8 or colour not in (2, 6) or interlace != 0:
        raise ValueError(
            f"{path}: unsupported PNG (depth={depth} colour={colour} "
            f"interlace={interlace}); expected 8-bit RGB/RGBA, non-interlaced"
        )
    channels = 3 if colour == 2 else 4
    raw = zlib.decompress(b"".join(idat))
    stride = w * channels
    rows, prev, off = [], bytearray(stride), 0
    for _ in range(h):
        ftype = raw[off]; off += 1
        line = bytearray(raw[off : off + stride]); off += stride
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if ftype == 1: line[i] = (line[i] + a) & 0xFF
            elif ftype == 2: line[i] = (line[i] + b) & 0xFF
            elif ftype == 3: line[i] = (line[i] + ((a + b) >> 1)) & 0xFF
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
            elif ftype != 0:
                raise ValueError(f"{path}: bad filter type {ftype}")
        prev = line
        if channels == 3:
            rows.append([(line[i], line[i+1], line[i+2], 255) for i in range(0, stride, 3)])
        else:
            rows.append([(line[i], line[i+1], line[i+2], line[i+3]) for i in range(0, stride, 4)])
    return w, h, rows


def artwork_bbox(w, h, rows):
    """Bounding box of pixels that differ from the corner colour."""
    bg = rows[0][0]
    def differs(p):
        return any(abs(p[i] - bg[i]) > TOLERANCE for i in range(4))
    xs, ys = [], []
    for y in range(h):
        row = rows[y]
        for x in range(w):
            if differs(row[x]):
                xs.append(x); ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def main() -> int:
    cfg = json.loads((ROOT / "app.json").read_text())["expo"]
    rel = (cfg.get("android", {}).get("adaptiveIcon", {}) or {}).get("foregroundImage")
    if not rel:
        print("SKIP  no expo.android.adaptiveIcon.foregroundImage configured")
        return 0
    path = (ROOT / rel.lstrip("./")).resolve()
    if not path.exists():
        print(f"FAIL  adaptive icon missing: {rel}")
        return 1

    w, h, rows = load_rgba(path)
    box = artwork_bbox(w, h, rows)
    if box is None:
        print(f"FAIL  {rel}: no artwork found — the image is a flat colour")
        return 1

    l, t, r, b = box
    inset = round(w * (1 - SAFE_FRACTION) / 2)
    lo, hi = inset, w - inset
    ok = l >= lo and t >= inset and r <= hi and b <= (h - inset)
    print(f"      {rel}: {w}x{h}, artwork ({l},{t})-({r},{b})")
    print(f"      safe zone (centre {SAFE_FRACTION:.1%}): [{lo}..{hi}]")
    if ok:
        print("PASS  adaptive icon artwork fits inside the mask safe zone")
        return 0
    over = []
    if t < inset: over.append(f"top by {inset - t}px")
    if b > h - inset: over.append(f"bottom by {b - (h - inset)}px")
    if l < lo: over.append(f"left by {lo - l}px")
    if r > hi: over.append(f"right by {r - hi}px")
    print("FAIL  adaptive icon artwork overflows the safe zone: " + ", ".join(over))
    print("      The launcher masks the centre 72dp of the 108dp layer to a")
    print("      circle/squircle, so this artwork is CLIPPED on device.")
    print(f"      Fix: scale the artwork to fit within {int(w*SAFE_FRACTION)}px centred.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
