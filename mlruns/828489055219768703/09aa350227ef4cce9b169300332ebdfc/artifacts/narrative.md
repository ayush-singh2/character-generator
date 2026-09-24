# v04_setaware_minsize_namedcast — Min size + named cast (over-corrects)

**status:** fail  |  **family:** A  |  **mentor-suggested:** True  |  **model:** `google/gemini-3-pro-image`  |  **cost:** ~$0.40  |  **anatomy:** 100  |  **cast:** 6/5

## Goal
Guarantee every character appears exactly once.

## Hypothesis (why we thought it would work)
Minimum capsule size + explicit 'all 5 must appear' roster stops omissions.

## Models used
image edit: google/gemini-3-pro-image

## Source files / functions involved
- `blocking_v8._min_size`
- `blocking_v8.generate_blocked`

## What we did
1. _min_size grows tiny boxes to a floor (MIN_W/MIN_H)
2. Instruction names all 5 and says 'do not omit or merge'

## Prompt / instruction
ALL 5 characters MUST appear, each once: Ferdinand, Boaris, Twiggy, Wooliam, Tallia. Do not omit or merge any.

## Code — all snippets this pipeline used
```python
# ---- [1] pipeline.blocking_v8._min_size ------------------------------
def _min_size(box):
    """Grow a too-small box around its centre to a minimum footprint, clamped
    to frame — so a small character (e.g. Twiggy) isn't dropped by the model."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = max(x1 - x0, MIN_W), max(y1 - y0, MIN_H)
    nx0, nx1 = max(0.0, cx - w / 2), min(1.0, cx + w / 2)
    ny0, ny1 = max(0.0, cy - h / 2), min(1.0, cy + h / 2)
    return [nx0, ny0, nx1, ny1]

# ---- [2] pipeline.blocking_v8.generate_blocked -----------------------
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

```

## Result
All 5 appear, but ADDED a duplicate pig (6 figures); still pasted.

## Why it fails / caveat
Prompt + blocking SUGGEST count; can't HARD-LOCK it on Gemini. Push on 'missing' -> get 'duplicate'. Ceiling of Family A.

## What we learned
Layout-forcing on Gemini can't guarantee exact cast or kill the pasted look. Try building in layers.

## Led to
v05 — layered compositing on fal/Flux.

