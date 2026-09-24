# v09_masked_inpaint_safetyoff — Masked repair, safety off (text-only)

**status:** fail  |  **family:** C  |  **mentor-suggested:** True  |  **model:** `fal-ai/flux-general/inpainting`  |  **cost:** ~$0.05  |  **anatomy:** None  |  **cast:** None/5

## Goal
Get a real (non-black) inpaint of the zebra region.

## Hypothesis (why we thought it would work)
With the checker off, a text prompt 'a zebra' repaints the region correctly.

## Models used
inpaint: fal-ai/flux-general/inpainting (enable_safety_checker=False)

## Source files / functions involved
- `fal_backend.inpaint`

## What we did
1. Same mask
2. inpaint with enable_safety_checker=False, text prompt

## Prompt / instruction
A striped zebra standing upright in yoga clothes; inpaint masked region. enable_safety_checker=False.

## Code — all snippets this pipeline used
```python
# ---- [1] pipeline.fal_backend.inpaint --------------------------------
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
Real image, but the region became a blank EASEL, not a zebra.

## Why it fails / caveat
A bare text prompt can't reconstruct the SPECIFIC character; studio context hijacked the fill into furniture.

## What we learned
Need identity conditioning (IP-Adapter on the zebra's sheet).

## Led to
v10 — add IP-Adapter.

