"""Single source of truth for the client's V3 feedback → hard generation rules.

Every point the client raised on the two V3 books — *Bilbo & Obi's Baseball
Adventure* and *Ella the Animal Shelter and You* — is distilled here into a small
set of INVARIANTS. The image-facing subset is injected verbatim into BOTH
model-call sites so a single edit changes what the generator and the corrector
enforce:

  * generate_v7.py  → the v7 page-generation prompt      via ``t2i_block``
(the legacy correct_v3 i2i/judge call sites were removed with the v7 pivot;
``i2i_block``/``judge_block`` remain for ad-hoc surgical edits.)

Structural / text-fidelity rules (front matter, verbatim manuscript, uniform
trim, gutter-safe type, copyedit) are NOT image-model prompts; they are enforced
by parse_v3 / copyedit_v3 / compose_v3 / book_v3 and are documented here as data
(see ``STRUCTURAL``) so the checklist stays the one place the feedback lives.

Traceability for every client line → rule code lives in V3_FEEDBACK_PIPELINE.md.
"""

# --- IMAGE INVARIANTS (t2i + i2i + judge) --------------------------------------
# id, one-line human label, category. The prompt text is built below so the two
# call sites phrase the same rule for their own medium (generate vs. edit).
IMAGE_RULES = [
    ("STY-1", "One book style — no per-page style/linework/palette drift", "Consistency"),
    ("CHR-1", "Match the reference sheet EXACTLY: face, hair, skin, build", "Consistency"),
    ("CHR-2", "Keep EVERY signature item (bandana pattern+colour, collar, shirt logo, hair tie, bracelets)", "Consistency"),
    ("CHR-3", "Photo characters match the real reference photo — never a celebrity/generic face", "Consistency"),
    ("CHR-4", "Keep co-present look-alikes clearly distinct (never merge them)", "Consistency"),
    ("CHR-5", "No body/role swap — a character keeps their own body, job and place", "Consistency"),
    ("SCN-1", "Stay in the scene's stated location — no drift, no indoor/outdoor mix", "Scene"),
    ("SCN-2", "Draw ONLY what the scene calls for — invent no extra props", "Scene"),
    ("SCN-3", "Positions must be physically logical for the action", "Scene"),
    ("SCN-4", "Include every prop the scene names (e.g. dog leash) — none missing", "Scene"),
    ("IMG-1", "Full-bleed — art fills the whole trim, no empty margins, nothing cut off", "Image"),
    ("IMG-2", "ONE unified scene — never a grid/collage/split panels/vignettes or a mirrored duplicate", "Image"),
    ("IMG-3", "Clean anatomy — no warped, melted, extra or merged limbs/faces", "Image"),
    ("PRO-1", "Believable, consistent SCALE — same-type characters are the same relative size; nobody wildly too big/small for the scene", "Image"),
    ("PRO-2", "Correct RELATIVE HEIGHT between characters on EVERY page — a child stays child-sized next to an adult (never toddler-sized, never near-adult); obey any stated SIZE LOCK exactly", "Image"),
    ("GRD-1", "Every character firmly GROUNDED on a surface with correct perspective — nobody floating or 'sitting on air'", "Image"),
    ("CRP-1", "Natural FRAMING — don't crop a character to just legs / a headless body; show enough of each character to read them", "Image"),
    ("TXT-1", "ZERO written text in the art — no words, letters or numbers anywhere", "Text"),
]

# Props the client explicitly flagged as hallucinated — named so the model has a
# concrete "do not add" list rather than an abstract instruction.
BANNED_PROPS = ("stray hotdog/food stands", "extra vehicles", "invented signs or banners",
                "safety vests", "steam or smoke from nowhere", "parades", "unmotivated crowds")

# --- STRUCTURAL / TEXT RULES (enforced outside the image models) ---------------
# Documented here so the checklist is complete; owner = the stage that enforces.
STRUCTURAL = [
    ("MAN-1", "Page text is VERBATIM from the manuscript — never paraphrased or invented", "copyedit_v3/parse_v3"),
    ("MAN-2", "No page exists that isn't in the manuscript; no manuscript page is dropped", "parse_v3/book_v3"),
    ("FM-1", "Title page present; dedication on its OWN page", "parse_v3 (front matter)"),
    ("BM-1", "Required back matter present (About the Author, fostering-kittens page, etc.)", "parse_v3 (back matter)"),
    ("DIM-1", "Every page shares ONE uniform trim size", "book_v3"),
    ("TYP-1", "One locked type scale — body text is the same size on every page", "compose_v3"),
    ("TYP-2", "Text sits in genuine in-scene negative space with a safe edge margin — never clipped", "compose_v3"),
    ("TYP-3", "One locked text colour/treatment across the book", "compose_v3"),
    ("CPY-1", "House-style copyedit (em-dash vs ellipsis, no repeated weekday, etc.)", "copyedit_v3"),
    ("TTL-1", "Title-page font is the central/display face, matching the design", "compose_v3/cover"),
]


def _lines(rules):
    return "\n".join(f"  - [{rid}] {label}" for rid, label, _cat in rules)


def t2i_block(setting: str = "") -> str:
    """Hard-rule block for the text-to-image (initial render) call."""
    loc = f" The location is: {setting}." if setting else ""
    return (
        "CLIENT CHECKLIST — every rule below is mandatory and was a specific client complaint:\n"
        + _lines(IMAGE_RULES)
        + f"\nSETTING: keep the whole scene in the stated place.{loc}\n"
        + "DO NOT ADD any of these unless the scene names them: "
        + ", ".join(BANNED_PROPS) + ".\n"
    )


def i2i_block(setting: str = "") -> str:
    """Hard-rule block for the image-to-image identity-fix (edit) call. Same rules,
    phrased as corrections so the editor repairs drift without breaking the page."""
    loc = f" Keep them in: {setting}." if setting else ""
    return (
        "While fixing, also enforce the CLIENT CHECKLIST (fix any that are violated, "
        "otherwise leave untouched):\n"
        + _lines(IMAGE_RULES)
        + f"\nKeep the same book style as the other pages.{loc}\n"
        + "Remove any invented props ("
        + ", ".join(BANNED_PROPS) + "), any duplicated/mirrored half of the image, "
        "and any warping. Keep the composition and other characters otherwise unchanged.\n"
    )


SIGNATURE_ALWAYS = (
    "You do NOT know which page number this is, so IGNORE any 'only on page X / "
    "cover / page 4' style conditions — you cannot verify them. Judge purely against "
    "the attached REFERENCE SHEET: if the reference shows an item (hat/cap, bandana/"
    "neckerchief, collar, accessory), that item MUST be present here too, in every "
    "pose; a signature item that is in the reference but missing on the page is a FAIL."
)


def judge_block() -> str:
    """Extra criteria appended to the vision judge so it flags scene/style/image
    problems, not only per-character identity drift."""
    return (
        "Beyond identity, also FAIL the page (correct=false) for any of: "
        "style/linework/palette differs from a consistent book look (STY-1); "
        "a signature item — bandana pattern, collar, shirt logo, hair tie, bracelet "
        "— is missing or redesigned (CHR-2); a photo-based face looks like a "
        "celebrity or generic person instead of the reference (CHR-3); the location "
        "is wrong or mixes indoor/outdoor (SCN-1); invented props appear (SCN-2); "
        "the page is a grid/collage/split panels/vignettes or a mirrored duplicate "
        "instead of one unified scene, or the subject is warped (IMG-2/IMG-3); "
        "or any written text appears in the art (TXT-1).\n"
        "ALSO judge COMPOSITION quality, not just identity: FAIL if two same-type "
        "characters are drawn at inconsistent sizes or anyone is wildly mis-scaled "
        "for the scene (PRO-1); if a character floats or is not properly grounded on "
        "a surface / the perspective is wrong (GRD-1); or if a main character is "
        "awkwardly cropped — e.g. shown as only legs or a headless body (CRP-1). "
        "Name the specific composition problem in 'issue' so it can be fixed.\n"
        + SIGNATURE_ALWAYS
    )


def all_rules():
    """(id, label, category, owner) for every rule — used to render the doc/report."""
    return ([(r, l, c, "t2i+i2i+judge") for r, l, c in IMAGE_RULES]
            + [(r, l, "Structural", o) for r, l, o in STRUCTURAL])
