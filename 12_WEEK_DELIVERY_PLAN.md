# 12-Week Delivery Plan — "Best-in-Class Illustrator Machine"

**The product is the pipeline, not the books.** The deliverable at Week 12 is a
**general-purpose illustrator machine**: give it *any* children's-book manuscript and
it returns a print-ready, professionally illustrated book with near-zero manual
rework.

**The two books are the acceptance harness, not the goal.** *Ella, the Animal
Shelter, and You!* and *Bilbo & Obi's Baseball Adventure* are our two known-answer
test manuscripts — we have reference sheets and client feedback for both, so we can
score the engine objectively against them. They must both come out perfect **because
that proves the engine works**, not because they are the product.

**Generality is proven on a held-out manuscript.** Two tuned books cannot prove the
machine generalizes — a pipeline can silently overfit to them. So a **third, unseen
manuscript** is run *cold* (no per-book tuning) at Week 9 and again at Week 12. The
engine is only "done" when the held-out book scores within a small margin of the two
tuned books.

### Generalization principles (apply to every sprint)

1. **Nothing per-book is hardcoded.** Every character, scene, prop, trim size,
   palette, and layout decision is derived from the manuscript + its references at
   runtime — never a literal in code keyed to Ella or Bilbo.
2. **Fixes go in at the source, generically.** A defect found on one book is fixed as
   a *rule* (in `checklist_v3` / a stage), not a one-off patch to that book's data —
   consistent with the v4 rebuild that removed "only-on-page-X" conditionals.
3. **The manuscript is the single source of truth.** Page list, verbatim text,
   dialogue, shot list, and character specs all flow from `parse_v3`; no stage invents
   book-specific content.
4. **Every gate is measured on ≥2 books + the held-out one**, so a green score can't
   come from overfitting a single manuscript.

**Cadence:** 1 sprint = 1 week. Every sprint has a single headline goal, a
root-cause it attacks, the exact modules it touches, and a **numeric exit gate**.
No sprint closes until its gate is met (or the miss is logged and re-planned).

---

## 0. Where we are today (measured baseline, Week 0)

These numbers are from an **independent visual audit** (39 final pages read by eye,
scored against the reference sheets) — *not* the pipeline's own judge, which
reports inflated pass rates because it only checks what it was told to check.

| Dimension | Ella | Bilbo | Combined | Target (Wk 12) |
|---|---|---|---|---|
| Image / character consistency | 78% | 91% | **85%** | **≥ 98%** |
| Negative space (clean text zone) | 74% | 85% | **80%** | **≥ 97%** |
| Text alignment / legibility | 82% | 80% | **81%** | **≥ 98%** |
| Thought / speech bubbles | n/a | n/a | **feature absent** | **shipped + ≥ 95%** |
| Front/back-matter & structure | placeholder leaks | placeholder leaks | **broken** | **100% clean** |

### The five defect classes causing the gap

| # | Defect (what the client sees) | Root cause in code | Owning module(s) |
|---|---|---|---|
| D1 | Character drift: scale/appearance/wardrobe change page-to-page; duplicated protagonist (Ella p11); Obi loses hat (p6-7); Mom's red-jersey drift | text-to-image cannot hold identity+scale; i2i correction is a patch, not a fix | `generate_v3`, `correct_v3`, `refs_v3`, `charspec` → **superseded by** `sprites_v3` + `composite_v3` + `stage_v3` + `render_v3` |
| D2 | Text over busy art (Ella 1,3,5,9,11); no genuine calm zone | plate/scene not composed with a reserved low-detail band tied to real character boxes | `generate_v3` / `render_v3`, `layout_v3` |
| D3 | Garbled/illegible captions (Bilbo p15 "the at Obi…"); low contrast white-on-sky | `compose_v3` text render: wrap/font/ink + no contrast guarantee | `compose_v3` |
| D4 | Placeholder/instruction text leaks into final art (Ella p16, Bilbo back cover) | front/back matter not authored; prompt strings printed as page copy | `parse_v3`, `book_v3` |
| D5 | No thought/speech bubbles at all | feature never built in v3 | **new module** |

**Strategic read:** the single highest-leverage move is **finishing the v5.0
layered-compositing engine** (already validated on isolated pages per DEVLOG v5.0).
It makes identity + scale *deterministic* — the client's #1 grievance — and its
known per-character boxes are also what unlock clean negative space (D2) and
box-aware text (D3). So Weeks 2–5 are sequenced to ride that one investment.

---

## 1. Effort allocation (where the 12 weeks go)

```
Consistency / compositing engine  ████████████  33%  (Wk 2,3, +9)
Text rendering & placement        ██████        17%  (Wk 5, +3)
Negative space / composition      ████          11%  (Wk 4)
Structure / front-back matter     ███            8%  (Wk 6)
Thought/speech bubbles (new)      ███            8%  (Wk 7)
Scene logic & props               ███            8%  (Wk 8)
Eval harness + QA + client rounds ██████        15%  (Wk 1,10,11)
Print-readiness & delivery        ██             ~   (Wk 12)
```
Rationale: consistency is both the biggest client complaint **and** the enabler for
D2/D3, so it gets the most time and is revisited in the full-book regen (Wk 9).

---

## 2. The 12 sprints

Each sprint: **Goal · Why · Modules · Tasks · Exit gate.**

---

### 🏁 Week 1 — Instrument before we build (the eval harness)

- **Goal:** A repeatable, *independent* scorecard so every later sprint has an
  objective pass/fail — replacing today's "the pipeline says 100%" self-report.
- **Why:** We just proved the built-in judge is blind to its own failures. We
  cannot claim "perfect at Week 12" without a measurement we trust.
- **Modules:** new `pipeline/eval_v3.py`; freeze current PDFs as `baseline/`.
- **Tasks:**
  1. Codify the 5-dimension rubric (D1–D5) into a vision-judge eval that scores a
     finished PDF page-by-page against the reference sheets — run as an *external*
     pass, separate from `correct_v3`, so it can disagree with the generator.
  2. Add a lightweight **human-review sheet** (per page: PASS/PARTIAL/FAIL + note)
     for the dimensions models judge poorly (legibility, taste).
  3. Emit `eval_report.md` + JSON scores to disk (this is what was missing — scores
     were only ever printed to stdout).
  4. Lock Week-0 numbers above as the committed baseline.
- **Exit gate:** `eval_v3` reproduces the Week-0 audit within ±5% on both books;
  report auto-generated and committed. **Eval runs on any PDF from any manuscript** —
  it takes references + pages as input, so it can score the held-out book later with
  zero changes.

---

### Week 2 — Orchestrate the full-book compositing engine

- **Goal:** Run *both entire books* through `sprites → stage → render → harmonize`
  (the STAGES_COMPOSITE path), not just isolated validation pages.
- **Why:** D1. DEVLOG v5.0 proved layered compositing makes identity+scale
  deterministic on page 9; it is not yet wired for a whole book, and box-aware text
  is still a TODO.
- **Modules:** `sprites_v3`, `composite_v3` (incl. `harmonize`), `stage_v3`,
  `render_v3`, `run_v3` (COMPOSITE engine default).
- **Tasks:**
  1. Generate the pose atlas for every high-consistency character once, cut to
     transparent PNG; verify on-model coverage (all poses each book needs).
  2. Full-book `stage_v3` staging.toon (pose/x/y/height/flip + char-free background)
     for all pages incl. spreads.
  3. `render_v3` end-to-end: char-free plate → composite sprites → harmonize →
     **record every character's box** to disk for downstream text/negative-space use.
  4. Make COMPOSITE the default engine in `run_v3`.
- **Exit gate:** Both books fully rendered on the compositing engine; character
  **scale variance across pages ≤ 5%**; zero duplicated-protagonist or hat-loss
  defects (the exact Wk-0 D1 failures) on a full eval pass.

---

### Week 3 — Consistency hardening: humans, duos, wardrobe

- **Goal:** Close the *human* and *look-alike* half of consistency the dog-focused
  work leaves open.
- **Why:** D1 residue — Mom's red-jersey drift (Bilbo 13/15/20-21), Ella's family
  generic faces, Ella-vs-shelter-woman body swaps historically.
- **Modules:** `charspec` (exact hex/wardrobe lock), `refs_v3` (real-photo likeness
  + duo/group sheet), `checklist_v3` (CHR rules), `stage_v3`.
- **Tasks:**
  1. Promote every recurring human to a hex-locked `charspec` (wardrobe items marked
     worn "always"; kill per-page conditionals that cause flip-flop).
  2. Bring humans into the sprite-atlas path where they recur ≥3 pages; keep t2i+ref
     only for one-off background people.
  3. Duo/group reference for every co-present look-alike pair (Bilbo+Obi, Ella+Sofia)
     so the model contrasts rather than averages them.
  4. Extend `eval_v3` to score wardrobe-item persistence explicitly.
- **Exit gate:** **Consistency ≥ 95%** combined on the eval harness; no wardrobe
  drift on any recurring named character across its pages.

---

### Week 4 — Negative-space engine (a real calm zone every page)

- **Goal:** Every text-bearing page has a genuinely low-detail region positioned
  where the text will go — designed in, not hoped for.
- **Why:** D2 — weakest Ella dimension (74%); text currently lands on frame-walls,
  dog-packs, shopfronts.
- **Modules:** `layout_v3`, `render_v3` (plate generation), `generate_v3` (t2i
  fallback path), `checklist_v3`.
- **Tasks:**
  1. `layout_v3` chooses the empty band (top/bottom/left) *before* render and passes
     it as a hard constraint to the plate prompt ("reserve a calm low-detail area
     here — open sky / soft wash / plain floor").
  2. Use the **known character boxes** (Wk 2) to keep subjects out of the text band.
  3. Adaptive horizon composition (low/high horizon) to manufacture the calm zone,
     per the reference-book negative-space model.
  4. Closed-loop check: `eval_v3` measures detail density inside the text band;
     regen the plate if it's too busy.
- **Exit gate:** **Negative space ≥ 92%**; text-band busyness under threshold on
  every page.

---

### Week 5 — Text rendering & placement overhaul

- **Goal:** Every caption crisp, correctly wrapped, high-contrast, box-aware, never
  garbled, never crossing the gutter.
- **Why:** D3 — Bilbo p15 garbled render; white-on-light low contrast (19, 20-21).
- **Modules:** `compose_v3` (the whole text-render path).
- **Tasks:**
  1. Fix the garble root cause in `compose_v3` (wrap/shaping/font-metrics bug that
     produced "the at Obi on the late afternoon").
  2. **Box-aware placement:** consume the character boxes + calm band so text is
     positioned deterministically, uniform type scale, gutter-safe on spreads.
  3. Guaranteed contrast: adaptive ink + soft white/dark bloom (no border card) with
     a measured minimum contrast ratio against the local background.
  4. Verbatim guard from `copyedit_v3` all the way to render — text on art must equal
     manuscript text exactly (no paraphrase, no repeats).
- **Exit gate:** **Legibility ≥ 95%**; automated contrast check passes every page;
  zero garbled/clipped/gutter-crossing captions.

---

### Week 6 — Structure, front/back matter & MID-PROJECT CHECKPOINT

- **Goal:** Correct book skeleton end-to-end; deliver one book as a
  reference-quality vertical slice to the client.
- **Why:** D4 — Ella p16 leaked instruction text; Bilbo back cover placeholder; and
  the client needs a mid-point signal that we're on track.
- **Modules:** `parse_v3` (front+back matter authoring), `book_v3` (assembly, one
  trim size), `copyedit_v3`.
- **Tasks:**
  1. `parse_v3` emits a real canonical page list: title, dedication, body,
     about-the-author, fostering/volunteering, back cover — with authored copy, not
     prompt strings.
  2. Kill every placeholder-leak path; add a guard that fails the build if any
     instruction/placeholder string reaches a page.
  3. `book_v3` assembles in manuscript order at one uniform trim size.
  4. **Checkpoint:** ship the stronger book (Bilbo) full-quality to the client for
     directional sign-off; capture feedback into the categorized-feedback workflow.
- **Exit gate:** **Structure 100% clean** (no leaks, correct matter, uniform trim);
  client checkpoint delivered and feedback logged.

---

### Week 7 — Thought & speech bubbles (new capability)

- **Goal:** Ship the missing bubble feature: dialogue/thought rendered as legible,
  style-consistent bubbles anchored to the speaker.
- **Why:** D5 — feature absent; needed for the genre and likely client expectation.
- **Modules:** new `pipeline/bubbles_v3.py`; hooks in `parse_v3` (detect
  dialogue/interior thought) and `compose_v3` (render).
- **Tasks:**
  1. `parse_v3` flags dialogue vs narration vs interior thought per page.
  2. `bubbles_v3` renders speech (tail) / thought (cloud + dots) bubbles, tail
     anchored to the **speaker's character box**, sized to text, in-style linework.
  3. Collision handling with the calm band + character boxes so bubbles don't cover
     faces or key art.
  4. `eval_v3` scores bubble legibility + correct speaker attribution.
- **Exit gate:** Bubble feature **≥ 95%** on eval where dialogue exists; toggleable
  per book (Ella/Bilbo may use sparingly).

---

### Week 8 — Scene logic & props (the shot-list contract)

- **Goal:** Every page is the *right scene*: correct location, all required props,
  no invented ones, physically plausible, clean anatomy, single subject.
- **Why:** Residual E/F failures — wrong location, missing leash, hotdog-stand
  inventions, warped/duplicated art seen in prior client rounds.
- **Modules:** `parse_v3` (illustration-notes → authoritative shot list), `stage_v3`,
  `checklist_v3` (SCN/IMG/GUT rules), `correct_v3` (composition critic).
- **Tasks:**
  1. Treat "Illustration:" notes as a binding shot list: location locked, named props
     required, forbidden inventions rejected.
  2. Anti-duplication + anatomy + full-bleed enforcement in the eval + fix loop.
  3. Gutter-safety on spreads (subjects/faces/key objects off the centre).
- **Exit gate:** 100% of pages match their shot-list location; all named props
  present; zero warped/duplicated/cropped-to-legs pages on eval.

---

### Week 9 — Full regen + FIRST held-out generality test

- **Goal:** Regenerate both books on the finished engine **and** run a third, unseen
  manuscript *cold* to prove the machine is a general illustrator, not a
  two-book fitter.
- **Why:** Integration risk + the core product claim. Only an unseen manuscript, run
  with zero per-book tuning, proves generality.
- **Modules:** full pipeline via `run_v3` (COMPOSITE); `eval_v3`.
- **Tasks:**
  1. Clean full run of Ella and Bilbo end-to-end.
  2. **Held-out run:** pick a new manuscript (with a couple of character photos),
     feed it in raw, generate with no code/data edits specific to it.
  3. Eval all three books across the 5 dimensions; any place the held-out book lags
     the tuned two is an **overfitting leak** — fix it as a generic rule, not a patch.
- **Exit gate:** Ella + Bilbo hit **all Week-12 targets**; the **held-out book scores
  within 5 points** of them on every dimension (the real proof of generality).

---

### Week 10 — Client review round (full books)

- **Goal:** Deliver both complete books; collect and categorize real client feedback.
- **Why:** The client is the final judge; their categorized-review workflow already
  exists (`Client_REVIEW/*_categorized.xlsx`).
- **Modules:** delivery packaging; feedback ingestion into `checklist_v3` rule codes.
- **Tasks:**
  1. Deliver Ella + Bilbo PDFs + a short "what changed since baseline" note using the
     eval numbers.
  2. Categorize every comment into existing rule buckets (A–F) or new codes.
  3. Triage: must-fix vs nice-to-have vs out-of-scope, sized against remaining time.
- **Exit gate:** Complete, prioritized client feedback ledger; each item mapped to a
  module + a fix estimate.

---

### Week 11 — Feedback remediation + regression guard

- **Goal:** Burn down the client's must-fix list without reintroducing old defects.
- **Why:** Late-stage fixes historically re-broke earlier wins (e.g. the bandana
  flip-flop); we need a regression net.
- **Modules:** whichever the tickets touch; `eval_v3` as the regression gate;
  `checklist_v3` for any new rule.
- **Tasks:**
  1. Fix all must-fix tickets.
  2. Re-run the **full eval** after every batch — no dimension may regress below its
     Week-9 gate.
  3. Encode any new client rule into `checklist_v3` so it's enforced in gen + judge.
- **Exit gate:** 100% of must-fix tickets closed; no eval-dimension regression;
  client verbally satisfied on a preview.

---

### Week 12 — Print-readiness, generality lock & delivery

- **Goal:** Perfect, print-ready hand-off of the two books **and** a proven general
  engine. Done.
- **Why:** Screen-correct ≠ press-correct; and the product is the machine, so its
  generality must be locked, not assumed.
- **Modules:** `book_v3` (export), packaging, `docs/` handoff.
- **Tasks:**
  1. Print spec: correct trim + bleed + safe margins, ≥300 DPI, CMYK-safe,
     PDF/X export, gutter-safe on spreads.
  2. Final full eval on the print PDFs → target scorecard, signed.
  3. **Second held-out run** on a *different* unseen manuscript to confirm Week-9's
     generality result was not luck.
  4. Delivery package: print-ready PDFs, source files, the **"drop in any manuscript"
     runbook**, and the final eval report (tuned books + both held-out books).
  5. Client sign-off.
- **Exit gate:** Both books **≥ all Week-12 targets**, print-spec validated; **both
  held-out books within 5 points** of the tuned books; client sign-off. **Ship.**

---

## 3. Metric trajectory (planned)

| Wk | Milestone | Consistency | NegSpace | Legibility | Bubbles | Structure |
|----|-----------|:-----------:|:--------:|:----------:|:-------:|:---------:|
| 0 | Baseline (measured) | 85 | 80 | 81 | — | broken |
| 2 | Compositing engine full-book | 93 | 82 | 81 | — | broken |
| 3 | Consistency hardened | **95** | 84 | 82 | — | broken |
| 4 | Negative-space engine | 95 | **92** | 85 | — | broken |
| 5 | Text overhaul | 96 | 93 | **95** | — | partial |
| 6 | Structure + checkpoint | 96 | 93 | 95 | — | **100** |
| 7 | Bubbles shipped | 96 | 93 | 96 | **95** | 100 |
| 8 | Scene logic | 97 | 95 | 96 | 95 | 100 |
| 9 | Full regen (internal green) | **98** | **97** | **98** | 95 | 100 |
| 10–11 | Client round + remediation | ≥98 | ≥97 | ≥98 | ≥95 | 100 |
| 12 | Print-ready delivery | **98+** | **97+** | **98+** | **95+** | **100** |

---

## 4. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Compositing engine harmonize still reads "pasted" on complex pages | Med | High | Wk 2 gate on scale-variance + eval; keep t2i+i2i as fallback per page |
| Sprite atlas lacks a needed pose → awkward staging | Med | Med | Atlas coverage audit in Wk 2; generate extra poses on demand |
| Bubble feature fights the calm-band/text logic | Med | Med | Build Wk 7 *after* boxes+text (Wk 5) so it reuses that geometry |
| Client feedback in Wk 10 is large/late | Med | High | Mid-project checkpoint Wk 6 de-risks direction early |
| Model moderation flags animal/child refs mid-run | Low | Med | Existing sanitize+fallback in `refs_v3`; keep it |
| Late fixes regress earlier wins | Med | High | `eval_v3` regression gate every batch (Wk 11) |

---

## 5. Definition of Done (Week 12)

**The product (the engine):**
- [ ] Any manuscript + character references can be dropped in and produces a
      print-ready book with **no code or per-book data edits**.
- [ ] **Two held-out (unseen) manuscripts** score within 5 points of the tuned books
      on every dimension — generality proven, not assumed.
- [ ] No per-book hardcoding anywhere; all fixes live as generic rules/stages.
- [ ] Runbook: a new manuscript can be illustrated with near-zero manual rework.

**The two acceptance books:**
- [ ] Both score **≥ Week-12 targets** on the independent eval harness.
- [ ] Zero placeholder/instruction leaks; correct front & back matter; one trim size.
- [ ] Character identity + scale deterministic (compositing engine) across all pages.
- [ ] Every caption legible, contrast-checked, gutter-safe, verbatim to manuscript.
- [ ] Thought/speech bubbles shipped and legible where dialogue exists.
- [ ] Print-ready PDF/X at ≥300 DPI with correct bleed/trim/CMYK.
- [ ] Client sign-off received.

---

*Baseline numbers in §0 are from an independent page-by-page visual audit, not the
pipeline's self-report. Every sprint gate is measured by `eval_v3` (Week 1), which is
deliberately built to be able to disagree with the generator.*
