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
