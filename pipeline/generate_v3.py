"""v3 page generation — generic, from the art plan + coordinate layout.

For each scene: build an instruction from the chosen STYLE, the scene
(setting/action/mood/camera), textual character placement from the layout
coordinates, and per-character identity locks from the plan. Reference sheets for
the present high-consistency characters (a GROUP sheet when a look-alike group is
fully present) are passed to the image editor. Incidental characters are drawn
from their written description. Output -> v3/output/art/page_<pg>.png.
"""

import os

from . import editor, plan_v3, toon_io

from .plan_v3 import DATA, REFS, ART  # noqa: F401


def _pos_words(box):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    area = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
    h = "left" if cx < 0.34 else "right" if cx > 0.66 else "centre"
    v = "upper" if cy < 0.34 else "lower" if cy > 0.66 else "middle"
    size = "large, foreground" if area > 0.22 else \
           "small, background" if area < 0.08 else "mid-sized"
    return f"{v}-{h}, {size}"


def _placement(lay, text_area):
    lines = []
    for c in (lay or {}).get("chars", []):
        note = f" — {c['note']}" if c.get("note") else ""
        lines.append(f"  - {c['name']}: {_pos_words(c['box'])}{note}")
    side = (lay or {}).get("empty_side") or text_area or "top"
    tz = (f"IMPORTANT: leave the entire {side} ~30% of the frame as genuine OPEN "
          f"background (sky, wall, floor or plain colour) with NO character, face or "
          f"important object in it — this band is reserved for text. Keep all "
          f"characters and key action out of the {side} band.")
    return ("\n".join(lines), tz)


def _refs_for(plan, present, refman):
    """Reference bytes: group sheet if a look-alike group is fully present, else
    individual sheets for present high-consistency characters."""
    by_name = {r["name"]: r["path"] for r in refman.get("refs", [])}
    imgs, covered = [], set()
    for g in refman.get("groups", []):
        members = g.get("members", [])
        if members and all(m in present for m in members) and os.path.exists(g["path"]):
            imgs.append(open(g["path"], "rb").read())
            covered.update(members)
    for n in present:
        if n in covered:
            continue
        p = by_name.get(n)
        if p and os.path.exists(p):
            imgs.append(open(p, "rb").read())
    return imgs[:6]


def generate(only=None, data_dir=DATA):
    os.makedirs(ART, exist_ok=True)
    plan = plan_v3.load(data_dir)
    style = plan_v3.style_text(plan)
    layouts = {}
    lp = f"{data_dir}/layout.toon"
    if os.path.exists(lp):
        layouts = {l["page"]: l for l in toon_io.load(lp)["layouts"]}
    refman = toon_io.load(f"{data_dir}/refs.toon") if os.path.exists(f"{data_dir}/refs.toon") else {}

    for sc in plan["scenes"]:
        pg = plan_v3.page_id(sc)
        if only and pg not in only:
            continue
        present = sc.get("chars", [])
        desc = plan_v3.scene_desc(sc)
        if not desc:
            print(f"  [{pg}] no scene description — skip"); continue
        spread = plan_v3.is_spread(sc)
        placement, tz = _placement(layouts.get(pg), sc.get("text_area"))
        aspect = ("WIDE two-page landscape spread (keep subjects clear of the "
                  "centre gutter)") if spread else "SQUARE single page"
        locks = plan_v3.present_locks(plan, present)
        distinguish = plan_v3.group_distinguish(plan, present)
        instr = (
            f"Create a children's picture-book illustration. STYLE: {style}.\n"
            f"FORMAT: {aspect}.\n"
            f"SCENE: {desc}\n"
            + (f"PLACE THE CHARACTERS (approximate):\n{placement}\n" if placement else "")
            + f"{tz}\n"
            + (f"CHARACTER IDENTITY (match the reference sheets EXACTLY): {locks}.\n"
               if locks else "")
            + (f"KEEP DISTINCT: {distinguish}.\n" if distinguish else "")
            + "Full-bleed art filling the whole frame. Do NOT draw any boxes, "
            "rectangles, panels, borders or grey bars. No text or letters."
        )
        try:
            out = editor.edit(instr, _refs_for(plan, present, refman))
        except Exception as e:
            print(f"  [{pg}] generate failed: {str(e)[:100]}"); continue
        path = f"{ART}/page_{plan_v3.slug(pg)}.png"
        open(path, "wb").write(out)
        print(f"  [{pg}] -> {path}  ({'spread' if spread else 'single'}, {len(present)} chars)")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    generate(only=only)
