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
