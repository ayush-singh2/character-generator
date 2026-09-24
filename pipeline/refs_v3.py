"""v3 reference generation — generic, driven by the art plan.

Generates a clean character reference sheet for every HIGH-consistency character
(from characters.toon), plus a combined GROUP sheet for each look-alike group so
the distinguishing feature is anchored in one image. Incidental one-off characters
are not given references (they are drawn from their text description per scene).

If a character carries a `photo` path (real-person likeness), the sheet is
stylised from that photo; otherwise it is designed from the written appearance.

Run from the book dir:  PYTHONPATH=<repo> python -m pipeline.refs_v3
"""

import io
import os

from PIL import Image

from . import editor, plan_v3, toon_io

from .plan_v3 import REFS

TRIES = int(os.getenv("V3_REF_TRIES", "3"))


def _photo(c):
    p = c.get("photo")
    return open(p, "rb").read() if p and os.path.exists(p) else None


def _style_technique(plan):
    """Style text for REFERENCE SHEETS: technique only (medium, linework,
    lighting). The full book style also describes the SUBJECT ("warm golds for
    the retrievers", "rim lighting on the dogs' fur") — on a solo sheet for a
    different character the image model obeys that flood and draws the book's
    protagonist instead (observed: Mom and the mascot rendered as dogs)."""
    s = plan.get("style")
    if isinstance(s, str):
        return s
    return "; ".join(p for p in (s.get("medium"), s.get("linework"),
                                 s.get("lighting")) if p)


def _sheet_problems(img_bytes, expect):
    """Vision QA on a freshly rendered sheet. Single-shot sheets used to ship
    with missing signature items (caps, bandanas) or the wrong character count,
    and EVERY downstream stage — page conditioning, LoRA training views —
    inherits a sheet defect. Returns a list of problems (empty = good);
    fail-open on any error so a judge outage can't block reference generation."""
    try:
        from . import llm
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        im.thumbnail((640, 640))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        r = llm.chat_json_image(
            "You QA character reference sheets for a picture book.",
            f"Check this reference sheet against the requirements and report "
            f"only REAL violations (wrong character count, a missing or "
            f"wrong-colour signature item like a hat/cap/bandana/collar, wrong "
            f"species/build, or an ADULT-proportioned figure where the "
            f"requirements describe a child/cub/young character — a child must "
            f"read as a child: large head for the body, short limbs, small "
            f"stature). Items the requirements mark as conditional or "
            f"page-specific ('when: pages 4, 9', 'select pages', 'visible on "
            f"cover') MAY legitimately be absent — do NOT report those. A "
            f"portrait view plus a full-body view of the SAME character counts "
            f"as ONE character. Requirements: {expect}. "
            'Reply as JSON: {"problems": ["<short problem>", ...]} — an empty '
            "list if the sheet is correct.",
            buf.getvalue(), mime="image/jpeg")
        return [str(p) for p in (r.get("problems") or [])]
    except Exception:
        return []


def _render_checked(instr, imgs, expect, label):
    """Render a sheet, judge it, and retry with the problems fed back into the
    instruction. Keeps the LAST attempt if none passes (partial > nothing)."""
    out, problems = None, []
    for attempt in range(1, TRIES + 1):
        fix = (" MOST IMPORTANT — the previous attempt had these mistakes, fix "
               "ALL of them: " + "; ".join(problems) + ".") if problems else ""
        out = editor.to_square(editor.edit(instr + fix, imgs))
        problems = _sheet_problems(out, expect)
        if not problems:
            return out
        print(f"    {label} attempt {attempt}: " + "; ".join(problems)[:140])
    print(f"    {label}: keeping last attempt despite problems")
    return out


def generate(only=None, data_dir=None):
    data_dir = data_dir or plan_v3.DATA
    os.makedirs(REFS, exist_ok=True)
    plan = plan_v3.load(data_dir)
    style = _style_technique(plan)

    def want(n):
        return only is None or n in only

    manifest = {"refs": [], "groups": [], "settings": []}
    mpath = f"{data_dir}/refs.toon"
    if only is not None and os.path.exists(mpath):
        # Partial regen must MERGE with the existing manifest: rebuilding from
        # scratch would drop every sheet not in `only` — still on disk, but
        # invisible to every downstream stage.
        manifest = toon_io.load(mpath)
        for k in ("refs", "groups", "settings"):
            manifest.setdefault(k, [])

    def _put(lst, entry, key):
        lst[:] = [e for e in lst if e.get(key) != entry.get(key)]
        lst.append(entry)

    # 1) look-alike group sheets first (shared identity anchor)
    for i, g in enumerate(plan["groups"]):
        members = g.get("members", [])
        if not members or not want(f"group{i}"):
            continue
        specs = "; ".join(plan_v3.char_lock(plan["by"][m])
                          for m in members if m in plan["by"])
        gphoto = _photo(g)   # a group photo (e.g. both real dogs) anchors likeness
        base = ("Using the attached reference PHOTO for the real characters' likeness, "
                if gphoto else "")
        instr = (
            f"{base}Repaint this square canvas as a clean character REFERENCE SHEET in "
            f"this style: {style}. Show these look-alike characters together, full "
            f"body, on a plain white background, clearly DISTINCT from each other: "
            f"{specs}. They must be told apart by: "
            f"{g.get('distinguish','their distinguishing features')}. No text."
        )
        expect = (f"exactly {len(members)} characters ({', '.join(members)}), "
                  f"full body, plain white background, each wearing ALL their "
                  f"signature items in the right colours: {specs}. Distinct by: "
                  f"{g.get('distinguish', '')}")
        try:
            imgs = [editor.blank_square()] + ([gphoto] if gphoto else [])
            out = _render_checked(instr, imgs, expect, f"group{i}")
        except Exception as e:
            print(f"  ! group{i} failed: {str(e)[:80]}"); continue
        path = f"{REFS}/group{i}.png"
        open(path, "wb").write(out)
        _put(manifest["groups"], {"members": members, "path": path,
                                  "distinguish": g.get("distinguish", "")}, "path")
        print(f"  group{i}: {members}{' (photo)' if gphoto else ''}")

    # 2) individual sheets for every high-consistency character
    for c in plan_v3.high_characters(plan):
        name = c["name"]
        if not want(name):
            continue
        photo = _photo(c)
        base = ((f"Using the attached reference PHOTO for likeness — if it shows "
                 f"several characters, take ONLY {name}'s likeness from it — ")
                if photo else "") + \
               f"repaint this square canvas as a clean character REFERENCE SHEET of " \
               f"{name}, drawn as a painterly children's picture-book illustration " \
               f"(NEVER photorealistic), in this style: {style}."
        # Text ages lose to visual priors (Grizzly Greg's sheet came out as a
        # portly ADULT bear despite "8-year-old, 110cm cub" in the lock, and
        # every page inherited it) — spell out child proportions explicitly.
        age = ((c.get("locked_spec") or {}).get("identity") or {}).get("age_years")
        kid = (f" CRITICAL: {name} is a CHILD ({age} years old) — draw with "
               f"unmistakable child proportions: head large relative to the "
               f"body (about 1/4 of total height), short limbs, small round "
               f"build; NEVER adult-proportioned."
               if age is not None and age < 13 else "")
        instr = (
            f"{base} {plan_v3.char_lock(c)}.{kid} Show a clear front PORTRAIT and a "
            "FULL-BODY view side by side, plain white background, friendly expression, "
            f"facing forward. Only {name}; no other character. No text."
        )
        expect = (f"exactly ONE character ({name}) shown as portrait + full-body "
                  f"views of the SAME character, plain white background, drawn as "
                  f"a painterly children's picture-book ILLUSTRATION (a "
                  f"photorealistic render is a violation), wearing ALL signature "
                  f"items in the right colours: {plan_v3.char_lock(c)}")
        # Blank square base forces a 1:1 sheet; a photo (if any) rides along as a
        # likeness reference. to_square is a belt-and-suspenders guarantee.
        try:
            imgs = [editor.blank_square()] + ([photo] if photo else [])
            out = _render_checked(instr, imgs, expect, name)
        except Exception as e:
            print(f"  ! {name} failed: {str(e)[:80]}"); continue
        path = f"{REFS}/{plan_v3.slug(name)}.png"
        open(path, "wb").write(out)
        _put(manifest["refs"], {"name": name, "path": path}, "name")
        print(f"  {name}")

    # 3) location reference per recurring setting — an establishing shot with NO
    #    characters, so every page in that place is drawn from the same location.
    for s in plan.get("settings", []):
        key = s.get("key")
        if not key or not want(f"setting_{key}"):
            continue
        instr = (
            f"Repaint this square canvas as a clean LOCATION / establishing-shot "
            f"REFERENCE in this style: {style}. Depict this place with NO characters "
            f"and NO people at all: {s.get('name','')} — {s.get('description','')}. "
            "Show the architecture, materials, colours and distinctive features clearly "
            "so this exact place can be redrawn consistently on other pages. No text."
        )
        try:
            out = editor.to_square(editor.edit(instr, [editor.blank_square()]))
        except Exception as e:
            print(f"  ! setting {key} failed: {str(e)[:80]}"); continue
        path = f"{REFS}/setting_{plan_v3.slug(key)}.png"
        open(path, "wb").write(out)
        _put(manifest["settings"], {"key": key, "path": path,
                                    "name": s.get("name", ""),
                                    "description": s.get("description", "")}, "key")
        print(f"  setting: {key}")

    toon_io.save(manifest, f"{data_dir}/refs.toon")
    print(f"  -> {data_dir}/refs.toon ({len(manifest['refs'])} refs, "
          f"{len(manifest['groups'])} groups, {len(manifest['settings'])} settings)")

    # Signature-item manifest: catalogue each approved sheet's outfit/accessory
    # items (chest logos etc.) so generate/gate enforce them per page. Fail-open
    # — a cataloguing error must not kill the refs stage.
    try:
        from . import items_v7
        print("  == signature items ==")
        items_v7.build(only=only, data_dir=data_dir)
    except Exception as e:  # noqa: BLE001
        print(f"  ! signature-item build failed: {str(e)[:80]}")

    # Setting manifests: lock each recurring location's floor + fixed props
    # from its rendered sheet (same approved-pixels philosophy as sig items).
    try:
        from . import items_v7
        print("  == setting manifests ==")
        items_v7.build_settings(data_dir=data_dir)
    except Exception as e:  # noqa: BLE001
        print(f"  ! setting manifest build failed: {str(e)[:80]}")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    generate(only=only)
