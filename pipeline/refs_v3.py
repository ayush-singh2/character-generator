"""v3 reference generation — generic, driven by the art plan.

Generates a clean character reference sheet for every HIGH-consistency character
(from characters.toon), plus a combined GROUP sheet for each look-alike group so
the distinguishing feature is anchored in one image. Incidental one-off characters
are not given references (they are drawn from their text description per scene).

If a character carries a `photo` path (real-person likeness), the sheet is
stylised from that photo; otherwise it is designed from the written appearance.

Run from the book dir:  PYTHONPATH=<repo> python -m pipeline.refs_v3
"""

import os

from . import editor, plan_v3, toon_io

REFS = "v3/refs"


def _photo(c):
    p = c.get("photo")
    return open(p, "rb").read() if p and os.path.exists(p) else None


def generate(only=None, data_dir="v3/data"):
    os.makedirs(REFS, exist_ok=True)
    plan = plan_v3.load(data_dir)
    style = plan_v3.style_text(plan)

    def want(n):
        return only is None or n in only

    manifest = {"refs": [], "groups": []}

    # 1) look-alike group sheets first (shared identity anchor)
    for i, g in enumerate(plan["groups"]):
        members = g.get("members", [])
        if not members or not want(f"group{i}"):
            continue
        specs = "; ".join(plan_v3.char_lock(plan["by"][m])
                          for m in members if m in plan["by"])
        instr = (
            f"Draw a clean character REFERENCE SHEET in this style: {style}. Show "
            f"these look-alike characters together, full body, on a plain white "
            f"background, clearly DISTINCT from each other: {specs}. They must be "
            f"told apart by: {g.get('distinguish','their distinguishing features')}. "
            "No text."
        )
        try:
            out = editor.edit(instr, [])
        except Exception as e:
            print(f"  ! group{i} failed: {str(e)[:80]}"); continue
        path = f"{REFS}/group{i}.png"
        open(path, "wb").write(out)
        manifest["groups"].append({"members": members, "path": path,
                                    "distinguish": g.get("distinguish", "")})
        print(f"  group{i}: {members}")

    # 2) individual sheets for every high-consistency character
    for c in plan_v3.high_characters(plan):
        name = c["name"]
        if not want(name):
            continue
        photo = _photo(c)
        base = ("Using the reference PHOTO, " if photo else "") + \
               f"draw a clean character REFERENCE SHEET of {name} in this style: {style}."
        instr = (
            f"{base} {plan_v3.char_lock(c)}. Show a clear front PORTRAIT and a "
            "FULL-BODY view, plain white background, friendly expression, facing "
            f"forward. Only {name}; no other character. No text."
        )
        try:
            out = editor.edit(instr, [photo] if photo else [])
        except Exception as e:
            print(f"  ! {name} failed: {str(e)[:80]}"); continue
        path = f"{REFS}/{plan_v3.slug(name)}.png"
        open(path, "wb").write(out)
        manifest["refs"].append({"name": name, "path": path})
        print(f"  {name}")

    toon_io.save(manifest, f"{data_dir}/refs.toon")
    print(f"  -> {data_dir}/refs.toon "
          f"({len(manifest['refs'])} refs, {len(manifest['groups'])} groups)")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    generate(only=only)
