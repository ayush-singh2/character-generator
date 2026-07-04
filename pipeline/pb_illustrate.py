"""Picture-book scene planner + cover art.

For each content unit of the parsed storybook it:
  1. Assigns a text-card zone (matching the renderer's rotation) so the art and
     the layout agree on where the words will sit.
  2. Asks Claude for a single illustration brief that depicts the page's moment,
     honours the manuscript's own art direction (spread / "different pictures of
     kids ..." etc.), restates each present character for consistency, and —
     crucially — keeps the CARD ZONE calm/empty so the translucent text card
     reads cleanly. Full-bleed landscape, no text rendered in the image.
  3. Generates the art with Flux, conditioned on the character reference sheets.

Also generates one cover illustration.

Run:  python -m pipeline.pb_illustrate
In:   data/storybook.json, data/characters.json, data/refs.json, data/style.json
Out:  output/storybook/art/page_*.png, cover_art.png  +  data/scenes_pb.json
"""

import json
import os

from . import flux
from .llm import chat_json
from .picturebook import ZONE_CYCLE
from .style import load_style_prompt

STORYBOOK = "data/storybook.json"
CHARACTERS = "data/characters.json"
REFS = "data/refs.json"
SCENES = "data/scenes_split.json"
ART_DIR = "output/storybook/art"
COVER_PATH = "output/storybook/cover_art.png"

MAX_REF_IMAGES = 4

# Where the calm/empty area must be for each card zone.
ZONE_HINT = {
    "left":   "the LEFT third of the frame",
    "right":  "the RIGHT third of the frame",
    "top":    "the TOP third of the frame (open sky / wall / soft space)",
    "bottom": "the BOTTOM third of the frame (open ground / floor / soft space)",
    "center": "the CENTRE of the frame",
}

# A page needs a dedicated text half (not a small floating card) when it carries
# a lot of words — otherwise the card is forced over the characters.
HEAVY_WORDS = 55

SCENE_SYSTEM = """\
You turn one page of a children's picture book into a single illustration brief.
You get the page text, the manuscript's own ART DIRECTION note, a roster of
designed characters, the chosen ART STYLE, and an EMPTY SIDE that must be left
open for the page's text.

Rules:
- Full-bleed LANDSCAPE illustration. Warm, gentle, age-appropriate.
- Depict the concrete moment the page describes (the narrator is the child).
- COMPOSITION IS CRITICAL: place ALL characters, faces, and the main action
  within roughly 60% of the frame on the side OPPOSITE the empty side. The EMPTY
  SIDE (about 40% of the width, full height) holds the page's words.
- THE BACKGROUND MUST FILL THE ENTIRE FRAME EDGE TO EDGE as ONE continuous
  painted illustration. The empty side is the SAME environment continued — the
  same wall, floor, sky, ambient colour, lighting and soft watercolour texture —
  just with fewer objects and characters. It is quiet, but it is still fully
  painted background. ABSOLUTELY DO NOT leave any part of the canvas blank,
  white, paper-coloured, or as a separate flat panel, and DO NOT create any
  vertical dividing line or seam between the two sides. It must look like one
  seamless scene whose left/right simply has more/less going on.
- If several characters are present (friends, a crowd), CLUSTER them tightly
  together on the character side — never spread them across the full width. Keep
  a small group (2-4 kids is enough to suggest "friends"); the empty side stays
  wide open.
- Honour the ART DIRECTION note if present (e.g. a montage of "different kids in
  different kitchens" => small vignettes clustered on the character side; a
  "spread" => a wide scene that still leaves the empty side open).
- RESTATE each present character's identity (face, hair, age) and outfit so they
  stay consistent page to page.
- Render NO text, letters, words, or numbers anywhere in the image.

Return STRICT JSON only:
{
  "characters_present": ["<exact bible names in scene; [] if none>"],
  "moment": "<the single moment to depict, one sentence>",
  "scene_prompt": "<complete Flux prompt: the moment; explicitly state the characters/action are clustered on the <opposite> side while the SAME background environment (wall/floor/sky, same colours + soft watercolour texture) continues seamlessly across the WHOLE frame into the quieter <empty side>; say 'full-bleed continuous illustration, background fills the entire frame edge to edge, no blank or white areas, no panel divide or seam'; lighting, mood, restated character identities + outfits; end with 'no text or letters in the image'>"
}
Use only names from the roster."""

COVER_SYSTEM = """\
You design the front-cover illustration for a children's picture book. Given the
title, a one-line summary, the main characters, and the art style, write ONE
Flux prompt for a warm, inviting full-bleed cover. Hero the main character(s)
with an appealing, emotive composition. Leave the TOP third of the image calmer
(a title banner sits there) and the very bottom calmer (author plate). Render NO
text, letters, or numbers in the image. Return STRICT JSON:
{"scene_prompt": "<the cover prompt, restating the main character's identity + outfit; end with 'no text or letters in the image'>"}"""


def _compact_bible(bible):
    rows = []
    for c in bible:
        rows.append(
            f"{c['name']}: {c.get('age_appearance','')}, {c.get('hair','')}, "
            f"{c.get('default_outfit',{}).get('description','')[:120]}"
        )
    return "\n".join(rows)


def _gather_refs(present, refs):
    present = [n for n in present if n in refs]
    imgs = []
    for n in present:
        imgs.append(open(refs[n]["portrait"], "rb").read())
    for n in present:
        if len(imgs) >= MAX_REF_IMAGES:
            break
        imgs.append(open(refs[n]["full_body"], "rb").read())
    return imgs[:MAX_REF_IMAGES]


def _render(prompt, ref_imgs):
    try:
        return flux.edit(prompt, ref_imgs) if ref_imgs else flux.generate(prompt)
    except flux.ModerationError:
        print("   moderated — retrying once with the raw prompt only ...")
        return flux.generate(prompt)


def plan_scene(unit, empty_side, bible, style_prompt):
    art_dir = unit.get("art_direction") or "(none)"
    other = "RIGHT" if empty_side == "left" else "LEFT"
    user = (
        f"ART STYLE: {style_prompt}\n"
        f"EMPTY SIDE (leave open for text): {empty_side.upper()} ~40% of the frame\n"
        f"CHARACTER/ACTION SIDE: {other} ~60%\n"
        f"ART DIRECTION NOTE: {art_dir}\n\n"
        f"CHARACTER ROSTER:\n{_compact_bible(bible)}\n\n"
        f"PAGE TEXT:\n{unit['text']}"
    )
    spec = chat_json(SCENE_SYSTEM, user, max_tokens=1200, temperature=0.5)
    if style_prompt and style_prompt.lower() not in spec.get("scene_prompt", "").lower():
        spec["scene_prompt"] = f"{spec.get('scene_prompt','')}. Art style: {style_prompt}"
    spec["text_region"] = empty_side        # left/right zone the renderer pins to
    return spec


def illustrate(force=False, recompose=False):
    doc = json.load(open(STORYBOOK))
    bible = json.load(open(CHARACTERS))["bible"]
    refs = json.load(open(REFS)) if os.path.exists(REFS) else {}
    style_prompt = load_style_prompt()
    os.makedirs(ART_DIR, exist_ok=True)

    scenes = json.load(open(SCENES)) if os.path.exists(SCENES) else {}
    content_idx = 0
    failed = []
    for unit in doc["units"]:
        if unit["kind"] != "content" or not unit.get("text", "").strip():
            continue
        label = unit["label"]
        # Alternate which side stays empty for the text, for left/right rhythm.
        empty_side = "left" if content_idx % 2 == 0 else "right"
        content_idx += 1
        path = os.path.join(ART_DIR, f"page_{unit['pages'][0]:02d}.png")
        done = label in scenes and scenes[label].get("image") and os.path.exists(path)
        # recompose re-illustrates every page with the character-on-one-side,
        # empty-background-on-the-other composition.
        if done and not force and not recompose:
            print(f"[{label}] already illustrated, skipping")
            continue
        for attempt in (1, 2, 3):
            try:
                print(f"[{label}] planning (empty side: {empty_side}) attempt {attempt} ...")
                spec = plan_scene(unit, empty_side, bible, style_prompt)
                present = spec.get("characters_present", [])
                print(f"   present: {present or '(none)'} | {spec.get('moment','')[:60]}")
                img = _render(spec["scene_prompt"], _gather_refs(present, refs))
                flux.save(img, path)
                spec["image"] = path
                scenes[label] = spec
                json.dump(scenes, open(SCENES, "w"), indent=2, ensure_ascii=False)
                print(f"   -> {path}")
                break
            except Exception as e:
                print(f"   .. attempt {attempt} failed: {str(e)[:120]}")
                if attempt == 3:
                    failed.append(label)

    json.dump(scenes, open(SCENES, "w"), indent=2, ensure_ascii=False)
    if failed:
        print(f"\nFailed pages (left on placeholder): {failed}")
    return scenes


def make_cover(force=False):
    if os.path.exists(COVER_PATH) and not force:
        print("[cover] already exists, skipping")
        return COVER_PATH
    doc = json.load(open(STORYBOOK))
    chars = json.load(open(CHARACTERS))
    bible = chars["bible"]
    refs = json.load(open(REFS)) if os.path.exists(REFS) else {}
    style_prompt = load_style_prompt()
    summary = (chars.get("roster") or [{}])[0].get("role", "")
    user = (
        f"ART STYLE: {style_prompt}\n"
        f"TITLE: {doc.get('title')}\n"
        f"SUMMARY: {summary}\n\n"
        f"MAIN CHARACTERS:\n{_compact_bible(bible[:2])}"
    )
    print("[cover] designing ...")
    spec = chat_json(COVER_SYSTEM, user, max_tokens=900, temperature=0.5)
    prompt = spec.get("scene_prompt", "")
    if style_prompt and style_prompt.lower() not in prompt.lower():
        prompt = f"{prompt}. Art style: {style_prompt}"
    lead = [c["name"] for c in bible[:2]]
    img = _render(prompt, _gather_refs(lead, refs))
    flux.save(img, COVER_PATH)
    print(f"   -> {COVER_PATH}")
    return COVER_PATH


def main():
    make_cover()
    illustrate()


if __name__ == "__main__":
    main()
