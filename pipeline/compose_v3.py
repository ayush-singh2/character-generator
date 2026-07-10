"""v3 text compositor — place the page text in the reserved calm zone.

No card and no border (the client disliked the hard seam between text and image).
Text sits directly on the art with a soft white bloom behind it for legibility
(the white-blur recipe), auto-sized to the layout's text_zone. Output ->
v3/output/pages/page_<pg>.png.
"""

import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import toon_io

DATA = "v3/data"
ART = "v3/output/art"
OUT = "v3/output/pages"
SERIF_B = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"


def _fit(draw, text, bw, bh, hi, lo):
    for size in range(hi, lo, -2):
        f = ImageFont.truetype(SERIF_B, size)
        words, lines, cur = text.split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if draw.textlength(t, font=f) <= bw:
                cur = t
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        lh = size * 1.32
        if lh * len(lines) <= bh and all(draw.textlength(l, font=f) <= bw for l in lines):
            return f, lines, lh
    return f, lines, lh


def compose(only=None):
    os.makedirs(OUT, exist_ok=True)
    scenes = {s["page"]: s for s in toon_io.load(f"{DATA}/scenes.toon")["scenes"]}
    layouts = {l["page"]: l for l in toon_io.load(f"{DATA}/layout.toon")["layouts"]}
    for pg, s in scenes.items():
        if only and pg not in only:
            continue
        art = f"{ART}/page_{pg}.png"
        if not os.path.exists(art):
            continue
        im = Image.open(art).convert("RGB")
        W, H = im.size
        tz = (layouts.get(pg, {}).get("text_zone")) or [0.06, 0.04, 0.94, 0.24]
        x0, y0, x1, y1 = tz[0] * W, tz[1] * H, tz[2] * W, tz[3] * H
        pad = 0.03 * W
        bw, bh = (x1 - x0 - 2 * pad), (y1 - y0 - 2 * pad)
        draw = ImageDraw.Draw(im)
        f, lines, lh = _fit(draw, s["text"], bw, bh, int(H * 0.05), int(H * 0.022))

        # ink colour from the text-zone luminance
        region = im.crop((int(x0), int(y0), int(x1), int(y1))).resize((16, 16))
        lum = sum(sum(px) / 3 for px in region.getdata()) / 256
        ink = (38, 32, 28) if lum > 140 else (250, 248, 244)
        glow = (255, 255, 255) if lum > 140 else (30, 28, 26)

        text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        td = ImageDraw.Draw(text_layer)
        ty = y0 + pad + max(0, (bh - lh * len(lines)) / 2)
        for i, l in enumerate(lines):
            lw = td.textlength(l, font=f)
            td.text((x0 + pad + (bw - lw) / 2, ty + i * lh), l, font=f, fill=ink + (255,))

        # soft bloom behind text (no card): dilate+blur the text alpha
        alpha = text_layer.split()[3]
        halo = alpha.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(7))
        halo = halo.point(lambda v: int(v * 0.9))
        halo_layer = Image.new("RGBA", (W, H), glow + (0,))
        halo_layer.putalpha(halo)

        out = Image.alpha_composite(im.convert("RGBA"), halo_layer)
        out = Image.alpha_composite(out, text_layer).convert("RGB")
        out.save(f"{OUT}/page_{pg}.png")
        print(f"  [{pg}] text placed ({len(lines)} lines)")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    compose(only=only)
