"""v3 img2img correction loop — the client's specified flow.

Per page:
  1. MATCH CHARACTERS — a vision judge checks each expected character against the
     locked identity (esp. hat colour; the two dogs are the same golden retriever
     told apart only by green=Bilbo / blue=Obi).
  2. IF WRONG, REGENERATE FROM REFERENCE — the page + the character reference
     sheet(s) (DUO sheet for the dog pair) go to the image editor, which fixes only
     those characters and leaves the rest of the scene intact. Looped until they
     pass (or V3_FIX_TRIES).
  3. PERFECT THE SCENE — a final light pass polishes the scene to match the note,
     guarded: if it breaks a character, the pre-polish page is kept.

Backs up the first render to page_<pg>.orig.png.
"""

import os

from . import editor, toon_io
from .generate_v3 import _char_locks
from .llm import chat_json_image

DATA = "v3/data"
ART = "v3/output/art"
TRIES = int(os.getenv("V3_FIX_TRIES", "2"))

JUDGE_SYSTEM = """\
You check a children's picture-book page against the EXPECTED characters. For \
each expected character, decide if it is present and matches — pay special \
attention to HAT COLOUR and that the two dogs are the SAME golden retriever breed \
distinguished ONLY by hat colour (Bilbo=green, Obi=blue), each with a baseball \
bandana. Reply with ONLY a JSON array:
[{"name":"<name>","present":true|false,"correct":true|false,"issue":"<short>"}]"""


def _refmap(refman):
    return {r["name"]: r["path"] for r in refman["refs"]}


def _present_locks(locks, present):
    return "; ".join(l for l in locks.split("; ") if l.split(" =")[0] in present)


def judge(page_bytes, present_locks):
    v = chat_json_image(JUDGE_SYSTEM, f"EXPECTED characters: {present_locks}", page_bytes)
    return v if isinstance(v, list) else []


def fix_chars(page_bytes, wrong, refman, present_locks):
    names = [w["name"] for w in wrong]
    rm = _refmap(refman)
    imgs = []
    if any(n in ("Bilbo", "Obi") for n in names) and os.path.exists(refman.get("duo", "")):
        imgs.append(open(refman["duo"], "rb").read())
    for n in names:
        if n in ("Bilbo", "Obi"):
            continue
        p = rm.get(n)
        if p and os.path.exists(p):
            imgs.append(open(p, "rb").read())
    issues = "; ".join(f"{w['name']}: {w.get('issue','')}" for w in wrong)
    instr = (
        f"Edit this storybook page to FIX these characters: {issues}. Make each match "
        f"the attached reference sheet(s) EXACTLY — {present_locks}. The two dogs are "
        "the SAME golden retriever, told apart ONLY by hat colour (Bilbo=green, "
        "Obi=blue), each wearing a baseball-print bandana. Keep the background, "
        "composition and the other characters unchanged. No text, letters or boxes."
    )
    return editor.edit(instr, [page_bytes] + imgs)


def perfect_scene(page_bytes, scene):
    instr = (
        f"Polish this children's picture-book illustration so it clearly depicts: "
        f"{scene}. Fix any awkward anatomy or artifacts and improve clarity, but KEEP "
        "each character's identity (breed, hat colour, bandana), their poses and the "
        "overall composition the same. No text, letters, boxes or borders."
    )
    return editor.edit(instr, [page_bytes])


def _wrong(verdict):
    # present-but-incorrect, or expected-but-missing -> both need the reference.
    return [v for v in verdict if not v.get("correct", True)]


def run(only=None, scene_pass=True):
    chars = toon_io.load(f"{DATA}/characters.toon")
    _, locks = _char_locks(chars)
    scenes = {s["page"]: s for s in toon_io.load(f"{DATA}/scenes.toon")["scenes"]}
    refman = toon_io.load(f"{DATA}/refs.toon")

    for pg, s in scenes.items():
        if only and pg not in only:
            continue
        path = f"{ART}/page_{pg}.png"
        if not os.path.exists(path):
            continue
        present = s["chars"]
        plocks = _present_locks(locks, present)
        page = open(path, "rb").read()
        backup = f"{ART}/page_{pg}.orig.png"
        if not os.path.exists(backup):
            open(backup, "wb").write(page)
        print(f"[{pg}] present: {present}")

        # 1-2) match characters, regenerate from reference if wrong
        for attempt in range(1, TRIES + 1):
            verdict = judge(page, plocks)
            for v in verdict:
                tag = "ok" if v.get("correct", True) else f"FIX — {v.get('issue','')}"
                print(f"   {v.get('name','?'):<8} {tag}")
            wrong = _wrong(verdict)
            if not wrong:
                break
            page = fix_chars(page, wrong, refman, plocks)
            open(path, "wb").write(page)
            print(f"   -> characters corrected (attempt {attempt})")

        # 3) perfect the scene (guarded — revert if it breaks a character)
        if scene_pass:
            polished = perfect_scene(page, s["scene"])
            if not _wrong(judge(polished, plocks)):
                page = polished
                open(path, "wb").write(page)
                print("   -> scene perfected")
            else:
                print("   -> scene pass skipped (would break a character)")
    print("correction done.")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    run(only=only)
