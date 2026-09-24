# v05_fal_background_plate — fal/Flux background plate (mentor #3)

**status:** success  |  **family:** B  |  **mentor-suggested:** True  |  **model:** `fal-ai/flux/dev`  |  **cost:** ~$0.03  |  **anatomy:** None  |  **cast:** 0/5

## Goal
Build the empty room as a clean base; test Flux style vs approved look.

## Hypothesis (why we thought it would work)
A character-free plate is easy and gives a correct background to place characters onto.

## Models used
text-to-image: fal-ai/flux/dev

## Source files / functions involved
- `fal_backend.text_to_image`

## What we did
1. Call fal flux/dev with 'empty studio, no characters'
2. Download the plate

## Prompt / instruction
Empty bright yoga studio: wooden floor, windows, plants, candle shelf, mats. NO characters. Soft watercolour, calm floor for text.

## Code — all snippets this pipeline used
```python
# ---- [1] pipeline.fal_backend.text_to_image --------------------------
def text_to_image(prompt: str, *, steps: int = 28) -> bytes:
    """Generate a character-free background plate."""
    fc = _client()
    r = fc.subscribe(_T2I_EP, arguments={
        "prompt": prompt, "image_size": "square_hd",
        "num_images": 1, "num_inference_steps": steps})
    return _download((r.get("images") or [{}])[0]["url"])

```

## Result
Excellent empty studio; Flux watercolour matches the approved style (style risk LOW).

## Why it fails / caveat
No failure — solid foundation.

## What we learned
fal/Flux is viable style-wise; the plate step is reliable.

## Led to
v06 — place a character into the plate with IP-Adapter.

