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
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Gemini's image model is best-in-class for localized, identity-preserving edits.
EDIT_MODEL = os.getenv("EDIT_MODEL", "google/gemini-3-pro-image")

MAX_RETRIES = 4
RETRYABLE = (
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)


def _data_url(image_bytes: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(image_bytes).decode()


def edit(instruction: str, images: list[bytes], *, model: str | None = None) -> bytes:
    """Edit the FIRST image per `instruction`; later images are references.

    Returns PNG/other bytes of the edited image. Raises on failure.
    """
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
            resp = requests.post(API_URL, headers=headers, json=body, timeout=300)
            if resp.status_code == 429 or resp.status_code >= 500:
                last_err = RuntimeError(f"editor {resp.status_code}: {resp.text[:200]}")
                raise requests.exceptions.ConnectionError(last_err)
            if resp.status_code != 200:
                raise RuntimeError(f"editor {resp.status_code}: {resp.text[:400]}")
            msg = resp.json().get("choices", [{}])[0].get("message", {})
            imgs = msg.get("images") or []
            if not imgs:
                raise RuntimeError(f"editor returned no image: {str(msg)[:300]}")
            url = imgs[0]["image_url"]["url"]
            return base64.b64decode(url.split(",", 1)[1])
        except RETRYABLE as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
                continue
            raise RuntimeError(f"editor failed after {MAX_RETRIES} attempts: {last_err}") from e
