#!/usr/bin/env python3
"""The Android 12+ splash icon must survive the system's circular mask.

WHY (2026-09-09): launching the app on Android showed the bird with its head
sliced off and the "Sparrow Collect" wordmark gone entirely, while the
generated drawable inside the APK contains both. Nothing caught it — the asset
is a valid PNG, the plugin config is valid, and a splash does render.

MECHANISM, read out of the installed plugin rather than assumed:

  @expo/prebuild-config .../expo-splash-screen/withAndroidSplashImages.js
      const size = imageWidth * multiplier;
      const canvasSize = 288 * multiplier;      # the Android 12 icon canvas
      ... the image is `contain`-fitted to size and centred on canvasSize

  The generated theme (verified in the APK with `aapt2 dump resources`) sets
  `windowSplashScreenAnimatedIcon` with NO icon background, so the platform
  shows only the inner 192dp of that 288dp canvas, MASKED TO A CIRCLE
  (Android splash-screen spec: 288dp canvas, art must fit a 192dp circle; with
  an icon background it is 240dp/160dp instead).

So the guarantee is a CIRCLE of radius 96dp about the canvas centre — not a
box. A rectangle that fits 192dp wide still loses its corners, which is exactly
how a full-bleed square logo loses its wordmark and its beak.

Artwork bounds are found by COLOUR, not alpha: the splash art is opaque over an
off-white field, so an alpha bbox is the whole canvas and tells you nothing.
Same trap as scripts/check_adaptive_icon.py, same reason.

Stdlib only (the PNG decoder is imported from check_adaptive_icon.py) — PIL is
not installed on the interpreter CI and preflight use.

    python3 scripts/check_splash_mask.py        # exit 0 ok, 1 clipped
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_adaptive_icon import load_rgba  # noqa: E402  (stdlib PNG decoder)

ROOT = Path(__file__).resolve().parent.parent

# Android splash-screen spec, no icon background: a 288dp canvas of which only
# a centred 192dp circle is guaranteed visible.
CANVAS_DP = 288
VISIBLE_DIAMETER_DP = 192
# Colour distance at which a pixel counts as artwork rather than background.
TOLERANCE = 26


def android_splash_config(cfg: dict):
    """The config the Android half of expo-splash-screen actually receives.

    Mirrors node_modules/expo-splash-screen/plugin/build/withSplashScreen.js:
    the top-level props with the `android` sub-object merged over them.
    """
    for plugin in cfg.get("plugins", []):
        if isinstance(plugin, list) and plugin[0] == "expo-splash-screen":
            props = plugin[1] if len(plugin) > 1 else {}
            merged = {k: v for k, v in props.items() if k not in ("ios", "android")}
            merged.update(props.get("android") or {})
            return merged
        if plugin == "expo-splash-screen":
            return {}
    return None


def artwork_max_radius(w: int, h: int, rows):
    """Furthest artwork pixel from the image centre, plus the artwork bbox."""
    bg = rows[0][0]

    def differs(p):
        return any(abs(p[i] - bg[i]) > TOLERANCE for i in range(4))

    cx, cy = (w - 1) / 2, (h - 1) / 2
    best = -1.0
    l, t, r, b = w, h, -1, -1
    for y in range(h):
        row = rows[y]
        for x in range(w):
            if differs(row[x]):
                d = math.hypot(x - cx, y - cy)
                if d > best:
                    best = d
                l, t = min(l, x), min(t, y)
                r, b = max(r, x), max(b, y)
    if best < 0:
        return None
    return best, l, t, r, b


def main() -> int:
    cfg = json.loads((ROOT / "app.json").read_text())["expo"]
    splash = android_splash_config(cfg)
    if splash is None:
        print("SKIP  expo-splash-screen is not configured")
        return 0
    rel = splash.get("image")
    if not rel:
        print("SKIP  no splash image configured for Android")
        return 0
    image_width = splash.get("imageWidth", 100)
    path = (ROOT / rel.lstrip("./")).resolve()
    if not path.exists():
        print(f"FAIL  splash image missing: {rel}")
        return 1

    w, h, rows = load_rgba(path)
    found = artwork_max_radius(w, h, rows)
    if found is None:
        print(f"FAIL  {rel}: no artwork found — the image is a flat colour")
        return 1
    radius_px, l, t, r, b = found

    # The plugin `contain`-fits the image into an imageWidth x imageWidth box,
    # so one source pixel is imageWidth / max(w, h) dp.
    dp_per_px = image_width / max(w, h)
    radius_dp = radius_px * dp_per_px
    limit_dp = VISIBLE_DIAMETER_DP / 2

    print(f"      {rel}: {w}x{h}, artwork ({l},{t})-({r},{b}), imageWidth={image_width}dp")
    print(f"      furthest artwork pixel: {radius_dp:.1f}dp from centre "
          f"(mask radius {limit_dp:.0f}dp of a {CANVAS_DP}dp canvas)")
    if radius_dp <= limit_dp:
        print("PASS  splash artwork fits inside the Android 12 circular mask")
        return 0

    max_width = int(limit_dp * max(w, h) / radius_px)
    print(f"FAIL  splash artwork overflows the mask by {radius_dp - limit_dp:.1f}dp — "
          "it is CLIPPED on every Android 12+ device.")
    print(f"      Either set android.imageWidth <= {max_width} for this asset, or "
          "use an asset whose art sits nearer the centre.")
    print("      The mask is a CIRCLE, so corners go first: a wordmark under a "
          "logo is the first thing to disappear.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
