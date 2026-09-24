# v01_colored_blocking — Colored silhouette blocking (mentor #4)

**status:** fail  |  **family:** A  |  **mentor-suggested:** True  |  **model:** `google/gemini-3-pro-image`  |  **cost:** ~$0.40  |  **anatomy:** None  |  **cast:** 5/5

## Goal
Stop the fusion by giving the model an explicit layout map.

## Hypothesis (why we thought it would work)
If each character gets its own colored capsule at a fixed position, the model can't merge or duplicate bodies.

## Models used
image edit: google/gemini-3-pro-image (editor.edit / _openrouter_edit)

## Source files / functions involved
- `blocking_v8.build_blocking`
- `blocking_v8._capsule`
- `editor.edit`

## What we did
1. Draw one bold colored capsule per character from the layout boxes
2. Add a text-band rectangle
3. Feed blocking + character sheets to Gemini with 'follow the guide'

## Prompt / instruction
Follow the color blocking image: each coloured capsule is ONE character standing upright; single upright body, two legs two arms, never a four-legged body.

## Code — all snippets this pipeline used
```python
# ---- [1] pipeline.blocking_v8.build_blocking -------------------------
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

# ---- [2] pipeline.blocking_v8._capsule -------------------------------
def _capsule(draw, box, size, color):
    """Draw an upright capsule (rounded vertical bar) inside a normalised box —
    reads as a single standing body."""
    x0, y0, x1, y1 = box
    px0, py0, px1, py1 = int(x0 * size), int(y0 * size), int(x1 * size), int(y1 * size)
    if px1 - px0 < 4 or py1 - py0 < 4:
        return
    r = max(4, (px1 - px0) // 2)
    draw.rounded_rectangle((px0, py0, px1, py1), radius=r, fill=color)

# ---- [3] pipeline.editor.edit ----------------------------------------
def edit(instruction: str, images: list[bytes], *, model: str | None = None) -> bytes:
    """Edit the FIRST image per `instruction`; later images are references.

    Returns PNG/other bytes of the edited image. Raises on failure.
    """
    return _openrouter_edit(instruction, images, model=model)

# ---- [4] pipeline.editor._openrouter_edit ----------------------------
def _openrouter_edit(instruction: str, images: list[bytes], *,
                     model: str | None = None) -> bytes:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    content = [{"type": "text", "text": instruction}]
    content += [{"type": "image_url", "image_url": {"url": _data_url(b)}} for b in images]
    body = {
        "model": model or EDIT_MODEL,
        "modalities": ["image", "text"],
        "messages": [{"role": "user", "content": content}],
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            status, raw = _post_bytes(API_URL, headers, body)
            if status == 429 or status >= 500:
                last_err = RuntimeError(f"editor {status}: {raw[:200]!r}")
                raise requests.exceptions.ConnectionError(last_err)
            if status != 200:
                raise RuntimeError(f"editor {status}: {raw[:400]!r}")
            choices = json.loads(raw).get("choices") or [{}]
            msg = choices[0].get("message", {})
            imgs = msg.get("images") or []
            if not imgs:
                # The image model sometimes returns reasoning/text and no image;
                # this is transient — back off and retry rather than failing.
                last_err = RuntimeError(f"editor returned no image: {str(msg)[:200]}")
                raise requests.exceptions.ConnectionError(last_err)
            url = imgs[0]["image_url"]["url"]
            return base64.b64decode(url.split(",", 1)[1])
        except RETRYABLE as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
                continue
            raise RuntimeError(f"editor failed after {MAX_RETRIES} attempts: {last_err}") from e

```

## Result
Chimera reduced, but bold capsule COLORS bled through as ghost-ovals.

## Why it fails / caveat
Gemini is an editing model — it PRESERVES input content. Bold colors read as real objects to keep, not as hints.

## What we learned
Layout idea works; colors are the problem — make them faint.

## Led to
v02 — same map in faint grey.

