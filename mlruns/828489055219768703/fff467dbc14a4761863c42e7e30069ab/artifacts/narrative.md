# v14_next_kontext_tuned — NEXT: tuned Kontext (planned)

**status:** planned  |  **family:** C  |  **mentor-suggested:** False  |  **model:** `fal-ai/flux-pro/kontext/max/multi (planned)`  |  **cost:** ~$0.00  |  **anatomy:** None  |  **cast:** None/5

## Goal
Make Kontext keep all cast fully in-frame + preserve composition, then verify cross-page consistency and wire it into the pipeline.

## Hypothesis (why we thought it would work)
A tighter instruction (keep all in-frame, preserve composition, change only the zebra) + verification turns v13's near-miss into a shippable page.

## Models used
instruction editor: fal-ai/flux-pro/kontext/max/multi | verify: anthropic/claude-sonnet-4.5 (anatomy/cast detector)

## Source files / functions involved
- `(planned) fal_client.subscribe (Kontext)`
- `anatomy_v8.audit_anatomy`

## What we did
1. Kontext edit with framing + preservation constraints
2. Re-verify with the anatomy/cast detector once the vision API recovers
3. Wire Kontext as the repair engine inside fal_repair
4. Test cross-page consistency with shared references

## Prompt / instruction
(planned) Fix the defect only; keep composition and ALL characters fully within the frame; do not crop any character.

## Code — all snippets this pipeline used
```python
# ---- [1] planned -----------------------------------------------------
# fal_client.subscribe('fal-ai/flux-pro/kontext/max/multi', arguments={
#   'prompt': '... keep all characters fully in frame, preserve composition ...',
#   'image_urls': [page, ref]})
# then verify:

# ---- [2] pipeline.anatomy_v8.audit_anatomy ---------------------------
def audit_anatomy(page_bytes: bytes, rules: dict | None = None) -> dict:
    """Full per-figure anatomy pass for a page.

    `rules` = canon_rules dict; when given, each figure is judged against its
    canon body plan (fixes the floor-pose false positive). Returns
    {"score": 0-100|None, "defects": [...], "checked": n, "figures": [...]}.
    score = % of checked figures that are coherent; None if nothing located.
    """
    if not ENABLED:
        return {"score": None, "defects": [], "checked": 0, "figures": []}
    figs = locate_figures(page_bytes)
    if not figs:
        return {"score": None, "defects": [], "checked": 0, "figures": []}
    from . import canon_rules as _cr
    verdicts = [check_figure(
        page_bytes, f,
        expected=_cr.expected_plan(f.get("species", ""), rules) if rules else None)
        for f in figs]
    graded = [v for v in verdicts if v.get("ok") is not None]
    if not graded:
        return {"score": None, "defects": [], "checked": 0, "figures": figs}
    defects = [v for v in graded if v["ok"] is False]
    score = round(100 * (1 - len(defects) / len(graded)))
    for d in defects:
        print(f"    [anatomy-zoom] DEFECT {d['issue']}  box={[round(x,2) for x in d['box']]}")
    return {"score": score, "defects": defects, "checked": len(graded),
            "figures": figs}

```

## Result
(planned — not yet run)

## Why it fails / caveat
(planned — not yet run)

## What we learned
(pending)

## Led to
(the shippable repair pass)

