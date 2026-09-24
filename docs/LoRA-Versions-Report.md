# LoRA-Era Pipeline: Version History, Advantages & Failures

This report covers every pipeline version since we adopted LoRA training
(v5.8 to v6.4), what each one added, where it helped, where it failed — and an
honest assessment of why character consistency is still not at the level of
our previous (reference-conditioned) pipeline.

---

## v5.8 — LoRA bootstrap (2026-09-07)

Per-character trained identity on fal.ai: ~10 curated views generated from the
character's reference sheet to strict judge curation to fal fast LoRA training to
trigger-token registry (`ellatok`, `biscuittok`).

**Advantages**

- Identity lives in model weights, not just in attached images — in a clean
  solo smoke test the likeness was essentially perfect.
- Curation loop proved its worth immediately (it dropped the one view missing
  Ella's charm bracelet).
- Crash-safe registry; ~$3 per character.

**Failures**

- None visible yet at this stage — the problems appeared when the LoRAs met
  the real page pipeline (v5.9).

## v5.9 — First A/B: the LoRA path LOSES (2026-09-07)

Pages 1/4/15 of the Ella book rendered pure text-to-image with stacked LoRAs
vs. the reference-conditioned baseline.

**Result: baseline 45 / 85 / 75 — LoRA 45 / 45 / 45.**

**Failures (both proven in isolation)**

- **Stacking dilution:** two LoRAs active at once interfere; both identities
  smear (wrong outfit, wrong hair, broken proportions).
- **Token drowning:** trigger tokens carry almost no weight inside a
  several-hundred-word page prompt (placement + checklist + hex locks + style).

**Advantage of doing it this way:** the 3-page gate stopped us from paying for
a full bad book, and gave us the two failure mechanisms to design against.

## v6.0 — Kontext+LoRA: the recipe that finally won (2026-09-07)

Reference-sheet conditioning AND trained weights in ONE call
(`flux-kontext-lora`), with a short prompt.

**Result: 95 / 85 / 75 vs. baseline 45 / 85 / 75 — ≥ baseline on all three.**

**Advantages**

- The sheet anchors what things look like; the weights anchor how they are
  drawn; the short prompt lets both speak.
- Produced the rules we still use: ONE LoRA per page (the main character);
  co-stars ride in a stitched reference sheet; scale 1.0; short prompt.

**Failures**

- Stacking both LoRAs still collapsed the score (45) even with conditioning —
  confirming one-LoRA-per-page is a hard rule, not a preference.
- Residual small defects (missing bracelet, a leaked in-art sign).

## v6.1 — Recipe wired into the real pipeline (2026-09-07)

`generate_v3`'s LoRA path became the kontext+LoRA recipe: main character
selected by largest layout box, stitched co-star sheets, clean fallback to the
reference path.

**Advantages**

- 3-page validation: 85 / 95 / 95 vs. baseline 45 / 85 / 75.
- No character-specific hard-coding; mixed casts safe (untrained co-stars are
  in the conditioning image).

**Failures**

- Render variance is real: the same page 15 scored 45 on one roll and 95 on a
  re-roll (bracelet dropped, busy crowd). Single renders prove nothing.
- The edge-energy "empty band" metric passed frames whose caption area was
  visibly full of characters (flat cel-shading has few edges).

## v6.2 — Client feedback round on the first full book (2026-09-07)

Client saw the full Ella book and flagged: tone drifting between pages, the
bracelet flipping wrists or vanishing, and no negative space for text.

**Advantages (fixes that came out of it)**

- Fixed seed + same-palette prompt sentence for tone stability.
- Compact signature-items line in the prompt ("charm bracelet, always on left
  wrist"); "each named character exactly ONCE" after a page rendered two Ellas.
- Vision occupancy veto behind the edge-energy metric.
- Discovery that the pipeline was fighting its own art plan: pages that
  explicitly ask for collage/montage were being "fixed" by the anti-panel
  rules. Author-intended panel pages now honored.

**Failures (what the client actually experienced)**

- **Tone consistency broke** across the book — every page sampled a fresh
  seed, and nothing anchored palette/lighting between pages.
- **Accessory consistency broke** — the LoRA does not reliably carry
  ~20-pixel items, and wrist-side flips are a known FLUX mirroring limit.
- **Negative space was not being produced** where the client needed it.

## v6.4 — Bilbo end-to-end (2026-09-08)

First full second-book run (19-page PDF). Green/blue cap contrast held on
every sampled page — the historical duo-collapse defect did not reappear.

**Advantages**

- The whole flow (parse to refs to LoRA training to gate to book) now runs
  hands-off on a new manuscript, ~4× faster page rendering (thread pool).
- Sheet QA loop, phantom-item judge filter, must-appear cast line — all
  generic hardening that book #3 inherits.

**Failures found (and what they say about the approach)**

- Raw renders still dropped or swapped the dogs' caps; one page rendered with
  ZERO dogs until an explicit cast list was added to the prompt.
- Reference sheets came out wrong three different ways before a QA loop was
  added (missing caps, wrong species from style-text contamination, wrong
  character counts).
- The curation judge hallucinated a collar that exists in no spec and no
  sheet, rejecting 17/20 training views.
- Residuals in the delivered book: a fire-breathing mascot, jersey lettering,
  coat-fluffiness variance between the two dogs.

---

# The honest comparison: consistency vs. the previous pipeline

The previous pipeline (reference-conditioned generation, and before that the
composite engine) delivered **more stable identity out of the raw render**.
The 2026-08-26 full Bilbo run on the composite engine shipped with the D1
defect class essentially gone at render time. The LoRA-era pipeline, by
contrast, **depends on the correction loop to converge**:

1. **Raw-render identity is less reliable.** Caps drop, swap between the two
   dogs, or change color; small accessories (bracelet, hair ties) vanish; in
   the worst case named characters are omitted entirely. The previous path
   conditioned every page directly on the sheets with a full lock text, and
   these defect classes were rarer at the first render.
2. **Tone/style drifts more.** Kontext inherits style from the conditioning
   image and its own priors; pages in the same book came out in noticeably
   different finishes until a fixed seed and palette-lock sentence were added
   — and those mitigate, not eliminate, the drift.
3. **More moving parts = more failure surfaces.** Training-view curation,
   trigger tokens, LoRA scales, stitched conditioning, prompt length budget —
   each was a real source of defects this week. The old path had one seam
   (sheet + prompt to render).
4. **The wins are conditional.** Kontext+LoRA beat baseline convincingly on
   solo close-ups (95 vs 45 on Ella p1) — weights genuinely help where the
   camera is close and the character is alone. On multi-character pages the
   scores tied or the correction loop did the heavy lifting, which the
   baseline needed less of.

**Bottom line:** kontext+LoRA raised the ceiling (best-case likeness is better
than the old pipeline ever produced) but lowered the floor (worst-case raw
renders are worse, and consistency across a full book leans on correction).
As of v6.4 the end-to-end system converges to a deliverable book, but
page-for-page raw consistency has not yet matched the previous
reference-conditioned pipeline. The v6_b feedback round should target exactly
that gap.
