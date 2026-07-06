"""Stage 4 — canonical character reference sheets.

For every character in the bible, generate TWO references that together lock
identity across the whole book (see the consistency recipe):
  * portrait   — head & shoulders, locks face / hair / age
  * full_body  — turnaround sheet, locks outfit / proportions

These are generated ONCE and reused as conditioning images for every page.

Run:  python -m pipeline.refs
In:   data/characters.json
Out:  output/refs/<slug>/portrait.png, full_body.png  +  data/refs.json
"""

import json
import os
import re

from . import flux
from .style import load_style_prompt

IN_PATH = "data/characters.json"
REFS_DIR = "output/refs"
MANIFEST = "data/refs.json"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _style(style_prompt: str) -> str:
    return style_prompt or "clean illustrated character design"


def _identity(c: dict) -> str:
    """The shared, canonical description of a character.

    Both the close-up and the full-body prompt are built on top of this exact
    block, so the two references carry *identical* detailing (same hair, eyes,
    face, outfit, palette) and only differ in framing.
    """
    outfit = c.get("default_outfit", {})
    outfit_colors = ", ".join(outfit.get("colors", [])[:4])
    parts = [
        f"{c.get('age_appearance', '')} {c.get('gender', '')}".strip(),
        f"height and build: {c.get('height_build', '')}",
        f"skin tone: {c.get('skin_tone', '')}",
        f"hair: {c.get('hair', '')}",
        f"eyes: {c.get('eyes', '')}",
        f"face: {c.get('face', '')}",
    ]
    feats = ", ".join(c.get("distinguishing_features", [])[:4])
    if feats:
        parts.append(f"distinguishing features: {feats}")
    outfit_desc = outfit.get("description", "")
    if outfit_desc:
        parts.append(f"wearing {outfit_desc}" + (f" ({outfit_colors})" if outfit_colors else ""))
    accessories = ", ".join(c.get("accessories", [])[:3])
    if accessories:
        parts.append(f"accessories: {accessories}")
    palette = ", ".join(c.get("color_palette", [])[:5])
    if palette:
        parts.append(f"colour palette: {palette}")
    # Drop any field whose value came back blank (e.g. "hair: ").
    return ", ".join(p for p in parts if p.rstrip(" :").strip() and not p.endswith((":", ": ")))


def portrait_prompt(c: dict, style_prompt: str = "") -> str:
    """Close view: an extreme head-and-shoulders headshot of ONE single character.

    Note the strong single-subject + tight-crop language: Flux otherwise tends
    to draw a full body or a group, especially when the character name is
    plural. When a reference image is passed (see close_up_edit_prompt), this
    same framing is applied on top of that reference for consistency.
    """
    return (
        "extreme close-up headshot portrait of ONE single solo character, "
        "just the head and shoulders, face fills the whole frame, tightly cropped "
        "at the shoulders, front view looking straight at the viewer, "
        "NOT full body, only one person, single subject, "
        "highly detailed facial features and expression, "
        f"{_identity(c)}, "
        "plain soft neutral background, soft even lighting, "
        "consistent canonical character design. "
        f"Art style: {_style(style_prompt)}"
    )


def close_up_edit_prompt(c: dict, style_prompt: str = "") -> str:
    """Prompt for turning a full-body reference into a matching close-up headshot.

    Used with flux.edit(reference=[full_body_image]) so the face, hair and
    outfit exactly match the full-body turnaround already generated.
    """
    # NOTE: we deliberately do NOT re-describe hair/outfit here. The reference
    # image is the single source of truth — restating the bible's description
    # can conflict with what the full-body actually rendered (e.g. it grew
    # braids) and make the close-up diverge. Trust the picture, not the text.
    return (
        "Create an extreme close-up headshot of the SAME single character shown "
        "in the reference image. "
        "EXACTLY ONE PERSON — no second person, no adult, no parent, no other "
        "figures, no one standing behind. "
        "Copy the reference EXACTLY: the same face, the SAME hairstyle, hair "
        "length and hair colour, the same eyes, and the same clothing as shown in "
        "the reference image. Do NOT change the hair or outfit. "
        "Crop very tightly to just the head and shoulders so the single face fills "
        "the entire frame, front view, looking straight at the viewer, not full body. "
        "Plain soft neutral background. "
        f"Art style: {_style(style_prompt)}"
    )


def full_body_prompt(c: dict, style_prompt: str = "") -> str:
    """Full view: one turnaround sheet with three full-length views of the same character."""
    return (
        "full-body character turnaround model sheet of ONE single solo character, "
        "one image showing the SAME one character "
        "three times side by side at identical scale, identical outfit and identical proportions: "
        "(1) full-length front view, (2) full-length side profile view, (3) full-length back view, "
        "each shown head-to-toe from head to feet in a neutral standing A-pose, "
        f"{_identity(c)}, "
        "the three figures evenly spaced on a plain white background, "
        "orthographic character reference sheet, consistent canonical character design. "
        f"Art style: {_style(style_prompt)}"
    )


def build_refs(only: list[str] | None = None, force: bool = False) -> dict:
    data = json.load(open(IN_PATH))
    style_prompt = load_style_prompt()
    # Resume-friendly: keep prior manifest, skip characters already done.
    manifest = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {}
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)

    for c in data["bible"]:
        name = c["name"]
        if only and name not in only:
            continue
        s = slug(name)
        out_dir = os.path.join(REFS_DIR, s)
        p_path = os.path.join(out_dir, "portrait.png")
        b_path = os.path.join(out_dir, "full_body.png")

        if not force and os.path.exists(p_path) and os.path.exists(b_path):
            print(f"[{name}] already done, skipping")
            manifest[name] = {"slug": s, "portrait": p_path, "full_body": b_path}
            continue

        print(f"[{name}] generating portrait + full_body ...")
        flux.save(flux.generate(portrait_prompt(c, style_prompt)), p_path)
        flux.save(flux.generate(full_body_prompt(c, style_prompt)), b_path)
        manifest[name] = {"slug": s, "portrait": p_path, "full_body": b_path}
        # Persist after each character so a crash never loses prior work.
        json.dump(manifest, open(MANIFEST, "w"), indent=2, ensure_ascii=False)
        print(f"   -> {p_path}, {b_path}")

    json.dump(manifest, open(MANIFEST, "w"), indent=2, ensure_ascii=False)
    return manifest


def main() -> None:
    refs = build_refs()
    print(f"\nReference sets ready for {len(refs)} characters -> {MANIFEST}")


if __name__ == "__main__":
    main()
