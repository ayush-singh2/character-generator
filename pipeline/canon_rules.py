"""Canon rules — one source of truth for per-character BODY PLAN, used by
BOTH generation (prevent the defect) and detection (judge against expectation).

The problem this fixes
----------------------
The client's "6-legged giraffe/zebra" is not a leg-count error — it's an
INCOHERENT BODY PLAN: a human-like torso + 2 arms on a full 4-legged animal
body (see memory: six-legs-is-body-plan-chimera). Root cause: background
animals (giraffe, zebra, goat) have no reference sheet and no declared body
plan, so the generator improvises — bipedal on one page, quadruped-chimera on
the next. Even the named cast had no explicit "you stand on two legs" rule.

The fix: declare each character's body plan once, then:
  - GENERATION reads it → the prompt states "draw X as an upright bipedal
    character (2 legs + 2 arms), never as a four-legged animal" → the chimera
    isn't drawn in the first place.
  - DETECTION reads it → anatomy_v8 judges each figure against its EXPECTED
    plan, so a bipedal pig in a floor-yoga pose is judged as bipedal (not a
    quadruped chimera) → kills the floor-pose false positive.

Data
----
Stored in <data_dir>/canon_rules.toon, author-editable:
  {"default_body_plan": "upright_bipedal",
   "body_plans": {"Ferdinand": "upright_bipedal", "giraffe": "upright_bipedal", ...}}
If the file is absent we synthesise a sensible default (every character +
common background species = the book default) and WRITE it, so there is always
a concrete, editable canon on disk.

Body-plan vocabulary matches anatomy_v8: "upright_bipedal" | "natural_quadruped".
"""

import os

from . import toon_io

FILE = "canon_rules.toon"
DEFAULT_PLAN = "upright_bipedal"

# Background/incidental animals a manuscript scene may call for but that have no
# reference sheet — given the book default plan so they can't drift to chimera.
COMMON_BACKGROUND = [
    "giraffe", "zebra", "goat", "sheep", "pig", "cat", "dog", "rabbit",
    "bear", "fox", "owl", "duck", "elephant", "lion", "monkey", "cow",
    "horse", "deer", "mouse", "frog", "bird",
]


def _species_of(char: dict) -> str:
    """Best-effort species word from a character's appearance text (for
    matching a located figure's species label back to a named character)."""
    txt = (char.get("appearance", "") + " " + char.get("name", "")).lower()
    for sp in COMMON_BACKGROUND:
        if sp in txt:
            return sp
    return ""


def build_default(data_dir: str) -> dict:
    """Synthesise a canon-rules dict: every named character + common background
    species mapped to the book default body plan."""
    plans = {}
    try:
        chars = toon_io.load(os.path.join(data_dir, "characters.toon")).get("characters", [])
    except Exception:                                        # noqa: BLE001
        chars = []
    for c in chars:
        plans[c["name"]] = DEFAULT_PLAN
        sp = _species_of(c)
        if sp:
            plans[sp] = DEFAULT_PLAN
    for sp in COMMON_BACKGROUND:
        plans.setdefault(sp, DEFAULT_PLAN)
    return {"default_body_plan": DEFAULT_PLAN, "body_plans": plans}


def species_map(data_dir: str) -> dict:
    """{character_name: species} from characters.toon (e.g. Twiggy→zebra,
    Tallia→giraffe, Ferdinand→goat). Needed because the vision locator labels
    figures by SPECIES while the scene cast is by NAME — comparing the two
    directly is why the cast-presence check false-flagged everyone missing."""
    out = {}
    try:
        chars = toon_io.load(os.path.join(data_dir, "characters.toon")).get("characters", [])
    except Exception:                                        # noqa: BLE001
        return out
    for c in chars:
        sp = _species_of(c)
        if sp:
            out[c["name"]] = sp
    return out


def load(data_dir: str) -> dict:
    """Load canon rules; create-and-persist a default if none exists."""
    path = os.path.join(data_dir, FILE)
    if os.path.exists(path):
        try:
            return toon_io.load(path)
        except Exception:                                    # noqa: BLE001
            pass
    rules = build_default(data_dir)
    try:
        toon_io.save(rules, path)
        print(f"  wrote default canon rules -> {path}")
    except Exception as e:                                    # noqa: BLE001
        print(f"  canon rules: could not persist default ({str(e)[:50]})")
    return rules


def expected_plan(name_or_species: str, rules: dict) -> str:
    """Expected body plan for a character name OR a located species label.
    Loose match (word-level, both directions) so 'baby giraffe' → 'giraffe'
    and a name whose species is declared both resolve."""
    plans = rules.get("body_plans", {})
    key = (name_or_species or "").lower().strip()
    for k, v in plans.items():
        kl = k.lower()
        if kl == key:
            return v
    for k, v in plans.items():
        kl = k.lower()
        if kl in key or key in kl or any(w in key for w in kl.split() if len(w) > 2):
            return v
    return rules.get("default_body_plan", DEFAULT_PLAN)


def generation_clause(rules: dict, present: list[str] | None = None) -> str:
    """A prompt clause telling the generator each present character's body plan,
    so chimeras aren't drawn. If `present` is given, scope to those names."""
    plans = rules.get("body_plans", {})
    names = [n for n in (present or plans) if n in plans] or list(plans)
    upright = sorted({n for n in names
                      if plans.get(n) == "upright_bipedal"})
    quad = sorted({n for n in names
                   if plans.get(n) == "natural_quadruped"})
    bits = []
    if upright:
        bits.append(
            f"BODY PLAN: {', '.join(upright)} are UPRIGHT BIPEDAL characters — "
            f"each stands and poses on TWO legs with TWO arms, like a person "
            f"(human-like torso, animal head/features). NEVER draw them with a "
            f"four-legged animal body, and NEVER add extra legs — exactly two "
            f"legs and two arms per character, even in a yoga/floor pose")
    if quad:
        bits.append(
            f"BODY PLAN: {', '.join(quad)} are NATURAL FOUR-LEGGED animals — "
            f"four legs, animal body, no human arms")
    return " . ".join(bits)
