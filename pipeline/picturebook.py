"""Stage (picture-book) — assemble the illustrated book, djfan.pdf style.

Design language taken from the reference book (Referance_book/djfan.pdf):
  * Landscape pages, ART IS FULL-BLEED edge to edge (no cream borders).
  * Page text sits in a SOFT TRANSLUCENT ROUNDED CARD over a calm part of the
    art — so it is always readable and NEVER painted raw on busy art.
  * The card's POSITION VARIES page to page (left / right / top / bottom /
    centre). The scene art is composed to keep that zone calm.
  * Small page-number circles. Clean title / copyright / dedication pages and a
    readable back-matter column.

This module is render-only and has NO API cost: if a unit has no generated art
yet it draws a labelled placeholder, so the whole layout can be proofed for
free before any Flux spend.

Run:  python -m pipeline.picturebook
In:   data/storybook.json, data/scenes.json (optional), data/refs.json, data/style.json
Out:  output/storybook/<title>.pdf  +  output/storybook/unit_NN.png
"""

import json
import math
import os
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import textplace

Image.init()

STORYBOOK = "data/storybook.json"
SCENES = "data/scenes_split.json"
REFS = "data/refs.json"
STYLE = "data/style.json"
OUT_DIR = "output/storybook"

# Landscape spread, djfan ratio (729:594 ≈ 1.227). 1500x1200 keeps it crisp.
PAGE_W, PAGE_H = 1500, 1200
MARGIN = 64                  # safe inset for cards & page numbers

INK = (38, 34, 46)
CREAM = (250, 245, 236)
CARD = (252, 249, 242)       # text-card fill (drawn translucent)
CARD_ALPHA = 242             # ~95% — readable even if art creeps under the card
ACCENT = (40, 70, 150)       # title/heading colour (overridden by style)
ACCENT2 = (193, 104, 47)

FONT_DIR = "/usr/share/fonts/truetype"
SERIF = f"{FONT_DIR}/dejavu/DejaVuSerif.ttf"
SERIF_B = f"{FONT_DIR}/dejavu/DejaVuSerif-Bold.ttf"
SERIF_I = f"{FONT_DIR}/liberation/LiberationSerif-Italic.ttf"
SANS = f"{FONT_DIR}/dejavu/DejaVuSans.ttf"
SANS_B = f"{FONT_DIR}/dejavu/DejaVuSans-Bold.ttf"

_FONT_CACHE: dict = {}
_EMPH = re.compile(r"(\*\*.+?\*\*|\*.+?\*)")


def font(path, size):
    key = (path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]


def _hex(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def _load_accents():
    global ACCENT, ACCENT2
    try:
        pal = json.load(open(STYLE)).get("palette", [])
        hexes = [c for c in pal if isinstance(c, str)
                 and re.fullmatch(r"#?[0-9a-fA-F]{6}", c.strip())]
        if hexes:
            ACCENT = _hex(hexes[0])
        if len(hexes) > 1:
            ACCENT2 = _hex(hexes[1])
    except (FileNotFoundError, json.JSONDecodeError):
        pass


# --------------------------- styled, wrapped text ---------------------------

def _tokens(text):
    """Split text into (word, style) tokens; '\n' is a hard break token."""
    out = []
    for line in text.split("\n"):
        for chunk in _EMPH.split(line):
            if not chunk:
                continue
            if chunk.startswith("**") and chunk.endswith("**"):
                st, body = "b", chunk[2:-2]
            elif chunk.startswith("*") and chunk.endswith("*"):
                st, body = "i", chunk[1:-1]
            else:
                st, body = "", chunk
            for w in body.split():
                out.append((w, st))
        out.append(("\n", ""))
    if out and out[-1] == ("\n", ""):
        out.pop()
    return out


def _fonts(base):
    return {
        "": lambda s: font(base, s),
        "b": lambda s: font(SERIF_B, s),
        "i": lambda s: font(SERIF_I, s),
    }


def _wrap(draw, tokens, fonts, size, max_w):
    """Lay tokens into lines of (word, font) within max_w. Returns list[list]."""
    space = draw.textlength(" ", font=fonts[""](size))
    lines, line, w = [], [], 0
    for word, st in tokens:
        if word == "\n":
            lines.append(line)
            line, w = [], 0
            continue
        f = fonts[st](size)
        ww = draw.textlength(word, font=f)
        add = (space if line else 0) + ww
        if line and w + add > max_w:
            lines.append(line)
            line, w = [(word, f)], ww
        else:
            line.append((word, f))
            w += add
    if line:
        lines.append(line)
    return lines


def _text_block_size(draw, tokens, fonts, size, max_w):
    lines = _wrap(draw, tokens, fonts, size, max_w)
    lh = int(size * 1.5)
    height = lh * len(lines)
    width = 0
    space = draw.textlength(" ", font=fonts[""](size))
    for ln in lines:
        lw = sum(draw.textlength(w, font=f) for w, f in ln) + space * max(0, len(ln) - 1)
        width = max(width, lw)
    return width, height, lines, lh


def _draw_lines(draw, lines, x, y, lh, fonts, size, align, box_w, fill):
    space = draw.textlength(" ", font=fonts[""](size))
    for ln in lines:
        lw = sum(draw.textlength(w, font=f) for w, f in ln) + space * max(0, len(ln) - 1)
        cx = x + (box_w - lw) / 2 if align == "center" else x
        for word, f in ln:
            draw.text((cx, y), word, font=f, fill=fill)
            cx += draw.textlength(word, font=f) + space
        y += lh


def _fit_text(draw, text, box, fonts, hi, lo, align, fill, base=SERIF):
    """Auto-size styled text to fill `box`, draw it vertically centred."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    toks = _tokens(text)
    for size in range(hi, lo - 1, -1):
        w, h, lines, lh = _text_block_size(draw, toks, fonts, size, bw)
        if h <= bh and w <= bw:
            _draw_lines(draw, lines, x0, y0 + (bh - h) // 2, lh, fonts, size, align, bw, fill)
            return size
    w, h, lines, lh = _text_block_size(draw, toks, fonts, lo, bw)
    _draw_lines(draw, lines, x0, y0, lh, fonts, lo, align, bw, fill)
    return lo


# --------------------------- art placement ---------------------------

def _fit_cover(img, w, h):
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    img = img.resize((max(1, int(iw * scale)), max(1, int(ih * scale))))
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))


def _placeholder(unit, calm_zone):
    """Free stand-in art so layout can be proofed before any Flux spend.
    Renders a soft gradient and marks where characters WOULD sit (opposite the
    calm zone) so we can verify the text card lands on the calm side."""
    w, h = PAGE_W, PAGE_H
    base = Image.new("RGB", (w, h), (210, 224, 232))
    d = ImageDraw.Draw(base)
    for y in range(h):                       # vertical gradient sky→grass
        t = y / h
        r = int(190 + 40 * (1 - t)); g = int(214 - 40 * t); b = int(232 - 90 * t)
        d.line([(0, y), (w, y)], fill=(r, max(120, g), max(90, b)))
    # "character" blob on the side OPPOSITE the calm/text zone
    bx = w * (0.74 if calm_zone in ("left", "top") else 0.26)
    by = h * 0.6
    for rr, col in [(230, (120, 150, 90)), (150, (180, 140, 110)), (90, (235, 205, 170))]:
        d.ellipse([bx - rr, by - rr, bx + rr, by + rr], fill=col)
    tag = f"[placeholder art · calm:{calm_zone}]"
    d.text((24, h - 40), tag, font=font(SANS, 22), fill=(60, 60, 60))
    return base


def _art_for(unit, scene, calm_zone):
    path = scene.get("image") if scene else None
    if path and os.path.exists(path):
        return _fit_cover(Image.open(path).convert("RGB"), PAGE_W, PAGE_H)
    return _placeholder(unit, calm_zone)


# --------------------------- text card ---------------------------

# Card geometry per zone: (x0,y0,x1,y1) as fractions of the page.
CARD_ZONES = {
    "left":   (0.05, 0.16, 0.46, 0.84),
    "right":  (0.54, 0.16, 0.95, 0.84),
    "top":    (0.14, 0.06, 0.86, 0.40),
    "bottom": (0.14, 0.60, 0.86, 0.94),
    "center": (0.20, 0.30, 0.80, 0.70),
}
# Rotation of zones for visual rhythm when the scene planner gives no hint.
# (Centre omitted for content — it's hard to keep an art's middle calm.)
ZONE_CYCLE = ["left", "bottom", "right", "top", "bottom", "left", "right", "top"]


# Zones a content card may occupy (centre excluded — can't keep art's middle calm).
CONTENT_ZONES = ["left", "right", "top", "bottom"]
CARD_PAD = 40
# Edge-energy (0-255) below which a text box counts as "calm" — only a subtle
# light bloom is laid; above it the bloom strengthens into a legibility scrim.
_CALM_MAX = float(os.getenv("PB_CALM_MAX", "14"))
_SCRATCH = ImageDraw.Draw(Image.new("L", (8, 8)))


def _card_box(zone):
    fx0, fy0, fx1, fy1 = CARD_ZONES.get(zone, CARD_ZONES["bottom"])
    return [int(fx0 * PAGE_W), int(fy0 * PAGE_H), int(fx1 * PAGE_W), int(fy1 * PAGE_H)]


# ---- art "busyness" so cards land on genuinely calm regions, not guessed ones ----

def _busy_map(img):
    """Coarse edge-energy map of the art; higher = busier (faces, detail)."""
    g = img.convert("L").filter(ImageFilter.FIND_EDGES).resize((100, 80))
    return g


def _region_energy(busy, box):
    bw, bh = busy.size
    x0, y0, x1, y1 = box
    crop = busy.crop((max(0, int(x0 / PAGE_W * bw)), max(0, int(y0 / PAGE_H * bh)),
                      max(1, int(x1 / PAGE_W * bw)), max(1, int(y1 / PAGE_H * bh))))
    data = list(crop.getdata())
    return sum(data) / max(1, len(data))


def _fits(text, zone, size, fonts, pad=CARD_PAD):
    x0, y0, x1, y1 = _card_box(zone)
    iw, ih = x1 - x0 - 2 * pad, y1 - y0 - 2 * pad
    w, h, _, _ = _text_block_size(_SCRATCH, _tokens(text), fonts, size, iw)
    return w <= iw and h <= ih


def _snug_card(text, zone, size, fonts, pad=CARD_PAD):
    """A card just big enough for the text, centred inside the zone box."""
    zx0, zy0, zx1, zy1 = _card_box(zone)
    iw = zx1 - zx0 - 2 * pad
    w, h, _, _ = _text_block_size(_SCRATCH, _tokens(text), fonts, size, iw)
    cw = min(zx1 - zx0, int(w) + 2 * pad)
    ch = min(zy1 - zy0, int(h) + 2 * pad)
    cx, cy = (zx0 + zx1) // 2, (zy0 + zy1) // 2
    return [cx - cw // 2, cy - ch // 2, cx + cw // 2, cy + ch // 2]


def _snug_size(text, size, fonts, max_iw, pad=CARD_PAD):
    """Card (w, h) just big enough for the text wrapped to `max_iw` inner width.
    Zone-independent — used for free (vision-guided) placement."""
    w, h, _, _ = _text_block_size(_SCRATCH, _tokens(text), fonts, size, max_iw)
    return int(w) + 2 * pad, int(h) + 2 * pad


def _global_body_size(units, fonts, hi=32, lo=18):
    """One font size that fits EVERY content page in at least one zone — so the
    body text is the same size on every page."""
    texts = [u["text"] for u in units
             if u["kind"] == "content" and u.get("text", "").strip()]
    for size in range(hi, lo - 1, -1):
        if all(any(_fits(t, z, size, fonts) for z in CONTENT_ZONES) for t in texts):
            return size
    return lo


def _draw_card(canvas, box, radius=40):
    x0, y0, x1, y1 = box
    # soft shadow
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x0 + 6, y0 + 10, x1 + 6, y1 + 10], radius=radius, fill=(30, 25, 20, 90))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    # translucent card with a very soft edge (no hard keyline)
    card = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle(
        [x0, y0, x1, y1], radius=radius, fill=CARD + (CARD_ALPHA,),
        outline=(255, 255, 255, 70), width=2)
    canvas.alpha_composite(card)


# Feathered "glow" scrim: a soft light pool behind the text with NO hard edge,
# so it melts into the art (continuity) instead of reading as a boxed panel.
SCRIM_PEAK = 224             # centre opacity of the glow


def _draw_scrim(canvas, box, feather=58, radius=70):
    x0, y0, x1, y1 = box
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(feather))
    mask = mask.point(lambda v: int(v * SCRIM_PEAK / 255))
    scrim = Image.new("RGBA", canvas.size, CARD + (255,))
    scrim.putalpha(mask)
    canvas.alpha_composite(scrim)


def _draw_card_soft(canvas, box, radius=38, alpha=250, feather=11):
    """A near-OPAQUE cream card with a soft feathered edge + subtle shadow.

    Unlike the faint scrim, this guarantees a genuinely clean background so the
    text stays fully legible even over busy art — while the feathered edge keeps
    it from reading as a hard boxed panel.
    """
    x0, y0, x1, y1 = box
    # soft drop shadow lifts the card off busy art
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x0 + 5, y0 + 9, x1 + 5, y1 + 9], radius=radius, fill=(30, 25, 20, 85))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(16)))
    # opaque cream fill, then feather only the edge
    panel = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle(
        [x0, y0, x1, y1], radius=radius, fill=CARD + (255,))
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(feather)).point(
        lambda v: int(v * alpha / 255))
    panel.putalpha(mask)
    canvas.alpha_composite(panel)


# --------------------------- reference-style text-on-art ---------------------------
# The three client interiors (Run Sparky Run, Bilbo & Obi, Sheep the Llama) never
# box the body text: it sits DIRECTLY on a calm patch of full-bleed art. Legibility
# comes from two things only — (1) the text colour is chosen to contrast the local
# art (dark ink over light sky/grass, near-white over dark art), and (2) a soft
# feathered halo in the opposite tone hugs the glyphs so they never smear into the
# picture. No rectangle, no keyline, no cream slab.

TEXT_LIGHT = (252, 249, 243)   # near-white, for dark art
TEXT_DARK = INK                # deep ink, for light art


def _region_stats(canvas, box):
    """Mean perceived luminance (0-255) and contrast (stddev) of art under `box`."""
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(canvas.width, max(x0 + 1, x1)), min(canvas.height, max(y0 + 1, y1))
    crop = canvas.convert("RGB").crop((x0, y0, x1, y1)).resize((40, 30))
    px = list(crop.getdata())
    lums = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px]
    n = max(1, len(lums))
    mean = sum(lums) / n
    var = sum((l - mean) ** 2 for l in lums) / n
    return mean, var ** 0.5


def _adaptive_scrim(canvas, box, dark_bg, alpha, feather=60):
    """A soft, edge-feathered light bloom behind the text — NO hard border.

    This is the "slight white blur / lightening" real picture books lay behind
    text so the words lift off the art (see the Bilbo interior: text on blue sky
    with a soft white wash behind it). Subtle on calm art, stronger when the
    text sits on a busy subject. Tinted cream over light art, a soft deep tone
    over dark art (so near-white text still lifts). Never a boxed card.
    """
    x0, y0, x1, y1 = [int(v) for v in box]
    pad = 34
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [x0 - pad, y0 - pad, x1 + pad, y1 + pad], radius=76, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(feather)).point(
        lambda v: int(v * alpha / 255))
    tone = (255, 253, 248) if not dark_bg else (16, 13, 20)
    scrim = Image.new("RGBA", canvas.size, tone + (255,))
    scrim.putalpha(mask)
    canvas.alpha_composite(scrim)


def _draw_text_on_art(canvas, text, box, fonts, size, align="center", protect=False):
    """Render body text directly on the art, reference-book style.

    Picks ink/near-white by the local art luminance and lays a soft feathered
    halo of the opposite tone behind the glyphs — legible over busy art, yet no
    boxed card. When `protect` is set (the text had to land on busy art) a soft
    feathered scrim is laid first so the words never smear into a subject.
    Returns nothing; mutates `canvas` (RGBA) in place.
    """
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    w, h, lines, lh = _text_block_size(_SCRATCH, _tokens(text), fonts, size, bw)
    ty = y0 + max(0, (bh - h) // 2)

    mean, contrast = _region_stats(canvas, box)
    dark_bg = mean < 130
    fill = TEXT_LIGHT if dark_bg else TEXT_DARK
    halo = (18, 14, 12) if not dark_bg else (12, 10, 14)
    if not dark_bg:
        halo = (255, 253, 247)          # light art → soft cream bloom lifts dark ink

    # Always lay a soft light bloom behind the text (the reference "slight white
    # blur"): subtle on calm art, stronger when it must sit on a busy subject.
    if dark_bg:
        bloom = 120 if protect else 66
    else:
        bloom = 168 if protect else 104
    _adaptive_scrim(canvas, [x0, ty, x1, ty + h], dark_bg, alpha=bloom)

    # Draw glyphs onto their own layer so we can build a matching blurred halo.
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    _draw_lines(ImageDraw.Draw(layer), lines, x0, ty, lh, fonts, size, align, bw, fill + (255,))

    # Halo strength scales with how busy/contrasty the underlying art is.
    strength = 150 if contrast > 55 else (110 if contrast > 30 else 80)
    feather = max(3, int(size * 0.16))
    alpha = layer.split()[3]
    halo_mask = alpha.filter(ImageFilter.MaxFilter(3)).filter(
        ImageFilter.GaussianBlur(feather)).point(lambda v: min(255, int(v * 2.4)))
    halo_mask = halo_mask.point(lambda v: int(v * strength / 255))
    halo_layer = Image.new("RGBA", canvas.size, halo + (0,))
    halo_layer.putalpha(halo_mask)
    canvas.alpha_composite(halo_layer)   # soft glow first…
    canvas.alpha_composite(layer)        # …crisp text on top


def _page_number(canvas, label, corner="br"):
    nums = re.findall(r"\d+", label)
    if not nums:
        return
    d = ImageDraw.Draw(canvas)
    for i, n in enumerate(nums[:2]):
        left = (corner == "bl") or (i == 0 and len(nums) > 1)
        cx = MARGIN + 26 if left else PAGE_W - MARGIN - 26
        cy = PAGE_H - MARGIN + 4
        d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=ACCENT + (255,))
        d.text((cx, cy), n, font=font(SANS_B, 22), fill=(255, 250, 240), anchor="mm")


# --------------------------- per-kind renderers ---------------------------

def _draw_text_fixed(draw, text, box, fonts, size, align="center", fill=INK):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    w, h, lines, lh = _text_block_size(draw, _tokens(text), fonts, size, bw)
    _draw_lines(draw, lines, x0, y0 + max(0, (bh - h) // 2), lh, fonts, size, align, bw, fill)


def render_content(unit, scene, size, fonts):
    canvas = _art_for(unit, scene, "right").convert("RGBA")
    has_art = bool(scene and scene.get("image") and os.path.exists(scene["image"]))

    # Preferred: ask a vision model which background is actually placeable
    # (open wall/sky, not a smooth sofa or the floor) and seat the card there.
    # We offer a ladder of card shapes — each font size at many column widths,
    # wide-short through narrow-tall — so place() can match a wide wall strip or
    # a tall wall gap while keeping the font as large as possible. Only worth it
    # on real art, and skippable.
    box = None
    draw_size = size
    pad = CARD_PAD
    if has_art and os.getenv("TEXTPLACE_VISION", "1") != "0":
        grid = textplace.weight_grid_for(unit["label"], canvas)
        vpad = 30  # tighter than CARD_PAD so text stays big in narrow wall gaps
        # Keep ONE body size across the book (consistency); vary only the column
        # width so a card can slot into a wide wall or a narrow gap between
        # figures. Allow a couple of smaller sizes only as a last resort for a
        # genuinely tiny wall — place() strongly prefers the global size.
        # One fixed body size (uniform book); vary only the column width so a
        # card fits a wide wall or a narrow gap. A tight page that can't fit
        # falls back to the zone renderer at the same size.
        cands = []
        for wf in (0.54, 0.46, 0.38, 0.30, 0.24, 0.19):
            cw, ch = _snug_size(unit["text"], size, fonts, int(PAGE_W * wf), pad=vpad)
            cands.append((size, cw, ch))
        placed = textplace.place(grid, cands, PAGE_W, PAGE_H, MARGIN)
        if placed:
            box, draw_size = placed
            pad = vpad
            print(f"    [textplace] {unit['label']}: vision-placed card (size {draw_size})")

    # Seat the text on the CALMEST available spot so it never overrides a
    # subject. Candidates: the vision box (if any) and every fitting third-zone.
    # The vision pick and the art's reserved side each get a small bias so a good
    # placement isn't discarded over a trivially-calmer alternative.
    busy = _busy_map(canvas)
    region = (scene or {}).get("text_region")
    zcands = [z for z in CONTENT_ZONES if _fits(unit["text"], z, size, fonts)] or ["bottom"]

    options = []  # (label, box, draw_size, pad, score)
    if box is not None:
        options.append(("vision", box, draw_size, pad,
                        _region_energy(busy, box) * 0.85))  # trust a good vision pick
    for z in zcands:
        zb = _snug_card(unit["text"], z, size, fonts)
        bias = 0.9 if z == region else 1.0     # gently prefer the art's reserved side
        options.append((z, zb, size, CARD_PAD, _region_energy(busy, zb) * bias))

    label_, box, draw_size, pad, _score = min(options, key=lambda o: o[4])
    if label_ != "vision":
        print(f"    [textplace] {unit['label']}: seated text on calmest zone '{label_}'")

    # Reference-book finish: text sits directly on the art, colour chosen to
    # contrast the local picture, with a soft feathered halo. If the only spot
    # available is busy art, a soft feathered scrim guarantees legibility without
    # a boxed slab (see the three client interiors' soft light behind text).
    inner = [box[0] + pad, box[1] + pad, box[2] - pad, box[3] - pad]
    protect = _region_energy(busy, box) > _CALM_MAX
    _draw_text_on_art(canvas, unit["text"], inner, fonts, draw_size,
                      align="center", protect=protect)
    _page_number(canvas, unit["label"])
    return canvas.convert("RGB")


def render_title(doc, refs):
    canvas = Image.new("RGB", (PAGE_W, PAGE_H), CREAM)
    d = ImageDraw.Draw(canvas)
    fonts = _fonts(SERIF_B)
    _fit_text(d, doc.get("title", ""), [MARGIN, 220, PAGE_W - MARGIN, 470],
              fonts, hi=92, lo=40, align="center", fill=ACCENT, base=SERIF_B)
    d.line([(PAGE_W / 2 - 140, 520), (PAGE_W / 2 + 140, 520)], fill=ACCENT2, width=4)
    if doc.get("author"):
        d.text((PAGE_W / 2, 560), doc["author"], font=font(SERIF, 40),
               fill=INK, anchor="ma")
    # one small spot illustration, like djfan's title page
    spot = _spot_source(refs)
    if spot:
        s = 260
        img = _fit_cover(Image.open(spot).convert("RGB"), s, s)
        mask = Image.new("L", (s, s), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, s, s], fill=255)
        canvas.paste(img, ((PAGE_W - s) // 2, 720), mask)
    return canvas


def render_simple_text(doc, unit, italic=False, heading=None):
    """Copyright / dedication / fallback front-matter on a calm cream page."""
    canvas = Image.new("RGB", (PAGE_W, PAGE_H), CREAM)
    d = ImageDraw.Draw(canvas)
    text = unit["text"].strip() or _default_frontmatter(doc, unit["kind"])
    base = SERIF_I if italic else SERIF
    fonts = _fonts(base)
    if heading:
        d.text((PAGE_W / 2, 200), heading, font=font(SERIF_B, 56), fill=ACCENT, anchor="ma")
    box = [PAGE_W * 0.18, PAGE_H * 0.34, PAGE_W * 0.82, PAGE_H * 0.66]
    _fit_text(d, text, box, fonts, hi=40, lo=20, align="center", fill=INK, base=base)
    return canvas


def render_backmatter(unit):
    canvas = Image.new("RGB", (PAGE_W, PAGE_H), CREAM)
    d = ImageDraw.Draw(canvas)
    lines = unit["text"].split("\n")
    # Only treat a SHORT first line as a section heading; a long sentence is body.
    if lines and len(lines[0]) <= 40:
        heading, body = lines[0], "\n".join(lines[1:]).strip()
    else:
        heading, body = "Parents' Guide", unit["text"].strip()
    hf = font(SERIF_B, 52)
    while d.textlength(heading, font=hf) > PAGE_W - 2 * MARGIN and hf.size > 26:
        hf = font(SERIF_B, hf.size - 2)
    d.text((PAGE_W / 2, 110), heading, font=hf, fill=ACCENT, anchor="ma")
    d.line([(PAGE_W / 2 - 160, 200), (PAGE_W / 2 + 160, 200)], fill=ACCENT2, width=3)
    if body:
        fonts = _fonts(SERIF)
        box = [PAGE_W * 0.12, 250, PAGE_W * 0.88, PAGE_H - MARGIN]
        _fit_text(d, body, box, fonts, hi=34, lo=18, align="left", fill=INK)
    _page_number(canvas, unit["label"])
    return canvas


def render_cover(doc, refs):
    art = os.path.join(OUT_DIR, "cover_art.png")
    canvas = Image.new("RGBA", (PAGE_W, PAGE_H), ACCENT + (255,))
    if os.path.exists(art):
        canvas = _fit_cover(Image.open(art).convert("RGB"), PAGE_W, PAGE_H).convert("RGBA")
    else:
        canvas = _placeholder({"label": "Cover"}, "top").convert("RGBA")
    d = ImageDraw.Draw(canvas)
    title = doc.get("title", "Untitled")
    busy = _busy_map(canvas)
    # Place the title banner on the CALMEST horizontal band in the upper area,
    # so it sits in open sky rather than over a face.
    bh = 230
    band_x0, band_x1 = MARGIN, PAGE_W - MARGIN
    tops = range(48, int(PAGE_H * 0.52), 24)
    top = min(tops, key=lambda t: _region_energy(busy, [band_x0, t, band_x1, t + bh]))
    box = [band_x0, top, band_x1, top + bh]
    banner = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(banner).rounded_rectangle(
        box, radius=38, fill=CARD + (250,), outline=(255, 255, 255, 240), width=5)
    canvas.alpha_composite(banner)
    d = ImageDraw.Draw(canvas)
    _fit_text(d, title, [box[0] + 44, box[1] + 26, box[2] - 44, box[3] - 26],
              _fonts(SERIF_B), hi=84, lo=40, align="center", fill=ACCENT, base=SERIF_B)
    if doc.get("author"):
        # Author plate on the calmest band near the bottom.
        ph = 78
        bots = range(int(PAGE_H * 0.80), PAGE_H - MARGIN - ph, 16)
        ay = min(bots, key=lambda t: _region_energy(busy, [band_x0, t, band_x1, t + ph]))
        aw = d.textlength(doc["author"], font=font(SANS_B, 38))
        plate = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(plate).rounded_rectangle(
            [(PAGE_W - aw) / 2 - 36, ay, (PAGE_W + aw) / 2 + 36, ay + ph],
            radius=20, fill=ACCENT2 + (236,))
        canvas.alpha_composite(plate)
        ImageDraw.Draw(canvas).text((PAGE_W / 2, ay + ph / 2), doc["author"],
                                    font=font(SANS_B, 38), fill=(255, 250, 240), anchor="mm")
    return canvas.convert("RGB")


# --------------------------- helpers ---------------------------

def _spot_source(refs):
    art = os.path.join(OUT_DIR, "cover_art.png")
    if os.path.exists(art):
        return art
    for r in (refs or {}).values():
        if os.path.exists(r.get("portrait", "")):
            return r["portrait"]
    return None


def _default_frontmatter(doc, kind):
    if kind == "copyright":
        return (f"{doc.get('title','')}\n\nText copyright © {doc.get('author','')}\n"
                f"All rights reserved.")
    if kind == "dedication":
        return "·   ·   ·"        # neutral ornament when the source gives no text
    return ""


# --------------------------- build ---------------------------

def build(limit=None):
    _load_accents()
    doc = json.load(open(STORYBOOK))
    scenes = json.load(open(SCENES)) if os.path.exists(SCENES) else {}
    refs = json.load(open(REFS)) if os.path.exists(REFS) else {}
    os.makedirs(OUT_DIR, exist_ok=True)

    units = doc["units"][:limit] if limit else doc["units"]
    body_fonts = _fonts(SERIF)
    # One body size for the whole book. Fixed 30pt by default (override with
    # PB_BODY_SIZE); pass PB_BODY_SIZE=auto to fit-to-largest as before.
    env = os.getenv("PB_BODY_SIZE", "30")
    body_size = _global_body_size(units, body_fonts) if env == "auto" else int(env)
    print(f"  uniform body size: {body_size}pt")

    pages = [render_cover(doc, refs)]
    for i, unit in enumerate(units):
        kind = unit["kind"]
        if kind == "title":
            page = render_title(doc, refs)
        elif kind == "copyright":
            page = render_simple_text(doc, unit, heading=None)
        elif kind == "dedication":
            page = render_simple_text(doc, unit, italic=True)
        elif kind == "backmatter":
            page = render_backmatter(unit)
        else:
            first_page = unit["pages"][0] if unit.get("pages") else None
            scene = (scenes.get(unit["label"])
                     or (scenes.get(str(first_page)) if first_page is not None else None))
            page = render_content(unit, scene, body_size, body_fonts)
        page.save(os.path.join(OUT_DIR, f"unit_{i:02d}_{kind}.png"))
        pages.append(page)

    safe = re.sub(r"[^A-Za-z0-9]+", "_", doc.get("title") or "book").strip("_")
    pdf = os.path.join(OUT_DIR, f"{safe}.pdf")
    pages[0].save(pdf, save_all=True, append_images=pages[1:])
    return pdf


def main():
    print("Storybook assembled ->", build())


if __name__ == "__main__":
    main()
