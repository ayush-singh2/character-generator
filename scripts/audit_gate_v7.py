"""Offline full-book gate audit — re-score every existing art page with the
CURRENT gate (probes only, no image generation). Prints a per-page table and
the pages that would fail the pass thresholds, so a pipeline upgrade can be
applied to a finished book without paying for regeneration to find out where
it matters.

    cd books/<slug> && PYTHONPATH=<repo> python -m scripts.audit_gate_v7 [V3_DIR]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if len(sys.argv) > 1:
    os.environ["V3_DIR"] = sys.argv[1]

from pipeline import gate_v7, generate_v7, items_v7, plan_v3, toon_io  # noqa: E402


def main():
    plan = plan_v3.load(plan_v3.DATA)
    refman = toon_io.load(f"{plan_v3.DATA}/refs.toon")
    by = {r["name"]: r["path"] for r in refman.get("refs", [])}
    lp = f"{plan_v3.DATA}/layout.toon"
    layouts = ({l["page"]: l for l in toon_io.load(lp)["layouts"]}
               if os.path.exists(lp) else {})
    style_plate = generate_v7._style_plate(refman)

    bad = []
    for sc in plan["scenes"]:
        pg = plan_v3.page_id(sc)
        path = f"{plan_v3.ART}/page_{plan_v3.slug(pg)}.png"
        if not os.path.exists(path):
            continue
        img = open(path, "rb").read()
        present = sc.get("chars", [])
        ci = items_v7.page_items(
            {n: items_v7.items_for(plan["by"][n]) for n in present
             if n in plan["by"] and items_v7.items_for(plan["by"][n])}, sc)
        refs = {n: open(by[n], "rb").read() for n in present
                if n in by and os.path.exists(by[n])}
        side = ((layouts.get(pg) or {}).get("empty_side")
                or sc.get("text_area") or "top")
        s = gate_v7.score_page(img, contract=gate_v7.page_contract(sc, plan),
                               char_refs=refs, style_plate=style_plate,
                               char_items=ci,
                               minimal_page=sc.get("role") in (
                                   "title", "dedication", "about_author",
                                   "backmatter"))
        band = ((not plan_v3.wants_panels(sc))
                and generate_v7._band_occupied(img, side, plan_v3.scene_text(sc)))
        fails = generate_v7._failures(s, band)
        row = "  ".join(f"{k}={s.get(k)}" for k in
                        ("identity", "items", "facts", "anatomy", "style"))
        print(f"[{pg:>12}] {row}  total={s['total']}"
              + (f"  FAILS={fails}" if fails else ""))
        for cat in ("items", "anatomy", "facts", "identity"):
            for q, ok in (s.get("detail", {}).get(cat) or {}).items():
                if not ok and cat in fails:
                    print(f"      x [{cat}] ...{q[-110:]}")
        if fails:
            bad.append(pg)
    print("\nwould-fail pages:", bad or "none")


if __name__ == "__main__":
    main()
