"""Generate the brand images in custom_components/smartsolar/brand/.

Home Assistant 2026.3+ shows icon.png / logo.png (plus dark_ and @2x variants)
from an integration's brand/ folder. Requires Pillow.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "custom_components" / "smartsolar" / "brand"
SS = 4  # supersampling factor for smooth edges

SUN = (255, 179, 0)
PANEL = (21, 101, 192)
PANEL_EDGE = (13, 71, 161)
GRID = (144, 202, 249)
TEXT_LIGHT = (33, 33, 33)
TEXT_DARK = (240, 240, 240)
FONTS = ("C:/Windows/Fonts/segoeuib.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf")


def draw_icon(size: int) -> Image.Image:
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Sun with rays, upper right
    cx, cy, r = s * 0.68, s * 0.30, s * 0.15
    for i in range(10):
        a = i * math.tau / 10
        inner, outer, half = r * 1.30, r * 1.75, 0.13
        d.polygon(
            [
                (cx + inner * math.cos(a - half), cy + inner * math.sin(a - half)),
                (cx + outer * math.cos(a), cy + outer * math.sin(a)),
                (cx + inner * math.cos(a + half), cy + inner * math.sin(a + half)),
            ],
            fill=SUN,
        )
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=SUN)

    # Solar panel in perspective, lower left
    tl, tr = (s * 0.20, s * 0.50), (s * 0.74, s * 0.50)
    br, bl = (s * 0.94, s * 0.92), (s * 0.06, s * 0.92)
    d.polygon([tl, tr, br, bl], fill=PANEL, outline=PANEL_EDGE, width=int(s * 0.02))

    def lerp(p, q, t):
        return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)

    w = int(s * 0.012)
    for t in (0.25, 0.5, 0.75):  # columns
        d.line([lerp(tl, tr, t), lerp(bl, br, t)], fill=GRID, width=w)
    for t in (1 / 3, 2 / 3):  # rows
        d.line([lerp(tl, bl, t), lerp(tr, br, t)], fill=GRID, width=w)

    return img.resize((size, size), Image.LANCZOS)


def load_font(px: int) -> ImageFont.FreeTypeFont:
    for name in FONTS:
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default(px)


def draw_logo(height: int, text_color: tuple[int, int, int]) -> Image.Image:
    icon = draw_icon(height)
    font = load_font(int(height * 0.42))
    left, top, right, bottom = font.getbbox("SmartSolar")
    gap = int(height * 0.08)
    width = height + gap + (right - left) + int(height * 0.05)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    img.alpha_composite(icon, (0, 0))
    y = (height - (bottom - top)) // 2 - top
    ImageDraw.Draw(img).text((height + gap - left, y), "SmartSolar", font=font, fill=text_color)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix, scale in (("", 1), ("@2x", 2)):
        draw_icon(256 * scale).save(OUT / f"icon{suffix}.png", optimize=True)
        draw_logo(128 * scale, TEXT_LIGHT).save(OUT / f"logo{suffix}.png", optimize=True)
        draw_logo(128 * scale, TEXT_DARK).save(OUT / f"dark_logo{suffix}.png", optimize=True)
    for f in sorted(OUT.iterdir()):
        with Image.open(f) as im:
            print(f"{f.name:20} {im.size}")


if __name__ == "__main__":
    main()
