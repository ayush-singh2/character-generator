"""v3 img2img correction loop — generic, the client's specified flow.

Per page:
  1. MATCH CHARACTERS — a vision judge checks each present character against its
     locked identity from the plan (and any look-alike distinction).
  2. IF WRONG, REGENERATE FROM REFERENCE — the page + the character reference
     sheet(s) (GROUP sheet when a look-alike group is fully present) go to the
     image editor, which fixes only those characters. Looped up to V3_FIX_TRIES.
  3. PERFECT THE SCENE — a guarded final polish; reverted if it breaks a character.

Backs up the first render to page_<pg>.orig.png. Resilient: a page that errors is
skipped, not fatal.
"""

import io
import os

from PIL import Image

from . import editor, plan_v3, toon_io
from .llm import chat_json_image


def _small(img_bytes, maxpx=896):
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    if max(im.size) > maxpx:
        s = maxpx / max(im.size)
        im = im.resize((int(im.width * s), int(im.height * s)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()

from .plan_v3 import DATA, ART  # noqa: F401
TRIES = int(os.getenv("V3_FIX_TRIES", "2"))

JUDGE_SYSTEM = """\
You check a children's picture-book page against the EXPECTED characters. Be STRICT
about identity — small drift matters because the character must look IDENTICAL on
every page. For each expected character check ALL of: species/type, hair (style,
colour, length), skin tone, outfit and its colours, and every signature item
(hats, accessories, collars, logos). Mark correct=false if ANY of these differs
from the description, even slightly. If two look-alike characters are noted, verify
they are clearly distinct. Reply ONLY JSON, naming the exact mismatch:
[{"name":"<name>","present":true|false,"correct":true|false,"issue":"<what differs>"}]"""


def _refmap(refman):
    return {r["name"]: r["path"] for r in refman.get("refs", [])}


def judge(page_bytes, locks, distinguish):
    extra = f" Keep distinct: {distinguish}." if distinguish else ""
    v = chat_json_image(JUDGE_SYSTEM, f"EXPECTED characters: {locks}.{extra}",
                        _small(page_bytes), mime="image/jpeg")
    return v if isinstance(v, list) else []


def fix_chars(page_bytes, wrong, plan, present, refman, locks, distinguish):
    names = [w["name"] for w in wrong]
    rm = _refmap(refman)
    imgs, covered = [], set()
    for g in refman.get("groups", []):
        members = g.get("members", [])
        if any(n in members for n in names) and all(m in present for m in members) \
           and os.path.exists(g["path"]):
            imgs.append(open(g["path"], "rb").read())
            covered.update(members)
    for n in names:
        if n in covered:
            continue
        p = rm.get(n)
        if p and os.path.exists(p):
            imgs.append(open(p, "rb").read())
    issues = "; ".join(f"{w['name']}: {w.get('issue','')}" for w in wrong)
    instr = (
        f"Edit this storybook page to FIX these characters: {issues}. Make each match "
        f"the attached reference sheet(s) EXACTLY — {locks}."
        + (f" Keep look-alikes distinct: {distinguish}." if distinguish else "")
        + " Keep the background, composition and the other characters unchanged. "
        "No text, letters or boxes."
    )
    return editor.edit(instr, [page_bytes] + imgs[:6])


def perfect_scene(page_bytes, desc):
    instr = (
        f"Polish this children's picture-book illustration so it clearly depicts: "
        f"{desc}. Fix awkward anatomy or artifacts and improve clarity, but KEEP each "
        "character's identity, poses and the overall composition the same. No text, "
        "letters, boxes or borders."
    )
    return editor.edit(instr, [page_bytes])


def _wrong(verdict):
    return [v for v in verdict if not v.get("correct", True)]


def run(only=None, scene_pass=True, data_dir=DATA):
    plan = plan_v3.load(data_dir)
    refman = toon_io.load(f"{data_dir}/refs.toon") if os.path.exists(f"{data_dir}/refs.toon") else {}
    for sc in plan["scenes"]:
        pg = plan_v3.page_id(sc)
        if only and pg not in only:
            continue
        present = sc.get("chars", [])
        if not present:
            continue
        path = f"{ART}/page_{plan_v3.slug(pg)}.png"
        if not os.path.exists(path):
            continue
        locks = plan_v3.present_locks(plan, present)
        distinguish = plan_v3.group_distinguish(plan, present)
        backup = f"{ART}/page_{plan_v3.slug(pg)}.orig.png"
        if not os.path.exists(backup):
            open(backup, "wb").write(open(path, "rb").read())
        print(f"[{pg}] present: {len(present)} chars")
        try:
            _correct_one(path, sc, plan, present, locks, distinguish, refman, scene_pass)
        except Exception as e:
            print(f"   ! {pg}: correction skipped ({str(e)[:100]})")
    print("correction done.")


def _correct_one(path, sc, plan, present, locks, distinguish, refman, scene_pass):
    page = open(path, "rb").read()
    for attempt in range(1, TRIES + 1):
        verdict = judge(page, locks, distinguish)
        for v in verdict:
            tag = "ok" if v.get("correct", True) else f"FIX — {v.get('issue','')}"
            print(f"   {str(v.get('name','?'))[:22]:<22} {tag}")
        wrong = _wrong(verdict)
        if not wrong:
            break
        page = fix_chars(page, wrong, plan, present, refman, locks, distinguish)
        open(path, "wb").write(page)
        print(f"   -> characters corrected (attempt {attempt})")
    if scene_pass:
        polished = perfect_scene(page, plan_v3.scene_desc(sc))
        if not _wrong(judge(polished, locks, distinguish)):
            open(path, "wb").write(polished)
            print("   -> scene perfected")
        else:
            print("   -> scene pass skipped (would break a character)")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    run(only=only)
