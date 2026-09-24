"""Silhouette / box blocking image (Hosted Approach #4, cheapest structural test).

Builds a flat "blocking" canvas from the layout the pipeline already computes:
one coloured UPRIGHT-BODY silhouette per character (positioned by its layout
box), plus a reserved text band. Fed into an img2img call, the image model
treats the coloured shapes as structural anchors — locking each character's
POSITION and relative SCALE, reserving the negative space for text, and (this
is the anti-chimera bit) suggesting ONE upright body per character rather than
letting the model graft on a second quadruped body.

Why a capsule, not a plain rectangle: a rectangle only pins position/size. A
tall rounded capsule reads as a single standing figure, which nudges the model
toward one coherent upright body — directly relevant to the body-plan chimera.

This is the PREVENTION counterpart to anatomy_v8's DETECTION: structural
conditioning tries to stop the defect at generation, which our test showed a
text prompt alone can't do.

Standalone preview (no API):
    python -m pipeline.blocking_v8 --book books/namaste-ferdinand/v3 --page 23
writes <book>/<V3>/output/blocking/page_23.png
"""

import argparse
import glob
import io
import os

from PIL import Image, ImageDraw

from . import toon_io

PAPER = (245, 242, 235)          # warm paper background
TEXT_BAND = (225, 228, 232)      # pale reserved caption zone
# distinct, muted character colours (kept low-sat so they don't bias hue)
PALETTE = [(150, 170, 200), (200, 160, 150), (160, 195, 165),
           (205, 185, 145), (185, 160, 195), (150, 195, 195),
           (210, 170, 190), (175, 180, 150)]
# FAINT palette: near-paper greys so the img2img model reads them as position
# hints, not as coloured objects to preserve (kills the colour-halo artifact
# that Gemini leaves when the capsules are strongly coloured).
FAINT_BASE = 225
FAINT_STEP = 6                    # tiny per-character brightness offset


def _faint(i: int):
    v = max(200, FAINT_BASE - (i % 6) * FAINT_STEP)
    return (v, v, v)


MIN_W = 0.16          # a capsule narrower/shorter than this reads as "skippable"
MIN_H = 0.28


def _min_size(box):
    """Grow a too-small box around its centre to a minimum footprint, clamped
    to frame — so a small character (e.g. Twiggy) isn't dropped by the model."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = max(x1 - x0, MIN_W), max(y1 - y0, MIN_H)
    nx0, nx1 = max(0.0, cx - w / 2), min(1.0, cx + w / 2)
    ny0, ny1 = max(0.0, cy - h / 2), min(1.0, cy + h / 2)
    return [nx0, ny0, nx1, ny1]


def _capsule(draw, box, size, color):
    """Draw an upright capsule (rounded vertical bar) inside a normalised box —
    reads as a single standing body."""
    x0, y0, x1, y1 = box
    px0, py0, px1, py1 = int(x0 * size), int(y0 * size), int(x1 * size), int(y1 * size)
    if px1 - px0 < 4 or py1 - py0 < 4:
        return
    r = max(4, (px1 - px0) // 2)
    draw.rounded_rectangle((px0, py0, px1, py1), radius=r, fill=color)


def build_blocking(layout_entry: dict, size: int = 1024, label: bool = False,
                   faint: bool = False) -> Image.Image:
    """Blocking canvas for one page's layout entry. `faint` uses near-paper
    greys instead of colours (avoids the img2img colour-halo artifact)."""
    img = Image.new("RGB", (size, size), PAPER)
    d = ImageDraw.Draw(img)

    tz = layout_entry.get("text_zone")
    if tz and len(tz) == 4:
        d.rectangle((int(tz[0] * size), int(tz[1] * size),
                     int(tz[2] * size), int(tz[3] * size)), fill=TEXT_BAND)

    for i, ch in enumerate(layout_entry.get("chars") or []):
        box = ch.get("box")
        if not (isinstance(box, list) and len(box) == 4):
            continue
        box = _min_size(box)          # tiny capsules get dropped by the model
        color = _faint(i) if faint else PALETTE[i % len(PALETTE)]
        _capsule(d, box, size, color)
        if label:
            d.text((int(box[0] * size) + 4, int(box[1] * size) + 4),
                   str(ch.get("name", "")), fill=(40, 40, 40))
    return img


def _load_layout(data_dir: str) -> dict:
    lay = toon_io.load(os.path.join(data_dir, "layout.toon"))
    return {str(l.get("page")): l for l in lay["layouts"]}


def _setting_ref(data_dir: str, setting_key: str):
    """(path, description) of the establishing setting plate for a scene's
    setting_key, or (None, '') — this is the piece the first blocking probe
    dropped, which is why the studio background vanished."""
    if not setting_key:
        return None, ""
    try:
        refs = toon_io.load(os.path.join(data_dir, "refs.toon"))
    except Exception:                                        # noqa: BLE001
        return None, ""
    for s in refs.get("settings", []) or []:
        if s.get("key") == setting_key:
            p = s.get("path", "")
            # paths in refs.toon are book-relative (v3_kimi/refs/...); resolve
            book_root = os.path.dirname(data_dir.rstrip("/"))
            full = p if os.path.isabs(p) else os.path.join(book_root, os.path.basename(os.path.dirname(p)), os.path.basename(p))
            if not os.path.exists(full):
                full = os.path.join(book_root, p.split("/", 1)[-1]) if "/" in p else p
            return (full if os.path.exists(full) else None), s.get("description", "")
    return None, ""


def generate_blocked(pid: str, book_dir: str, *, faint: bool = True):
    """Full setting-aware blocking generation for one page. Feeds, IN ORDER:
    [blocking guide, setting plate, character sheets] into the image editor with
    an instruction that (a) keeps the real setting background, (b) follows the
    blocking for position/scale/negative-space, (c) forces ONE upright body per
    character. Returns the rendered PNG bytes. This is the fix for the
    background-regression: the first probe omitted the setting plate.
    """
    from . import editor  # local import: editor pulls network deps
    data_dir = os.path.join(book_dir, "data")
    layouts = _load_layout(data_dir)
    scenes = {str(s.get("page")): s for s in
              toon_io.load(os.path.join(data_dir, "scenes.toon"))["scenes"]}
    entry = layouts.get(str(pid))
    sc = scenes.get(str(pid))
    if not entry or not sc:
        raise SystemExit(f"no layout/scene for page {pid}")

    present = [c.get("name") for c in (entry.get("chars") or []) if c.get("name")]
    # character reference sheets (skip the auto placeholder duplicates)
    refs = []
    for nm in dict.fromkeys(present):                       # de-dup, keep order
        p = os.path.join(book_dir, "refs", f"{nm.lower()}.png")
        if os.path.exists(p):
            refs.append(open(p, "rb").read())

    set_path, set_desc = _setting_ref(data_dir, sc.get("setting_key"))
    setting_bytes = [open(set_path, "rb").read()] if set_path else []

    import io as _io
    blk = build_blocking(entry, faint=faint)
    buf = _io.BytesIO(); blk.save(buf, "PNG")

    desc = (sc.get("illustration") or sc.get("action") or "")[:600]
    if present:
        roster = ", ".join(dict.fromkeys(present))
        instr = (
            f"Illustrate this children's yoga-book page in the SAME soft "
            f"watercolour style as the reference images. SCENE: {desc}. "
            f"ALL {len(dict.fromkeys(present))} of these characters MUST appear, "
            f"each drawn once as a distinct figure: {roster}. Do not omit or "
            f"merge any of them. "
            f"BACKGROUND: render the full setting from the setting reference "
            f"image — {set_desc[:280]}. Keep that room/scene fully painted "
            f"behind the characters (do NOT leave a blank or plain background). "
            f"COMPOSITION: the grey-capsule image is a LAYOUT GUIDE — each grey "
            f"capsule marks WHERE one character stands and how tall; paint "
            f"characters at those positions and do NOT keep any grey shapes. "
            f"Each character is a SINGLE upright bipedal body — two legs, two "
            f"arms, human-like torso with an animal head — NEVER a four-legged "
            f"body, NEVER an extra second body or extra legs. Keep the bottom "
            f"band clear of characters for the caption. Match each character to "
            f"its reference sheet.")
    else:
        instr = (
            f"Illustrate this children's book page in soft watercolour style. "
            f"SCENE: {desc}. This page has NO animal or human characters — only "
            f"the setting/decoration. Do NOT draw any animals or people. Keep "
            f"open space for text.")

    imgs = [buf.getvalue()] + setting_bytes + refs
    print(f"  page {pid}: blocking + {len(setting_bytes)} setting + {len(refs)} "
          f"char refs ({'set='+os.path.basename(set_path) if set_path else 'NO SETTING'})")
    return editor.to_square(editor.edit(instr, imgs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="books/namaste-ferdinand/v3")
    ap.add_argument("--page", required=True)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--label", action="store_true", help="draw names (preview only)")
    ap.add_argument("--faint", action="store_true", help="near-paper greys (no colour halos)")
    args = ap.parse_args()

    data_dir = os.path.join(args.book, "data")
    layouts = _load_layout(data_dir)
    entry = layouts.get(str(args.page))
    if not entry:
        raise SystemExit(f"no layout for page {args.page}")
    img = build_blocking(entry, size=args.size, label=args.label, faint=args.faint)

    out_dir = os.path.join(args.book, "output", "blocking")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"page_{args.page}.png")
    img.save(out)
    n = len(entry.get("chars") or [])
    print(f"blocking page {args.page}: {n} character shapes + text band -> {out}")


if __name__ == "__main__":
    main()
