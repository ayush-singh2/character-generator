"""Visual-language motifs for picture-book actions.

A human illustrator draws *verbs*, not just nouns. When the manuscript says a
squirrel "smells new smells" she paints a lifted pink nose with curling scent
wisps rising off the source; when it says "RUN!" the tails stream back and the
paws blur mid-stride. A text-to-image model, left to itself, tends to paint the
noun (a squirrel, a nest) and drop the verb — the picture goes static.

This module is that missing vocabulary. Given a page's story text and the
writer's illustration note, it detects action cues and returns short, concrete
drawing instructions to splice into the Flux prompt so the *action reads at a
glance* — the way it does in the human-illustrated reference books.

Two ways to use it:
    cues = motif_cues(text, art_direction)      # -> ["scent wisps ...", ...]
    addendum = annotate(text, art_direction)    # -> one prompt-ready sentence

Plus explicit constructors when you already know the beat:
    smell("Drooling Dog", "a hot dog")          # the user's canonical example
    motion(["Scooter", "Caroline"])
    fear("Mother")
"""

import re

# Each motif: a set of trigger words (matched whole-word, case-insensitive
# against text + art direction) and the visual cue to inject. Ordered by
# specificity so the most telling action leads the addendum.
_MOTIFS: list[dict] = [
    {
        "name": "smell",
        "triggers": ["smell", "smells", "sniff", "sniffs", "sniffing", "scent",
                     "whiff", "nose out", "drooling"],
        "cue": ("show the SMELLING clearly: nose lifted and tilted toward the "
                "source, nostrils flared, a few soft curling scent-wisps drawn "
                "as faint ribbons of vapour drifting from the food or source up "
                "to the character's nose"),
    },
    {
        "name": "run",
        "triggers": ["run", "runs", "running", "ran", "sprint", "sprints",
                     "dart", "darts", "flee", "fled", "scurry", "race", "races",
                     "chase", "dashes"],
        "cue": ("show RUNNING in motion: body stretched low mid-stride, legs "
                "extended front-and-back, tail streaming straight out behind, a "
                "couple of light speed-lines and small kicked-up dust puffs at "
                "the feet"),
    },
    {
        "name": "fear",
        "triggers": ["afraid", "fear", "scared", "danger", "worried", "terrified",
                     "trembling", "shakes", "startles", "startled", "panic"],
        "cue": ("show FEAR on the face: eyes wide and round, pupils small, ears "
                "back, shoulders hunched and body leaning away from the threat"),
    },
    {
        "name": "shout",
        "triggers": ["shout", "shouts", "yell", "yells", "cries", "screams",
                     "screech", "calls", "exclaims", "roar"],
        "cue": ("show the SHOUT: mouth open wide mid-call, body leaning forward "
                "and one paw raised or pointing — leave the sound-word itself to "
                "the page text, do not draw letters"),
    },
    {
        "name": "look_up",
        "triggers": ["looks up", "look up", "looking up", "gaze", "peering up",
                     "stares up", "high above", "overhead", "circles above"],
        "cue": ("heads tilted up and eyes directed toward the sky / the thing "
                "above, chins lifted"),
    },
    {
        "name": "leap",
        "triggers": ["leap", "leaps", "leaping", "jump", "jumps", "jumping",
                     "hop", "pounce", "spring"],
        "cue": ("caught airborne mid-leap: legs tucked or spread, tail arced for "
                "balance, a small motion arc suggesting the jump path"),
    },
    {
        "name": "eat",
        "triggers": ["eat", "eats", "eating", "nibble", "nibbles", "nibbling",
                     "munch", "munching", "chew", "acorn", "acorns", "peanut",
                     "peanuts", "food", "snack"],
        "cue": ("holding the food in both front paws up to the mouth, cheeks "
                "rounded, taking a bite"),
    },
    {
        "name": "sleep",
        "triggers": ["sleep", "sleeps", "sleeping", "curled", "curls", "nap",
                     "asleep", "cozy", "snug", "rest", "resting"],
        "cue": ("curled into a soft cozy ball, eyes gently closed, tail wrapped "
                "around the body, calm restful posture"),
    },
    {
        "name": "hide",
        "triggers": ["hide", "hides", "hiding", "peek", "peeks", "peeking",
                     "poking out", "pokes out", "disguise", "disguised",
                     "ventures out", "darts back"],
        "cue": ("only partly visible — head and shoulders poking out from the "
                "nest hole / behind cover, curious cautious expression"),
    },
    {
        "name": "cry",
        "triggers": ["sad", "cries softly", "tears", "weeps", "sobbing",
                     "sighs", "misses", "lonely", "sighs desperately"],
        "cue": ("gentle downcast expression: drooping ears, soft eyes, a small "
                "glistening tear, shoulders lowered"),
    },
]

# Precompile a whole-word matcher per motif.
for _m in _MOTIFS:
    _m["_re"] = re.compile(
        r"\b(?:%s)\b" % "|".join(re.escape(t) for t in _m["triggers"]),
        re.IGNORECASE,
    )


def detect(text: str, art_direction: str = "") -> list[str]:
    """Return the names of motifs whose triggers appear in text or art note."""
    hay = f"{text}\n{art_direction}"
    return [m["name"] for m in _MOTIFS if m["_re"].search(hay)]


def motif_cues(text: str, art_direction: str = "", limit: int = 3) -> list[str]:
    """Return up to `limit` visual-cue strings for the actions on this page.

    Capped so the prompt stays focused on the page's dominant motion rather
    than piling on every incidental verb.
    """
    hits = [m["cue"] for m in _MOTIFS if m["_re"].search(f"{text}\n{art_direction}")]
    return hits[:limit]


def annotate(text: str, art_direction: str = "", limit: int = 3) -> str:
    """One prompt-ready sentence of action direction, or '' if nothing fires."""
    cues = motif_cues(text, art_direction, limit=limit)
    if not cues:
        return ""
    return "Make the action read clearly — " + "; ".join(cues) + "."


# --- explicit constructors: use when you already know the beat --------------

def smell(subject: str, source: str) -> str:
    """The canonical example: `smell("Drooling Dog", "a plate of food")`."""
    return (f"{subject} is smelling {source}: nose lifted toward {source}, "
            f"nostrils flared, soft curling scent-wisps rising as faint vapour "
            f"ribbons from {source} up to {subject}'s nose")


def motion(subjects) -> str:
    """Running/fleeing figures. `subjects` is a name or list of names."""
    who = subjects if isinstance(subjects, str) else ", ".join(subjects)
    return (f"{who} running hard mid-stride, bodies stretched low, tails "
            f"streaming out behind, light speed-lines and small dust puffs at "
            f"the feet")


def fear(subject: str) -> str:
    return (f"{subject} shows fear: eyes wide and round, ears back, body "
            f"leaning away, one paw drawn up")


def look_up(subjects, at: str = "the sky") -> str:
    who = subjects if isinstance(subjects, str) else ", ".join(subjects)
    return f"{who} looking up at {at}, chins lifted, eyes directed upward"


# Sound-words that a human illustrator sets in big emphatic display type rather
# than body text. Detecting these lets the renderer style them (bold / colour /
# larger) the way the reference books do with "SCREECH" and "RUN, SPARKY, RUN!".
_EMPHASIS_RE = re.compile(r"\b[A-Z]{3,}(?:[,!?]|\b)|[“\"][^”\"]*!”?")


def emphasis_words(text: str) -> list[str]:
    """Return shout/onomatopoeia fragments that deserve display styling.

    Picks up ALL-CAPS words (SCREECH, RUN) and exclaimed quoted phrases
    ("RUN, SPARKY, RUN!"). Used to tell the text renderer which runs to set
    bold / coloured / oversized, matching the human books.
    """
    out: list[str] = []
    for token in re.findall(r"\b[A-Z]{3,}\b", text):
        if token not in out:
            out.append(token)
    for phrase in re.findall(r"[“\"]([^”\"]*!)[”\"]", text):
        p = phrase.strip()
        if p and p not in out:
            out.append(p)
    return out
