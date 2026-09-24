# v10_masked_inpaint_ipadapter — Masked repair + IP-Adapter (erases neighbour)

**status:** fail  |  **family:** C  |  **mentor-suggested:** True  |  **model:** `fal-ai/flux-general/inpainting + InstantX/FLUX.1-dev-IP-Adapter`  |  **cost:** ~$0.07  |  **anatomy:** 100  |  **cast:** 4/5

## Goal
Repair the zebra region AS Twiggy (mask=where, IP-Adapter=who).

## Hypothesis (why we thought it would work)
Mask + IP-Adapter on Twiggy's sheet paints the right zebra in the right place.

## Models used
inpaint: fal-ai/flux-general/inpainting | IP-Adapter: InstantX/FLUX.1-dev-IP-Adapter (twiggy sheet, scale 0.9)

## Source files / functions involved
- `fal_backend.make_mask`
- `fal_backend.inpaint`

## What we did
1. Mask box [0.60-0.97]
2. inpaint + ip_adapters=twiggy, strength 0.85

## Prompt / instruction
A single upright striped zebra like the reference; IP-Adapter on twiggy.png; inpaint masked zebra region.

## Code — all snippets this pipeline used
```python
# ---- [1] call --------------------------------------------------------
zebra_box = [0.60, 0.33, 0.97, 0.90]        # TOO WIDE
mask = fal_backend.make_mask((W,H), zebra_box)
fal_backend.inpaint(original, mask, prompt,
    ip_adapter_ref=open(f'{REFS}/twiggy.png','rb').read(),
    ip_scale=0.9, strength=0.85)   # box overlapped giraffe -> erased

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
Zebra fixed, but the giraffe (Tallia) VANISHED — 4/5 cast.

## Why it fails / caveat
Mask box too wide — overlapped the giraffe's region, so the inpaint repainted (deleted) Tallia.

## What we learned
Masks must be NEIGHBOUR-SAFE.

## Led to
v11 — tight hand-placed mask on only the extra part.

