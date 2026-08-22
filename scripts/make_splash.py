#!/usr/bin/env python3
"""Generate assets/splash.png — the icon art plus the "Sparrow Collect" wordmark.

WHY A SCRIPT AND NOT A ONE-OFF EXPORT

The native splash (expo-splash-screen) can only show an IMAGE. There is no way
to render text through config, so the wordmark has to be baked into the asset —
and an asset nobody can regenerate is one nobody can adjust. This keeps the
inputs explicit: the real icon, the real app font, and the measured background.

FACTS THIS SCRIPT RELIES ON, ALL MEASURED RATHER THAN ASSUMED
  - assets/icon.png is 1024x1024 with an OPAQUE background sampled at
    (249, 249, 244). It is not transparent, so anything drawn behind it shows
    as a rectangle — which is why the canvas uses the icon's own background
    colour and app.json's `backgroundColor` must match it. Getting this wrong
    is what previously framed the logo in a visible cream square.
  - The bird art occupies x[212,816], y[124,900] — about 60% of the canvas.
    `imageWidth` in app.json sizes the WHOLE CANVAS, not the art, which is why
    a value that sounds large still renders a small logo.
  - The font is node_modules/@expo-google-fonts/roboto/900Black — the exact
    file `fonts.black` resolves to, so the splash wordmark and the in-app
    wordmark are the same typeface rather than merely similar.

Usage:
    .venv/bin/python scripts/make_splash.py
Then point app.json's expo-splash-screen `image` at ./assets/splash.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "assets" / "icon.png"
OUT = ROOT / "assets" / "splash.png"
FONT = ROOT / "node_modules" / "@expo-google-fonts" / "roboto" / "900Black" / "Roboto_900Black.ttf"

WORDMARK = "Sparrow Collect"
# The app's own text colour (theme `colors.text`, light palette). Dark on cream
# rather than the brand teal: teal-on-cream is a low-contrast pairing and this
# is the first thing anyone sees.
TEXT_RGB = (15, 23, 42)
# Matches the in-app wordmark, which carries letterSpacing: 2 at 36pt.
TRACKING_RATIO = 2 / 36


def main() -> int:
    if not ICON.exists():
        print(f"missing {ICON}", file=sys.stderr)
        return 1
    if not FONT.exists():
        print(f"missing {FONT} — run npm install", file=sys.stderr)
        return 1

    icon = Image.open(ICON).convert("RGB")
    bg = icon.getpixel((5, 5))  # measured, not hardcoded

    # Crop to the art with a small margin so the wordmark sits close to it
    # rather than to the icon's generous internal padding.
    art = icon.crop((212, 124, 817, 901))

    CANVAS_W = 1024
    ART_W = 560
    art = art.resize((ART_W, round(art.height * ART_W / art.width)), Image.LANCZOS)

    font_size = 118
    font = ImageFont.truetype(str(FONT), font_size)
    tracking = round(font_size * TRACKING_RATIO)

    def text_width(f: ImageFont.FreeTypeFont, track: int) -> int:
        return sum(f.getbbox(ch)[2] - f.getbbox(ch)[0] + track for ch in WORDMARK) - track

    # Shrink until the wordmark fits with a comfortable gutter.
    while text_width(font, tracking) > CANVAS_W - 140 and font_size > 40:
        font_size -= 2
        font = ImageFont.truetype(str(FONT), font_size)
        tracking = round(font_size * TRACKING_RATIO)

    gap = 56
    ascent, descent = font.getmetrics()
    text_h = ascent + descent
    canvas_h = art.height + gap + text_h + 120

    out = Image.new("RGB", (CANVAS_W, canvas_h), bg)
    out.paste(art, ((CANVAS_W - art.width) // 2, 40))

    draw = ImageDraw.Draw(out)
    # Drawn CHARACTER BY CHARACTER: PIL has no letter-spacing, and the in-app
    # wordmark is tracked. Without this the two would read differently.
    x = (CANVAS_W - text_width(font, tracking)) // 2
    y = 40 + art.height + gap
    for ch in WORDMARK:
        draw.text((x, y), ch, font=font, fill=TEXT_RGB)
        b = font.getbbox(ch)
        x += (b[2] - b[0]) + tracking

    out.save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)}  {out.size[0]}x{out.size[1]}  bg={bg}  font_size={font_size}")
    print("Now ensure app.json expo-splash-screen has:")
    print(f'  "image": "./assets/splash.png", "backgroundColor": "#{bg[0]:02X}{bg[1]:02X}{bg[2]:02X}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
