"""Flux image client (OpenRouter /images endpoint).

Two operations:
  * generate(prompt)                  — text-to-image
  * edit(prompt, reference_images=[]) — image(s) + text, used to keep a
                                        character consistent by passing its
                                        reference sheet back in on every page.

Returned images are PNG bytes. The endpoint replies with base64 in
data[0].b64_json; reference images are passed in as data: URLs.
"""

import base64
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://openrouter.ai/api/v1/images"
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "black-forest-labs/flux.2-max")

MAX_RETRIES = 4
RETRYABLE = (
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)


class ModerationError(RuntimeError):
    """Black Forest Labs refused the prompt as moderated content (non-retryable)."""


def _data_url(image_bytes: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(image_bytes).decode()


def _post(body: dict) -> bytes:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(API_URL, headers=headers, json=body, timeout=300)
            if resp.status_code == 429 or resp.status_code >= 500:
                # Rate-limited or server error: back off and retry.
                last_err = RuntimeError(f"Flux {resp.status_code}: {resp.text[:200]}")
                raise requests.exceptions.ConnectionError(last_err)
            if resp.status_code == 400 and "Moderated" in resp.text:
                raise ModerationError(resp.text[:300])
            if resp.status_code != 200:
                raise RuntimeError(f"Flux {resp.status_code}: {resp.text[:400]}")
            j = resp.json()
            if "data" not in j or not j["data"]:
                raise RuntimeError(f"No image returned: {str(j)[:400]}")
            return base64.b64decode(j["data"][0]["b64_json"])
        except RETRYABLE as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)  # 2s, 4s, 6s backoff
                continue
            raise RuntimeError(f"Flux failed after {MAX_RETRIES} attempts: {last_err}") from e


def generate(prompt: str, *, model: str | None = None) -> bytes:
    return _post({"model": model or IMAGE_MODEL, "prompt": prompt})


def edit(prompt: str, reference_images: list[bytes], *, model: str | None = None) -> bytes:
    """Generate from a prompt conditioned on one or more reference images."""
    body = {
        "model": model or IMAGE_MODEL,
        "prompt": prompt,
        "images": [_data_url(b) for b in reference_images],
    }
    return _post(body)


def save(image_bytes: bytes, path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path
