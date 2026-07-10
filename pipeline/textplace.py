"""Vision-guided text placement for picture-book pages.

The renderer used to snap each text card to the *calmest of four fixed
zones*, judged only by edge-energy. That mistakes a smooth-painted sofa
for an equally good surface as an open wall — both have low edges, but
only one should carry words.

Here we ask a vision model to read the generated illustration and mark
which BACKGROUND regions are placeable (open wall, sky, empty floor/
ground) versus which must stay CLEAR (characters, faces, hands, solid
furniture, toys). We rasterise that into a weight grid, temper it with
the same edge-energy signal (so a picture frame on a wall still gets
penalised), and let the renderer slide a card-sized box to the single
highest-weight spot that fits the text — free position, not four zones.

Cheap: one vision call per page, cached to data/placement.json keyed by a
hash of the composited art, so re-running the `book` stage is free.
Degrades to the edge-energy heuristic (returns None) if the call fails.
"""

import hashlib
import io
import json
import os

from PIL import Image, ImageDraw, ImageFilter

from .llm import chat_json_image

CACHE_PATH = "data/placement.json"

# Weight grid resolution (columns x rows). Coarse is fine — cards are big.
GRID_W, GRID_H = 48, 36

# Longest image edge sent to the vision model (keeps the call cheap).
VISION_MAX_EDGE = 768

# CV calmness prior: a cell's baseline placeability is CALM_BASE (busiest) up to
# CALM_BASE+CALM_SPAN (perfectly smooth). This makes large plain walls usable
# even when the vision model forgets to box them.
CALM_BASE = 0.15
CALM_SPAN = 0.58

# Keep-clear labels that are HARD (a card must never touch); everything else in
# keepclear (furniture, toys, props) is soft — allowed only as a last resort.
# Animals, pets, mascots and costumed creatures (e.g. Homer the dragon) are
# SUBJECTS just like people — their smooth bellies/costumes read calm to edge
# detection, so they must be hard, not soft, or text lands right on them.
HARD_LABELS = ("character", "person", "face", "hand", "head", "arm", "kid",
               "child", "animal", "creature", "dragon", "mascot", "dog", "cat",
               "pet", "puppy", "monster", "body", "torso", "chest", "figure",
               "costume")
# Of those, these are ALWAYS fully forbidden (never eroded) — a card must not sit
# on a face/hand even where it's smooth. Body labels get CV erosion instead.
FACE_LABELS = ("face", "head", "hand", "eye", "mouth", "hair")
SOFT_WEIGHT = 0.14
# Grow face boxes by this fraction of the frame as a safety buffer — vision
# boxes often clip wispy hair or an outstretched limb.
HARD_DILATE = 0.03
# A body cell counts as "really the figure" (and is forbidden) only if its edge
# detail reaches this; flatter cells inside a loose person-box are kept.
DETAIL_MIN = 0.22
# Fraction to shrink each side of a subject box to reach its solid core. That
# core is hard-forbidden no matter how smoothly it is painted — a dog's flank or
# a dragon's costumed belly is edge-calm but is still the subject and must never
# carry text. The looser box margins stay reclaimable by the calm prior, so a
# strip of plain wall beside a figure is still usable.
CORE_INSET = 0.20

# Vertical prior: weight is full down to VERT_FULL of the height, then ramps to
# VBOTTOM at the bottom edge — a smooth floor (and the wall/floor boundary) is
# demoted vs the wall above it, so text lifts toward the middle of the wall and
# off the floor/tiles, without being forbidden from the floor entirely.
VERT_FULL = 0.44
VBOTTOM = 0.18

# Map model labels -> base suitability. Walls & sky are the real target; floors
# and ground are a weak last resort (text on a floor reads messy). Unknown
# labels fall to 0.5.
PLACEABLE_WEIGHT = {
    "wall": 1.0, "sky": 1.0, "background": 0.92, "backdrop": 0.92,
    "floor": 0.5, "ground": 0.5, "grass": 0.5, "water": 0.5,
    "foliage": 0.42, "table_surface": 0.3,
}

SYSTEM = """\
You help place a translucent TEXT CARD on a children's picture-book
illustration. Look at the image and report, in NORMALISED coordinates
(0..1, origin top-left, x right, y down):

PLACEABLE regions — large, calm, EMPTY background a rounded text box could
sit over and still read clearly: a BLANK stretch of wall, open sky, empty
floor or ground, plain backdrop. Prefer the biggest emptiest areas. A
placeable region must be featureless — do NOT include a window, mirror,
picture, or any object inside it; box only the bare wall around them.

KEEPCLEAR regions — anything a card must NOT cover: any character, person, or
CREATURE — this includes animals, pets, dogs, cats, and costumed mascots or
dragons; box the WHOLE creature (its body/belly/costume too, not just the
face), even where its coat or costume looks smooth and calm. Also faces,
hands; solid foreground objects (sofa, chair, table, bed, patterned rug, toys,
books); AND wall FEATURES that read as clutter under text — windows, mirrors,
framed pictures, shelves, clocks, TV/screens, wall lamps. Text should sit on
BLANK wall/sky beside these, never on top of them.

Return STRICT JSON only:
{
  "placeable": [{"box":[x0,y0,x1,y1],"label":"wall|sky|floor|ground|background","score":0.0-1.0}],
  "keepclear": [{"box":[x0,y0,x1,y1],"label":"character|animal|mascot|dragon|face|furniture|toy|prop|window|picture|shelf|lamp"}]
}
List placeable regions largest/emptiest first. Boxes may touch the edges.
If the whole frame is busy with characters, return "placeable": []."""


def _load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        try:
            return json.load(open(CACHE_PATH))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    json.dump(cache, open(CACHE_PATH, "w"), indent=2)


def _art_hash(img: Image.Image) -> str:
    small = img.convert("RGB").resize((64, 48))
    return hashlib.sha1(small.tobytes()).hexdigest()[:16]


def _vision_regions(img: Image.Image) -> dict | None:
    """Ask the vision model for placeable / keepclear regions. None on failure."""
    small = img.convert("RGB")
    small.thumbnail((VISION_MAX_EDGE, VISION_MAX_EDGE))
    buf = io.BytesIO()
    small.save(buf, format="PNG")
    try:
        spec = chat_json_image(
            SYSTEM,
            "Where can a text card sit on this illustration? Return the JSON.",
            buf.getvalue(),
            max_tokens=1200,
            temperature=0.1,
        )
    except Exception as e:  # network / parse / model error -> caller falls back
        print(f"    [textplace] vision call failed: {str(e)[:100]}")
        return None
    if not isinstance(spec, dict):
        return None
    return spec


def _edge_grid(img: Image.Image) -> list[list[float]]:
    """Normalised edge-energy per grid cell (0 calm .. 1 busy)."""
    g = img.convert("L").filter(ImageFilter.FIND_EDGES).resize((GRID_W, GRID_H))
    px = list(g.getdata())
    hi = max(px) or 1
    return [[px[r * GRID_W + c] / hi for c in range(GRID_W)] for r in range(GRID_H)]


def _fill(grid, box, value, mode):
    """Paint a normalised box into the grid cells (max for placeable, min/set
    for keepclear)."""
    x0, y0, x1, y1 = box
    x0, x1 = sorted((max(0.0, min(1.0, x0)), max(0.0, min(1.0, x1))))
    y0, y1 = sorted((max(0.0, min(1.0, y0)), max(0.0, min(1.0, y1))))
    c0, c1 = int(x0 * GRID_W), max(int(x0 * GRID_W) + 1, int(round(x1 * GRID_W)))
    r0, r1 = int(y0 * GRID_H), max(int(y0 * GRID_H) + 1, int(round(y1 * GRID_H)))
    for r in range(r0, min(r1, GRID_H)):
        for c in range(c0, min(c1, GRID_W)):
            grid[r][c] = max(grid[r][c], value) if mode == "max" else value


def _weight_grid(img: Image.Image, spec: dict) -> list[list[float]] | None:
    """Placement weight per grid cell (0 = never .. ~1 = ideal wall/sky).

    The model is trusted to LOCATE things (characters to avoid, wall/sky to
    prefer) but NOT to outline every empty area — it routinely under-boxes big
    plain walls. So the baseline placeability comes from image *calmness* (low
    edge detail): any large smooth region is usable even if the model never
    boxed it. Vision `placeable` boxes then lift confirmed wall/sky above that
    baseline; `keepclear` boxes demote furniture (soft) and forbid characters
    (hard). This is what lets text find a big unboxed wall (e.g. page 4)."""
    edges = _edge_grid(img)  # 0 calm .. 1 busy

    # CV calmness prior — smooth background is placeable in proportion to how
    # edge-free it is; detail (toys, patterns, hair, faces) starts low.
    grid = [[CALM_BASE + CALM_SPAN * (1.0 - edges[r][c]) for c in range(GRID_W)]
            for r in range(GRID_H)]

    # Vision placeable regions lift wall/sky/floor above the baseline, still
    # damped by local detail so a framed picture on a wall doesn't score high.
    for reg in spec.get("placeable", []) or []:
        box = reg.get("box")
        if not (isinstance(box, list) and len(box) == 4):
            continue
        label = str(reg.get("label", "")).lower()
        base = PLACEABLE_WEIGHT.get(label, 0.5)
        score = reg.get("score")
        w = base * float(score) if isinstance(score, (int, float)) else base
        x0, x1 = sorted((box[0], box[2]))
        y0, y1 = sorted((box[1], box[3]))
        c0, c1 = int(max(0, x0) * GRID_W), int(round(min(1, x1) * GRID_W))
        r0, r1 = int(max(0, y0) * GRID_H), int(round(min(1, y1) * GRID_H))
        for r in range(r0, min(max(r0 + 1, r1), GRID_H)):
            for c in range(c0, min(max(c0 + 1, c1), GRID_W)):
                grid[r][c] = max(grid[r][c], w * (1.0 - edges[r][c]))

    # Keep-clears, ordered so the strongest constraint always wins.
    kc = [r for r in (spec.get("keepclear", []) or [])
          if isinstance(r.get("box"), list) and len(r["box"]) == 4]
    labels = [str(r.get("label", "")).lower() for r in kc]

    # 1) Soft: furniture/props may be sat over as a last resort.
    for reg, label in zip(kc, labels):
        if not any(h in label for h in HARD_LABELS):
            _fill(grid, reg["box"], SOFT_WEIGHT, "set")

    # 2) Body characters: ERODE. Model person-boxes are loose — they over-claim
    # flat wall beside a figure and under-cover limbs. So a body box forbids only
    # cells that actually carry detail (a limb/torso); flat wall it wrongly
    # covers survives at its calm weight.
    for reg, label in zip(kc, labels):
        if any(h in label for h in HARD_LABELS) and not _is_face(label):
            _erode_zero(grid, edges, reg["box"])
            # ...and hard-forbid the box's solid core regardless of edge detail:
            # a dog's flank or a mascot/dragon's costumed belly reads calm to the
            # eroder but IS the subject. Shrinking inward keeps the loose margins
            # (plain wall beside the figure) reclaimable.
            x0, y0, x1, y1 = reg["box"]
            x0, x1 = sorted((x0, x1))
            y0, y1 = sorted((y0, y1))
            dx, dy = (x1 - x0) * CORE_INSET, (y1 - y0) * CORE_INSET
            _fill(grid, [x0 + dx, y0 + dy, x1 - dx, y1 - dy], 0.0, "set")

    # 3) Faces/hands/heads: fully forbidden, with a safety dilation for wispy
    # hair the box clips. Applied LAST so nothing re-exposes them.
    for reg, label in zip(kc, labels):
        if _is_face(label):
            x0, y0, x1, y1 = reg["box"]
            _fill(grid, [x0 - HARD_DILATE, y0 - HARD_DILATE,
                         x1 + HARD_DILATE, y1 + HARD_DILATE], 0.0, "set")

    # 4) Vertical prior: a smooth floor scores as calm as a smooth wall, but
    # picture-book text belongs on wall/sky, not the floor. Gently demote the
    # lower band so text prefers (and centres within) the wall above it. Hard-0
    # cells stay 0.
    for r in range(GRID_H):
        vf = _vfac(r)
        if vf < 1.0:
            for c in range(GRID_W):
                grid[r][c] *= vf
    return grid


def _vfac(r: int) -> float:
    """Vertical weight factor: full through the upper band, ramping down to
    VBOTTOM at the very bottom (floor)."""
    t = r / (GRID_H - 1)
    if t <= VERT_FULL:
        return 1.0
    return 1.0 - (t - VERT_FULL) / (1.0 - VERT_FULL) * (1.0 - VBOTTOM)


def _is_face(label: str) -> bool:
    return any(f in label for f in FACE_LABELS)


def _erode_zero(grid, edges, box):
    """Zero only the detailed cells of a (dilated) box; leave flat cells at
    their calm weight so an over-wide body box doesn't swallow plain wall."""
    x0, y0, x1, y1 = box
    x0, x1 = sorted((x0 - HARD_DILATE, x1 + HARD_DILATE))
    y0, y1 = sorted((y0 - HARD_DILATE, y1 + HARD_DILATE))
    c0, c1 = int(max(0, x0) * GRID_W), int(round(min(1, x1) * GRID_W))
    r0, r1 = int(max(0, y0) * GRID_H), int(round(min(1, y1) * GRID_H))
    for r in range(r0, min(max(r0 + 1, r1), GRID_H)):
        for c in range(c0, min(max(c0 + 1, c1), GRID_W)):
            if edges[r][c] >= DETAIL_MIN:
                grid[r][c] = 0.0


def weight_grid_for(label: str, img: Image.Image) -> list[list[float]] | None:
    """Weight grid for a page's composited art. None -> caller uses fallback.

    We cache the *vision regions* (the expensive part) keyed by an art hash and
    rebuild the grid from them every run, so tweaking the weight table or edge
    tempering never needs another model call — only new art does.
    """
    cache = _load_cache()
    key = _art_hash(img)
    entry = cache.get(label)
    if entry and entry.get("hash") == key and "spec" in entry:
        spec = entry["spec"]
    else:
        spec = _vision_regions(img)
        cache[label] = {"hash": key, "spec": spec}   # spec may be None
        _save_cache(cache)
    return _weight_grid(img, spec) if spec else None


# Preference tiers: try to seat the card in a pure wall/sky rectangle first,
# then a looser one, then any placeable (incl. floor) as a last resort. Values
# are post-edge-tempering weights, so they sit below the raw label weights.
# Cells at/above this weight are the wall/sky "calm mass" we centre text in.
CENTROID_MIN = 0.5

# Unified placement score weights (lower total = better). Balances how much of
# the card sits on real wall, how near it lands to the empty-wall centre, how
# comfortably wide the text column is, and how big the font stays.
W_WALL = 1.0       # prefer wall coverage over floor/furniture
W_CENTER = 0.55    # prefer the middle of the open wall
W_NARROW = 0.5     # penalise thin ribbons (columns under IDEAL_W)
W_SIZE = 1.5       # strongly prefer the global font (keep the book uniform)
IDEAL_W = 400      # a comfortable column width (px); wider gets no penalty


def _mean_under(grid, x, y, cw, ch, page_w, page_h) -> float:
    """Mean weight under a pixel card; -1 if it touches ANY hard keep-clear (0)
    cell, so a card can never overlap a character or face."""
    c0 = int(x / page_w * GRID_W)
    c1 = max(c0 + 1, int(round((x + cw) / page_w * GRID_W)))
    r0 = int(y / page_h * GRID_H)
    r1 = max(r0 + 1, int(round((y + ch) / page_h * GRID_H)))
    tot = n = 0
    for r in range(max(0, r0), min(r1, GRID_H)):
        for c in range(max(0, c0), min(c1, GRID_W)):
            v = grid[r][c]
            if v <= 0.0:
                return -1.0
            tot += v
            n += 1
    return tot / n if n else -1.0


def _centroid(grid, thresh, page_w, page_h):
    """Pixel-space centre of the calm mass (cells >= thresh). None if empty."""
    sx = sy = n = 0
    for r in range(GRID_H):
        for c in range(GRID_W):
            if grid[r][c] >= thresh:
                sx += (c + 0.5) / GRID_W * page_w
                sy += (r + 0.5) / GRID_H * page_h
                n += 1
    return (sx / n, sy / n) if n else None


def _max_rect_cells(grid, thresh):
    """Largest all-True axis-aligned rectangle of cells >= thresh. Histogram
    method. Returns (area, r0, c0, r1, c1) inclusive."""
    heights = [0] * GRID_W
    best = (0, 0, 0, 0, 0)
    for r in range(GRID_H):
        for c in range(GRID_W):
            heights[c] = heights[c] + 1 if grid[r][c] >= thresh else 0
        stack, c = [], 0
        while c <= GRID_W:
            h = heights[c] if c < GRID_W else 0
            start = c
            while stack and stack[-1][1] > h:
                sc, sh = stack.pop()
                area = sh * (c - sc)
                if area > best[0]:
                    best = (area, r - sh + 1, sc, r, c - 1)
                start = sc
            stack.append((start, h))
            c += 1
    return best


def _target_center(grid, page_w, page_h):
    """Pixel centre of the biggest clear wall/sky rectangle — where the eye
    reads a page as 'empty'. Text should aim here, not at the centroid of a
    scattered calm mass (which drifts toward whatever band is widest)."""
    area, r0, c0, r1, c1 = _max_rect_cells(grid, CENTROID_MIN)
    if area > 0:
        return ((c0 + c1 + 1) / 2 / GRID_W * page_w,
                (r0 + r1 + 1) / 2 / GRID_H * page_h)
    return _centroid(grid, CENTROID_MIN, page_w, page_h) or (page_w / 2, page_h / 2)


def _best_pos(grid, cw, ch, page_w, page_h, margin, centroid, min_score, step=16):
    """Slide a cw x ch card and return (box, mean_weight) for the spot with the
    most wall coverage; ties (within a weight band) break toward `centroid` for
    balance. (None, -1) if nothing reaches `min_score` without hitting a hard
    keep-clear cell."""
    cw = min(cw, page_w - 2 * margin)
    ch = min(ch, page_h - 2 * margin)
    best_box, best_key, best_m = None, None, -1.0
    y = margin
    while y + ch <= page_h - margin:
        x = margin
        while x + cw <= page_w - margin:
            m = _mean_under(grid, x, y, cw, ch, page_w, page_h)
            if m >= min_score:
                d = ((x + cw / 2 - centroid[0]) ** 2 + (y + ch / 2 - centroid[1]) ** 2
                     if centroid else 0)
                key = (round(m / 0.05), -d)   # weight band first, then centred
                if best_key is None or key > best_key:
                    best_key, best_box, best_m = key, [x, y, x + cw, y + ch], m
            x += step
        y += step
    return best_box, best_m


def place(grid, candidates, page_w, page_h, margin):
    """Seat the text card. `candidates` is (size, cw, ch) ordered largest-first.
    Returns (box, size) or None.

    Aims the card at the centre of the biggest CLEAR wall rectangle (`target`)
    so text sits in the middle of the empty wall, not shoved to an edge or
    pulled low by a wide calm band. Pass 1: at the largest font, among all
    column widths that sit mostly on wall, pick the one whose card lands
    closest to that target, preferring the WIDER card when equally close (so a
    narrow wall gets a narrow column, a big wall a comfortable one). Pass 2
    (wall too small for any card): allow soft-furniture overlap, most wall
    coverage first. None only if there is no character-free spot at all."""
    if not grid:
        return None
    target = _target_center(grid, page_w, page_h)
    diag = (page_w ** 2 + page_h ** 2) ** 0.5
    maxsize = max(s for s, _, _ in candidates)

    best = None  # (score, box, size)
    for size, cw, ch in candidates:
        box, m = _best_pos(grid, cw, ch, page_w, page_h, margin, target, 0.02)
        if not box:
            continue
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        dist = ((cx - target[0]) ** 2 + (cy - target[1]) ** 2) ** 0.5
        score = (W_WALL * (1.0 - min(1.0, m))                   # more wall = better
                 + W_CENTER * (dist / diag)                     # nearer target = better
                 + W_NARROW * max(0.0, (IDEAL_W - cw) / IDEAL_W)  # avoid thin ribbons
                 + W_SIZE * ((maxsize - size) / maxsize))       # bigger font = better
        if best is None or score < best[0]:
            best = (score, box, size)
    return (best[1], best[2]) if best else None
