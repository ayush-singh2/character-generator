"""Style selection — judge the best art style for a manuscript.

The illustration guide's ~36 portfolio samples collapse into a handful of
style families (encoded below from a review of the guide). This stage asks
Claude to read the manuscript and pick the family that best fits its tone and
audience, then refine it into ONE concrete style descriptor that is injected
into every image prompt (character refs and pages) so the whole book is
visually coherent.

Run:  python -m pipeline.style
In:   data/manuscript.json
Out:  data/style.json   ({chosen, style_prompt, palette, reasoning})
"""

import json

from .llm import chat_json

IN_PATH = "data/manuscript.json"
OUT_PATH = "data/style.json"

# Style families distilled from the Blue Balloon Artist Portfolio (guide pp9-16).
STYLE_CATALOG = {
    "warm_watercolor": "warm ink-and-watercolor children's book illustration, bold confident outlines, vibrant saturated colours, expressive rounded characters, soft textured washes — like the reference book 'Brunt and Eggbert'",
    "soft_digital": "soft modern digital children's illustration, gentle gradients, pastel palette, rounded friendly shapes, soft diffuse lighting",
    "whimsical_storybook": "whimsical classic storybook watercolour, soft dreamy palette, delicate linework, gentle fantasy atmosphere",
    "bright_cartoon": "bright modern cartoon, clean vector-like shapes, bold flat colours, playful high-energy, thick clean outlines",
    "painterly_cinematic": "painterly cinematic illustration, dramatic directional lighting, rich atmospheric colour, semi-realistic forms, mood-driven composition",
    "muted_vintage": "muted vintage editorial illustration, ink-wash and pencil texture, limited desaturated palette, literary and atmospheric",
    "bold_comic": "bold graphic-novel style, dynamic camera angles, strong inking, saturated colour, energetic motion",
    "seinen_anime": "seinen anime style, realistic proportions, detailed expressive faces, cinematic lighting, mature tone",
}

SYSTEM = """\
You are an art director choosing an illustration style for a book. You are
given the manuscript and a catalog of available style families. Judge the
book's tone, genre, and target audience, then choose the single best-fitting
style family and write a refined, concrete style descriptor to feed an AI
illustrator consistently across every page.

CRITICAL: the style_prompt is appended to EVERY image prompt, so it must
describe ONLY the visual STYLE — medium, linework, colour palette, texture,
lighting, and overall mood. It must NOT mention any subject matter, scenes,
characters, actions, poses, settings, or props from the story (no "flight
scenes", "forest", "running", etc.). Base it on the chosen catalog family and
the book's tone only. If you invent style details, keep them generic to the
medium, never specific to this book's plot.

Return STRICT JSON only:
{
  "audience": "<inferred reader age/group>",
  "tone": "<2-4 mood adjectives>",
  "chosen": "<exact key from the catalog>",
  "runner_up": "<exact key>",
  "reasoning": "<2-3 sentences on why this style fits>",
  "style_prompt": "<one dense STYLE-ONLY descriptor, refined from the chosen family — medium, linework, colour, texture, lighting, mood. NO subject matter or scenes>",
  "palette": ["<4-6 signature colours, names or hex>"]
}"""


def _sample(doc: dict, n_pages: int = 6) -> str:
    out = []
    for p in doc["pages"][:n_pages]:
        out.append(p["text"][:600])
    return "\n\n".join(out)


def judge(doc: dict) -> dict:
    catalog = "\n".join(f"- {k}: {v}" for k, v in STYLE_CATALOG.items())
    user = (
        f"STYLE CATALOG:\n{catalog}\n\n"
        f"BOOK: {doc.get('title')} by {doc.get('author')}\n"
        f"SAMPLE PROSE:\n{_sample(doc)}"
    )
    result = chat_json(SYSTEM, user, max_tokens=1200, temperature=0.3)
    # Guard: ensure chosen key is valid; fall back to warm_watercolor.
    if result.get("chosen") not in STYLE_CATALOG:
        result["chosen"] = "warm_watercolor"
        result["style_prompt"] = STYLE_CATALOG["warm_watercolor"]
    return result


def load_style_prompt() -> str:
    """Used by refs.py / illustrate.py to append the style to every prompt."""
    try:
        return json.load(open(OUT_PATH)).get("style_prompt", "")
    except FileNotFoundError:
        return ""


def main() -> None:
    doc = json.load(open(IN_PATH))
    result = judge(doc)
    json.dump(result, open(OUT_PATH, "w"), indent=2, ensure_ascii=False)
    print(f"Audience : {result.get('audience')}")
    print(f"Tone     : {result.get('tone')}")
    print(f"Chosen   : {result.get('chosen')}  (runner-up: {result.get('runner_up')})")
    print(f"Why      : {result.get('reasoning')}")
    print(f"Palette  : {result.get('palette')}")
    print(f"\nstyle_prompt -> {OUT_PATH}\n  {result.get('style_prompt')}")


if __name__ == "__main__":
    main()
