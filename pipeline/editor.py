"""Instruction-based image editing via OpenRouter image models.

Unlike flux.py (reference-conditioned *generation*, which reimagines the whole
frame), these models EDIT an image in place from a text instruction and preserve
everything not mentioned — the surgical behaviour Approach 1's correction needs.
Given a page + "add Obi's green cap, change nothing else", the beagle keeps its
breed/pose/position and only the cap changes; no doubling, no identity swap.

Called through OpenRouter's chat-completions endpoint with image output; the
edited image comes back as a data URL in message.images[0].
"""

import base64
import io
import json
import os
import threading
import time

from PIL import Image

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Gemini's image model is best-in-class for localized, identity-preserving edits.
EDIT_MODEL = os.getenv("EDIT_MODEL", "google/gemini-3-pro-image")

MAX_RETRIES = 4
CONNECT_TIMEOUT = float(os.getenv("EDIT_CONNECT_TIMEOUT", "15"))    # secs to establish
READ_TIMEOUT = float(os.getenv("EDIT_READ_TIMEOUT", "120"))        # secs between bytes
# Hard wall-clock cap on a single request. A per-read timeout alone does NOT stop a
# server that trickles bytes forever (observed: a 95-min hang under timeout=300);
# this bounds the whole response so a stalled call can't freeze a book run.
HARD_DEADLINE = float(os.getenv("EDIT_HARD_DEADLINE", "240"))
RETRYABLE = (
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)


def _post_bytes(url, headers, body):
    """POST and return (status_code, raw_bytes), enforcing HARD_DEADLINE over the
    whole request+response. A per-read timeout can't stop a server that trickles
    bytes just under the gap (observed: a 95-min hang under timeout=300), and
    closing the socket from another thread doesn't reliably wake a blocked read.
    So the call runs in a daemon worker and we join with the deadline — if it
    overruns we abandon the thread (it dies with the process) and raise."""
    box = {}

    def _work():
        try:
            r = requests.post(url, headers=headers, json=body,
                              timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            box["resp"] = r
            box["status"], box["raw"] = r.status_code, r.content
        except Exception as e:                          # noqa: BLE001 — surfaced below
            box["err"] = e

    th = threading.Thread(target=_work, daemon=True)
    th.start()
    th.join(HARD_DEADLINE)
    if th.is_alive():
        try:
            if "resp" in box:
                box["resp"].close()
        except Exception:
            pass
        raise requests.exceptions.Timeout(
            f"hard deadline {HARD_DEADLINE:.0f}s exceeded")
    if "err" in box:
        raise box["err"]
    return box["status"], box["raw"]


def _data_url(image_bytes: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(image_bytes).decode()


def blank_square(px: int = 1024) -> bytes:
    """A white square PNG used as the EDIT BASE so the model returns a 1:1 square
    (Gemini otherwise emits landscape ~1.83:1, which a square book would crop)."""
    buf = io.BytesIO()
    Image.new("RGB", (px, px), (255, 255, 255)).save(buf, "PNG")
    return buf.getvalue()


def to_square(img_bytes: bytes) -> bytes:
    """Safety net: centre-crop any non-square output to 1:1. The model matches the
    reference aspect, so with square refs this is a no-op; if a stray landscape
    slips through it trims left/right (keeping the top/bottom text band intact)."""
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = im.size
    if w == h:
        return img_bytes
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def edit(instruction: str, images: list[bytes], *, model: str | None = None) -> bytes:
    """Edit the FIRST image per `instruction`; later images are references.

    Returns PNG/other bytes of the edited image. Raises on failure.
    """
    return _openrouter_edit(instruction, images, model=model)


def inpaint_region(page_bytes: bytes, box, instruction: str,
                   refs: list[bytes] | None = None, *, margin: float = 0.10,
                   feather: float = 0.06, model: str | None = None) -> bytes:
    """Masked repair: regenerate ONLY the defect region and composite it back.

    Full-page regen re-rolls the whole scene (and reproduces the same 6-leg
    artifact); a global "change only here" instruction isn't respected. Instead
    we crop the flagged box (+context `margin` so the model can blend), fix just
    that crop, then feather-paste it over the original — so every pixel OUTSIDE
    the box is preserved exactly and only the broken region changes.

    box: [x0,y0,x1,y1] normalised (0..1), the defect's bounding box.
    Returns the composited full-page PNG bytes. Raises on edit failure.
    """
    page = Image.open(io.BytesIO(page_bytes)).convert("RGB")
    W, H = page.size
    x0, y0, x1, y1 = box
    # expand by margin for blend context, clamp to frame
    ex0 = max(0.0, x0 - margin); ey0 = max(0.0, y0 - margin)
    ex1 = min(1.0, x1 + margin); ey1 = min(1.0, y1 + margin)
    px0, py0 = int(ex0 * W), int(ey0 * H)
    px1, py1 = int(ex1 * W), int(ey1 * H)
    if px1 - px0 < 8 or py1 - py0 < 8:                    # degenerate box
        raise RuntimeError(f"inpaint box too small: {box}")

    crop = page.crop((px0, py0, px1, py1))
    cbuf = io.BytesIO(); crop.save(cbuf, "PNG")

    instr = (
        "This is a cropped region of a children's storybook illustration. "
        + instruction.strip().rstrip(".") + ". "
        "Keep the SAME framing, camera, art style, colours, lighting and "
        "background — redraw ONLY what is needed to fix the described problem, "
        "and keep the character's identity and outfit identical. Do not zoom, "
        "pan, add or remove other characters.")
    fixed_bytes = edit(instr, [cbuf.getvalue()] + list(refs or []), model=model)
    fixed = Image.open(io.BytesIO(fixed_bytes)).convert("RGB")
    # the model may return a different size; fit it back to the crop box
    fixed = fixed.resize(crop.size, Image.LANCZOS)

    # feathered alpha so the seam blends: solid interior, soft edges
    from PIL import ImageDraw, ImageFilter
    cw, ch = crop.size
    inset = max(1, int(min(cw, ch) * feather))
    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).rectangle(
        (inset, inset, cw - inset, ch - inset), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(1, inset // 2)))

    out = page.copy()
    out.paste(fixed, (px0, py0), mask)
    obuf = io.BytesIO(); out.save(obuf, "PNG")
    return obuf.getvalue()


def generate_with_refs(instruction: str, refs: list[bytes], *,
                       model: str | None = None) -> bytes:
    """Gemini multi-reference GENERATION (not an edit of refs[0]): all images
    are references whose roles must be assigned in `instruction` ("Image 1 is
    Bilbo's design; Image 2 is the art style to match; …"). This is the v7
    primary route where identity lives in role-assigned references."""
    return _openrouter_edit(instruction, refs, model=model)


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
