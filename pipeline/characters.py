"""Stage 2 + 3 — character mining and the character bible.

Stage 2 reads the whole manuscript and produces a *roster*: every named
character, ranked by narrative weight, with every visual detail the text
mentions about them gathered in one place.

Stage 3 takes the top characters and drafts a detailed, image-ready visual
"bible" — the canonical description we'll feed to Flux to generate each
character's reference sheet and keep them consistent across pages.

Run:  python -m pipeline.characters
In:   data/manuscript.json     (from pipeline.extract)
Out:  data/characters.json     (roster + bible)
"""

import json
import os

from .llm import TEXT_MODEL, chat_json

IN_PATH = "data/manuscript.json"
OUT_PATH = "data/characters.json"

# How many of the top-ranked characters get a full visual bible.
MAX_BIBLE_CHARACTERS = 5

ROSTER_SYSTEM = """\
You are a literary character analyst preparing a book for illustration.
You read a manuscript and identify its characters, then rank them by how
much they MATTER visually to the illustrations (screen time + how often they
are present in scenes that would be drawn), not just by plot importance.

Return STRICT JSON only, no prose, with this shape:
{
  "characters": [
    {
      "name": "<canonical name>",
      "aliases": ["<other names/titles used>"],
      "weight": <integer 0-100, narrative+visual prominence>,
      "tier": "main" | "supporting" | "minor",
      "role": "<one sentence: who they are in the story>",
      "visual_mentions": [
        "<each concrete visual detail the text states about them, verbatim or close paraphrase: clothing, body, age, hair, etc.>"
      ]
    }
  ]
}
Rank the array by weight, highest first. Include every named, embodied
character. Exclude pure abstractions, places, and unnamed crowds.
Only list visual_mentions the text actually supports — do not invent."""

BIBLE_SYSTEM = """\
You are a character designer creating a visual bible for an ANIME-STYLE
illustrated edition of a book. For each character you are given the text's
visual mentions and role. Produce a complete, internally consistent visual
design — where the text is silent, make tasteful choices that fit the
character's era, culture, and role, and mark those as "inferred".

The output drives an AI image generator, so be concrete and unambiguous
(exact colors, specific garments). Return STRICT JSON only:
{
  "characters": [
    {
      "name": "...",
      "tier": "...",
      "age_appearance": "...",
      "gender": "...",
      "height_build": "...",
      "skin_tone": "...",
      "hair": "<color, length, style>",
      "eyes": "<color, shape>",
      "face": "<face shape, notable features, expression at rest>",
      "distinguishing_features": ["..."],
      "default_outfit": {
        "description": "<full head-to-toe outfit>",
        "colors": ["<dominant colors>"]
      },
      "accessories": ["..."],
      "color_palette": ["<3-5 signature hex or named colors>"],
      "art_style_notes": "<anime sub-style cues that suit this character>",
      "inferred": ["<which fields were invented vs. text-stated>"],
      "flux_reference_prompt": "<a single dense prompt, ready to paste into Flux, that would generate a clean full-body character reference sheet of this character: anime style, neutral pose, plain background, front view>"
    }
  ]
}"""


def _manuscript_text(doc: dict, story_no: int | None = None) -> str:
    parts = []
    for p in doc["pages"]:
        if story_no is not None and p.get("chapter_no") != story_no:
            continue
        head = f"[page {p['page_no']}"
        if p.get("chapter_no"):
            head += f", ch{p['chapter_no']}: {p['chapter_title']}"
        head += "]"
        parts.append(f"{head}\n{p['text']}")
    return "\n\n".join(parts)


def mine_roster(doc: dict, story_no: int | None = None) -> dict:
    user = (
        f"Title: {doc.get('title')}\nAuthor: {doc.get('author')}\n\n"
        f"MANUSCRIPT:\n{_manuscript_text(doc, story_no)}"
    )
    return chat_json(ROSTER_SYSTEM, user, max_tokens=8192, temperature=0.3)


def draft_bible(roster: dict, doc: dict, limit: int = MAX_BIBLE_CHARACTERS) -> dict:
    top = roster["characters"][:limit]
    user = (
        f"Book: {doc.get('title')} by {doc.get('author')}\n"
        f"Setting/era cues come from the visual mentions below.\n\n"
        f"CHARACTERS TO DESIGN:\n{json.dumps(top, indent=2, ensure_ascii=False)}"
    )
    return chat_json(BIBLE_SYSTEM, user, max_tokens=6000, temperature=0.5)


def build_characters(story_no: int | None = None) -> dict:
    with open(IN_PATH) as f:
        doc = json.load(f)

    scope = f" (story {story_no})" if story_no else ""
    print(f"Model: {TEXT_MODEL}")
    print(f"Stage 2: mining character roster{scope} ...")
    roster = mine_roster(doc, story_no)

    print("Stage 3: drafting visual bible for top characters ...")
    bible = draft_bible(roster, doc)

    out = {
        "title": doc.get("title"),
        "author": doc.get("author"),
        "story_no": story_no,
        "roster": roster["characters"],
        "bible": bible["characters"],
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"\nRoster ({len(roster['characters'])} characters):")
    for c in roster["characters"]:
        print(f"  [{c['weight']:>3}] {c['tier']:<10} {c['name']} — {c['role']}")
    print(f"\nBible drafted for {len(bible['characters'])} characters -> {OUT_PATH}")
    return out


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", type=int, default=None, help="scope to one story number")
    build_characters(ap.parse_args().story)


if __name__ == "__main__":
    main()
