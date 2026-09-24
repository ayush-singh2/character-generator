"""fal.ai Flux backend — text-to-image plate + masked inpainting.

Encodes what the probe established actually works against fal-ai/flux-general:
- `enable_safety_checker=False` — the checker intermittently returns an
  all-BLACK image even for benign content (a zebra in yoga clothes), so we
  disable it and rely on our own审查; the API still reports has_nsfw_concepts.
- IP-Adapter needs the WEIGHTS specified (`path`, `weight_name`,
  `image_encoder_path`), not just a reference image — the standard FLUX
  InstantX adapter + SigLIP encoder.
- Inpainting semantics: white mask = region to repaint, black = frozen.

Two repair modes the wrapper uses:
- ERASE  : prompt = background, no IP-Adapter, high strength → removes a
           defect (e.g. an extra hindquarters) and fills with scene backdrop.
- REDRAW : prompt = the character, IP-Adapter on that character's sheet,
           moderate strength → replaces a wrong/whole-body defect on-model.

Requires FAL_KEY (read from env or .env).
"""

import io
import os

import requests
from PIL import Image, ImageDraw, ImageFilter

_IP_ADAPTER = {
    "path": "InstantX/FLUX.1-dev-IP-Adapter",
    "weight_name": "ip-adapter.bin",
    "image_encoder_path": "google/siglip-so400m-patch14-384",
}
_INPAINT_EP = "fal-ai/flux-general/inpainting"
_T2I_EP = "fal-ai/flux/dev"


def _ensure_key():
    if os.environ.get("FAL_KEY"):
        return
    for line in open(os.path.join(os.getcwd(), ".env")):
        if line.startswith("FAL_KEY="):
            os.environ["FAL_KEY"] = line.split("=", 1)[1].strip()
            return
    raise SystemExit("FAL_KEY not set (env or .env)")


def _client():
    _ensure_key()
    import fal_client
    return fal_client


def _download(url: str) -> bytes:
    return requests.get(url, timeout=120).content


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


def text_to_image(prompt: str, *, steps: int = 28) -> bytes:
    """Generate a character-free background plate."""
    fc = _client()
    r = fc.subscribe(_T2I_EP, arguments={
        "prompt": prompt, "image_size": "square_hd",
        "num_images": 1, "num_inference_steps": steps})
    return _download((r.get("images") or [{}])[0]["url"])
