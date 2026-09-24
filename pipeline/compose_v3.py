"""v3 text compositor — set page text in genuine in-scene negative space.

A vision model looks at the finished art and returns the calmest, emptiest
rectangle (open sky / wall / floor / plain background) that avoids characters and
busy detail; the caption is drawn there in ONE locked size and colour with a soft
white halo (no card, no border/seam) and a hard safe margin so it can never clip
at the frame edge. Front/back matter is handled by role: cover/title pages get the
book title (display serif); the dedication page gets its verbatim text centred.
Output -> v3/output/pages/page_<pg>.png.
"""

import io
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import plan_v3, toon_io
from .llm import chat_json_image

from .plan_v3 import DATA, ART, PAGES as OUT  # noqa: F401

# Font is author-selectable (New Project → Typography). COMPOSE_FONT_PATH is set
# by the backend from the chosen family, mapped to an available .ttf; falls back
# to the bundled serif so a book always composes.
SERIF_B = os.getenv("COMPOSE_FONT_PATH") or "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"

# TYP: one locked, modest type scale for the whole book (fraction of page height).
# The client called the previous text "big and huge"; these are deliberately small.
# COMPOSE_BODY_FRAC lets the author's chosen body size scale it.
BODY_FRAC = float(os.getenv("COMPOSE_BODY_FRAC", "0.030"))   # body captions
PAGENUM = os.getenv("COMPOSE_PAGENUM", "0") == "1"           # draw printed page numbers
PAGENUM_FRAC = 0.020
TITLE_FRAC = 0.072      # cover / title-page book title
AUTHOR_FRAC = 0.034     # author line under the title
DED_FRAC = 0.034        # dedication text
LINE_SPACING = 1.28
MARGIN = 0.055          # hard safe area — text never enters this edge band (TYP-2)
PAD = 0.02              # inner padding inside the chosen zone (fraction of width)
INK = (38, 32, 28)      # dark ink for light backgrounds
INK_LIGHT = (247, 245, 241)   # light ink for dark backgrounds
GLOW = (255, 255, 255)

# Full-width top/bottom bands — the reserved diegetic negative space (open
# sky / open ground) the generator was told to leave. Text spans the whole band.
TOP_BAND = [0.06, 0.05, 0.94, 0.32]
BOT_BAND = [0.06, 0.68, 0.94, 0.95]


def _region_stats(im, box):
    """(mean luminance 0-255, mean edge energy) for a normalised region."""
    W, H = im.size
    r = im.crop((int(box[0] * W), int(box[1] * H),
                 int(box[2] * W), int(box[3] * H))).convert("L")
    n = max(1, r.width * r.height)
    lum = sum(r.getdata()) / n
    energy = sum(r.filter(ImageFilter.FIND_EDGES).getdata()) / n
    return lum, energy


def _pick_band(im, prefer):
    """Choose the calmest full-width band (biased to the side the art reserved),
    and pick ink that contrasts with it (dark on light, light on dark)."""
    bands = {"top": TOP_BAND, "bottom": BOT_BAND}
    stats = {s: _region_stats(im, b) for s, b in bands.items()}
    calmest = min(bands, key=lambda s: stats[s][1])
    # keep the requested side unless the other is clearly calmer
    side = prefer if (prefer in bands and stats[prefer][1] <= stats[calmest][1] + 6) else calmest
    lum, energy = stats[side]
    ink = INK if lum > 125 else INK_LIGHT
    glow = GLOW if lum > 125 else (18, 16, 14)
    return bands[side], ink, glow, energy


def _overlap(a, b):
    """Vertical overlap fraction of strip `a` with box `b` (both normalised)."""
    lo, hi = max(a[1], b[1]), min(a[3], b[3])
    return max(0.0, hi - lo)


def _ink_lum(ink):
    return 0.299 * ink[0] + 0.587 * ink[1] + 0.114 * ink[2]


def _glow_for(ink):
    return GLOW if ink == INK else (18, 16, 14)


def _contrast_level(im, box, ink):
    """How much help the caption needs to read on this strip.
    0 = plain halo; 1 = strong halo; 2 = strong halo + soft scrim.
    Ink-vs-strip luminance delta is the primary signal; a busy strip
    (high edge energy) can defeat a borderline delta, so it escalates too."""
    lum, energy = _region_stats(im, box)
    delta = abs(lum - _ink_lum(ink))
    if delta >= 70 and energy <= 25:
        return 0
    if delta >= 45:
        return 1
    return 2


def _strip_occupied(im, box, energy=0.0):
    """Vision veto for a candidate caption strip. Edge energy misses
    flat-shaded characters (few edges) — the exact blindness already fixed in
    the generation band check but not here, which let a caption land on a
    background figure the layout never listed. Crop the strip and ask.

    Forced-choice, not yes/no (yes/no probes agree with themselves — the
    same agreement bias the scale gate hit). Fail-open is energy-conditional:
    an API error on an already-busy strip counts as occupied."""
    try:
        from . import llm
        W, H = im.size
        crop = im.convert("RGB").crop((int(box[0] * W), int(box[1] * H),
                                       int(box[2] * W), int(box[3] * H)))
        buf = io.BytesIO()
        crop.save(buf, "JPEG", quality=85)
        r = llm.chat_json_image(
            "You QA caption placement in picture books.",
            "This is a horizontal strip of an illustration where a caption "
            "would be printed. What does the strip contain? Reply ONLY JSON: "
            '{"content": "background_only" | "partial_figure" | "figure" | '
            '"face"} — "face" means any face or head is inside the strip; '
            '"background_only" means NO part of any person, face, character '
            "or animal is inside the strip.",
            buf.getvalue(), mime="image/jpeg")
        return str(r.get("content", "background_only")) != "background_only"
    except Exception:
        return energy > 30.0


def _caption_overlaps(out_im, box):
    """Post-draw gate: what does the caption AS DRAWN sit over? Boxes and
    the strip veto judge candidates, not the composited result — this is the
    only check that sees exactly what the reader sees. Forced-choice; returns
    the category ("plain_background" | "partly_a_figure" | "a_figure" |
    "a_face"); fail-open (accept the draw) on any error."""
    try:
        from . import llm
        W, H = out_im.size
        crop = out_im.convert("RGB").crop(
            (int(box[0] * W), int(max(0.0, box[1] - 0.03) * H),
             int(box[2] * W), int(min(1.0, box[3] + 0.03) * H)))
        buf = io.BytesIO()
        crop.save(buf, "JPEG", quality=85)
        r = llm.chat_json_image(
            "You QA caption placement in picture books.",
            "This crop shows printed caption text on an illustration. What "
            "is directly UNDER the text glyphs? Reply ONLY JSON: "
            '{"under_text": "plain_background" | "partly_a_figure" | '
            '"a_figure" | "a_face"} — "a_face" means text sits over any '
            'face or head; "plain_background" means no part of any person, '
            "character or animal sits under any of the text.",
            buf.getvalue(), mime="image/jpeg")
        v = str(r.get("under_text", "plain_background"))
        return v if v in ("plain_background", "partly_a_figure",
                          "a_figure", "a_face") else "plain_background"
    except Exception:
        return "plain_background"


def _locate_figures(im):
    """Ground-truth character boxes measured on the FINAL art.

    The 600x collision penalty in _clearest_strip was dead code — nothing in
    v7 wrote staging.toon, so placement leaned on edge energy (blind to
    flat-shaded figures) and a 3-candidate veto. One enumerate-then-locate
    call (count first, then one tight box per figure — counting first stops
    the model dropping background figures) feeds the penalty real boxes.
    Fail-open -> [] (offline compose behaves exactly as before)."""
    try:
        from . import llm
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=85)
        r = llm.chat_json_image(
            "You locate figures in children's picture-book illustrations "
            "with tight bounding boxes.",
            "Step 1: COUNT every character, person, animal or creature "
            "visible in this illustration — including partial, background "
            "and flat-colour figures.\n"
            "Step 2: give exactly ONE tight bounding box per figure, PLUS a "
            "tight box around that figure's head/face (null if the head is "
            "not visible).\n"
            "Coordinates normalised 0..1, origin top-left, x right, y down.\n"
            'Reply ONLY JSON: {"count": N, "figures": [{"label": "short '
            'description", "box": [x0,y0,x1,y1], "head_box": [x0,y0,x1,y1] '
            'or null}]}. Boxes must be tight — '
            "never the whole page unless the figure truly fills it.",
            _small(buf.getvalue()), mime="image/jpeg")
        out = []
        for f in (r.get("figures") or []):
            b = f.get("box")
            if not (isinstance(b, list) and len(b) == 4):
                continue
            x0, y0, x1, y1 = (min(max(float(v), 0.0), 1.0) for v in b)
            if x1 - x0 < 0.02 or y1 - y0 < 0.02:   # sliver = noise
                continue
            head = None
            hb = f.get("head_box")
            if isinstance(hb, list) and len(hb) == 4:
                hx0, hy0, hx1, hy1 = (min(max(float(v), 0.0), 1.0) for v in hb)
                if hx1 - hx0 >= 0.01 and hy1 - hy0 >= 0.01:
                    head = [hx0, hy0, hx1, hy1]
            out.append({"label": str(f.get("label", ""))[:60],
                        "box": [max(0.0, x0 - 0.02), max(0.0, y0 - 0.02),
                                min(1.0, x1 + 0.02), min(1.0, y1 + 0.02)],
                        "head": head})
        return out
    except Exception as e:
        print(f"     (figure locate failed: {str(e)[:60]})")
        return []


def _page_boxes(pg, im, art_path, staging):
    """Cached per-page figure boxes + head boxes, keyed by the art file's
    mtime so a regenerated page re-detects automatically. Entries from older
    schema versions (src != vlm_v8, no head boxes) re-detect too — otherwise
    the mtime cache would serve face-blind box lists forever. Mutates
    `staging`. Returns (boxes, heads)."""
    mt = os.path.getmtime(art_path)
    e = staging.get(pg)
    if (e and abs(e.get("art_mtime", -1) - mt) < 1e-6
            and e.get("src") == "vlm_v8"):
        return e.get("boxes", []), e.get("heads", [])
    figs = _locate_figures(im)
    staging[pg] = {"page": pg, "boxes": [f["box"] for f in figs],
                   "heads": [f["head"] for f in figs if f.get("head")],
                   "labels": [f["label"] for f in figs],
                   "src": "vlm_v8", "art_mtime": mt}
    return staging[pg]["boxes"], staging[pg]["heads"]


def _clearest_strip(im, bh_frac, prefer, avoid=None, faces=None):
    """Slide a full-width strip of height bh_frac down the safe area and return the
    position with the least detail AND clear of the known character boxes (`avoid`),
    so text can never land on a character. `faces` (head boxes) are an order
    harder to touch than bodies — a caption near feet is acceptable, on a face
    never. `prefer` (top/bottom) breaks ties.
    The top candidates are then vision-vetoed (background figures aren't in
    `avoid`); the best strip nobody occupies wins, else the best by score."""
    x0, x1 = MARGIN, 1 - MARGIN
    y_lo, y_hi = MARGIN, max(MARGIN, 1 - MARGIN - bh_frac)
    avoid = avoid or []
    faces = faces or []
    cands = []
    steps = 30
    for i in range(steps + 1):
        y = y_lo + (y_hi - y_lo) * i / steps
        strip = [x0, y, x1, y + bh_frac]
        lum, energy = _region_stats(im, strip)
        centre = y + bh_frac / 2
        bias = (centre * 7) if prefer == "top" else ((1 - centre) * 7)  # gentle side pull
        if avoid and centre > 0.62:
            bias -= 2.0   # characters present: near-feet strips beat near-face ones
        # hard penalty for sitting on top of any character box (600 * overlap);
        # face overlap is an order harder (5000 *) — never worth it
        collide = sum(_overlap(strip, b) for b in avoid)
        face_hit = sum(_overlap(strip, f) for f in faces)
        cands.append((energy + bias + collide * 600 + face_hit * 5000,
                      strip, lum, energy, collide, face_hit))
    cands.sort(key=lambda c: c[0])
    # veto pass: probe up to 3 well-separated top candidates, keep the first
    # unoccupied one. Candidates already overlapping a known box >0.15 (or any
    # face at all) are doomed — skip the probe, don't waste it. If every probed
    # candidate is occupied, DON'T silently take cands[0] (the old behaviour
    # that let captions land on figures): re-rank by (face, collide, energy) so
    # the ground-truth boxes pick the least-overlapping, face-free strip.
    best = None
    tried_y = []
    for c in cands:
        if len(tried_y) >= 3:
            break
        if c[4] > 0.15 or c[5] > 0 or any(abs(c[1][1] - ty) < 0.12 for ty in tried_y):
            continue
        tried_y.append(c[1][1])
        if not _strip_occupied(im, c[1], c[3]):
            best = c
            break
    if best is None:
        best = min(cands, key=lambda c: (c[5], c[4], c[3]))
    _, box, lum, energy, collide, _face = best
    ink = INK if lum > 125 else INK_LIGHT
    glow = GLOW if lum > 125 else (18, 16, 14)
    return box, ink, glow, energy, collide


def _body_metrics(im, text):
    """Font/lines/normalised block-height for body text at the locked size across
    the full safe width — used to size the clearest-strip search."""
    W, H = im.size
    size = max(12, int(BODY_FRAC * H))
    font = ImageFont.truetype(SERIF_B, size)
    bw = (1 - 2 * MARGIN) * W - 2 * PAD * W
    lines = _wrap(ImageDraw.Draw(im), text, font, bw)
    block_h = int(size * LINE_SPACING) * len(lines)
    return (block_h + 2 * PAD * W) / H

PLACE_SYSTEM = """\
You place a caption on a children's book illustration. Return the largest CALM, \
EMPTY rectangle that is a NATURAL part of the scene — open sky, a plain wall, calm \
ground/floor, or still water — with no faces, characters or busy detail, where a \
few lines of text will read clearly. Do NOT pick a spot on top of a character.
Reply ONLY JSON: {"box":[x0,y0,x1,y1]}
Coordinates normalised 0..1 (origin top-left). Prefer the %s area if it is calm."""


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
            return [float(v) for v in box]
    except Exception as e:
        print(f"     (vision place failed: {str(e)[:60]})")
    return None


def _safe(box):
    """Clamp a normalised box into the hard safe area (never touches the edges)."""
    x0, y0, x1, y1 = box
    x0 = min(max(x0, MARGIN), 1 - MARGIN)
    y0 = min(max(y0, MARGIN), 1 - MARGIN)
    x1 = min(max(x1, MARGIN), 1 - MARGIN)
    y1 = min(max(y1, MARGIN), 1 - MARGIN)
    if x1 - x0 < 0.2:                       # keep a usable width
        x0, x1 = MARGIN, 1 - MARGIN
    if y1 - y0 < 0.1:
        y1 = min(1 - MARGIN, y0 + 0.18)
    return [x0, y0, x1, y1]


def _wrap(draw, text, font, bw):
    lines = []
    for para in text.split("\n"):
        words, cur = para.split(), ""
        for w in words:
            t = (cur + " " + w).strip()
            if draw.textlength(t, font=font) <= bw or not cur:
                cur = t
            else:
                lines.append(cur); cur = w
        lines.append(cur)
    return lines or [text]


def _draw_block(im, text, box, frac, valign="center", ink=INK, glow=GLOW,
                halo_level=0):
    """Draw `text` inside `box` (normalised) at height-fraction `frac`, centred
    horizontally, with a soft halo. Size shrinks ONLY if the block cannot fit the
    safe vertical area; it never clips the frame. Returns a new RGB image.
    `halo_level` escalates legibility help on weak-contrast strips: 0 = plain
    halo, 1 = stronger/denser halo, 2 = strong halo + soft rounded scrim in the
    glow colour under the whole block (last resort — still no hard card)."""
    W, H = im.size
    box = _safe(box)
    x0, y0, x1, y1 = box[0] * W, box[1] * H, box[2] * W, box[3] * H
    pad = PAD * W
    bw = (x1 - x0) - 2 * pad
    scratch = ImageDraw.Draw(im)
    safe_top, safe_bot = MARGIN * H, (1 - MARGIN) * H

    size = max(12, int(frac * H))
    while size > 12:
        font = ImageFont.truetype(SERIF_B, size)
        lines = _wrap(scratch, text, font, bw)
        lh = int(size * LINE_SPACING)
        if lh * len(lines) <= (safe_bot - safe_top):
            break
        size -= 2
    font = ImageFont.truetype(SERIF_B, size)
    lines = _wrap(scratch, text, font, bw)
    lh = int(size * LINE_SPACING)
    block_h = lh * len(lines)

    zone_h = y1 - y0
    by0 = y0 + (zone_h - block_h) / 2 if valign == "center" else y0
    by0 = min(max(by0, safe_top), max(safe_top, safe_bot - block_h))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    cx = (x0 + x1) / 2
    for i, l in enumerate(lines):
        lw = ld.textlength(l, font=font)
        ld.text((cx - lw / 2, by0 + i * lh), l, font=font, fill=ink + (255,))

    alpha = layer.split()[3]
    mf = 13 if halo_level >= 1 else 9
    blur = 12 if halo_level >= 1 else 8
    amul = 1.0 if halo_level >= 1 else 0.94
    halo = alpha.filter(ImageFilter.MaxFilter(mf)).filter(ImageFilter.GaussianBlur(blur))
    halo = halo.point(lambda v: min(255, int(v * amul)))
    halo_layer = Image.new("RGBA", (W, H), glow + (0,))
    halo_layer.putalpha(halo)

    base = im.convert("RGBA")
    if halo_level >= 2:
        # soft scrim: blurred rounded rectangle in the glow colour under the
        # block (~35% alpha) — enough separation on any background, no card
        maxlw = max(scratch.textlength(l, font=font) for l in lines)
        pad_s = size * 0.9
        sx0 = max(0.0, cx - maxlw / 2 - pad_s)
        sx1 = min(float(W), cx + maxlw / 2 + pad_s)
        sy0 = max(0.0, by0 - pad_s * 0.6)
        sy1 = min(float(H), by0 + block_h + pad_s * 0.6)
        scrim = Image.new("L", (W, H), 0)
        ImageDraw.Draw(scrim).rounded_rectangle(
            [sx0, sy0, sx1, sy1], radius=int(size * 0.8), fill=90)
        scrim = scrim.filter(ImageFilter.GaussianBlur(size * 0.5))
        scrim_layer = Image.new("RGBA", (W, H), glow + (0,))
        scrim_layer.putalpha(scrim)
        base = Image.alpha_composite(base, scrim_layer)

    out = Image.alpha_composite(base, halo_layer)
    out = Image.alpha_composite(out, layer)
    return out.convert("RGB")


def _page_number(im, label, ink=INK, glow=GLOW, halo_level=0):
    """Draw a small centred page number inside the bottom safe margin, with the
    same soft halo the captions use so it stays legible on any background."""
    W, H = im.size
    size = max(12, int(PAGENUM_FRAC * H))
    font = ImageFont.truetype(SERIF_B, size)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    tw = ld.textlength(label, font=font)
    x = (W - tw) / 2
    y = int((1 - MARGIN) * H) - size
    ld.text((x, y), label, font=font, fill=ink + (255,))
    alpha = layer.split()[3]
    mf = 13 if halo_level >= 1 else 9
    blur = 12 if halo_level >= 1 else 8
    amul = 1.0 if halo_level >= 1 else 0.94
    halo = alpha.filter(ImageFilter.MaxFilter(mf)).filter(ImageFilter.GaussianBlur(blur))
    halo_layer = Image.new("RGBA", (W, H), glow + (0,))
    halo_layer.putalpha(halo.point(lambda v: min(255, int(v * amul))))
    out = Image.alpha_composite(im.convert("RGBA"), halo_layer)
    out = Image.alpha_composite(out, layer)
    return out.convert("RGB")


def compose(only=None, data_dir=DATA):
    os.makedirs(OUT, exist_ok=True)
    plan = plan_v3.load(data_dir)
    title = plan.get("title", "")
    author = plan.get("author", "")
    # Ground-truth figure boxes measured on the final art (staging.toon) let
    # text avoid characters deterministically. Cached by art mtime; a page
    # regen re-detects on the next compose.
    sp = f"{data_dir}/staging.toon"
    staging = ({s["page"]: s for s in toon_io.load(sp)["pages"]}
               if os.path.exists(sp) else {})
    report = {}
    for sc in plan["scenes"]:
        pg = plan_v3.page_id(sc)
        if only and pg not in only:
            continue
        art = f"{ART}/page_{plan_v3.slug(pg)}.png"
        if not os.path.exists(art):
            continue
        im = Image.open(art).convert("RGB")
        role = sc.get("role", "body")
        out_path = f"{OUT}/page_{plan_v3.slug(pg)}.png"

        # Front matter: cover + title page carry the book title (+ author).
        if role in ("cover", "title") and title:
            out = _draw_block(im, title, [0.10, 0.07, 0.90, 0.26], TITLE_FRAC, "center")
            if author:
                out = _draw_block(out, f"by {author}", [0.15, 0.80, 0.85, 0.93],
                                  AUTHOR_FRAC, "center")
            out.save(out_path); print(f"  [{pg}] title page"); continue

        text = plan_v3.scene_text(sc)
        if not text.strip():
            im.save(out_path); print(f"  [{pg}] (no text)"); continue

        # Dedication: centred on the page, mostly empty art.
        if role == "dedication":
            _draw_block(im, text, [0.15, 0.34, 0.85, 0.66], DED_FRAC, "center").save(out_path)
            print(f"  [{pg}] dedication"); continue

        # Body / back matter: slide a strip the exact height of the caption down the
        # page and drop it in the CLEAREST gap (least detail) — biased to the side
        # the art reserved. This deterministically nudges text off the characters
        # (the "shift it up/down to avoid collision" fix) with no guesswork.
        prefer = sc.get("text_area") or "top"
        bh = _body_metrics(im, text)
        avoid, faces = _page_boxes(pg, im, art, staging)

        def _place(av):
            # pick the strip, then the ink that actually contrasts best on it,
            # then how much halo/scrim help that pairing still needs
            b, k, g, en, co = _clearest_strip(im, bh, prefer, av, faces)
            alt = INK_LIGHT if k == INK else INK
            if _contrast_level(im, b, alt) < _contrast_level(im, b, k):
                k, g = alt, _glow_for(alt)
            return b, k, g, en, co, _contrast_level(im, b, k)

        box, ink, glow, energy, collide, lvl = _place(avoid)
        out = _draw_block(im, text, box, BODY_FRAC, "center", ink, glow,
                          halo_level=lvl)
        # Closed loop: verify the DRAWN caption sits on background, not a
        # figure (boxes + veto judge candidate strips, not the composited
        # result). One retry with the failed strip excluded — but text on a
        # FACE earns one extra retry before we accept; then accept, since a
        # page with slightly-overlapping text beats a page with no text.
        retries, max_r = 0, 1
        verdict = _caption_overlaps(out, box)
        while verdict != "plain_background" and retries < max_r:
            retries += 1
            if verdict == "a_face":
                max_r = 2
            avoid = avoid + [[0.0, max(0.0, box[1] - 0.02),
                              1.0, min(1.0, box[3] + 0.02)]]
            box, ink, glow, energy, collide, lvl = _place(avoid)
            out = _draw_block(im, text, box, BODY_FRAC, "center", ink, glow,
                              halo_level=lvl)
            verdict = _caption_overlaps(out, box)
        retried, residual = retries > 0, verdict != "plain_background"
        # Printed page number (author opt-in): only on numbered story pages, using
        # the same ink the caption picked so it reads on this page's background.
        if PAGENUM and str(pg).isdigit():
            out = _page_number(out, str(pg), ink=ink, glow=glow,
                               halo_level=min(lvl, 1))
        out.save(out_path)
        report[pg] = {"y": round(box[1], 3), "energy": round(energy, 1),
                      "collide": round(collide, 3), "retried": retried,
                      "residual_overlap": residual, "overlap": verdict,
                      "halo_level": lvl}
        print(f"  [{pg}] text @ y={round(box[1],2)} (clearest, e={energy:.0f}, "
              f"collide={collide:.2f}{', RETRIED' if retried else ''}"
              f"{f', RESIDUAL {verdict}' if residual else ''}) "
              f"ink={'dark' if ink == INK else 'light'} halo={lvl}")
    toon_io.save({"pages": list(staging.values())}, sp)
    import json
    json.dump(report, open(f"{OUT}/compose_report.json", "w"), indent=2)
    bad = [p for p, r in report.items() if r.get("residual_overlap")]
    if bad:
        print(f"  RESIDUAL OVERLAP (send back through generate --only): {bad}")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    compose(only=only)
