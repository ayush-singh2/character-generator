"""v3 page generation — render each scene from its coordinate layout + refs.

Uses the image editor (Gemini) as a reference-conditioned generator: it gets a
faint labelled-box SKETCH built from the layout coordinates, the correct
character reference sheet(s) (the DUO sheet when both dogs are present, so the
green-vs-blue-hat contrast is anchored), and an instruction with the scene, the
V6 style, and per-character identity locks. Output -> v3/output/art/page_<pg>.png.
"""

import os

from . import editor, toon_io

DATA = "v3/data"
REFS = "v3/refs"
ART = "v3/output/art"


def _char_locks(chars):
    by = {c["name"]: c for c in chars["characters"]}
    lines = []
    for c in chars["characters"]:
        bits = [c["species"]]
        if c.get("hat"):
            bits.append("wears " + c["hat"])
        if c.get("bandana"):
            bits.append(c["bandana"])
        lines.append(f"{c['name']} = {', '.join(bits)} ({c['distinguish']})")
    return by, "; ".join(lines)


def _pos_words(box):
    """Turn a normalised box into a plain-language position + size phrase."""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    area = max(0.0, (box[2] - box[0])) * max(0.0, (box[3] - box[1]))
    h = "left" if cx < 0.34 else "right" if cx > 0.66 else "centre"
    v = "upper" if cy < 0.34 else "lower" if cy > 0.66 else "middle"
    size = "large, in the foreground" if area > 0.22 else \
           "small, further back" if area < 0.08 else "mid-sized"
    return f"{v}-{h}, {size}"


def _layout_text(layout):
    """Describe the coordinate layout in words (no drawn sketch to leak)."""
    lines = []
    for c in layout.get("chars", []):
        note = f" — {c['note']}" if c.get("note") else ""
        lines.append(f"  - {c['name']}: {_pos_words(c['box'])}{note}")
    tz = layout.get("text_zone")
    side = layout.get("empty_side", "top")
    tzline = (f"Keep the {side} region (about the {side} "
              f"{'third' if side in ('left','right') else 'quarter'}) calm and "
              "nearly empty — soft sky/plain background only — for text later.")
    return "\n".join(lines), tzline


def _refs_for(present, refman):
    """Reference image bytes for the present characters (duo sheet for the pair)."""
    by = {r["name"]: r["path"] for r in refman["refs"]}
    imgs, covered = [], set()
    dogs = [n for n in present if n in ("Bilbo", "Obi")]
    if len(dogs) == 2 and os.path.exists(refman.get("duo", "")):
        imgs.append(open(refman["duo"], "rb").read())
        covered.update(dogs)
    for n in present:
        if n in covered:
            continue
        p = by.get(n)
        if p and os.path.exists(p):
            imgs.append(open(p, "rb").read())
    return imgs[:6]


def generate(only=None):
    os.makedirs(ART, exist_ok=True)
    chars = toon_io.load(f"{DATA}/characters.toon")
    style = chars.get("style", "")
    by, locks = _char_locks(chars)
    scenes = {s["page"]: s for s in toon_io.load(f"{DATA}/scenes.toon")["scenes"]}
    layouts = {l["page"]: l for l in toon_io.load(f"{DATA}/layout.toon")["layouts"]}
    refman = toon_io.load(f"{DATA}/refs.toon")

    for pg, s in scenes.items():
        if only and pg not in only:
            continue
        lay = layouts.get(pg)
        if not lay:
            print(f"  [{pg}] no layout — skip"); continue
        present = s["chars"]
        spread = s.get("layout") == "spread"
        present_locks = "; ".join(l for l in locks.split("; ")
                                  if l.split(" =")[0] in present)
        placement, tzline = _layout_text(lay)
        aspect = ("WIDE two-page landscape spread (keep subjects clear of the "
                  "centre gutter)") if spread else "SQUARE single page"
        instr = (
            f"Create a children's picture-book illustration. STYLE: {style}.\n"
            f"FORMAT: {aspect}.\n"
            f"SCENE: {s['scene']}\n"
            f"COMPOSITION: {lay.get('composition','')}\n"
            f"PLACE THE CHARACTERS (approximate positions):\n{placement}\n{tzline}\n"
            f"CHARACTER IDENTITY (match the reference sheets EXACTLY): {present_locks}. "
            "The two dogs are the SAME breed and the SAME warm golden colour as the "
            "reference; tell them apart ONLY by hat colour (Bilbo=green, Obi=blue), "
            "each wearing a baseball-print bandana.\n"
            "Full-bleed art filling the whole frame. Do NOT draw any boxes, "
            "rectangles, panels, borders, frames or grey bars. No text or letters."
        )
        try:
            out = editor.edit(instr, _refs_for(present, refman))
        except Exception as e:
            print(f"  [{pg}] generate failed: {str(e)[:100]}"); continue
        path = f"{ART}/page_{pg}.png"
        open(path, "wb").write(out)
        print(f"  [{pg}] -> {path}  ({'spread' if spread else 'single'}, {present})")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    generate(only=only)
