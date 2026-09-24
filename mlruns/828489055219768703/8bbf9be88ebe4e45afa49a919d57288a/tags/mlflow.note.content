# v12_auto_mask_wrapper — Auto-mask + repair wrapper (fused case fails)

**status:** fail  |  **family:** C  |  **mentor-suggested:** True  |  **model:** `fal-ai/flux-general/inpainting (+ anthropic/claude-sonnet-4.5 detect)`  |  **cost:** ~$1.00  |  **anatomy:** 100  |  **cast:** 4/5

## Goal
Turn v10/v11 into an automatic, reusable repair pass.

## Hypothesis (why we thought it would work)
Detect defect box -> auto neighbour-safe mask -> classify ERASE vs REDRAW -> inpaint -> re-audit -> revert if worse.

## Models used
inpaint: fal-ai/flux-general/inpainting | detection/anomaly-locate: anthropic/claude-sonnet-4.5 (VISION_MODEL) | IP-Adapter on REDRAW

## Source files / functions involved
- `fal_repair.repair_page`
- `fal_repair.repair_defect`
- `fal_repair._clip_to_neighbors`
- `fal_repair._is_erase`
- `anatomy_v8.locate_anomaly`

## What we did
1. Multi-pass anatomy detection (stochastic, so retry)
2. locate_anomaly boxes the extra part; _clip_to_neighbors shrinks it
3. ERASE to background or REDRAW with IP-Adapter
4. re-audit; revert if defect count rises

## Prompt / instruction
(auto) ERASE extra part to background, OR REDRAW single upright {species} with IP-Adapter, per classification.

## Code — all snippets this pipeline used
```python
# ---- [1] pipeline.fal_repair._is_erase -------------------------------
def _is_erase(issue: str) -> bool:
    s = (issue or "").lower()
    if any(h in s for h in _REDRAW_HINTS) and not any(h in s for h in _ERASE_HINTS):
        return False
    if any(h in s for h in _ERASE_HINTS):
        return True
    # default: prefer ERASE (identity-safe) unless clearly a whole-figure redraw
    return True

# ---- [2] pipeline.fal_repair._clip_to_neighbors ----------------------
def _clip_to_neighbors(box, others, *, pad: float = 0.01):
    """Shrink `box` so it does not overlap any box in `others`. For each
    neighbour that overlaps, push whichever of box's edges is nearest the
    neighbour inward past the neighbour's edge (+pad). Neighbour-safety first:
    better to mask slightly less than to eat an adjacent character."""
    x0, y0, x1, y1 = box
    for o in others:
        ox0, oy0, ox1, oy1 = o
        # skip if no overlap
        if x1 <= ox0 or x0 >= ox1 or y1 <= oy0 or y0 >= oy1:
            continue
        # horizontal push: if neighbour is to our left, raise x0; to our right, lower x1
        ncx = (ox0 + ox1) / 2
        bcx = (x0 + x1) / 2
        if ncx < bcx:                 # neighbour on the left → cut left edge
            x0 = max(x0, ox1 + pad)
        else:                         # neighbour on the right → cut right edge
            x1 = min(x1, ox0 - pad)
    if x1 - x0 < 0.03 or y1 - y0 < 0.03:
        return None                   # nothing safe left to mask
    return [x0, y0, x1, y1]

# ---- [3] pipeline.anatomy_v8.locate_anomaly --------------------------
def locate_anomaly(page_bytes: bytes, fig: dict, issue: str):
    """Box of ONLY the anomalous part of a defect (e.g. the extra hindquarters/
    legs), so an ERASE repair removes just that and preserves the real
    character. Returns a normalised [x0,y0,x1,y1] or None. Zooms on the figure
    (wide margin) and asks the VLM to box the extra/duplicated part."""
    crop_box = fig["box"]
    user = (
        f"This crop contains a {fig.get('species','animal')} that has an "
        f"ANATOMY DEFECT: {issue}. Return a TIGHT normalised bounding box "
        f"(0..1 over THIS FULL PAGE image) around ONLY the extra/duplicated/"
        f"anomalous part (the extra body, extra legs, or floating limb) — NOT "
        f"the whole correct character, and NOT any neighbouring character.\n"
        f'Return JSON: {{"anomaly_box":[x0,y0,x1,y1]}}')
    try:
        r = llm.chat_json_images(_CHECK_SYSTEM, user, [page_bytes], max_tokens=200)
    except Exception:                                        # noqa: BLE001
        return None
    b = r.get("anomaly_box") if isinstance(r, dict) else None
    if isinstance(b, list) and len(b) == 4:
        return [min(max(float(v), 0.0), 1.0) for v in b]
    return None

# ---- [4] pipeline.fal_repair.repair_defect ---------------------------
def repair_defect(page_bytes, defect, figures, refs, *, rounds_note=""):
    """Repair one defect surgically. Returns (new_bytes, info)."""
    from PIL import Image
    import io
    W, H = Image.open(io.BytesIO(page_bytes)).size

    others = [f["box"] for f in figures if f is not defect.get("_fig")]
    erase = _is_erase(defect.get("issue", ""))

    if erase:
        # target only the anomalous sub-region
        target = anatomy_v8.locate_anomaly(page_bytes, defect["_fig"], defect["issue"])
        target = target or defect["box"]
        mode = "ERASE"
    else:
        target = defect["box"]
        mode = "REDRAW"

    safe = _clip_to_neighbors(target, others)
    if safe is None:
        return page_bytes, {"mode": mode, "skipped": "no neighbour-safe mask"}

    mask = fal_backend.make_mask((W, H), safe)
    sp = defect.get("species", "character")
    if erase:
        prompt = (f"clean empty background matching the surrounding scene "
                  f"(floor, wall, plants) — no animal, no extra legs, no {sp} "
                  f"body here; soft watercolour children's book style")
        new = fal_backend.inpaint(page_bytes, mask, prompt, strength=0.95)
    else:
        # REDRAW identity tuning: anchor on BOTH the character sheet (canonical
        # identity, high scale) AND the original in-scene crop (pose/scale/colour
        # of THIS figure) so the species holds ("zebra", not a drifted "cat").
        # Lower strength keeps more of the original structure.
        ref = refs.get(sp) or refs.get(defect.get("name", "").lower())
        ip_refs = []
        if ref:
            ip_refs.append((ref, 1.0))
        crop = _crop_bytes(page_bytes, defect["box"])   # in-scene anchor
        if crop:
            ip_refs.append((crop, 0.6))
        prompt = (f"a single {sp} — clearly a {sp} with its distinctive {sp} "
                  f"markings — standing upright on two legs like a person, two "
                  f"legs and two arms, one coherent body, soft watercolour "
                  f"children's book style, matching the scene")
        new = fal_backend.inpaint(page_bytes, mask, prompt, strength=0.7,
                                  ip_refs=ip_refs)
    return new, {"mode": mode, "box": [round(x, 3) for x in safe]}

# ---- [5] pipeline.fal_repair.repair_page -----------------------------
def repair_page(page_bytes, rules, refs, *, max_defects=4, detect_passes=3):
    """Detect defects, repair each surgically, re-audit. Returns (bytes, report)."""
    za = _detect(page_bytes, rules, detect_passes)
    figures = za.get("figures", [])
    defects = za.get("defects", [])
    for d in defects:                       # attach the figure object for neighbour exclusion
        d["_fig"] = next((f for f in figures
                          if f.get("box") == d.get("box")), {"box": d.get("box")})
    report = {"before_score": za.get("score"), "before_defects": len(defects),
              "actions": []}
    cur = page_bytes
    for d in defects[:max_defects]:
        try:
            cur, info = repair_defect(cur, d, figures, refs)
            report["actions"].append({"issue": d.get("issue", "")[:60], **info})
        except Exception as e:              # noqa: BLE001
            report["actions"].append({"issue": d.get("issue", "")[:60],
                                      "error": str(e)[:80]})
    post = anatomy_v8.audit_anatomy(cur, rules=rules)
    report["after_score"] = post.get("score")
    report["after_defects"] = len(post.get("defects", []))
    # safety: if repair made it worse, keep the original
    if report["after_defects"] > report["before_defects"]:
        report["reverted"] = True
        return page_bytes, report
    return cur, report

```

## Result
Ran end-to-end; on the FUSED chimera it either erased the whole zebra (->plant) or redrew it into a 'cat'. 4/5 cast.

## Why it fails / caveat
A fused chimera has NO clean seam; locate_anomaly boxes the whole figure. Masking needs a separable defect.

## What we learned
Masking is the wrong tool for a FUSED defect. Need an editor that localizes by MEANING.

## Led to
v13 — instruction-based editing (FLUX Kontext).

