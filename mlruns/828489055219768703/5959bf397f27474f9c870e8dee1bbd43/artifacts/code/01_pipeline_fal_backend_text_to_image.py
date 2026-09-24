def text_to_image(prompt: str, *, steps: int = 28) -> bytes:
    """Generate a character-free background plate."""
    fc = _client()
    r = fc.subscribe(_T2I_EP, arguments={
        "prompt": prompt, "image_size": "square_hd",
        "num_images": 1, "num_inference_steps": steps})
    return _download((r.get("images") or [{}])[0]["url"])
