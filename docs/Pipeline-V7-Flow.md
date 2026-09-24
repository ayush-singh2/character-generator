# The v7 Pipeline — How a Manuscript Becomes an Illustrated Book

One sentence: **manuscript -> plan -> QA'd reference sheets -> per-page fact
contracts -> multi-reference generation (sheets + style plate as images) ->
scored yes/no verification -> targeted repair or flag -> typeset -> PDF.**

The philosophy shift from the previous pipeline: character identity and art
style used to be *requested* in prompts and repaired afterwards; now they are
*supplied* as reference images and *measured* before a page is accepted.

---

## Stage 1 — Parse (docx -> plan)

We read the client's manuscript docx and have an LLM extract the whole book
plan as structured data: the style description, every character with a locked
spec (species, colours, signature items like "green cap, red baseball
bandana — always"), look-alike groups (Bilbo + Obi), recurring settings, and
one scene per page (setting, action, mood, and the printed page text).
Saved as `.toon` files under the version dir (e.g. `v6_b/data/`).

## Stage 2 — Reference sheets (the "Book Bible")

For each main character we generate an official character sheet (portrait +
full body on a white background); for the look-alike duo a *combined* sheet
showing both side by side, so their contrast — green vs blue cap — is defined
in one image; and a plate per recurring setting. When the client provides
real art (their V6 PDF pages), we condition on it for likeness. Every sheet
is QA'd by a vision judge and re-rendered until it matches the spec.

These sheets become the single source of truth: everything downstream copies
*them*, never a fresh interpretation of the text.

## Stage 3 — Layout

An LLM decides each page's composition: where each character sits (coordinate
boxes) and which side of the frame stays empty for the caption text.

## Stage 4 — Page contracts  *(new in v7)*

From the *printed text* of each page we extract verifiable facts: "exactly
2 adults", "exactly 2 pup cups", "the dogs must look sleepy". Each contract
is used twice — written into the generation prompt, and checked against the
finished art. Generation and verification can never disagree about what was
required.

## Stage 5 — Generate  *(the big v7 change)*

For every page — story pages AND cover / title / dedication / about-author —
we call Gemini's image model with the scene prompt plus a stack of reference
images, each with a named job:

- "Image 1 = Bilbo & Obi's official designs — copy each EXACTLY."
- "Image 2 = the book's ART STYLE — match it; don't copy its scene."
- "Image 3 = the recurring location — same place, same colours."

Identity and style come from *images*, not from words. Because the style
plate rides on every page, matter pages can no longer drift photorealistic.

(The previous way was FLUX Kontext + trained LoRA weights. A measured
bake-off on the six hardest pages showed raw Gemini multi-ref beats even the
*corrected* Kontext output — so LoRA training was removed from the flow:
cheaper, faster, and one fewer copy-of-a-copy in the identity chain.)

## Stage 6 — Measured gate  *(new in v7)*

Instead of a judge saying "looks fine", we ask a vision model batches of
yes/no questions and score each category 0–100:

- **Identity** — same muzzle/head shape, same signature items, same apparent
  age as the reference sheet?
- **Facts** — exactly two pup cups? exactly two adults? do the dogs look
  sleepy? (straight from the page contract)
- **Anatomy** — every limb attached and counted, no human legs on animals,
  no duplicated characters, no text inside the art?
- **Style** — same rendering family as the style plate, not photorealistic?

Binary questions anchored to spec facts leave the judge nothing to invent —
this replaced a prose judge that once hallucinated a collar that existed in
no spec and no sheet.

## Stage 7 — Diagnostic repair

Each failure type gets its *own* remedy (never "same prompt, roll again"):

| Failure | Remedy |
|---|---|
| anatomy or style | REGENERATE the page — structure can't be patched |
| identity or facts | surgical i2i edit quoting the exact failed questions ("remove the third pup cup") |
| caption band occupied | repaint just that band into calm sky/ground |

Two repair rounds maximum. A page that still fails keeps its best-scoring
attempt and is **flagged** in `gate_report.json` for human review — surfaced
honestly instead of shipped silently.

## Stage 8 — Compose + book

Typesetting: find the calmest strip on the page, place the caption there with
adaptive ink (dark or light) and a soft scrim when the background needs it —
then bind all pages into the print-ready PDF.

---

## Old pipeline vs v7, at a glance

| | v6 (kontext + LoRA) | v7 |
|---|---|---|
| identity carried by | trained LoRA weights + stitched sheet | role-assigned reference images |
| style carried by | prompt text (nothing on matter pages) | style plate image on EVERY page |
| story facts | not extracted, not checked | contract: in the prompt AND verified |
| quality check | prose vision judge | scored yes/no probes per category |
| on failure | same-prompt retry lottery | remedy matched to the failure type |
| unfixable page | shipped anyway | flagged for human review |
| LoRA training | ~$6 + 20 min per book | none |
