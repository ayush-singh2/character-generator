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
