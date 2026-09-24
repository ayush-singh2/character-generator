# v09_masked_inpaint_safetyoff — all code snippets used

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
