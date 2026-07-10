"""v3 layout stage — define each scene's characters + text in COORDINATES.

For every scene the text model reads the illustration note and returns a
composition: a normalised bounding box for each character, a text zone, and which
side to keep calmer for text. Stored as TOON (v3/data/layout.toon). Downstream,
generate_v3 renders a faint labelled-box sketch from these coordinates so the
image model places characters where the note wants them.
"""

import os

from . import llm, toon_io

DATA = "v3/data"

SYSTEM = """\
You are a picture-book art director. Given ONE scene (its illustration note and \
the characters present), lay out the page in normalised coordinates.

Coordinate system: 0..1, origin top-left, x = right, y = down. For a two-page \
SPREAD treat the whole thing as one wide 0..1 frame and keep the main subjects \
clear of the vertical centre (the gutter, x≈0.5).

Return ONLY JSON:
{
  "empty_side": "left" | "right" | "top" | "bottom",
  "text_zone": [x0,y0,x1,y1],
  "chars": [{"name": "<name>", "box": [x0,y0,x1,y1], "note": "<pose/action>"}],
  "composition": "<one sentence on staging>"
}
Rules: boxes must not cover the text_zone; size boxes by importance and the \
action (a jumping dog is tall and high, a cowering dog is low and small); \
foreground characters are larger. Every listed character gets exactly one box."""


def build(only=None):
    scenes = toon_io.load(f"{DATA}/scenes.toon")["scenes"]
    layouts = []
    for s in scenes:
        pg = s["page"]
        if only and pg not in only:
            continue
        user = (f"SCENE (page {pg}, layout={s['layout']}):\n{s['scene']}\n\n"
                f"Characters present: {', '.join(s['chars'])}\n"
                f"Reserve a calm area for this text: {s['text'][:120]}")
        try:
            lay = llm.chat_json(SYSTEM, user)
        except Exception as e:
            print(f"  [{pg}] layout failed: {str(e)[:80]}")
            continue
        lay["page"] = pg
        layouts.append(lay)
        print(f"  [{pg}] empty={lay.get('empty_side')} "
              f"chars={[c['name'] for c in lay.get('chars', [])]}")
    # merge with any existing layout not re-run
    if only and os.path.exists(f"{DATA}/layout.toon"):
        prev = {l["page"]: l for l in toon_io.load(f"{DATA}/layout.toon")["layouts"]}
        for l in layouts:
            prev[l["page"]] = l
        layouts = [prev[k] for k in sorted(prev)]
    toon_io.save({"layouts": layouts}, f"{DATA}/layout.toon")
    print(f"  -> {DATA}/layout.toon ({len(layouts)} pages)")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    build(only=only)
