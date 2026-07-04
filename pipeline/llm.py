"""Shared OpenRouter chat client for the text stages (character mining,
scene prompting). Image generation has its own client in flux.py.

Kept deliberately small: a `chat_json` helper that calls a Claude model
through OpenRouter and returns parsed JSON (tolerating the ```json code
fences the model sometimes adds), plus `chat_json_image` for the vision
stages (text-placement mapping) that need to look at a generated image.
"""

import base64
import json
import os
import re
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://openrouter.ai/api/v1/chat/completions"
TEXT_MODEL = os.getenv("TEXT_MODEL", "anthropic/claude-sonnet-4.5")
# Vision-capable model for looking at generated art (text placement, QA).
VISION_MODEL = os.getenv("VISION_MODEL", "anthropic/claude-sonnet-4.5")

# Network resiliency: transient hiccups (dropped connections, rate limits,
# 5xx) are retried with backoff rather than crashing the caller.
MAX_RETRIES = 4
RETRYABLE = (
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _strip_fences(s: str) -> str:
    s = s.strip()
    s = _FENCE_RE.sub("", s)
    return s.strip()


def _post_chat(body: dict) -> str:
    """POST a chat-completions request with retries; return the reply text.

    Retries on dropped connections, timeouts, 429s and 5xx with linear
    backoff. Raises RuntimeError once retries are exhausted or on a
    non-retryable non-200.
    """
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    headers = {"Authorization": f"Bearer {key}"}

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(API_URL, headers=headers, json=body, timeout=180)
            if resp.status_code == 429 or resp.status_code >= 500:
                # Rate-limited or server error: back off and retry.
                last_err = RuntimeError(f"OpenRouter {resp.status_code}: {resp.text[:200]}")
                raise requests.exceptions.ConnectionError(last_err)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenRouter {resp.status_code}: {resp.text[:300]}")
            return resp.json()["choices"][0]["message"]["content"]
        except RETRYABLE as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)  # 2s, 4s, 6s backoff
                continue
            raise RuntimeError(f"OpenRouter failed after {MAX_RETRIES} attempts: {last_err}") from e


def chat_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.4,
) -> dict | list:
    """Call the text model and parse its reply as JSON.

    Raises RuntimeError on a non-200, ValueError if the reply isn't JSON.
    """
    content = _post_chat({
        "model": model or TEXT_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    })
    return _parse_json(content)


def chat_json_image(
    system: str,
    user: str,
    image: bytes,
    *,
    mime: str = "image/png",
    model: str | None = None,
    max_tokens: int = 1500,
    temperature: float = 0.2,
) -> dict | list:
    """Call the vision model with one image and parse its reply as JSON.

    `image` is raw image bytes (PNG/JPEG). Used by the text-placement stage
    to read a generated illustration and report where a card may sit.
    Raises RuntimeError on a non-200, ValueError if the reply isn't JSON.
    """
    data_url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
    content = _post_chat({
        "model": model or VISION_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": [
                {"type": "text", "text": user},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]},
        ],
    })
    return _parse_json(content)


def _parse_json(content: str) -> dict | list:
    cleaned = _strip_fences(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback 1: grab the outermost JSON object/array and parse it.
    m = re.search(r"[\{\[].*[\}\]]", cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback 2: the reply was truncated (hit max_tokens) mid-structure —
    # salvage the last complete element and close the open containers.
    repaired = _repair_truncated(cleaned)
    if repaired is not None:
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Model did not return valid JSON:\n{content[:500]}")


def _repair_truncated(s: str) -> str | None:
    """Best-effort repair of JSON truncated mid-output.

    Walks the string tracking string/bracket state and remembers the last
    point where an object inside an array closed cleanly — a safe element
    boundary. Cuts there and appends the closers for the still-open
    containers, turning `{"chars":[{..},{..truncated` into valid JSON.
    """
    stack: list[str] = []
    in_str = escape = False
    cut: int | None = None
    closers = ""
    for i, ch in enumerate(s):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
            # Closed an object whose parent is an array: a clean element boundary.
            if ch == "}" and stack and stack[-1] == "[":
                cut = i + 1
                closers = "".join("]" if c == "[" else "}" for c in reversed(stack))
    if cut is None:
        return None
    return s[:cut] + closers
