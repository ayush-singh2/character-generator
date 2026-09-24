# v03_faint_plus_setting — Faint blocking + setting reference

**status:** partial  |  **family:** A  |  **mentor-suggested:** True  |  **model:** `google/gemini-3-pro-image`  |  **cost:** ~$0.40  |  **anatomy:** 100  |  **cast:** 4/5

## Goal
Restore the background while keeping the anatomy fix.

## Hypothesis (why we thought it would work)
Feeding studio plate + blocking + character sheets gives where + who + scene, enough for a full correct page.

## Models used
image edit: google/gemini-3-pro-image

## Source files / functions involved
- `blocking_v8.generate_blocked`
- `blocking_v8._setting_ref`
- `editor.edit`

## What we did
1. Look up the scene's setting_key -> setting_yoga_studio.png
2. Feed [blocking, setting plate, character sheets] to Gemini

## Prompt / instruction
Render the full setting from the setting reference behind the characters; follow the grey layout guide; single upright bodies.

## Code — all snippets this pipeline used
```python
# ---- [1] pipeline.blocking_v8._setting_ref ---------------------------
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
Background restored, anatomy 100 — but DROPPED Twiggy (zebra), 4/5.

## Why it fails / caveat
Small/crowded capsules get under-rendered; the model skipped the smallest figure.

## What we learned
Need minimum figure size + explicitly named cast.

## Led to
v04 — min capsule size + named roster.

