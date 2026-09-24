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
