"""Cover & front-matter art.

Generates dedicated cover KEY ART (a dramatic hero scene, no text, with a calm
area at the top for the title) using the protagonist's reference images so the
cover character matches the interior. Also drafts a back-cover blurb.

Run:  python -m pipeline.cover
In:   data/characters.json, data/refs.json, data/style.json, data/manuscript.json
Out:  output/book/cover_art.png  +  data/cover.json (blurb)
"""

import json
import os

from . import flux
from .llm import chat_json
from .style import load_style_prompt

CHARACTERS = "data/characters.json"
REFS = "data/refs.json"
MANUSCRIPT = "data/manuscript.json"
BOOK_DIR = "output/book"
OUT_ART = os.path.join(BOOK_DIR, "cover_art.png")
OUT_META = "data/cover.json"

COVER_BRIEF_SYSTEM = """\
You are a book-cover art director. From the book info, write a single cover
key-art prompt: one iconic, emotionally resonant image featuring the lead
character that captures the book's essence. Composition MUST leave the upper
third calmer/lighter for the title, and contain NO text or lettering.
Also write a short back-cover blurb (3-4 sentences, enticing, no spoilers).

Return STRICT JSON:
{"cover_prompt": "<the image prompt>", "blurb": "<back-cover text>"}"""


def _lead(characters):
    bible = characters["bible"]
    return bible[0] if bible else None


def make_cover():
    characters = json.load(open(CHARACTERS))
    refs = json.load(open(REFS)) if os.path.exists(REFS) else {}
    doc = json.load(open(MANUSCRIPT))
    style_prompt = load_style_prompt()
    lead = _lead(characters)

    user = (
        f"BOOK: {doc.get('title')} by {doc.get('author')}\n"
        f"LEAD: {lead['name']} — {lead.get('age_appearance')}, "
        f"{lead.get('hair')}, {lead.get('default_outfit',{}).get('description','')}\n"
        f"ART STYLE: {style_prompt}"
    )
    brief = chat_json(COVER_BRIEF_SYSTEM, user, max_tokens=900, temperature=0.6)

    prompt = (
        f"{brief['cover_prompt']}. Restate the character exactly for consistency: "
        f"{lead.get('age_appearance')}, {lead.get('hair')}, "
        f"{lead.get('default_outfit',{}).get('description','')}. "
        f"Leave the top third soft and uncluttered for a title. No text, no letters. "
        f"Art style: {style_prompt}"
    )

    os.makedirs(BOOK_DIR, exist_ok=True)
    ref_imgs = []
    if lead and lead["name"] in refs:
        ref_imgs = [open(refs[lead["name"]]["portrait"], "rb").read(),
                    open(refs[lead["name"]]["full_body"], "rb").read()]
    img = flux.edit(prompt, ref_imgs) if ref_imgs else flux.generate(prompt)
    flux.save(img, OUT_ART)

    json.dump({"blurb": brief.get("blurb", ""), "cover_prompt": brief["cover_prompt"]},
              open(OUT_META, "w"), indent=2, ensure_ascii=False)
    print(f"Cover art -> {OUT_ART}")
    print(f"Blurb: {brief.get('blurb','')[:200]}")
    return OUT_ART


def main():
    make_cover()


if __name__ == "__main__":
    main()
