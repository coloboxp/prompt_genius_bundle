#!/usr/bin/env python3
"""Render the DMG backdrop (660×420 PNG) from splash.png.

Output: ``packaging/dmg_background.png`` plus an ``@2x`` retina variant.
The dmgbuild settings file reads the standard-resolution file; Finder
auto-picks the @2x on Retina displays when both are present.

Layout slots match ``dmg_settings.py`` (app at 160,210; Applications at
500,210). The backdrop only paints decoration — no app icons, dmgbuild
overlays those.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    print("FATAL: Pillow required (pip install pillow)", file=sys.stderr)
    sys.exit(2)


ROOT = Path(__file__).resolve().parent.parent
SPLASH = ROOT / "splash.png"
OUT_1X = ROOT / "packaging" / "dmg_background.png"
OUT_2X = ROOT / "packaging" / "dmg_background@2x.png"

WIDTH, HEIGHT = 660, 420


def _load_splash() -> Image.Image | None:
    if not SPLASH.exists():
        return None
    return Image.open(SPLASH).convert("RGBA")


def _render(scale: int) -> Image.Image:
    w, h = WIDTH * scale, HEIGHT * scale
    canvas = Image.new("RGBA", (w, h), (24, 24, 28, 255))

    splash = _load_splash()
    if splash is not None:
        # Cover the canvas with splash, slightly desaturated + darkened.
        sw, sh = splash.size
        ratio = max(w / sw, h / sh)
        new = (int(sw * ratio), int(sh * ratio))
        bg = splash.resize(new, Image.LANCZOS)
        # Center-crop.
        x = (bg.width - w) // 2
        y = (bg.height - h) // 2
        bg = bg.crop((x, y, x + w, y + h))
        # Darken + blur slightly so the foreground text reads.
        bg = bg.filter(ImageFilter.GaussianBlur(radius=2 * scale))
        dark = Image.new("RGBA", bg.size, (0, 0, 0, 130))
        bg = Image.alpha_composite(bg, dark)
        canvas = bg

    draw = ImageDraw.Draw(canvas)

    def _font(size: int) -> ImageFont.ImageFont:
        for path in (
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/SFNSDisplay.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ):
            try:
                return ImageFont.truetype(path, size=size * scale)
            except OSError:
                continue
        return ImageFont.load_default()

    title_font = _font(28)
    sub_font = _font(15)
    hint_font = _font(13)

    draw.text(
        (28 * scale, 28 * scale),
        "🦊 Prompt Genius",
        fill=(255, 255, 255, 255),
        font=title_font,
    )
    draw.text(
        (28 * scale, 64 * scale),
        "Drag the app into Applications to install.",
        fill=(220, 220, 230, 255),
        font=sub_font,
    )

    # Arrow between the two icon slots (160 → 500 on the 1× layout).
    arrow_y = 210 * scale
    start_x = (160 + 80) * scale
    end_x = (500 - 80) * scale
    draw.line(
        [(start_x, arrow_y), (end_x, arrow_y)],
        fill=(255, 255, 255, 180),
        width=4 * scale,
    )
    # Arrowhead.
    head = [
        (end_x, arrow_y),
        (end_x - 14 * scale, arrow_y - 8 * scale),
        (end_x - 14 * scale, arrow_y + 8 * scale),
    ]
    draw.polygon(head, fill=(255, 255, 255, 220))

    # Slot captions (sit just under each icon).
    cap_y = 305 * scale
    draw.text(
        (160 * scale, cap_y), "Prompt Genius",
        fill=(255, 255, 255, 230), font=hint_font, anchor="ma",
    )
    draw.text(
        (500 * scale, cap_y), "Applications",
        fill=(255, 255, 255, 230), font=hint_font, anchor="ma",
    )

    return canvas


def main() -> int:
    OUT_1X.parent.mkdir(parents=True, exist_ok=True)
    _render(1).save(OUT_1X, "PNG")
    _render(2).save(OUT_2X, "PNG")
    print(f"[dmg-bg] wrote {OUT_1X} ({WIDTH}×{HEIGHT})")
    print(f"[dmg-bg] wrote {OUT_2X} ({WIDTH * 2}×{HEIGHT * 2})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
