# v02_faint_blocking — all code snippets used

```python
# ---- [1] pipeline.blocking_v8._faint ---------------------------------
def _faint(i: int):
    v = max(200, FAINT_BASE - (i % 6) * FAINT_STEP)
    return (v, v, v)

# ---- [2] pipeline.blocking_v8._min_size ------------------------------
def _min_size(box):
    """Grow a too-small box around its centre to a minimum footprint, clamped
    to frame — so a small character (e.g. Twiggy) isn't dropped by the model."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = max(x1 - x0, MIN_W), max(y1 - y0, MIN_H)
    nx0, nx1 = max(0.0, cx - w / 2), min(1.0, cx + w / 2)
    ny0, ny1 = max(0.0, cy - h / 2), min(1.0, cy + h / 2)
    return [nx0, ny0, nx1, ny1]

# ---- [3] pipeline.blocking_v8.build_blocking -------------------------
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

```
