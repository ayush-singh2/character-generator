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
