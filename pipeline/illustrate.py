"""Stage 5 — per-page illustration.

For each manuscript page:
  1. Claude reads the page text + the character bible and returns a scene
     spec: who is present, the setting, and a dense Flux scene prompt that
     restates each present character's identity + outfit.
  2. Flux generates the page art, conditioned on the reference images of the
     characters present (portrait + full-body), so they stay consistent.

Run:  python -m pipeline.illustrate [--pages 1-3]
In:   data/manuscript.json, data/characters.json, data/refs.json
Out:  output/pages/page_NN.png  +  data/scenes.json
"""

import argparse
import json
import os

from . import flux
from .llm import chat_json
from .style import load_style_prompt

PAGES = "data/pages.json"            # re-paginated beats (preferred)
MANUSCRIPT = "data/manuscript.json"  # fallback if not paginated
CHARACTERS = "data/characters.json"
REFS = "data/refs.json"
PAGES_DIR = "output/pages"
SCENES = "data/scenes.json"

# Cap reference images per page so no single character's signal is drowned out.
MAX_REF_IMAGES = 4

# Where on the page the text will sit. The illustrator must keep that zone
# visually calm and light so the overlaid words stay readable.
TEXT_ZONES = ["bottom", "top", "left", "right"]

SCENE_SYSTEM = """\
You turn one short page-beat of a book into a single illustration brief for a
picture-book edition. You are given the beat text, a roster of designed
characters, and the chosen ART STYLE. Decide who appears, the best moment to
depict, where the text should sit on the page, and whether a thought/dream
bubble is warranted.

Picture-book layout rule: the art is full-bleed, and the page TEXT is overlaid
in a soft light area of the art. So you must (a) choose a text_zone and
(b) compose so that zone is DELIBERATELY calm — empty sky, wall, ground, or
soft blurred background, with NO faces, hands, or key action in it. Place the
characters and action in the OPPOSITE part of the frame from the text_zone.
Vary the text_zone across pages for visual rhythm.

Use a bubble ONLY when the beat depicts a character thinking, imagining,
dreaming, or remembering. The bubble text must be the character's OWN words —
a natural first-person thought or a vivid short dream image — NOT a third-person
description. Good: "Could the gods really be watching me?" / "A field of gold,
as far as I can see." Bad: "Ramu imagines the gods in heaven."

Return STRICT JSON only:
{
  "characters_present": ["<exact bible names visibly in scene; [] if none>"],
  "setting": "<where/when, one phrase>",
  "moment": "<the single moment to depict, one sentence>",
  "text_zone": "bottom" | "top" | "left" | "right",
  "bubble": null | {"type": "thought" | "dream", "character": "<bible name>", "text": "<the character's own first-person thought/dream words, <=12 words>"},
  "scene_prompt": "<complete image prompt: the moment, composition, lighting, mood; RESTATE each present character's identity (face/hair/age) + outfit for consistency; explicitly note 'leave the <text_zone> area soft, light and uncluttered for text overlay'; if a bubble is used, add 'leave a soft empty light area in an upper corner near the character for a thought bubble' — do NOT render any text or letters in the image>"
}
Use only names from the roster."""


def _compact_bible(bible: list[dict]) -> str:
    rows = []
    for c in bible:
        look = (
            f"{c['name']}: {c.get('age_appearance','')}, {c.get('hair','')}, "
            f"{c.get('default_outfit',{}).get('description','')[:120]}"
        )
        rows.append(look)
    return "\n".join(rows)


def scene_for_page(page: dict, bible: list[dict], style_prompt: str) -> dict:
    user = (
        f"ART STYLE: {style_prompt}\n\n"
        f"CHARACTER ROSTER:\n{_compact_bible(bible)}\n\n"
        f"PAGE-BEAT TEXT:\n{page['text']}"
    )
    spec = chat_json(SCENE_SYSTEM, user, max_tokens=1200, temperature=0.5)
    # Always append the chosen style so every page is visually coherent.
    if style_prompt and style_prompt.lower() not in spec.get("scene_prompt", "").lower():
        spec["scene_prompt"] = f"{spec.get('scene_prompt','')}. Art style: {style_prompt}"
    if spec.get("text_zone") not in TEXT_ZONES:
        spec["text_zone"] = "bottom"
    return spec


def _gather_refs(present: list[str], refs: dict) -> list[bytes]:
    """Portrait+full_body for each present character, capped at MAX_REF_IMAGES.
    With many characters, prefer portraits (face lock) over full bodies."""
    present = [n for n in present if n in refs]
    images: list[bytes] = []
    # Pass 1: portraits (most important for identity).
    for n in present:
        images.append(open(refs[n]["portrait"], "rb").read())
    # Pass 2: full bodies while we still have room.
    for n in present:
        if len(images) >= MAX_REF_IMAGES:
            break
        images.append(open(refs[n]["full_body"], "rb").read())
    return images[:MAX_REF_IMAGES]


SOFTEN_SYSTEM = """\
An image generator's content filter rejected the following illustration prompt
for a serious literary novel. Rewrite it to be tasteful and non-graphic while
keeping the same characters, setting and emotional beat — soften any violence,
gore, nudity, or distress into suggestion and mood (shadow, expression,
composition) rather than explicit depiction. Return STRICT JSON:
{"scene_prompt": "<the rewritten prompt>"}"""


def _soften(scene_prompt: str) -> str:
    out = chat_json(SOFTEN_SYSTEM, scene_prompt, max_tokens=800, temperature=0.4)
    return out.get("scene_prompt", scene_prompt)


def _render_scene(spec: dict, ref_imgs: list[bytes]) -> bytes:
    """Generate the page image, retrying once with a softened prompt if the
    content filter rejects it."""
    prompt = spec["scene_prompt"]
    try:
        return flux.edit(prompt, ref_imgs) if ref_imgs else flux.generate(prompt)
    except flux.ModerationError:
        print("   moderated — softening prompt and retrying ...")
        safe = _soften(prompt)
        spec["scene_prompt_softened"] = safe
        return flux.edit(safe, ref_imgs) if ref_imgs else flux.generate(safe)


def illustrate(page_range: range | None = None, force: bool = False) -> dict:
    # Prefer the re-paginated picture-book beats; fall back to raw manuscript.
    doc = json.load(open(PAGES if os.path.exists(PAGES) else MANUSCRIPT))
    bible = json.load(open(CHARACTERS))["bible"]
    refs = json.load(open(REFS)) if os.path.exists(REFS) else {}
    style_prompt = load_style_prompt()

    scenes = json.load(open(SCENES)) if os.path.exists(SCENES) else {}
    failed = []
    for page in doc["pages"]:
        n = page["page_no"]
        if page_range and n not in page_range:
            continue
        if not page["text"].strip():
            continue
        path = os.path.join(PAGES_DIR, f"page_{n:02d}.png")
        if not force and str(n) in scenes and scenes[str(n)].get("image") and os.path.exists(path):
            print(f"[page {n}] already illustrated, skipping")
            continue

        try:
            print(f"[page {n}] planning scene ...")
            spec = scene_for_page(page, bible, style_prompt)
            present = spec.get("characters_present", [])
            bub = f" | 💭 {spec['bubble']['type']}" if spec.get("bubble") else ""
            print(f"   present: {present or '(none)'} | zone={spec.get('text_zone')}{bub} | {spec.get('moment','')[:55]}")

            ref_imgs = _gather_refs(present, refs)
            img = _render_scene(spec, ref_imgs)
            flux.save(img, path)
            spec["image"] = path
            scenes[str(n)] = spec
            # Persist after every page so a later failure never loses progress.
            json.dump(scenes, open(SCENES, "w"), indent=2, ensure_ascii=False)
            print(f"   -> {path} ({len(ref_imgs)} refs)")
        except Exception as e:  # isolate per-page failures
            failed.append(n)
            print(f"   !! page {n} failed: {str(e)[:160]}")

    json.dump(scenes, open(SCENES, "w"), indent=2, ensure_ascii=False)
    if failed:
        print(f"\nFailed pages (left text-only): {failed}")
    return scenes


def _parse_range(s: str | None) -> range | None:
    if not s:
        return None
    if "-" in s:
        a, b = s.split("-")
        return range(int(a), int(b) + 1)
    v = int(s)
    return range(v, v + 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", help="e.g. 1-3 or 5", default=None)
    args = ap.parse_args()
    scenes = illustrate(_parse_range(args.pages))
    print(f"\nIllustrated {len(scenes)} pages total -> {SCENES}")


if __name__ == "__main__":
    main()
