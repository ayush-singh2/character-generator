"""v3 text compositor — place page text in the genuinely empty region.

A vision model looks at the finished art and returns the calmest, emptiest
rectangle (sky / wall / floor / plain background) that avoids characters and busy
detail — fixing the earlier overlap where text was dropped onto a subject. Text is
drawn there with a soft white bloom (no card, no border/seam). Output ->
v3/output/pages/page_<pg>.png.
"""

import io
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import plan_v3
from .llm import chat_json_image

from .plan_v3 import DATA, ART, PAGES as OUT  # noqa: F401
SERIF_B = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"

PLACE_SYSTEM = """\
You place a caption on a children's book illustration. Return the largest CALM, \
EMPTY rectangle (open sky, wall, floor, plain background) that avoids faces, \
characters and busy detail, where a few lines of text will read clearly.
Reply ONLY JSON: {"box":[x0,y0,x1,y1],"dark_text":true|false}
Coordinates normalised 0..1 (origin top-left). "dark_text" true if the area is \
light (use dark ink), false if dark (use light ink). Prefer the %s side/edge if it \
is empty enough."""


def _small(img_bytes, maxpx=896):
    """Downscale for vision calls — smaller payload, faster, fewer empty replies."""
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    if max(im.size) > maxpx:
        s = maxpx / max(im.size)
        im = im.resize((int(im.width * s), int(im.height * s)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def _find_zone(img_bytes, prefer):
    try:
        r = chat_json_image(PLACE_SYSTEM % (prefer or "top"),
                            "Find the caption area.", _small(img_bytes), mime="image/jpeg")
        box = r.get("box")
        if isinstance(box, list) and len(box) == 4 and box[2] > box[0] and box[3] > box[1]:
            return box, bool(r.get("dark_text", True))
    except Exception as e:
        print(f"     (vision place failed: {str(e)[:60]})")
    return None, True


def _busy(im, box, thresh=34.0):
    """True if the text region has high detail/contrast (needs a scrim)."""
    W, H = im.size
    region = im.crop((int(box[0] * W), int(box[1] * H),
                      int(box[2] * W), int(box[3] * H))).convert("L")
    edges = region.filter(ImageFilter.FIND_EDGES)
    px = list(edges.getdata())
    if not px:
        return False
    return (sum(px) / len(px)) > thresh


def _fit(draw, text, bw, bh, hi, lo):
    f, lines, lh = None, [text], hi
    for size in range(hi, lo, -2):
        f = ImageFont.truetype(SERIF_B, size)
        words, lines, cur = text.split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if draw.textlength(t, font=f) <= bw:
                cur = t
            else:
                lines.append(cur); cur = w
        if cur:
            lines.append(cur)
        lh = size * 1.3
        if lh * len(lines) <= bh and all(draw.textlength(l, font=f) <= bw for l in lines):
            return f, lines, lh
    return f, lines, lh


def compose(only=None, data_dir=DATA):
    os.makedirs(OUT, exist_ok=True)
    plan = plan_v3.load(data_dir)
    for sc in plan["scenes"]:
        pg = plan_v3.page_id(sc)
        if only and pg not in only:
            continue
        text = plan_v3.scene_text(sc)
        art = f"{ART}/page_{plan_v3.slug(pg)}.png"
        if not os.path.exists(art):
            continue
        im = Image.open(art).convert("RGB")
        W, H = im.size
        if not text.strip():
            im.save(f"{OUT}/page_{plan_v3.slug(pg)}.png"); print(f"  [{pg}] (no text)"); continue

        box, dark_text = _find_zone(open(art, "rb").read(), sc.get("text_area"))
        if not box:
            box = [0.06, 0.04, 0.94, 0.24]
        x0, y0, x1, y1 = box[0] * W, box[1] * H, box[2] * W, box[3] * H
        pad = 0.025 * W
        bw, bh = (x1 - x0 - 2 * pad), (y1 - y0 - 2 * pad)
        draw = ImageDraw.Draw(im)
        f, lines, lh = _fit(draw, text, bw, bh, int(H * 0.05), int(H * 0.02))
        ink = (38, 32, 28) if dark_text else (250, 248, 244)
        glow = (255, 255, 255) if dark_text else (25, 22, 20)

        # If the text area is busy/detailed, lay a soft feathered scrim behind the
        # text block so it separates cleanly (no hard card, just a gentle wash).
        block_h = lh * len(lines)
        by0 = y0 + pad + max(0, (bh - block_h) / 2)
        out = im.convert("RGBA")
        if _busy(im, box):
            scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            sd = ImageDraw.Draw(scrim)
            m = 0.02 * W
            sd.rounded_rectangle([x0 - m, by0 - m, x1 + m, by0 + block_h + m],
                                 radius=int(0.03 * W),
                                 fill=(glow + (150,)))
            scrim = scrim.filter(ImageFilter.GaussianBlur(int(0.02 * W)))
            out = Image.alpha_composite(out, scrim)

        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ty = by0
        for i, l in enumerate(lines):
            lw = ld.textlength(l, font=f)
            ld.text((x0 + pad + (bw - lw) / 2, ty + i * lh), l, font=f, fill=ink + (255,))
        alpha = layer.split()[3]
        halo = alpha.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(8))
        halo = halo.point(lambda v: int(v * 0.92))
        halo_layer = Image.new("RGBA", (W, H), glow + (0,))
        halo_layer.putalpha(halo)
        out = Image.alpha_composite(out, halo_layer)
        out = Image.alpha_composite(out, layer).convert("RGB")
        out.save(f"{OUT}/page_{plan_v3.slug(pg)}.png")
        print(f"  [{pg}] text placed @ {[round(b,2) for b in box]} ({len(lines)} lines)")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    compose(only=only)
