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

import docx

from . import llm, toon_io

SYSTEM = """\
You are a children's picture-book ART DIRECTOR and CHARACTER DESIGNER. Read the \
whole manuscript, then produce a COMPLETE, richly detailed art plan.

Do all of this:
- Choose ONE cohesive ART STYLE that best fits THIS book's tone and audience (be \
specific and vivid — pick what suits the story, don't default to one look).
- DESIGN every recurring character that must stay consistent: give each a precise, \
REPEATABLE appearance (exact age, hair, skin, clothing, colours, signature items). \
Mark characters "high" consistency if they recur, "incidental" if one-off.
- Flag LOOK-ALIKE groups (characters that could be confused) and state the single \
feature that tells them apart.
- For EVERY page, infer a specific illustration from the page text: setting, what \
each character is doing, mood, and camera. Keep the page TEXT verbatim.

Return ONLY JSON, no prose:
{
  "title": "...",
  "style": {"name":"","medium":"","linework":"","palette":"","lighting":"","mood":"","influences":""},
  "characters": [
    {"name":"","role":"","kind":"human|dog|animal|creature","appearance":"",
     "hair":"","outfit":"","palette":"","distinguishing_features":"","personality":"",
     "consistency":"high|incidental"}
  ],
  "lookalike_groups": [{"members":["",""],"distinguish":""}],
  "scenes": [
    {"page":"1","layout":"single|spread","chars":["name",...],
     "setting":"","action":"","mood":"","camera":"","text":"","text_area":"top|bottom|left|right"}
  ]
}
Rules: every name in a scene's "chars" must exist in "characters" (use [] if a page \
has no recurring character); number pages sequentially in reading order; text_area \
is where the page text should sit (a calm side away from the main subject)."""


def _read_docx(path):
    d = docx.Document(path)
    return "\n".join(p.text for p in d.paragraphs if p.text.strip())


def parse(docx_path, out_dir):
    text = _read_docx(docx_path)
    print(f"  read {docx_path} ({len(text)} chars)")
    plan = llm.chat_json(SYSTEM, text, max_tokens=12000)
    os.makedirs(out_dir, exist_ok=True)

    characters = {
        "style": plan.get("style", {}),
        "characters": plan.get("characters", []),
        "lookalike_groups": plan.get("lookalike_groups", []),
    }
    scenes = {"title": plan.get("title", ""), "scenes": plan.get("scenes", [])}
    toon_io.save(characters, f"{out_dir}/characters.toon")
    toon_io.save(scenes, f"{out_dir}/scenes.toon")
    print(f"  title: {scenes['title']}")
    print(f"  style: {characters['style'].get('name','?')}")
    print(f"  characters: {[c['name'] for c in characters['characters']]}")
    print(f"  look-alike groups: {[g['members'] for g in characters['lookalike_groups']]}")
    print(f"  scenes: {len(scenes['scenes'])} pages")
    return plan


if __name__ == "__main__":
    import sys
    parse(sys.argv[1], sys.argv[2])
