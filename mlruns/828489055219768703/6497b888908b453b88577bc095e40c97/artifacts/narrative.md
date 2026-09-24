# v11_erase_extra_body_manual — ERASE only the extra body (best masked result)

**status:** success  |  **family:** C  |  **mentor-suggested:** True  |  **model:** `fal-ai/flux-general/inpainting`  |  **cost:** ~$0.05  |  **anatomy:** 100  |  **cast:** 5/5

## Goal
Remove the anomaly while keeping the real zebra 100% intact.

## Hypothesis (why we thought it would work)
The zebra = good bipedal front + separate extra hindquarters. Mask ONLY the extra hindquarters, fill with background -> real zebra untouched (zero drift).

## Models used
inpaint: fal-ai/flux-general/inpainting (strength 0.95, no IP-Adapter)

## Source files / functions involved
- `fal_backend.make_mask`
- `fal_backend.inpaint`

## What we did
1. Hand-draw a TIGHT mask over only the extra hindquarters [0.86-0.99]
2. inpaint that region to 'floor + plant' background

## Prompt / instruction
Clean empty wooden studio floor + plant, no animal here (inpaint ONLY the tight extra-hindquarters box).

## Code — all snippets this pipeline used
```python
# ---- [1] call --------------------------------------------------------
extra_box = [0.86, 0.42, 0.99, 0.88]        # ONLY the extra part
mask = fal_backend.make_mask((W,H), extra_box, feather=6)
fal_backend.inpaint(original, mask,
    'clean wooden studio floor and plant, no animal, no extra legs',
    strength=0.95)

# ---- [2] pipeline.fal_backend.make_mask ------------------------------
def make_mask(size, box, *, feather: int = 8) -> bytes:
    """White-in-box, black-out mask PNG bytes for a normalised box on a WxH
    image. Feathered so the inpaint seam blends."""
    W, H = size
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rectangle(
        (int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)),
        fill=255)
    if feather:
        m = m.filter(ImageFilter.GaussianBlur(feather))
    buf = io.BytesIO(); m.convert("RGB").save(buf, "PNG")
    return buf.getvalue()

# ---- [3] pipeline.fal_backend.inpaint --------------------------------
def inpaint(image_bytes: bytes, mask_bytes: bytes, prompt: str, *,
            strength: float = 0.9, steps: int = 32,
            ip_adapter_ref: bytes | None = None, ip_scale: float = 0.7,
            ip_refs: list | None = None) -> bytes:
    """Masked inpaint via fal flux-general. Returns the full-page PNG bytes
    (fal composites the frozen region back itself). Raises on a black result
    (safety-checker glitch) so the caller can retry.

    Identity conditioning: pass either `ip_adapter_ref` (+`ip_scale`) for a
    single anchor, or `ip_refs` = [(bytes, scale), ...] for several — e.g. the
    character SHEET (canonical identity) plus the original in-scene CROP
    (pose/scale), which holds "zebra" far better than a lone weak adapter."""
    fc = _client()
    # fal_client.upload_file wants a path; write temp files
    import tempfile
    def _up(b, suffix=".png"):
        f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        f.write(b); f.flush(); f.close()
        return fc.upload_file(f.name)

    args = {
        "image_url": _up(image_bytes),
        "mask_url": _up(mask_bytes),
        "prompt": prompt,
        "strength": strength,
        "num_inference_steps": steps,
        "num_images": 1,
        "enable_safety_checker": False,
    }
    refs = list(ip_refs or [])
    if ip_adapter_ref is not None:
        refs.append((ip_adapter_ref, ip_scale))
    if refs:
        args["ip_adapters"] = [{**_IP_ADAPTER, "image_url": _up(b), "scale": s}
                               for b, s in refs]
    r = fc.subscribe(_INPAINT_EP, arguments=args)
    imgs = r.get("images") or []
    if not imgs:
        raise RuntimeError(f"fal inpaint returned no image: {str(r)[:160]}")
    out = _download(imgs[0]["url"])
    # guard against the black-image glitch
    im = Image.open(io.BytesIO(out)).convert("L")
    import numpy as np
    if np.asarray(im).mean() < 8:
        raise RuntimeError("fal returned a black image (safety-checker glitch); retry")
    return out

```

## Result
Chimera gone, zebra AND giraffe preserved, 5/5, anatomy 100. Best masked result.

## Why it fails / caveat
Worked — but required a HUMAN to place the precise mask on the separable extra part. Not automatic.

## What we learned
ERASE-the-separable-part is identity-safe; blocker is AUTO-locating that part.

## Led to
v12 — automate detect -> mask -> repair.

