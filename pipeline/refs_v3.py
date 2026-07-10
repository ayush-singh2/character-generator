"""v3 reference generation — fresh, correct, distinct character sheets.

Grounded in the manuscript, not v4/v5. The author's real photo
(manuscript_media/notes-000.png) shows both dogs with the CORRECT hats
(Bilbo green, Obi blue) + baseball bandanas; we stylise it into clean reference
sheets in the client's V6 picture-book style. Look-alikes get a single DUO sheet
so the green-vs-blue-hat contrast is locked in one image.

Humans (Mom/Dad) use their real photos directly as references.

Run from the book dir:
    PYTHONPATH=<repo> python -m pipeline.refs_v3
"""

import os

from . import editor, toon_io

DATA = "v3/data"
REFS = "v3/refs"
PHOTO = "manuscript_media/notes-000.png"          # real photo of both dogs
STYLE_REF = "manuscript_media/v6-03.png"          # a V6 interior page for style


def _style(chars):
    return chars.get("style", "soft classic children's picture-book illustration")


def _by_name(chars):
    return {c["name"]: c for c in chars["characters"]}


def generate(only=None):
    os.makedirs(REFS, exist_ok=True)
    chars = toon_io.load(f"{DATA}/characters.toon")
    style = _style(chars)
    by = _by_name(chars)
    photo = open(PHOTO, "rb").read()
    style_ref = open(STYLE_REF, "rb").read() if os.path.exists(STYLE_REF) else None
    style_imgs = [style_ref] if style_ref else []

    def want(n):
        return (only is None) or (n in only)

    # 1) DUO sheet — both golden retrievers together, distinguished by hat colour.
    if want("duo"):
        instr = (
            f"Using the reference PHOTO of two real golden retrievers, draw a clean "
            f"character REFERENCE SHEET in this style: {style}. Show BOTH dogs, full "
            "body, standing side by side on a plain white background, facing forward. "
            "The dog on the LEFT is BILBO wearing a LIGHT GREEN baseball cap; the dog "
            "on the RIGHT is OBI wearing a LIGHT BLUE baseball cap. Both wear a bandana "
            "with a baseball print. They are the SAME breed (golden retriever) and must "
            "be clearly told apart ONLY by hat colour (green=Bilbo, blue=Obi). No text."
        )
        out = editor.edit(instr, [photo] + style_imgs)
        open(f"{REFS}/duo_dogs.png", "wb").write(out)
        print("  duo_dogs.png")

    # 2) Individual sheets for the two dogs, cut from the same look.
    for name, hat in (("Bilbo", "LIGHT GREEN"), ("Obi", "LIGHT BLUE")):
        if not want(name):
            continue
        instr = (
            f"Using the reference PHOTO, draw a clean single-character REFERENCE SHEET "
            f"of {name} in this style: {style}. {name} is a golden retriever wearing a "
            f"{hat} baseball cap and a bandana with a baseball print. Show a clear "
            "front portrait AND a full-body view, plain white background, facing "
            f"forward, friendly expression. Only {name}. No other dog. No text."
        )
        out = editor.edit(instr, [photo] + style_imgs)
        open(f"{REFS}/{name.lower()}.png", "wb").write(out)
        print(f"  {name.lower()}.png")

    # 3) Homer the dragon mascot (no photo — from description + style).
    if want("Homer"):
        h = by.get("Homer", {})
        instr = (
            f"Draw a clean character REFERENCE SHEET in this style: {style}. A friendly "
            "team mascot: a person in a big GREEN dragon costume with giant green wings, "
            "wearing a baseball cap and jersey, full body, plain white background, "
            "smiling. No text."
        )
        out = editor.edit(instr, style_imgs or [])
        open(f"{REFS}/homer.png", "wb").write(out)
        print("  homer.png")

    # 4) Humans — stylise their real photo into a matching character sheet so
    #    they read as book characters (likeness anchored to the real photo).
    for name, src in (("Mom", "../../CLIENT_DOC/ref_img/mom.jpg"),
                      ("Dad", "../../CLIENT_DOC/ref_img/dad.jpg")):
        if not want(name):
            continue
        if not os.path.exists(src):
            print(f"  ! {name}: photo not found at {src}"); continue
        photo_h = open(src, "rb").read()
        instr = (
            f"Using the reference PHOTO of a real person, draw a clean character "
            f"REFERENCE SHEET of {name} in this style: {style}. Keep their real "
            "likeness (face, hair, build). Show a front portrait and a full-body "
            f"view, plain white background, friendly. Only {name}. No text."
        )
        out = editor.edit(instr, [photo_h] + style_imgs)
        open(f"{REFS}/{name.lower()}.png", "wb").write(out)
        print(f"  {name.lower()}.png (stylised from photo)")

    # manifest so downstream stages know where each ref is.
    man = {"refs": []}
    for n in ("Bilbo", "Obi", "Homer", "Mom", "Dad"):
        for ext in ("png", "jpg"):
            p = f"{REFS}/{n.lower()}.{ext}"
            if os.path.exists(p):
                man["refs"].append({"name": n, "path": p})
                break
    man["duo"] = f"{REFS}/duo_dogs.png"
    toon_io.save(man, f"{DATA}/refs.toon")
    print("  -> v3/data/refs.toon")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    generate(only=only)
