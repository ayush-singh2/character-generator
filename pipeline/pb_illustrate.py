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

import io
import json
import os

from PIL import Image, ImageFilter

from . import charspec
from . import flux
from . import motifs
from .llm import chat_json
from .picturebook import ZONE_CYCLE
from .style import load_style_prompt

# Closed-loop negative-space: after each page we measure the edge-energy of the
# reserved text band vs the character band. The text side must be clearly calmer
# (and calm in absolute terms) or the page is regenerated with a stronger
# emptiness directive. Tunable via env for calibration.
NS_RATIO = float(os.getenv("PB_NS_RATIO", "0.62"))   # empty < other * ratio
NS_FLOOR = float(os.getenv("PB_NS_FLOOR", "26"))     # empty < floor (absolute)
NS_TRIES = int(os.getenv("PB_NS_TRIES", "3"))        # attempts per page

STORYBOOK = "data/storybook.json"
CHARACTERS = "data/characters.json"
REFS = "data/refs.json"
GROUP_REFS = "data/group_refs.json"
SCENES = "data/scenes_split.json"
ART_DIR = "output/storybook/art"
COVER_PATH = "output/storybook/cover_art.png"

MAX_REF_IMAGES = 8   # flux.2 accepts up to ~10 reference images

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
- THE TEXT AREA MUST BE GENUINELY CALM (this is how a real picture book leaves
  room for words — study any human-illustrated page: the text sits on open sky, a
  soft plain wall, a gentle colour wash, or a blurred distant background). So the
  EMPTY SIDE must be a SMOOTH, LOW-DETAIL, EVENLY-TONED region — open sky, a soft
  plain wash of the ambient colour, gently blurred far background — with NO busy
  texture, NO detailed objects, NO wood-grain/foliage/pattern detail, and enough
  tonal calm and contrast that dark or light text laid over it stays legible.
- Keep it full-bleed: the calm side is the SAME environment and colour family
  continued (so it reads as one scene), just simplified almost to a plain wash.
  Do NOT hard-cut to white/paper, and do NOT draw a panel divide or seam — let the
  detailed side melt gradually into the quiet, simplified text side.
- If several characters are present (friends, a crowd), CLUSTER them tightly
  together on the character side — never spread them across the full width. Keep
  a small group (2-4 kids is enough to suggest "friends"); the empty side stays
  wide open.
- The ART DIRECTION note is AUTHORITATIVE staging: place every element it names,
  in the position and mood it specifies (e.g. "hawk circling high above, small in
  the sky, top corner" => draw exactly that; "Sparky does not look afraid while
  the others flee" => stage that contrast). Do not omit or relocate what it asks.
- Obey the LAYOUT line: a SPREAD is one seamless wide scene with the subject off
  the gutter; SPOT means the given number of small separate vignettes floating on
  a soft plain background (not one full-bleed scene); single is full-bleed.
- If an ACTION TO STAGE line is given, make those verbs read at a glance — put the
  described motion cues (streaming tails, lifted sniffing nose + scent wisps, wide
  fearful eyes, mid-leap arc) into the scene_prompt so the action is unmistakable.
- RESTATE each present character's identity (face, hair, age) and outfit so they
  stay consistent page to page.
- Render NO text, letters, words, or numbers anywhere in the image.

Return STRICT JSON only:
{
  "characters_present": ["<exact bible names in scene; [] if none>"],
  "moment": "<the single moment to depict, one sentence>",
  "scene_prompt": "<complete Flux prompt: the moment; explicitly state the characters/action are clustered on the <opposite> side; then explicitly describe the <empty side> as a CALM, SIMPLIFIED, LOW-DETAIL area — open sky / a soft plain wash of the ambient colour / a gently blurred distant background — smooth and evenly toned with generous uncluttered negative space for text, NO busy texture or detailed objects there, tonally calm enough that text stays legible; say 'full-bleed continuous illustration, one seamless scene, no white border, no panel divide or seam, the detailed side melting gradually into the quiet simplified <empty side>'; lighting, mood, restated character identities + outfits; end with 'no text or letters in the image'>"
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


def _locks_for(present, bible):
    """Serialise the locked spec of each present character into one exact block."""
    by_name = {c["name"]: c for c in bible}
    blocks = []
    for name in present:
        c = by_name.get(name)
        if c and charspec.has_spec(c):
            blocks.append(charspec.serialize(c["locked_spec"], name))
    return "\n".join(blocks)


def _ref_tag(c):
    """Short, punchy identity tag — coat/hair colour + the CAP ON the head.

    The full locked_spec already carries this, but buried in a long block the
    model ignores it. A brief, scannable restatement placed right after the lock
    (repetition + brevity) is what actually forces the cap and coat to render.
    """
    name = c.get("name", "")
    spec = c.get("locked_spec") or {}
    bits = []
    hair = spec.get("hair") or {}
    if hair.get("style"):
        bits.append(hair["style"])
    elif c.get("hair"):
        bits.append(str(c["hair"]))
    top = (spec.get("outfit") or {}).get("top") or {}
    g = str(top.get("garment", "")).lower()
    if "cap" in g or "hat" in g:
        logo = top.get("logo") or {}
        cap = f"ALWAYS wearing the {top.get('color_hex', '')} {top['garment']}".strip()
        if logo.get("motif"):
            cap += f" with {logo['motif']}"
        cap += " ON its head (the cap is present in EVERY scene)"
        bits.append(cap)
    return f"{name} — " + "; ".join(b for b in bits if b)


def _ref_binding(present, bible):
    """Forceful, book-agnostic instruction to actually honour the references."""
    by = {c["name"]: c for c in bible}
    tags = [t for t in (_ref_tag(by[n]) for n in present if n in by) if t.strip(" —")]
    if not tags:
        return ""
    nonhuman = any((by[n].get("locked_spec") or {}).get("identity", {}).get("species",
                   "human") not in ("human", "", None) for n in present if n in by)
    guard = (" Do NOT simplify or default any animal to a plain generic breed — keep "
             "each one's exact coat colour and markings." if nonhuman else "")
    return ("Match every reference image faithfully: each character in the scene must "
            "have the SAME coat/hair colour, the SAME markings, and the SAME hat/cap "
            "ON its head as in its reference image." + guard
            + " Characters: " + " | ".join(tags) + ".")


# Flux sometimes paints a hard vertical edge where the calm text side begins.
_NO_SEAM = ("Paint the whole frame edge-to-edge as ONE continuous scene — the calmer, "
            "emptier area reserved for text is simply the same scene continuing "
            "(open sky, distant field, soft wash), NOT a separate blank panel. No hard "
            "border, no vertical seam, no dividing line, no framed box anywhere.")


def _compose_prompt(scene_prompt, lock, present, refs, bible=None):
    """Build the final Flux prompt for maximum character consistency.

    Order matters: models weight the opening of a prompt most, so the exact
    CHARACTER LOCK and a punchy reference-binding instruction lead, and the
    scene description follows. The reference sheets themselves are passed as
    conditioning images (the strongest consistency lever).
    """
    has_ref = [n for n in present if n in refs]
    parts = []
    if lock:
        parts.append(lock)
    if has_ref:
        binding = _ref_binding(present, bible or [])
        if binding:
            parts.append(binding)
        else:
            who = ", ".join(has_ref)
            parts.append(
                f"Keep {who}'s character design consistent throughout the book: the "
                "same face, coat/hair colour, the same outfit and colours, and the "
                "same cap. Only their pose and action change to fit the scene.")
    parts.append("SCENE: " + scene_prompt + "\n" + _NO_SEAM)
    return "\n\n".join(parts)


def _load_group_refs():
    """Optional combined ('duo'/'cast') reference images, from data/group_refs.json.

    Two similar characters (Bilbo & Obi) get collapsed into one prototype when
    their SEPARATE reference sheets are passed together — the dominant one (a
    generic golden retriever) contaminates the other, so Obi loses his amber coat
    and green cap. A single image that already shows BOTH dogs with the correct
    CONTRAST anchors the difference so the model can't merge them. Each entry:
    {"members": ["Bilbo","Obi"], "image": "output/refs/duo_dogs.png"}.
    """
    if not os.path.exists(GROUP_REFS):
        return []
    try:
        return json.load(open(GROUP_REFS))
    except Exception:
        return []


def _gather_refs(present, refs):
    present = [n for n in present if n in refs]
    imgs, covered = [], set()
    # 1) Combined group reference(s) first (strongest position). When all members
    #    of a group are on the page, its single duo/cast image replaces their
    #    individual sheets so they can't contaminate each other.
    for grp in _load_group_refs():
        members = grp.get("members", [])
        if members and all(m in present for m in members) and os.path.exists(grp.get("image", "")):
            imgs.append(open(grp["image"], "rb").read())
            covered.update(members)
    # 2) Clean front-view PORTRAIT for every character NOT covered by a group
    #    (Mom, Dad, Homer) — the strongest single-character identity anchor.
    rest = [n for n in present if n not in covered]
    for n in rest:
        if len(imgs) >= MAX_REF_IMAGES:
            break
        imgs.append(open(refs[n]["portrait"], "rb").read())
    # 3) Their full-bodies for outfit/proportion, if slots remain.
    for n in rest:
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


def _layout_directive(unit) -> str:
    """Translate the manuscript's page layout into composition guidance."""
    layout = unit.get("layout", "single")
    if layout == "spot":
        n = unit.get("spot_count") or 2
        return (f"LAYOUT: {n} SPOT illustrations — compose {n} small separate "
                f"vignette scenes (one per beat of the art direction), each "
                f"floating on a soft plain background, NOT one full-bleed scene.")
    if layout == "spread":
        return ("LAYOUT: two-page SPREAD — one seamless wide scene; keep the "
                "main subject clear of the vertical centre (the gutter).")
    return "LAYOUT: single full-bleed page."


def plan_scene(unit, empty_side, bible, style_prompt):
    art_dir = unit.get("art_direction") or "(none)"
    other = "RIGHT" if empty_side == "left" else "LEFT"
    # The writer's Illustration note stages the shot; motifs make the verbs read.
    action = motifs.annotate(unit.get("text", ""), unit.get("art_direction", ""))
    emphasis = motifs.emphasis_words(unit.get("text", ""))
    user = (
        f"ART STYLE: {style_prompt}\n"
        f"EMPTY SIDE (leave open for text): {empty_side.upper()} ~40% of the frame\n"
        f"CHARACTER/ACTION SIDE: {other} ~60%\n"
        f"{_layout_directive(unit)}\n"
        f"ART DIRECTION NOTE (authoritative staging — follow it exactly, place "
        f"every element it names): {art_dir}\n"
        + (f"ACTION TO STAGE: {action}\n" if action else "")
        + f"\nCHARACTER ROSTER:\n{_compact_bible(bible)}\n\n"
        f"PAGE TEXT:\n{unit['text']}"
    )
    spec = chat_json(SCENE_SYSTEM, user, max_tokens=1200, temperature=0.5)
    # Belt-and-suspenders: fold the action cues straight into the Flux prompt so
    # the motion survives even if the planner under-weights them.
    if action and action.lower() not in spec.get("scene_prompt", "").lower():
        spec["scene_prompt"] = f"{spec.get('scene_prompt','')} {action}"
    if style_prompt and style_prompt.lower() not in spec.get("scene_prompt", "").lower():
        spec["scene_prompt"] = f"{spec.get('scene_prompt','')}. Art style: {style_prompt}"
    spec["text_region"] = empty_side        # left/right zone the renderer pins to
    spec["layout"] = unit.get("layout", "single")
    spec["emphasis_words"] = emphasis       # shout/onomatopoeia for the renderer
    return spec


def _reserved_side_calm(img_bytes, empty_side):
    """Is the reserved text band genuinely low-detail?

    Compares edge-energy of the empty ~40% band against the character ~60%
    band. Returns (ok, empty_energy, other_energy). The text side must be
    clearly calmer than the subject side AND calm in absolute terms.
    """
    im = (Image.open(io.BytesIO(img_bytes)).convert("L")
          .filter(ImageFilter.FIND_EDGES).resize((100, 100)))
    px = list(im.getdata())

    def band(c0, c1):
        vals = [px[r * 100 + c] for r in range(100) for c in range(c0, c1)]
        return sum(vals) / len(vals)

    if empty_side == "left":
        empty, other = band(0, 40), band(45, 100)
    else:
        empty, other = band(60, 100), band(0, 55)
    ok = empty < other * NS_RATIO and empty < NS_FLOOR
    return ok, empty, other


def _emptiness_boost(empty_side):
    other = "right" if empty_side == "left" else "left"
    return (f"CRITICAL COMPOSITION RULE: the entire {empty_side.upper()} ~40% of the "
            f"frame MUST be almost empty — a smooth, plain, evenly-toned wash of the "
            f"ambient colour (open sky, soft wall, or blurred distance) with absolutely "
            f"NO characters, animals, objects, props or busy detail in it. Move EVERY "
            f"subject fully into the {other.upper()} portion of the frame. This empty "
            f"area is reserved for text and must stay clean and low-detail. ")


def illustrate(force=False, recompose=False, only=None):
    doc = json.load(open(STORYBOOK))
    bible = json.load(open(CHARACTERS))["bible"]
    refs = json.load(open(REFS)) if os.path.exists(REFS) else {}
    style_prompt = load_style_prompt()
    os.makedirs(ART_DIR, exist_ok=True)

    scenes = json.load(open(SCENES)) if os.path.exists(SCENES) else {}
    content_idx = 0
    failed = []
    weak = []
    for unit in doc["units"]:
        if unit["kind"] != "content" or not unit.get("text", "").strip():
            continue
        label = unit["label"]
        # Alternate which side stays empty for the text, for left/right rhythm.
        empty_side = "left" if content_idx % 2 == 0 else "right"
        content_idx += 1
        if only and label not in only:
            continue
        path = os.path.join(ART_DIR, f"page_{unit['pages'][0]:02d}.png")
        done = label in scenes and scenes[label].get("image") and os.path.exists(path)
        # recompose re-illustrates every page with the character-on-one-side,
        # empty-background-on-the-other composition.
        if done and not force and not recompose and not only:
            print(f"[{label}] already illustrated, skipping")
            continue
        best = None  # (img, spec, empty_energy) — kept as fallback if none pass
        for attempt in range(1, NS_TRIES + 1):
            try:
                print(f"[{label}] planning (empty side: {empty_side}) attempt {attempt} ...")
                spec = plan_scene(unit, empty_side, bible, style_prompt)
                present = spec.get("characters_present", [])
                print(f"   present: {present or '(none)'} | {spec.get('moment','')[:60]}")
                # Pin every present character to its EXACT locked spec, appended
                # deterministically (not left to the planner to paraphrase) so
                # colours/logo/features never drift between pages.
                lock = _locks_for(present, bible)
                scene_prompt = spec["scene_prompt"]
                # Escalate the emptiness directive on every retry so Flux actually
                # leaves the reserved text band clean.
                if attempt > 1:
                    scene_prompt = _emptiness_boost(empty_side) + scene_prompt
                prompt = _compose_prompt(scene_prompt, lock, present, refs, bible)
                img = _render(prompt, _gather_refs(present, refs))

                ok, empty_e, other_e = _reserved_side_calm(img, empty_side)
                print(f"   negative-space: {empty_side} band={empty_e:.1f} "
                      f"vs subject={other_e:.1f} -> {'CALM' if ok else 'too busy'}")
                if best is None or empty_e < best[2]:
                    best = (img, spec, empty_e)
                if ok or attempt == NS_TRIES:
                    img, spec, _ = best  # save the calmest of the attempts
                    if not ok:
                        print(f"   .. kept calmest attempt (no fully-empty side found)")
                        weak.append(label)
                    flux.save(img, path)
                    spec["image"] = path
                    scenes[label] = spec
                    json.dump(scenes, open(SCENES, "w"), indent=2, ensure_ascii=False)
                    print(f"   -> {path}")
                    break
                print("   .. reserved side not empty enough — regenerating")
            except Exception as e:
                print(f"   .. attempt {attempt} failed: {str(e)[:120]}")
                if attempt == NS_TRIES:
                    failed.append(label)

    json.dump(scenes, open(SCENES, "w"), indent=2, ensure_ascii=False)
    if failed:
        print(f"\nFailed pages (left on placeholder): {failed}")
    if weak:
        print(f"Pages with no fully-empty text band (kept calmest): {weak}")
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
