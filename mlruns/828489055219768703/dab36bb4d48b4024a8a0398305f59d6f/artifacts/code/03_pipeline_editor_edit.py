def edit(instruction: str, images: list[bytes], *, model: str | None = None) -> bytes:
    """Edit the FIRST image per `instruction`; later images are references.

    Returns PNG/other bytes of the edited image. Raises on failure.
    """
    return _openrouter_edit(instruction, images, model=model)
