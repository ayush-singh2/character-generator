# v00_original_gemini — all code snippets used

```python
# ---- [1] call --------------------------------------------------------
from pipeline import generate_v7
generate_v7.generate(only=['23'])   # -> output/art/page_23.png

# ---- [2] pipeline.editor.generate_with_refs --------------------------
def generate_with_refs(instruction: str, refs: list[bytes], *,
                       model: str | None = None) -> bytes:
    """Gemini multi-reference GENERATION (not an edit of refs[0]): all images
    are references whose roles must be assigned in `instruction` ("Image 1 is
    Bilbo's design; Image 2 is the art style to match; …"). This is the v7
    primary route where identity lives in role-assigned references."""
    return _openrouter_edit(instruction, refs, model=model)

```
