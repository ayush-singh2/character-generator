"""Stage 6 — assemble the illustrated picture book (v3 layout).

Design goals (from the illustration guide + reference book):
  * Image and text NEVER overlap. Text flows in the cream page area and wraps
    AROUND the illustration, like spot illustrations in the guide.
  * Layout VARIES page to page (wide bands, corner spots, centred vignettes) —
    no monotonous fixed bottom text box.
  * Illustrations are soft rounded panels (or feathered vignettes) on a warm
    cream page, not full-bleed.
  * Clean thought/dream bubbles whose tail actually points at the character.
  * A designed cover with a title banner — not a plain page.

Run:  python -m pipeline.book
In:   data/pages.json, data/scenes.json, data/characters.json, data/refs.json
Out:  output/book/<title>.pdf  +  output/book/page_NN.png
"""

import json
import os
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont

Image.init()

PAGES = "data/pages.json"
SCENES = "data/scenes.json"
CHARACTERS = "data/characters.json"
REFS = "data/refs.json"
STYLE = "data/style.json"
BOOK_DIR = "output/book"

PAGE_W, PAGE_H = 1080, 1440
M = 70                       # page margin
GUT = 34                     # gutter between image and text
INK = (54, 44, 38)
CREAM = (250, 245, 235)
ACCENT = (193, 104, 47)      # warm terracotta (overridden by style palette)
ACCENT2 = (30, 112, 110)     # deep teal

SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SERIF_B = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SERIF_I = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"
SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

_EMPH = re.compile(r"(\*\*.+?\*\*|\*.+?\*)")
_FONT_CACHE = {}


def font(path, size):
    key = (path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]


def _sizes(path):
    return {s: font(path, s) for s in range(14, 40)}


def _palette_accents():
    """Pull two accent colours from the style palette if they are hex."""
    global ACCENT, ACCENT2
    try:
        pal = json.load(open(STYLE)).get("palette", [])
        hexes = [c for c in pal if isinstance(c, str) and re.fullmatch(r"#?[0-9a-fA-F]{6}", c.strip())]
        if hexes:
            ACCENT = _hex(hexes[0])
            if len(hexes) > 1:
                ACCENT2 = _hex(hexes[1])
    except FileNotFoundError:
        pass


def _hex(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


# --------------------------- styled text ---------------------------

def _tokens(text):
    out = []
    for chunk in _EMPH.split(text):
        if not chunk:
            continue
        if chunk.startswith("**") and chunk.endswith("**"):
            style, body = "b", chunk[2:-2]
        elif chunk.startswith("*") and chunk.endswith("*"):
            style, body = "i", chunk[1:-1]
        else:
            style, body = "", chunk
        for w in body.split():
            out.append((w, style))
    return out


def _font_for(style, size, fonts):
    return fonts["b" if style == "b" else "i" if style == "i" else ""][size]


def _segments(x0, x1, ya, yb, img_rect, pad):
    """Horizontal text segments in [x0,x1] at vertical band [ya,yb], avoiding
    the image rectangle. Returns list of (sx0, sx1)."""
    if img_rect:
        ix0, iy0, ix1, iy1 = img_rect
        if not (yb < iy0 - pad or ya > iy1 + pad):     # band overlaps image
            segs = []
            if (ix0 - pad) - x0 > 150:                 # room on the left
                segs.append((x0, ix0 - pad))
            if x1 - (ix1 + pad) > 150:                 # room on the right
                segs.append((ix1 + pad, x1))
            return segs
    return [(x0, x1)]


def _flow(draw, text, region, img_rect, fonts, size, draw_it=True):
    """Flow styled text in `region`, wrapping around `img_rect`. Returns True
    if all text fits."""
    x0, y0, x1, y1 = region
    tokens = _tokens(text)
    space = draw.textlength(" ", font=fonts[""][size])
    lh = int(size * 1.5)
    pad = 26
    y, i, n = y0, 0, len(tokens)
    while i < n and y + lh <= y1:
        segs = _segments(x0, x1, y, y + lh, img_rect, pad)
        if not segs:
            y = (img_rect[3] + pad) if img_rect else y + lh   # jump past image
            continue
        sx0, sx1 = max(segs, key=lambda s: s[1] - s[0])
        line, w = [], 0
        while i < n:
            word, st = tokens[i]
            f = _font_for(st, size, fonts)
            ww = draw.textlength(word, font=f)
            add = (space if line else 0) + ww
            if line and w + add > sx1 - sx0:
                break
            line.append((word, st, f))
            w += add
            i += 1
        if draw_it:
            xx = sx0
            for word, _s, f in line:
                draw.text((xx, y), word, font=f, fill=INK)
                xx += draw.textlength(word, font=f) + space
        y += lh
    return i >= n


def _autosize_flow(draw, text, region, img_rect, fonts, hi=30, lo=15):
    for size in range(hi, lo - 1, -1):
        if _flow(draw, text, region, img_rect, fonts, size, draw_it=False):
            return size
    return lo


# --------------------------- image panels ---------------------------

def _rounded(img, radius=34):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0], img.size[1]], radius=radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def _vignette(img):
    """Feather the image edges into transparency for a soft spot look."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse([int(-w * 0.06), int(-h * 0.06), int(w * 1.06), int(h * 1.06)], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h) * 0.07))
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def _fit(img, w, h):
    """Cover-fit crop image to (w,h)."""
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    img = img.resize((int(iw * scale), int(ih * scale)))
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))


def _place(canvas, img_path, rect, vignette=False):
    ix0, iy0, ix1, iy1 = rect
    w, h = ix1 - ix0, iy1 - iy0
    img = _fit(Image.open(img_path).convert("RGB"), w, h)
    if vignette:
        panel = _vignette(img)
        canvas.alpha_composite(panel, (ix0, iy0))
    else:
        # soft drop shadow + rounded panel
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle([ix0 + 8, iy0 + 12, ix1 + 8, iy1 + 12], radius=34, fill=(60, 40, 30, 90))
        canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(12)))
        panel = _rounded(img, 34)
        canvas.alpha_composite(panel, (ix0, iy0))
        ImageDraw.Draw(canvas).rounded_rectangle([ix0, iy0, ix1, iy1], radius=34,
                                                 outline=(255, 255, 255, 230), width=5)


# --------------------------- layouts ---------------------------

def _layout(page_no, chapter_start, has_bubble):
    """Pick an image rectangle + vignette flag, varied per page."""
    cw0, cw1 = M, PAGE_W - M
    ch0, ch1 = M, PAGE_H - M
    sq = int((cw1 - cw0) * 0.50)      # spot square size
    band_h = int((ch1 - ch0) * 0.46)  # band height

    if chapter_start:
        return ("band_top", (cw0, ch0 + 90, cw1, ch0 + 90 + band_h), False)

    options = [
        ("band_top",    (cw0, ch0, cw1, ch0 + band_h), False),
        ("band_bottom", (cw0, ch1 - band_h, cw1, ch1), False),
        ("spot_tr",     (cw1 - sq, ch0, cw1, ch0 + sq), True),
        ("spot_tl",     (cw0, ch0, cw0 + sq, ch0 + sq), True),
        ("spot_br",     (cw1 - sq, ch1 - sq, cw1, ch1), True),
        ("spot_bl",     (cw0, ch1 - sq, cw0 + sq, ch1), True),
        ("center",      (cw0 + int((cw1 - cw0 - int(sq * 1.2)) / 2), ch0 + 60,
                         cw0 + int((cw1 - cw0 - int(sq * 1.2)) / 2) + int(sq * 1.2),
                         ch0 + 60 + int(sq * 1.2)), True),
    ]
    name, rect, vig = options[page_no % len(options)]
    return name, rect, vig


# --------------------------- bubbles ---------------------------

def _draw_bubble(canvas, bubble, img_rect, fonts):
    """Clean elliptical thought/dream bubble near the image, tail pointing in."""
    ix0, iy0, ix1, iy1 = img_rect
    img_cx, img_cy = (ix0 + ix1) // 2, (iy0 + iy1) // 2
    bw, bh = 360, 190
    # Place bubble in the largest free margin beside the image.
    space_right = PAGE_W - M - ix1
    space_left = ix0 - M
    space_top = iy0 - M
    if space_top >= bh + 40:
        bx, by = max(M, min(img_cx - bw // 2, PAGE_W - M - bw)), iy0 - bh - 30
    elif space_right >= bw + 20:
        bx, by = ix1 + 16, max(M, iy0)
    elif space_left >= bw + 20:
        bx, by = ix0 - bw - 16, max(M, iy0)
    else:
        bx, by = max(M, min(img_cx - bw // 2, PAGE_W - M - bw)), M
    bcx, bcy = bx + bw // 2, by + bh // 2

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    white = (255, 255, 255, 244)
    outline = (150, 120, 100, 255)
    # Tail: three shrinking dots from bubble toward the character.
    for k, r in enumerate([20, 13, 8]):
        t = 0.30 + k * 0.22
        px = int(bcx + (img_cx - bcx) * t)
        py = int(bcy + (img_cy - bcy) * t)
        ld.ellipse([px - r, py - r, px + r, py + r], fill=white, outline=outline, width=3)
    # Body: smooth ellipse (clean, not scalloped).
    ld.ellipse([bx, by, bx + bw, by + bh], fill=white, outline=outline, width=4)
    canvas.alpha_composite(layer)

    d = ImageDraw.Draw(canvas)
    fpath = SERIF_I if bubble.get("type") == "dream" else SERIF
    f = {"": _sizes(fpath), "b": _sizes(SERIF_B), "i": _sizes(SERIF_I)}
    inner = (bx + 34, by + 26, bx + bw - 34, by + bh - 26)
    size = _autosize_flow(d, bubble.get("text", ""), inner, None, f, hi=27, lo=14)
    # Centre the bubble text block vertically.
    _flow(d, bubble.get("text", ""), inner, None, f, size, draw_it=True)


# --------------------------- page render ---------------------------

def render_page(beat, scene, fonts):
    canvas = Image.new("RGBA", (PAGE_W, PAGE_H), CREAM + (255,))
    d = ImageDraw.Draw(canvas)
    has_bubble = bool(scene and scene.get("bubble"))
    name, rect, vig = _layout(beat["page_no"], beat.get("chapter_start"), has_bubble)

    region = [M, M, PAGE_W - M, PAGE_H - M]

    # Chapter/story title on the first page of a story.
    if beat.get("chapter_start") and beat.get("chapter_title"):
        tf = font(SANS_B, 46)
        d.text((PAGE_W // 2, M), beat["chapter_title"], font=tf, fill=ACCENT2, anchor="ma")

    if scene and scene.get("image") and os.path.exists(scene["image"]):
        _place(canvas, scene["image"], rect, vignette=vig)
        img_rect = rect
    else:
        img_rect = None

    d = ImageDraw.Draw(canvas)
    if has_bubble and img_rect:
        _draw_bubble(canvas, scene["bubble"], img_rect, fonts)
        d = ImageDraw.Draw(canvas)

    size = _autosize_flow(d, beat["text"], region, img_rect, fonts)
    _flow(d, beat["text"], region, img_rect, fonts, size, draw_it=True)

    _page_number(d, beat["page_no"])
    return canvas.convert("RGB")


def _page_number(d, n):
    r, cx, cy = 24, PAGE_W - M - 24, PAGE_H - M + 6
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ACCENT)
    d.text((cx, cy), str(n), font=font(SANS_B, 22), fill=CREAM, anchor="mm")


# --------------------------- cover / front matter ---------------------------

def cover_page(doc, refs):
    art = os.path.join(BOOK_DIR, "cover_art.png")
    src = art if os.path.exists(art) else (next(iter(refs.values()))["full_body"] if refs else None)
    canvas = Image.new("RGBA", (PAGE_W, PAGE_H), ACCENT2 + (255,))
    if src and os.path.exists(src):
        canvas.alpha_composite(_fit(Image.open(src).convert("RGB"), PAGE_W, PAGE_H).convert("RGBA"))
    d = ImageDraw.Draw(canvas)

    # Decorative inner frame.
    d.rounded_rectangle([28, 28, PAGE_W - 28, PAGE_H - 28], radius=24, outline=(255, 248, 235, 235), width=6)

    # Title banner near the top.
    title = doc.get("title", "Untitled")
    tf = font(SERIF_B, 78)
    tw = d.textlength(title, font=tf)
    if tw > PAGE_W - 200:
        tf = font(SERIF_B, 60)
        tw = d.textlength(title, font=tf)
    bx0, bx1, by0 = (PAGE_W - tw) // 2 - 46, (PAGE_W + tw) // 2 + 46, 120
    banner = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(banner).rounded_rectangle([bx0, by0, bx1, by0 + 150], radius=30,
                                             fill=ACCENT + (235,), outline=(255, 248, 235, 240), width=5)
    canvas.alpha_composite(banner)
    d = ImageDraw.Draw(canvas)
    d.text((PAGE_W // 2, by0 + 75), title, font=tf, fill=(255, 250, 240), anchor="mm")

    # Author plate near the bottom.
    af = font(SANS_B, 40)
    aw = d.textlength(doc.get("author", ""), font=af)
    ay = PAGE_H - 190
    plate = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle([(PAGE_W - aw) // 2 - 34, ay, (PAGE_W + aw) // 2 + 34, ay + 70],
                                            radius=20, fill=ACCENT2 + (220,))
    canvas.alpha_composite(plate)
    ImageDraw.Draw(canvas).text((PAGE_W // 2, ay + 35), doc.get("author", ""),
                                font=af, fill=(255, 250, 240), anchor="mm")
    return canvas.convert("RGB")


def title_page(doc):
    canvas = Image.new("RGB", (PAGE_W, PAGE_H), CREAM)
    d = ImageDraw.Draw(canvas)
    d.text((PAGE_W // 2, 520), doc.get("title", ""), font=font(SERIF_B, 60), fill=INK, anchor="ma")
    d.line([(PAGE_W // 2 - 120, 640), (PAGE_W // 2 + 120, 640)], fill=ACCENT, width=3)
    d.text((PAGE_W // 2, 680), doc.get("author", ""), font=font(SERIF, 34), fill=ACCENT2, anchor="ma")
    return canvas


# --------------------------- build ---------------------------

def build(limit=None, page_range=None):
    _palette_accents()
    doc = json.load(open(PAGES if os.path.exists(PAGES) else "data/manuscript.json"))
    scenes = json.load(open(SCENES)) if os.path.exists(SCENES) else {}
    refs = json.load(open(REFS)) if os.path.exists(REFS) else {}
    os.makedirs(BOOK_DIR, exist_ok=True)
    fonts = {"": _sizes(SERIF), "b": _sizes(SERIF_B), "i": _sizes(SERIF_I)}

    imgs = [cover_page(doc, refs), title_page(doc)]
    beats = doc["pages"][:limit] if limit else doc["pages"]
    if page_range is not None:
        beats = [b for b in beats if b["page_no"] in page_range]
    for beat in beats:
        if not beat["text"].strip():
            continue
        scene = scenes.get(str(beat["page_no"]))
        page = render_page(beat, scene, fonts)
        page.save(os.path.join(BOOK_DIR, f"page_{beat['page_no']:02d}.png"))
        imgs.append(page)

    safe = (doc.get("title") or "book").replace(" ", "_").replace("'", "")
    pdf = os.path.join(BOOK_DIR, f"{safe}.pdf")
    imgs[0].save(pdf, save_all=True, append_images=imgs[1:])
    return pdf


def main():
    print("Book assembled ->", build())


if __name__ == "__main__":
    main()
