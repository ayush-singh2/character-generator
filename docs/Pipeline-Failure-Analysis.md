# Failure Analysis — Why the Current Pipeline Cannot Guarantee Consistency

Evidence base: client QA notes on the v6_a Bilbo book, the Ella v3/v3_klora
books, the v5.8→v6.4 DEVLOG, and every defect observed during this week's
runs. The goal here is mechanism-level diagnosis, not blame: each class ends
with the invariant a redesigned pipeline must guarantee.

---

## Class 1 — Character identity drift (faces, muzzles, proportions, age)

**Observed:** Bilbo/Obi facial features, muzzle shapes, ears, proportions and
apparent age change page to page (QA pp. 5–10, 17–18); the dogs are only
recognizable by cap color. Ella's hair puffs drifted position across pages;
her bracelet flipped wrists or vanished.

**Mechanisms, in order of importance:**

1. **Every page is an independent draw from a distribution.** Nothing couples
   page N to page N+1 except shared inputs (sheet, LoRA, seed). Two draws
   from the same distribution still differ — and 19 draws explore its whole
   width. We never render "the same dog twice"; we render 19 plausible dogs.
2. **Conditioning is advisory, not binding.** Kontext "repaints" the
   reference; adherence degrades as scenes get busier. There is no mechanism
   that *forces* the output's character to match the reference — only a
   preference.
3. **One LoRA per page (anti-stacking rule) leaves the co-star unanchored.**
   On every duo page, exactly one dog has trained weights; the other rides
   only the stitched sheet — and it drifts most.
4. **Compounding generational loss.** Identity flows sheet → training views →
   LoRA weights → page render → i2i corrections. Every arrow re-interprets
   rather than preserves; small errors multiply. The LoRA is a copy of a
   copy of the sheet.
5. **Correction adds its own drift.** Each i2i fix redraws the character; the
   judge accepts "roughly matching", so repeated fixes random-walk within the
   judge's tolerance band.
6. **Identity is judged in prose, not measured.** A vision judge saying
   "looks right" has wide, inconsistent tolerance (it also hallucinated a
   collar). There is no quantitative identity metric with a threshold.

**Required invariant:** one canonical identity asset per character, used
identically by every render, plus a *measured* identity check (not prose)
that a page must pass to be accepted.

## Class 2 — Rendering-style drift (cartoon ↔ painterly ↔ photorealistic)

**Observed:** title/dedication/about-author pages photorealistic-cinematic
(QA pp. 2, 3, 19); p9/p11 more painterly/realistic than neighbors; Ella book
tone drift was the client's first complaint.

**Mechanisms:**

1. **Style is carried by text only** — the weakest channel. Pages WITH
   character sheets inherit some style from them incidentally; pages WITHOUT
   conditioning (matter pages) get pure model prior → photorealism.
2. **Different page classes take different model routes** (kontext+LoRA vs
   pure t2i) with different style priors.
3. **Sampling randomness**: seed was per-page random until v6.2; fixed seed
   mitigates but doesn't pin style.
4. **No style asset exists.** We have a style *paragraph*, not a style
   *reference image* or style *LoRA* that every page must obey.

**Required invariant:** a single style anchor (image or trained weights)
applied to EVERY page — story, matter, and cover — through one model route,
plus a style-similarity check per page.

## Class 3 — Anatomy artifacts

**Observed:** human-like legs on dogs + duplicated/extra hands (QA p11);
disembodied floating legs (QA p12); two Ellas hugging one puppy (Ella p15).

**Mechanisms:**

1. Diffusion's known weakness in **interaction scenes** (holding, hugging,
   petting) — limb ownership between touching bodies is where extra/merged
   limbs appear. Our worst artifacts are all interaction pages.
2. **No artifact-specific QA.** The composition judge has an ANATOMY category
   but is instructed to be conservative; it shipped every one of these.
3. Crowded multi-character scenes multiply risk; nothing budget-limits
   background cast density.

**Required invariant:** an artifact detector tuned to the known classes
(limb count, limb attachment, species-correct anatomy, duplicated
characters) run on every page, with regeneration — not i2i patching — as the
response to structural failures.

## Class 4 — Text–image contradictions

**Observed:** "they each got a pup cup" → three cups (QA p12); Mom and Dad →
three adults (QA p15); "became very sleepy" → alert dogs (QA p14).

**Mechanisms:**

1. **The render prompt is built from the scene DESCRIPTION, not the page
   TEXT.** The narrative facts (counts, cast, emotional states) are never
   extracted, so they constrain nothing.
2. Counting is a known diffusion weakness — unconstrained, it fails often.
3. **No fidelity check exists**: nothing ever asks "does this image
   contradict the words printed on it?"

**Required invariant:** per-page structured fact sheet (who, how many of
what, what state/mood) derived from the page text — injected into the prompt
AND verified against the final art by a VLM check.

## Class 5 — Negative space for captions

**Observed:** bands occupied by subjects; close-up scenes that cannot have an
empty third; edge-energy metric passing occupied bands; retries burning money.

**Mechanisms:**

1. **A hard layout constraint expressed as a soft prompt preference.** The
   model treats "leave the top empty" as a suggestion.
2. The verification metric (edge energy) measured texture, not occupancy.
3. The retry loop is a lottery: pay again, hope the next sample complies.
4. Layout desires conflict with shot types (a close-up hug can't yield an
   empty band) and nothing reconciles them at planning time.

**Required invariant:** caption space guaranteed by construction — e.g.
generate art for the art region and extend/outpaint the caption band, or
regional control — not by re-rolling and hoping.

## Class 6 — Systemic/process weaknesses (cross-cutting)

1. **Judge unreliability:** hallucinated items (the collar), pedantic flags
   on conditional items, inconsistent tolerance. QA noise causes both wasted
   retries and false accepts. Judges need calibration and structured rubrics,
   and should verify *measurable* facts where possible.
2. **Retry-lottery economics:** most quality mechanisms are "sample again" —
   cost scales with defect rate and convergence is probabilistic.
3. **Plan-vs-rule conflicts:** blanket rules (no collages) fought explicit
   author intent until special-cased; constraint precedence was implicit.
4. **Spec vs. sheet ambiguity:** LLM-invented hex specs fought accepted
   sheets; source-of-truth precedence (client art > client text > sheet >
   generated spec) was never formalized.
5. **The correction loop is load-bearing.** The old reference-conditioned
   pipeline needed it less; the current one does not converge without it.
   A pipeline whose primary quality mechanism is post-hoc repair of its
   primary generator is architecturally upside down.

---

## What the redesign must guarantee (requirements going into design)

- **R1 Canonical identity:** one identity asset per character (and per DUO),
  used by every render; page acceptance gated on a measured identity
  similarity, not judge prose.
- **R2 Global style lock:** one style anchor applied to all 19+ pages through
  one model route; measured style similarity per page.
- **R3 Layout by construction:** caption zones guaranteed structurally
  (region control / outpainting), not by prompt hope + retry.
- **R4 Narrative fact contract:** per-page facts (cast, counts, states)
  extracted from the printed text; used in generation and verified after.
- **R5 Specialized artifact QA:** limb/attachment/duplication checks on every
  page; structural failures trigger regeneration, not patching.
- **R6 Bounded, diagnostic retries:** every retry must change strategy based
  on the specific failure (different conditioning, different shot, different
  model) — never the same prompt re-rolled.
- **R7 Source-of-truth precedence:** client art > client text > accepted
  sheet > generated spec, encoded once, honored by every stage.
