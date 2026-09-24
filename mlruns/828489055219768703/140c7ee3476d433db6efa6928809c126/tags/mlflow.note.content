# v00_original_gemini — One-shot Gemini render (the defect appears)

**status:** fail  |  **family:** baseline  |  **mentor-suggested:** False  |  **model:** `google/gemini-3-pro-image`  |  **cost:** ~$0.00  |  **anatomy:** 0  |  **cast:** 5/5

## Goal
Produce page 23 the normal way and see the defect.

## Hypothesis (why we thought it would work)
The standard pipeline (multi-reference Gemini) can draw the whole page correctly from the scene text + character sheets.

## Models used
image: google/gemini-3-pro-image (via OpenRouter) | text: moonshotai/kimi-k2.6 | audit: anthropic/claude-sonnet-4.5

## Source files / functions involved
- `generate_v7.generate`
- `editor.generate_with_refs`

## What we did
1. generate_v7 builds a prompt from scene + character locked-specs
2. Gemini renders the full page in ONE call from the reference sheets
3. gate/audit scores the page

## Prompt / instruction
(scene prompt) Yoga studio; Ferdinand, Boaris, Twiggy, Wooliam, Tallia doing poses; render faithfully from each character's reference sheet.

## Code — all snippets this pipeline used
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

## Result
All 5 animals present and integrated, BUT the zebra is a chimera: a bipedal torso fused with a full four-legged zebra body ('6 legs').

## Why it fails / caveat
The generator decides body layout itself; with 5 animals it fused two body plans. Text can't reliably constrain anatomy/counting.

## What we learned
The base art is GOOD (integrated, not pasted) — only one localized defect. Reframes the problem: fix the defect, don't rebuild.

## Led to
v01 — constrain layout with a blocking image.

