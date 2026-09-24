# v07_harmonize_img2img_sweep — img2img harmonization sweep (mentor #3)

**status:** fail  |  **family:** B  |  **mentor-suggested:** True  |  **model:** `fal-ai/flux-general/image-to-image`  |  **cost:** ~$0.30  |  **anatomy:** None  |  **cast:** 5/5

## Goal
Blend the pasted composite into one cohesive painting.

## Hypothesis (why we thought it would work)
A low-denoise img2img pass unifies lighting/grain (removes pasted look) while keeping the characters.

## Models used
img2img: fal-ai/flux-general/image-to-image (strength sweep 0.4-0.7)

## Source files / functions involved
- `fal_client.subscribe (inline sweep)`

## What we did
1. Take the pasted Gemini composite as init
2. Run flux img2img at strength 0.4 / 0.5 / 0.6 / 0.7

## Prompt / instruction
One cohesive watercolour yoga-studio scene, five upright animal friends, unified lighting, not pasted. (denoise sweep 0.4-0.7)

## Code — all snippets this pipeline used
```python
# ---- [1] img2img_sweep -----------------------------------------------
for s in (0.4, 0.5, 0.6, 0.7):
    r = fal_client.subscribe('fal-ai/flux-general/image-to-image',
        arguments={'image_url': init_url, 'prompt': prompt,
                   'strength': s, 'num_inference_steps': 36,
                   'image_size': 'square_hd', 'num_images': 1})
    open(f'fal_harm_p23_s{int(s*100)}.png','wb').write(
        requests.get(r['images'][0]['url']).content)

```

## Result
0.4-0.5 still pasted; 0.6 cohesive but shifting; 0.7 beautiful but characters re-invented into generic animals.

## Why it fails / caveat
Denoise<->identity tension: without an identity anchor, 'blend more' = 'drift more'. No strength both blends AND preserves identity.

## What we learned
Rebuilding/harmonizing the whole page trades away consistency. Fix ONLY the defect instead.

## Led to
v08 — surgical masked repair of just the zebra.

