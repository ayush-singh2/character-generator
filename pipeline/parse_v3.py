"""v3 parse — a manuscript .docx becomes a rich art plan in TOON.

Generic and manuscript-driven (works on any book, not just Bilbo). The text model
acts as art director + character designer: it picks a cohesive art STYLE that fits
this particular book, DESIGNS every recurring character with a repeatable
appearance, flags look-alike groups that need a shared reference, and infers a
detailed illustration for every page. Output:

  <book>/v3/data/characters.toon   {style, characters[], lookalike_groups[]}
  <book>/v3/data/scenes.toon       {title, scenes[]}

Richer than a hand-written bible: characters carry appearance/palette/outfit/
distinguishing features; scenes carry setting/action/mood/camera/text placement.
"""

import glob
import os
import re

import docx

from . import llm, toon_io

SYSTEM = """\
You are a children's picture-book ART DIRECTOR and CHARACTER DESIGNER. Read the \
whole manuscript, then produce a COMPLETE, richly detailed art plan.

Do all of this:
- Choose ONE cohesive ART STYLE that best fits THIS book's tone and audience (be \
specific and vivid — pick what suits the story, don't default to one look).
- DESIGN every recurring character that must stay consistent. ANY character that \
appears on 2 or more pages MUST be "high" consistency — never leave a recurring \
side animal (a sheep, a zebra, a pig) as "incidental"; that is exactly how their \
outfits and sizes drift. "incidental" is only for true one-offs. For EVERY "high" \
character, also produce a LOCKED_SPEC: an exact, enumerated appearance where every \
trait has ONE committed value (never "X or Y", never "often"), colours are HEX \
codes, and nothing is left vague. If the manuscript is silent on a detail, INVENT \
one specific value and lock it. This is what stops the character drifting between \
pages, so be concrete: exact hair style + colour, skin hex, exact outfit garments \
+ colours, signature items with position.
- Flag LOOK-ALIKE groups (characters that could be confused) and state the single \
feature that tells them apart.
- For EVERY page, infer a specific illustration from the page text: setting, what \
each character is doing, mood, and camera. Keep the page TEXT verbatim.
- Include the book's FRONT MATTER and BACK MATTER as their own pages, in order: a \
TITLE page first, a DEDICATION on its OWN page if the manuscript has one, and any \
back matter the manuscript contains (e.g. "About the Author", a fostering/adoption \
note). Mark each with "role": "title" | "dedication" | "about_author" | "backmatter".

Return ONLY JSON, no prose:
{
  "title": "...",
  "author": "...",
  "style": {"name":"","medium":"","linework":"","palette":"","lighting":"","mood":"","influences":""},
  "characters": [
    {"name":"","role":"","kind":"human|dog|animal|creature","appearance":"",
     "hair":"","outfit":"","palette":"","distinguishing_features":"","personality":"",
     "consistency":"high|incidental",
     "dress_state":"clothed|unclothed",
     "locked_spec": {
       "identity": {"species":"human","age_years":9,"gender_presentation":"girl",
                    "skin":{"hex":"#E8B48C","undertone":"warm","notes":""},
                    "stance":"anthro|feral (animals only)",
                    "build":{"height_cm":135,"body_type":"slender"}},
       "hair": {"color_hex":"#3B2A1A","length":"shoulder-length","style":"two low puffs",
                "texture":"coily","accessory":{"item":"hair ties","color_hex":"#FF4D4D"}},
       "face": {"eye_color_hex":"#5B3A1E","eye_shape":"round","eyebrows":"soft arched",
                "nose":"small","distinguishing":[""]},
       "outfit": {"top":{"garment":"t-shirt","color_hex":"#FFD23F","fit":"relaxed",
                         "logo":{"present":false}},
                  "bottom":{"garment":"denim overalls","color_hex":"#3E5C76","fit":"relaxed"},
                  "footwear":{"garment":"sneakers","color_hex":"#7A4FB5","sole_hex":"#FFFFFF"},
                  "outerwear":"none"},
       "accessories": [{"item":"charm bracelet","color_hex":"#C0C0C0","when":"always, left wrist"}]
     }}
  ],
  "lookalike_groups": [{"members":["",""],"distinguish":""}],
  "settings": [
    {"key":"ballpark","name":"the baseball stadium",
     "description":"exact, repeatable location: architecture, materials, colours, "
                   "seating, field, signage, distinctive features — enough to redraw "
                   "the SAME place every time",
     "floor":"exact floor material + colour, e.g. wide oak planks in warm honey #C89A5B",
     "fixed_props":[{"item":"candles","count":3,"design":"covered glass lanterns on the window sill"}]}
  ],
  "scenes": [
    {"page":"1","role":"body","layout":"single","chars":["name",...],
     "setting":"","setting_key":"ballpark","action":"","mood":"","camera":"",
     "text":"","text_area":"top|bottom"}
  ]
}
Rules:
- SETTINGS (location lock): list every RECURRING place that appears on 2+ pages, each
with a key and an exact, repeatable visual description (so it can be drawn the SAME
every time). Tag each scene with the "setting_key" of the place it happens in (or ""
for a one-off/plain setting). This keeps recurring locations consistent across pages.
- LOCKED_SPEC (identity lock): include it for EVERY "high" character. One committed
value per trait, hex colours, no "or"/"often"/"maybe". For animals: put coat colour
+ markings under hair, collar/bandana (or "none") under outfit, muzzle/ears under
face; omit human-only garments. Incidental characters may omit locked_spec.
Signature items are part of the character's constant look: do NOT restrict a
worn item to specific page numbers (never a "when":"cover/page 4 only" condition).
If the character wears it, mark it worn ALWAYS; only note a condition for something
genuinely situational (e.g. a helmet "only when riding").
- HEIGHTS (size lock): every "high" character's build.height_cm is REQUIRED — for
animals, the height of the top of the head in the character's normal stance. The
cast's heights must be mutually plausible so relative sizes read correctly on shared
pages (a pig clearly shorter than a goat, a giraffe far taller than both).
- STANCE (animals): every animal character's identity carries "stance": "anthro"
(walks upright, person-like, gestures with hands) or "feral" (a natural four-legged
animal). Commit to ONE for the whole book — a yoga pose or action moment never
changes a character's stance. Omit for humans.
- ORIENTATION: any directional feature (horns, tail, ears, crest, trunk) listed in
face.distinguishing must state its direction explicitly and absolutely, e.g. "two
horns curving BACKWARD over the head, tips pointing behind — never sideways or
forward".
- DRESS STATE: every "high" character carries "dress_state": "clothed" (wears the
locked outfit on EVERY page) or "unclothed" (a natural animal wearing nothing — and
it must NEVER gain clothes on any page). Never leave it ambiguous.
- SETTING LOCK DETAILS: each setting also locks "floor" (ONE exact material +
colour) and "fixed_props" (the recurring furniture/props of the place, each with an
exact count and design). The same floor and the same props must appear every time
the location recurs — never redecorate between pages.
- VERBATIM (MAN-1): the "text" of every page must be copied EXACTLY from the \
manuscript — never paraphrase, summarise, reword, add, or invent any sentence, \
caption, or title. If a page has no words, use "text": "".
- COMPLETE & FAITHFUL (MAN-2): produce exactly the pages the manuscript implies — \
do NOT invent extra pages, and do NOT drop any manuscript page or paragraph.
- SINGLE PAGES: every page is one square page ("layout":"single"); there are no \
two-page spreads. text_area is top or bottom (a calm side away from the subject).
- every name in a scene's "chars" must exist in "characters" (use [] if a page has \
no recurring character); number BODY pages sequentially in reading order; front/back \
matter keep their role but still appear in the scenes list in reading order."""


def _read_docx(path):
    d = docx.Document(path)
    return "\n".join(p.text for p in d.paragraphs if p.text.strip())


def _norm(s):
    """Lowercase, strip punctuation/whitespace — for verbatim substring matching."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def reconcile(scenes, manuscript):
    """MAN-2: warn about any body page whose text isn't found verbatim in the
    manuscript (a likely invented/paraphrased caption). Report-only — never fatal."""
    hay = _norm(manuscript)
    flagged = []
    for sc in scenes:
        if sc.get("role") not in (None, "body"):   # skip generated front/back matter
            continue
        t = (sc.get("text") or "").strip()
        if len(_norm(t)) >= 12 and _norm(t) not in hay:
            flagged.append(sc.get("page", "?"))
    if flagged:
        print(f"  ! MAN-2: {len(flagged)} page(s) have text not found verbatim "
              f"in the manuscript (check for invented/paraphrased text): {flagged}")
    return flagged


# "Continuation of the two-page spread from page 8; no separate illustration
# needed." — the extractor's marker for the right-hand page of a spread.
_CONT = re.compile(r"continuation of the .*?spread.*?page\s+(\w+)", re.I)


def _split_text(text):
    """Split caption text at the sentence boundary nearest its midpoint.
    Returns (first, second); second == '' when there is only one sentence."""
    parts = re.findall(r"[^.!?]*[.!?]+[\"'”’)]*\s*|[^.!?]+$", text)
    parts = [p for p in parts if p.strip()]
    if len(parts) < 2:
        return text.strip(), ""
    total, acc, cut = len(text), 0, 1
    bestd = 1e9
    for i in range(1, len(parts)):
        acc += len(parts[i - 1])
        d = abs(acc - total / 2)
        if d < bestd:
            bestd, cut = d, i
    return ("".join(parts[:cut]).strip(), "".join(parts[cut:]).strip())


def balance_spreads(scenes):
    """Spread text balancing (client feedback: 'all the text is crammed on
    one page of the spread while the other has none').

    A manuscript two-page spread arrives as a pair: page A holds ALL the
    spread's text and the full scene; page B is a stub ('continuation of the
    spread from page A', no text, no chars). Split A's text at the sentence
    midpoint, move the second half to B, and promote B to a real companion
    scene (same cast/setting, continue-the-moment action) so both facing
    pages carry balanced text over real art. Idempotent: a B page that
    already has text is left alone. Mutates and returns `scenes`."""
    by = {str(s.get("page")): s for s in scenes}
    for s in scenes:
        m = _CONT.search(s.get("action", "") or "")
        if not m or (s.get("text") or "").strip():
            continue
        a = by.get(m.group(1))
        if a is None:
            continue
        first, second = _split_text(a.get("text", ""))
        if not second:
            continue
        a["text"], s["text"] = first, second
        for k in ("chars", "setting", "setting_key", "mood", "camera",
                  "text_area"):
            if not s.get(k):
                s[k] = a.get(k)
        s["action"] = (
            f"Right-hand page of the two-page spread that begins on page "
            f"{a.get('page')}: the SAME moment, place and cast a beat later, "
            f"from a slightly different angle — do NOT duplicate page "
            f"{a.get('page')}'s exact composition. Spread scene: "
            f"{a.get('action', '')}")
        print(f"  spread balance: page {a.get('page')} -> {a.get('page')}"
              f"+{s.get('page')} ({len(first)}/{len(second)} chars)")
    return scenes


def parse(docx_path, out_dir):
    text = _read_docx(docx_path)
    print(f"  read {docx_path} ({len(text)} chars)")
    plan = llm.chat_json(SYSTEM, text, max_tokens=32000)
    balance_spreads(plan.get("scenes", []))
    os.makedirs(out_dir, exist_ok=True)

    characters = {
        "style": plan.get("style", {}),
        "characters": plan.get("characters", []),
        "lookalike_groups": plan.get("lookalike_groups", []),
    }
    scenes = {"title": plan.get("title", ""), "author": plan.get("author", ""),
              "settings": plan.get("settings", []),
              "scenes": plan.get("scenes", [])}
    toon_io.save(characters, f"{out_dir}/characters.toon")
    toon_io.save(scenes, f"{out_dir}/scenes.toon")
    print(f"  title: {scenes['title']}  author: {scenes['author']}")
    print(f"  style: {characters['style'].get('name','?')}")
    locked = [c['name'] for c in characters['characters'] if c.get('locked_spec')]
    print(f"  characters: {[c['name'] for c in characters['characters']]}")
    print(f"  locked_spec on: {locked}")
    print(f"  look-alike groups: {[g['members'] for g in characters['lookalike_groups']]}")
    print(f"  settings: {[s.get('key') for s in scenes['settings']]}")
    print(f"  scenes: {len(scenes['scenes'])} pages")
    reconcile(scenes["scenes"], text)
    return plan


if __name__ == "__main__":
    import sys
    parse(sys.argv[1], sys.argv[2])
