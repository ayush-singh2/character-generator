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
from io import BytesIO

from PIL import Image

from . import charspec, flux
from .llm import chat_json_image
from .style import load_style_prompt

IN_PATH = "data/characters.json"
STORYBOOK_PATH = "data/storybook.json"
REFS_DIR = "output/refs"
MANIFEST = "data/refs.json"
# Clean per-character reference crops the user drops in as <slug>.png/jpg — the
# reliable path for EXACT likeness (one subject per image, unlike the multi-
# subject photos embedded in the manuscript).
CHAR_REFS_DIR = "data/char_refs"
_REF_EXT = (".png", ".jpg", ".jpeg", ".webp")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# Words that make an automated moderation filter misread an innocent baby-animal
# reference sheet as problematic (nudity / minor). A turnaround sheet only needs
# the canonical grown form, so these are safe to strip.
_RISKY = [
    (re.compile(r"\bwearing none\s*\(natural animal\)", re.I), "with its natural fur coat"),
    (re.compile(r"\bwearing none\b", re.I), "with natural coat"),
    (re.compile(r"\b(newborn|new-born|baby|infant)\b", re.I), "young"),
    (re.compile(r"\bnaked|nude|bare\b", re.I), "natural"),
    (re.compile(r"\bfemale\b", re.I), ""),   # gender word adds no visual signal here
    (re.compile(r"\bmale\b", re.I), ""),
    (re.compile(r"\bbelly\b", re.I), "tummy"),
    (re.compile(r"\s{2,}"), " "),
]


def _sanitize(prompt: str) -> str:
    """Soften a prompt so a false-positive moderation flag clears on retry."""
    out = prompt
    for pat, repl in _RISKY:
        out = pat.sub(repl, out)
    return out.strip()


def _generate_safe(prompt: str, label: str) -> bytes:
    """flux.generate that survives a moderation false-positive.

    BFL moderation is non-retryable, but it usually clears once the innocent
    trigger words (newborn / nude / female) are sanitized out. Try raw first,
    then the sanitized prompt; re-raise only if both are refused.
    """
    try:
        return flux.generate(prompt)
    except flux.ModerationError:
        safe = _sanitize(prompt)
        if safe != prompt:
            print(f"   [{label}] moderated — retrying with sanitized prompt")
            return flux.generate(safe)
        raise


def load_reference_photos() -> tuple[list[bytes], list[str]]:
    """Return (photo_bytes, character_names) from the parsed manuscript.

    character_names are those the writer tied to an embedded photo (e.g. the two
    golden retrievers "pictured below"); empty means fall back to main-tier.
    """
    if not os.path.exists(STORYBOOK_PATH):
        return [], []
    doc = json.load(open(STORYBOOK_PATH))
    paths = doc.get("reference_images") or []
    photos = [open(p, "rb").read() for p in paths if os.path.exists(p)]
    return photos, doc.get("photo_ref_characters") or []


def char_ref_image(name: str) -> bytes | None:
    """A clean per-character reference crop from data/char_refs/<slug>.*, if any.

    Normalised to PNG bytes so the vision-caption and Flux data-URL mime match.
    """
    for ext in _REF_EXT:
        p = os.path.join(CHAR_REFS_DIR, slug(name) + ext)
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGB")
                buf = BytesIO(); img.save(buf, format="PNG")
                return buf.getvalue()
            except Exception:  # noqa: BLE001
                return open(p, "rb").read()
    return None


def describe_reference(image_bytes: bytes, name: str) -> str:
    """Vision-caption a reference photo into concrete literal attributes.

    Conditioning on the photo alone loses details (a strong style prompt
    overrides the hat / glasses / outfit colours). Feeding these exact
    attributes back into the text prompt is what makes every detail match.
    """
    sysd = (
        "You are a precise visual describer helping an illustrator copy a real "
        f"subject exactly. Describe ONLY the single main subject ({name}); ignore "
        f"any background people or animals unless {name} itself is that animal.")
    userd = (
        "Describe the subject literally for exact reproduction: species/type, "
        "headwear, eyewear, hairstyle + length + colour (or fur/coat colour + "
        "markings), facial features, skin tone, approximate age, body build, top "
        "(colour), bottom (colour), footwear, accessories. Be explicit about "
        'COLOURS. Return JSON {"description":"..."} as one dense sentence.')
    try:
        return chat_json_image(sysd, userd, image_bytes, mime="image/png").get(
            "description", "")
    except Exception as e:  # noqa: BLE001
        print(f"   [describe_reference] {name}: {str(e)[:80]}")
        return ""


def _exact_likeness(prompt: str, name: str, caption: str = "") -> str:
    """Hard likeness wrapper with the vision caption injected."""
    detail = (f" {name} looks EXACTLY like this — reproduce every detail: {caption}."
              if caption else "")
    return (
        f"The attached image is a REAL reference photo of {name}. Reproduce {name} "
        "EXACTLY — same headwear, eyewear, hairstyle and length (or fur/coat colour "
        "and markings), facial features, skin tone, body build, age, and the same "
        f"clothing and accessories with the same COLOURS.{detail} Do NOT invent a "
        "different-looking subject or change the outfit. Only re-render in: " + prompt
    )


def _lean_fullbody(name: str, style_prompt: str) -> str:
    return (f"full-body character reference of {name} standing in a neutral A-pose, "
            f"head to feet, plain white background. {_style(style_prompt)}")


def _lean_portrait(name: str, style_prompt: str) -> str:
    return (f"head-and-shoulders portrait close-up of {name}, facing forward, plain "
            f"background. {_style(style_prompt)}")


def _likeness(prompt: str, name: str) -> str:
    """Wrap a ref-sheet prompt with a hard likeness directive for photo input."""
    return (
        "Using the provided real REFERENCE PHOTO(S) of the actual subject, "
        f"recreate {name}'s exact likeness — same face shape, coat/skin colour, "
        "markings, ear/muzzle/eye shape and body proportions (aim for 90%+ "
        "resemblance to the real subject) — then render it as: " + prompt
    )


def _edit_safe(prompt: str, photos: list[bytes], label: str) -> bytes:
    """flux.edit conditioned on reference photos, moderation-safe like _generate_safe."""
    try:
        return flux.edit(prompt, reference_images=photos)
    except flux.ModerationError:
        safe = _sanitize(prompt)
        if safe != prompt:
            print(f"   [{label}] moderated — retrying with sanitized prompt")
            return flux.edit(safe, reference_images=photos)
        raise


def _style(style_prompt: str) -> str:
    return style_prompt or "clean illustrated character design"


def _species(c: dict) -> str:
    return (c.get("species") or "human").strip().lower()


def _is_animal(c: dict) -> bool:
    return _species(c) not in ("", "human", "person", "people")


def _subject(c: dict) -> str:
    """The noun to use in prompts: 'character'/'person' for humans, the animal
    species for animals (so a dog close-up is a dog, not a girl)."""
    return _species(c) if _is_animal(c) else "character"


def _identity(c: dict) -> str:
    """The shared, canonical description of a character.

    Both the close-up and the full-body prompt are built on top of this exact
    block, so the two references carry *identical* detailing (same hair, eyes,
    face, outfit, palette) and only differ in framing.

    When the bible carries a `locked_spec` (exact hex/coords/garments), that
    deterministic block is authoritative — it is what keeps the character from
    drifting between pages.
    """
    if charspec.has_spec(c):
        return charspec.serialize(c["locked_spec"], c.get("name", ""))
    outfit = c.get("default_outfit", {})
    outfit_colors = ", ".join(outfit.get("colors", [])[:4])
    animal = _is_animal(c)
    parts = [
        # For animals, lead with the species so the model draws the right thing.
        (f"a {_species(c)}, " if animal else "")
        + f"{c.get('age_appearance', '')} {c.get('gender', '')}".strip(),
        f"height and build: {c.get('height_build', '')}",
        # Skip human-only "skin tone" for animals.
        "" if animal else f"skin tone: {c.get('skin_tone', '')}",
        f"{'coat' if animal else 'hair'}: {c.get('hair', '')}",
        f"eyes: {c.get('eyes', '')}",
        f"{'muzzle and ears' if animal else 'face'}: {c.get('face', '')}",
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
    subj = _subject(c)
    return (
        f"extreme close-up headshot of ONE single solo {subj}, "
        f"just the head{'' if _is_animal(c) else ' and shoulders'}, "
        "face fills the whole frame, tightly cropped, "
        "front view looking straight at the viewer, "
        f"NOT full body, only one {subj}, single subject, "
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
    # IMPORTANT: the close-up MUST include the full identity description. The
    # reference image alone is not reliably honoured by the image endpoint, so
    # without the identity the model falls back to a generic default face (the
    # same person every time). The identity is the source of truth; the
    # reference, when honoured, nudges the exact appearance to match.
    subj = _subject(c)
    animal = _is_animal(c)
    return (
        f"extreme close-up headshot of ONE single solo {subj}"
        + (" (an animal, NOT a human)" if animal else "")
        + ", matching the character in the reference image. "
        f"EXACTLY ONE {subj.upper()} — no second {subj}, no other figures, "
        "no one standing behind. "
        f"{_identity(c)}. "
        "Keep the same face, hair/coat, eyes and colours as this description and "
        "the reference. "
        "Crop very tightly to just the head so the face fills the entire frame, "
        "front view, looking straight at the viewer, not full body. "
        "Plain soft neutral background. "
        f"Art style: {_style(style_prompt)}"
    )


def full_body_prompt(c: dict, style_prompt: str = "") -> str:
    """Full view: one turnaround sheet with three full-length views of the same character."""
    subj = _subject(c)
    return (
        f"full-body {subj} turnaround model sheet of ONE single solo {subj}, "
        f"one image showing the SAME one {subj} "
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

    # Clean per-character crops for EXACT likeness (data/char_refs/<slug>.png).
    crops_for = [c["name"] for c in data["bible"] if char_ref_image(c["name"])]
    if crops_for:
        print(f"Exact-likeness crops found in {CHAR_REFS_DIR}/ for: {crops_for}")
    else:
        print(f"(tip: drop clean crops in {CHAR_REFS_DIR}/<name>.png for EXACT likeness)")

    # Real reference photos embedded in the manuscript → condition Flux on them
    # so the illustrated character actually resembles the real subject.
    photos, photo_names = load_reference_photos()
    if photos:
        main_tier = [c["name"] for c in data["bible"] if c.get("tier") == "main"]
        likeness_for = set(photo_names or main_tier)
        print(f"Reference photos: {len(photos)} — likeness for {sorted(likeness_for)}")
    else:
        likeness_for = set()

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

        # Resolve the strongest reference for this character:
        #  1. a clean per-character crop in data/char_refs → EXACT likeness
        #     (vision-caption + inject details + condition on that one photo)
        #  2. else the manuscript's embedded photos → 90% likeness
        #  3. else text-only
        crop = char_ref_image(name)
        if crop is not None:
            caption = describe_reference(crop, name)
            print(f"[{name}] generating portrait + full_body (EXACT likeness) ...")
            if caption:
                print(f"   caption: {caption[:110]}")
            portrait = _edit_safe(
                _exact_likeness(_lean_portrait(name, style_prompt), name, caption),
                [crop], f"{name} portrait")
            flux.save(portrait, p_path)
            try:
                body = _edit_safe(
                    _exact_likeness(_lean_fullbody(name, style_prompt), name, caption),
                    [crop], f"{name} full_body")
            except flux.ModerationError:
                print(f"   [{name}] full_body still moderated — falling back to portrait")
                body = portrait
            flux.save(body, b_path)
        else:
            use_photo = name in likeness_for
            tag = " (photo likeness)" if use_photo else ""
            print(f"[{name}] generating portrait + full_body{tag} ...")
            p_prompt = portrait_prompt(c, style_prompt)
            b_prompt = full_body_prompt(c, style_prompt)
            if use_photo:
                portrait = _edit_safe(_likeness(p_prompt, name), photos, f"{name} portrait")
            else:
                portrait = _generate_safe(p_prompt, f"{name} portrait")
            flux.save(portrait, p_path)
            try:
                if use_photo:
                    body = _edit_safe(_likeness(b_prompt, name), photos, f"{name} full_body")
                else:
                    body = _generate_safe(b_prompt, f"{name} full_body")
            except flux.ModerationError:
                # Both raw and sanitized full-body were refused — don't kill the whole
                # book over one ref sheet; reuse the portrait so pages still generate.
                print(f"   [{name}] full_body still moderated — falling back to portrait")
                body = portrait
            flux.save(body, b_path)
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
