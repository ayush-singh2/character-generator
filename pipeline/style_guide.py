"""Single source of truth for the Ballast Books house style guide.

The guide (data/ballast_style_guide.md) is a prose COPYEDITING standard — numbers,
dates, punctuation, italics, a canonical word list, etc. It governs every piece of
text the pipeline writes or corrects, so it is loaded once here and injected into
the system prompt of every text-authoring LLM call via `with_guide(...)`, and
enforced wholesale by the copyedit stage (copyedit_v3.py).

Path resolution uses the module's *real* path so it works from the per-book
working dirs gen_book.sh creates (which symlink `pipeline` back to the repo).
"""

import os

# repo_root/pipeline/style_guide.py -> repo_root
_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
GUIDE_PATH = os.path.join(_ROOT, "data", "ballast_style_guide.md")

_cache: str | None = None


def load() -> str:
    """Return the full guide text (cached). Empty string if the file is missing
    so a misplaced guide degrades gracefully instead of crashing a whole run."""
    global _cache
    if _cache is None:
        try:
            with open(GUIDE_PATH, encoding="utf-8") as f:
                _cache = f.read().strip()
        except OSError:
            print(f"  WARN: Ballast style guide not found at {GUIDE_PATH}")
            _cache = ""
    return _cache


# Framing shown to the model around the raw rules when appended to a prompt.
_HEADER = (
    "\n\n---\n"
    "HOUSE STYLE — Ballast Books. Any prose you write, rewrite, or place on a "
    "page MUST follow every rule below (Chicago Manual of Style house variant). "
    "Apply it to titles, captions, cover/back-cover copy, and page text alike. "
    "Preserve the author's meaning, voice, and dialogue; change only what a rule "
    "requires.\n\n"
)


def with_guide(system_prompt: str) -> str:
    """Append the full house style guide to a system prompt.

    Every text-authoring stage wraps its SYSTEM prompt with this so the guide is
    fed to the model on every book generation, in full (no snippet retrieval)."""
    guide = load()
    if not guide:
        return system_prompt
    return system_prompt + _HEADER + guide
