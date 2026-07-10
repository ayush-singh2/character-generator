"""Compositing book builder — the 'director' + assembly stage.

Replaces the old per-page flux illustration (which redrew characters freehand and
so could never be consistent) with:

    for each page:
        1. director(): LLM stages the shot -> which atlas pose each character
           strikes, where, how big, facing which way, + a character-free
           background description.
        2. generate a character-free BACKGROUND PLATE (allowed to vary per page).
        3. composite the exact atlas sprites onto the plate (compositor.py) — the
           characters are pixel-identical to every other page.
        4. save as output/storybook/art/page_NN.png (the standard art path).

Then the existing picturebook.build() adds the text + page numbers + PDF exactly
as before, so the text placement the client already likes is unchanged.
"""

import json
import os

from PIL import Image

from . import compositor, flux, refs as R, sprites
from . import llm, style

STORYBOOK = "data/storybook.json"
CHARACTERS = "data/characters.json"
ART_DIR = "output/storybook/art"


# --- pose vocabularies per body plan (must match sprites.POSES keys built) -----
POSE_GROUPS = {
    "dog":    ["sit", "stand", "walk", "run", "lookup", "sleep", "sniff"],
    "mascot": ["mascot_stand", "hold"],
    "human":  ["stand_person", "walk_person", "crouch", "sit_person"],
}


def _group(char):
    spec = char.get("locked_spec") or {}
    sp = (spec.get("identity", {}) or {}).get("species", "") or ""
    if "dragon" in sp or "mascot" in sp:
        return "mascot"
    if R._is_animal(char):
        return "dog"
    return "human"


def _atlas(manifest, name, pose, group):
    """Path to a sprite, falling back to the group's first pose if missing."""
    poses = manifest.get(name, {})
    if pose in poses:
        return poses[pose]
    # fallback: any available pose for this character
    for p in POSE_GROUPS[group]:
        if p in poses:
            return poses[p]
    return next(iter(poses.values()), None)


DIRECTOR_SYS = """You are the art director/stager for one page of a children's
picture book that is assembled by COMPOSITING pre-drawn character sprites onto a
painted background. You do NOT draw; you decide staging.

For the given page, output STRICT JSON:
{
  "background": "<the SETTING only — no characters/animals/people — e.g. 'a sunny baseball stadium interior seen from the stands'>",
  "characters": [
    {"name": "<exact roster name>",
     "pose": "<one allowed pose key for that character>",
     "x": <0..1 horizontal centre>, "y": <0..1 where the FEET touch>,
     "height": <0..1 sprite height as fraction of the page>,
     "flip": <true to face left, false to face right>}
  ]
}

Rules:
- Use ONLY characters actually in the scene, and ONLY their allowed pose keys.
- The TEXT will sit on the '{empty_side}' side, so place characters on the OTHER
  side and keep the {empty_side} side clear (low x if text is right / high x if
  text is left).
- Bilbo is the BIG dog, Obi the SMALL dog — Bilbo's height must be visibly larger
  than Obi's. Humans are tallest, Homer (dragon) is tall.
- Face characters toward the scene's action / each other.
- Ground everyone realistically (y near 0.9-0.98 for standing, higher sprites overlap less).
Return ONLY the JSON.
"""


def _director(unit, empty_side, bible, manifest):
    roster = []
    for c in bible:
        if c["name"] not in manifest:
            continue
        g = _group(c)
        roster.append(f"{c['name']} ({g}) allowed poses: {POSE_GROUPS[g]}")
    user = (
        f"PAGE {unit.get('label')}\n"
        f"Illustration note: {unit.get('art_direction') or '(none)'}\n"
        f"Text on page: {unit.get('text') or ''}\n\n"
        f"Available characters and their allowed poses:\n" + "\n".join(roster) +
        f"\n\nText will be on the '{empty_side}' side."
    )
    sys = DIRECTOR_SYS.replace("{empty_side}", empty_side)
    try:
        spec = llm.chat_json(sys, user)
        if isinstance(spec, dict) and spec.get("characters"):
            return spec
    except Exception as e:
        print(f"   [director] LLM failed ({str(e)[:70]}) — heuristic staging")
    return _heuristic(unit, empty_side, bible, manifest)


def _heuristic(unit, empty_side, bible, manifest):
    """Fallback staging when the LLM is unavailable: everyone bottom, sized by role."""
    text = (unit.get("text", "") + " " + (unit.get("art_direction") or "")).lower()
    pose_kw = [("run", "run"), ("ran", "run"), ("sleep", "sleep"), ("nap", "sleep"),
               ("curl", "sleep"), ("look", "lookup"), ("stare", "lookup"),
               ("sniff", "sniff"), ("smell", "sniff"), ("walk", "walk"),
               ("enter", "walk"), ("sit", "sit"), ("pose", "sit")]
    present = [c["name"] for c in bible
               if c["name"] in manifest and c["name"].lower() in text]
    if not present:
        present = [c["name"] for c in bible[:2] if c["name"] in manifest]
    base_x = 0.32 if empty_side == "right" else 0.68
    chars = []
    for i, name in enumerate(present):
        c = next(x for x in bible if x["name"] == name)
        g = _group(c)
        pose = next((p for kw, p in pose_kw if kw in text and p in POSE_GROUPS[g]),
                    POSE_GROUPS[g][0])
        h = 0.6 if name == "Bilbo" else 0.45 if g == "dog" else 0.72
        chars.append({"name": name, "pose": pose,
                      "x": min(0.9, max(0.1, base_x + i * 0.16)),
                      "y": 0.95, "height": h, "flip": empty_side == "left"})
    return {"background": unit.get("art_direction") or "a simple outdoor scene",
            "characters": chars}


def _plate(desc, empty_side, style_prompt, out_path):
    prompt = (
        "Children's storybook watercolour BACKGROUND ONLY — absolutely no "
        "characters, no animals, no people, an empty stage. Scene: " + desc + ". "
        f"Keep the {empty_side} side open, soft and uncluttered for text. "
        "Continuous full-bleed painting, no border, no panel, no frame. "
        "Art style: " + style_prompt)
    b = flux.generate(prompt)
    im = Image.open(__import__("io").BytesIO(b)).convert("RGB")
    im.save(out_path)
    return im


def _valid_pose(name, pose, bible, manifest):
    c = next((x for x in bible if x["name"] == name), None)
    if not c:
        return None
    g = _group(c)
    if pose not in POSE_GROUPS[g]:
        pose = POSE_GROUPS[g][0]
    return _atlas(manifest, name, pose, g)


def build_page(unit, empty_side, bible, manifest, style_prompt, force=False):
    page_no = unit["pages"][0]
    out = os.path.join(ART_DIR, f"page_{page_no:02d}.png")
    if os.path.exists(out) and not force:
        return out
    spec = _director(unit, empty_side, bible, manifest)
    plate = _plate(spec.get("background", "a simple scene"), empty_side,
                   style_prompt, out.replace(".png", ".plate.png"))
    # smaller sprites drawn last (in front); sort by height descending
    chars = sorted(spec.get("characters", []), key=lambda c: -float(c.get("height", 0.5)))
    stage = []
    for c in chars:
        path = _valid_pose(c["name"], c.get("pose", ""), bible, manifest)
        if not path:
            continue
        stage.append({"path": path,
                      "anchor": (float(c.get("x", 0.5)), float(c.get("y", 0.95))),
                      "height": float(c.get("height", 0.5)),
                      "flip": bool(c.get("flip", False))})
    img = compositor.place(plate, stage)
    img.save(out)
    names = ", ".join(f"{c['name']}:{c.get('pose')}" for c in chars)
    print(f"   [compose] {unit['label']} -> {out}  [{names}]")
    return out


def build(only=None, force=True):
    doc = json.load(open(STORYBOOK))
    bible = json.load(open(CHARACTERS))["bible"]
    manifest = json.load(open(sprites.MANIFEST))
    style_prompt = style.load_style_prompt()
    os.makedirs(ART_DIR, exist_ok=True)
    idx = 0
    for unit in doc["units"]:
        if unit.get("kind") != "content" or not (unit.get("text") or "").strip():
            continue
        empty_side = "left" if idx % 2 == 0 else "right"
        idx += 1
        if only and unit.get("label") not in only:
            continue
        build_page(unit, empty_side, bible, manifest, style_prompt, force=force)


if __name__ == "__main__":
    build()
