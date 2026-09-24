def generate_with_refs(instruction: str, refs: list[bytes], *,
                       model: str | None = None) -> bytes:
    """Gemini multi-reference GENERATION (not an edit of refs[0]): all images
    are references whose roles must be assigned in `instruction` ("Image 1 is
    Bilbo's design; Image 2 is the art style to match; …"). This is the v7
    primary route where identity lives in role-assigned references."""
    return _openrouter_edit(instruction, refs, model=model)
