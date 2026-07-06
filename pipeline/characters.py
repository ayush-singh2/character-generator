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
      "kind": "individual" | "representative",
      "role": "<one sentence: who they are in the story>",
      "visual_mentions": [
        "<each concrete visual detail the text states about them, verbatim or close paraphrase: clothing, body, age, hair, etc.>"
      ]
    }
  ]
}
Rank the array by weight, highest first.

GOAL: return the cast an illustrator needs to draw the scenes — aim for 5-8
subjects, and AT LEAST 3 whenever the story has any supporting cast at all.
A richer cast lets the illustrator compose varied, populated scenes.

Two kinds of entries are allowed:
  * "individual" — a distinct named person or animal (e.g. "Ella", "Grandma").
  * "representative" — ONE stand-in for a recurring group or a supporting/
    background role the pictures need, given a concise descriptive name (e.g.
    "Shelter dog", "Kid volunteer", "Shelter staff member", "Adoption visitor",
    "Café barista", "Second shelter dog"). Mark tier "supporting" or "minor".

Beyond the obvious leads, ALSO include the 2-3 most useful supporting or
background subjects that plausibly appear in the story's settings (e.g. staff
at a workplace, other animals, shopkeepers, event visitors, classmates) so the
scenes aren't empty. Ground them in what the text describes — do not invent an
unrelated cast.

RULES:
  * Rank real named individuals highest, then supporting, then background.
  * Do NOT emit raw narration phrases as characters (e.g. "Girls and boys",
    "Moms and dads", "Grown-ups and kids", "Everyone", "You"). Instead, if such
    a group recurs visually, CONSOLIDATE it into a single "representative"
    entry with a clean name (e.g. "Kid volunteer") — never one entry per phrase.
  * A prominent animal that recurs in the art (like the dogs in a dog book) is a
    valid subject — you may add up to two distinct ones if the story features
    several (e.g. "Shelter dog" and "Second shelter dog" of a different breed).
  * Exclude pure abstractions, places, and the reader ("YOU").
  * Only list visual_mentions the text actually supports — do not invent details.
Give the illustrator the main character plus its 3-5 most important supporting
and background subjects so full scenes can be composed."""

BIBLE_SYSTEM = """\
You are a character designer creating a visual bible for an ANIME-STYLE
illustrated edition of a book. For each character you are given the text's
visual mentions and role. Produce a complete, internally consistent visual
design — where the text is silent, make tasteful choices that fit the
character's era, culture, and role, and mark those as "inferred".

The output drives an AI image generator, so be concrete and unambiguous
(exact colors, specific garments).

CRITICAL — commit to ONE concrete individual per entry:
  * Even for a "representative" subject (e.g. "Shelter dog", "Kid volunteer"),
    design ONE specific individual with a SINGLE fixed appearance. Pick one
    breed, one gender, one hair/coat, one outfit. NEVER describe a category or
    a range ("various breeds", "mixed male and female", "diverse", "assorted",
    "different colors") — that makes an inconsistent, corrupted reference sheet.
    Choose one and describe only that one.
  * Set "species" correctly. For NON-human subjects (animals), the visual fields
    describe the ANIMAL: "hair" = its coat colour/length, "skin_tone" = "N/A",
    "default_outfit" = collar/bandana or "none", "face" = its muzzle/ears. Do
    NOT give an animal human clothing, hairstyles, or a human face.

Return STRICT JSON only:
{
  "characters": [
    {
      "name": "...",
      "tier": "...",
      "species": "human | dog | cat | <specific animal>",
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


# Pure narration / reader-address phrases that are never a real subject. These
# are dropped as a safety net; note we intentionally KEEP words like "kid",
# "dog", "child" so legitimate representative subjects ("Kid volunteer",
# "Shelter dog") survive.
_NON_SUBJECT = {"everyone", "you", "yourself", "anyone", "anybody",
                "someone", "somebody", "nobody", "us", "them", "all"}
# Bare multi-word narration phrases to drop outright.
_NON_SUBJECT_PHRASES = {
    "girls and boys", "boys and girls", "moms and dads", "dads and moms",
    "grown-ups and kids", "grown ups and kids", "kids and grown-ups",
    "mothers and fathers", "men and women",
}


def _is_group_name(name: str) -> bool:
    n = name.lower().strip()
    if n in _NON_SUBJECT_PHRASES:
        return True
    tokens = {t.strip("-_/.,") for t in n.replace("/", " ").split()}
    # Drop only if EVERY token is a non-subject word (e.g. "everyone", "you"),
    # so descriptive representatives like "kid volunteer" are kept.
    return bool(tokens) and tokens.issubset(_NON_SUBJECT)


def mine_roster(doc: dict, story_no: int | None = None) -> dict:
    user = (
        f"Title: {doc.get('title')}\nAuthor: {doc.get('author')}\n\n"
        f"MANUSCRIPT:\n{_manuscript_text(doc, story_no)}"
    )
    result = chat_json(ROSTER_SYSTEM, user, max_tokens=8192, temperature=0.3)
    # Safety net: drop any collective/group entries the LLM left in.
    chars = result.get("characters", [])
    result["characters"] = [c for c in chars if not _is_group_name(c.get("name", ""))]
    return result


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
