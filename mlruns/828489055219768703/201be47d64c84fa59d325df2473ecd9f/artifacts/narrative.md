# v13_flux_kontext_instruction — FLUX Kontext instruction edit (our idea; best overall)

**status:** partial  |  **family:** C  |  **mentor-suggested:** False  |  **model:** `fal-ai/flux-pro/kontext/max/multi`  |  **cost:** ~$0.05  |  **anatomy:** None  |  **cast:** 5/5

## Goal
Fix the fused chimera without a mask or denoise dial.

## Hypothesis (why we thought it would work)
An instruction-based editor (image + reference + written fix) localizes by UNDERSTANDING, so no clean mask seam or strength setting is needed.

## Models used
instruction editor: fal-ai/flux-pro/kontext/max/multi (image + reference + written edit instruction)

## Source files / functions involved
- `fal_client.subscribe (Kontext, inline)`

## What we did
1. Feed [error page, Twiggy reference] to FLUX Kontext multi
2. Written instruction: fix only the zebra, keep the rest

## Prompt / instruction
Fix ONLY the striped zebra (chimera with an extra body/legs): make it a single upright bipedal zebra like the reference; keep the giraffe, pig, goat, sheep and studio unchanged.

## Code — all snippets this pipeline used
```python
# ---- [1] kontext_call ------------------------------------------------
err_url = fal_client.upload_file(original_page)
ref_url = fal_client.upload_file(f'{REFS}/twiggy.png')
r = fal_client.subscribe('fal-ai/flux-pro/kontext/max/multi',
    arguments={'prompt': 'Fix ONLY the striped zebra ... keep the rest unchanged',
               'image_urls': [err_url, ref_url],
               'num_images': 1, 'guidance_scale': 3.5})
open('kontext_fix_p23.png','wb').write(
    requests.get(r['images'][0]['url']).content)

```

## Result
BEST result: cohesive, NOT pasted, all 5 present, correct watercolour style, 14s / ~$0.05.

## Why it fails / caveat
Redrew the WHOLE scene (composition/poses changed) and the zebra came out half-cut at the frame edge — a framing/instruction issue, far more fixable than the fundamental walls the other methods hit.

## What we learned
Instruction-based editing is the RIGHT class of tool; remaining issues are prompt/framing tuning.

## Led to
v14 — tune Kontext for framing + composition preservation.

