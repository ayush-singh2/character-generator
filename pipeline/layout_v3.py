"""v3 layout stage — define each scene's characters + text in COORDINATES.

Generic over the art plan. For every scene the text model reads the illustration
description and returns a composition: a normalised bounding box per character, a
text zone, and which side to keep calm. Stored as TOON (v3/data/layout.toon).
"""

import os

from . import llm, plan_v3, toon_io

from .plan_v3 import DATA

SYSTEM = """\
You are a picture-book art director. Given ONE scene (its illustration description \
and the characters present), lay out the page in normalised coordinates.

Coordinates: 0..1, origin top-left, x = right, y = down. For a two-page SPREAD \
treat the whole thing as one wide 0..1 frame and keep main subjects clear of the \
vertical centre (x≈0.5).

Return ONLY JSON:
{"empty_side":"left|right|top|bottom","text_zone":[x0,y0,x1,y1],
 "chars":[{"name":"","box":[x0,y0,x1,y1],"note":"pose/action"}],
 "composition":"one sentence"}
Rules: boxes must not cover text_zone; size by importance/action; every listed \
character gets exactly one box; prefer the given text side if sensible."""


def build(only=None, data_dir=DATA):
    plan = plan_v3.load(data_dir)
    layouts = []
    for sc in plan["scenes"]:
        pg = plan_v3.page_id(sc)
        if only and pg not in only:
            continue
        desc = plan_v3.scene_desc(sc)
        chars = sc.get("chars", [])
        if not desc:
            continue
        user = (f"SCENE (page {pg}, layout={sc.get('layout','single')}):\n{desc}\n\n"
                f"Characters present: {', '.join(chars) if chars else '(none named)'}\n"
                f"Preferred text side: {sc.get('text_area','top')}. "
                f"Reserve a calm area for: {plan_v3.scene_text(sc)[:120]}")
        try:
            lay = llm.chat_json(SYSTEM, user)
        except Exception as e:
            print(f"  [{pg}] layout failed: {str(e)[:80]}"); continue
        lay["page"] = pg
        layouts.append(lay)
        print(f"  [{pg}] empty={lay.get('empty_side')} chars={[c.get('name') for c in lay.get('chars',[])]}")
    if only and os.path.exists(f"{data_dir}/layout.toon"):
        prev = {l["page"]: l for l in toon_io.load(f"{data_dir}/layout.toon")["layouts"]}
        for l in layouts:
            prev[l["page"]] = l
        layouts = [prev[k] for k in prev]
    toon_io.save({"layouts": layouts}, f"{data_dir}/layout.toon")
    print(f"  -> {data_dir}/layout.toon ({len(layouts)} pages)")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    build(only=only)
