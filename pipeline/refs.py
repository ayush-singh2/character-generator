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
    """Close view: a tight head-and-shoulders bust, face filling most of the frame."""
    return (
        "character close-up portrait, head-and-shoulders bust, upper body only, "
        "the face fills most of the frame, front view looking toward the viewer, "
        "highly detailed facial features and expression, "
        f"{_identity(c)}, "
        "plain soft neutral background, soft even lighting, "
        "consistent canonical character design. "
        f"Art style: {_style(style_prompt)}"
    )


def full_body_prompt(c: dict, style_prompt: str = "") -> str:
    """Full view: one turnaround sheet with three full-length views of the same character."""
    return (
        "full-body character turnaround model sheet, one image showing the SAME character "
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
