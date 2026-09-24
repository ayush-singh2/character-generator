# v06_plate_ipadapter_inpaint — IP-Adapter inpaint into plate (mentor #1)

**status:** fail  |  **family:** B  |  **mentor-suggested:** True  |  **model:** `fal-ai/flux-general/inpainting + InstantX/FLUX.1-dev-IP-Adapter`  |  **cost:** ~$0.15  |  **anatomy:** None  |  **cast:** 0/5

## Goal
Paint ONE character into its box, identity locked by IP-Adapter.

## Hypothesis (why we thought it would work)
IP-Adapter conditions the masked region on a reference image, so one-at-a-time placement avoids cross-character bleed.

## Models used
inpaint: fal-ai/flux-general/inpainting | IP-Adapter: InstantX/FLUX.1-dev-IP-Adapter | encoder: google/siglip-so400m-patch14-384

## Source files / functions involved
- `fal_backend.inpaint`
- `fal_backend.make_mask`

## What we did
1. Mask over the character's layout box on the plate
2. flux-general/inpainting with ip_adapters = Ferdinand's sheet

## Prompt / instruction
A cream goat standing upright in his box; IP-Adapter on ferdinand.png; inpaint the masked region only.

## Code — all snippets this pipeline used
```python
# ---- [1] pipeline.fal_backend.make_mask ------------------------------
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

# ---- [2] pipeline.fal_backend.inpaint --------------------------------
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
Masked region came back a WHITE BLOCK / no coherent character.

## Why it fails / caveat
Inpainting into an EMPTY plate region gives no surrounding context to build a figure on; IP-Adapter conditions identity but can't conjure a body from blank space.

## What we learned
Inpainting works best repairing WITHIN existing content, not into a void.

## Led to
v07 — paste then harmonize instead.

