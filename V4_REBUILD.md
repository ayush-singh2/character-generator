# v4.0 — Picture-Book Pipeline Rebuild

**Date:** 2026-07-20
**Trigger:** The v3 Ella build was rejected by the client on sight. This version
rebuilds the generation pipeline end-to-end to fix every structural cause of that
rejection, and strips the repo down to a single, clean v3 flow.

This document lists **every change** in v4.0: what it fixes, why, which files, and
how it was verified.

---

## 1. What the client saw (the rejection)

Rendering the v3 PDF confirmed four hard failures:

1. **Wide two-page spreads.** Pages were generated at 2:1 and printed as spreads.
   The client prints **one manuscript page per sheet**, so spreads are unusable.
2. **Text in a bordered strip that clipped and overlapped.** Captions sat in a
   reserved blank band that read as a border; some were clipped at the page edge,
   some overlapped the art, sizes jumped page to page.
3. **Character drift.** Ella's hair, outfit and face changed on almost every page
   (low ponytail → two afro-puffs → single bun).
4. **Dead code.** Three generations of pipeline (`run.py`, `pb_run`, `v3`)
   coexisted; ~20 modules were unused.

---

## 2. Root causes (traced in code)

| Symptom | Root cause |
|---|---|
| Spreads | `generate_v3` aspect + `book_v3 SPREAD_TRIM`; a hidden `is_spread` branch across 4 files |
| Text border/clip/size | generation reserved a hardcoded 30% **edge band**; `compose_v3` baked text with a scrim card + erratic global size, then `book_v3` cropped it |
| Character drift | `charspec.py` (an exact hex-locked spec) **existed but was orphaned**; v3 locked characters with vague free text ("two puffs **or** a headband"); the judge compared against that text; `perfect_scene` re-rendered with no reference and reverted fixes |
| Dead code | never cleaned up after two rewrites |

Two further **model-behaviour** bugs surfaced during the first rebuild runs and
were also fixed (see §9).

---

## 3. Repo cleanup — v3-only

**Deleted 22 files:** the ancient flow (`run, extract, paginate, book, cover,
illustrate`), the old `pb_run` flow (`pb_run, storybook, picturebook, characters,
style, refs, archive, pb_illustrate, motifs, textplace`), one-off scripts
(`rebuild_v3, regen_pages`), unused utilities (`consistency, logo_composite,
versions`), the now-unused `flux.py`, and `gen_book.sh` (which drove `pb_run`).

**Live set — 16 modules:**
`run_v3` (orchestrator) · `parse_v3, copyedit_v3, refs_v3, layout_v3, generate_v3,
correct_v3, compose_v3, book_v3` (stages) · `plan_v3, checklist_v3, charspec`
(shared logic) · `editor, llm, toon_io, style_guide` (support).

*Verified:* no live module imports a deleted one; `import pipeline.run_v3` clean.

---

## 4. Single square pages (no spreads)

Every manuscript page is now one **8.5×8.5 square** sheet.

| File | Change |
|---|---|
| `book_v3.py` | `SINGLE_TRIM = (2550, 2550)` (8.5in @300dpi); deleted `SPREAD_TRIM`; every page normalised to that one trim |
| `generate_v3.py` | aspect is always `"SQUARE single page, 1:1"` (removed the spread ternary + gutter wording) |
| `compose_v3.py` | deleted `_gutter_safe` / `GUTTER_MARGIN` |
| `plan_v3.py` | `is_spread` → always `False` |
| `parse_v3.py` / `layout_v3.py` | prompts drop spreads; `text_area` is top/bottom only |
| `checklist_v3.py` | removed the `GUT-1` gutter rule |

*Verified:* final PDFs report uniform square pages via `pdfinfo`.

---

## 5. Character consistency — wired in `charspec` (the #1 fix)

The core fix: every stage now speaks from **one exact, enumerated spec** instead of
free text, so a character cannot drift.

- **`parse_v3.py`** now emits a `locked_spec` for every high-consistency character:
  a nested JSON where every trait has **one committed value** (no "X or Y"),
  colours are **hex codes**, and gaps are invented-and-locked. Example (Ella):
  hair = `two low puffs at nape, #2C1810, coily 4a`; top = `#F4A261, PLAIN chest,
  no logo`; overalls `#5B8FA3`; sneakers `#9D4EDD`; charm bracelet, left wrist.
- **`plan_v3.char_lock`** is the single chokepoint: if a `locked_spec` exists it
  returns `charspec.serialize(spec)` (deterministic, identical text every time);
  else it falls back to the old free-text. Because `refs_v3`, `generate_v3` and
  `correct_v3` all build identity text through `char_lock` / `present_locks`, they
  **all** now use the exact spec automatically.
- **`refs_v3.py`** builds one **canonical** portrait + full-body sheet per high
  character from that spec — the visual ground truth.
- **Judge now compares against the reference IMAGE**, not just text
  (`llm.chat_json_images`, new multi-image call). `correct_v3.judge` sends the page
  **plus** the character's reference sheet and fails on any visible mismatch.
- **`perfect_scene` no longer reverts fixes:** it receives the reference sheets and
  is told to keep identity identical to them (previously it re-rendered blind).

*Verified:* Ella's serialized lock is exact and unambiguous; her reference sheet
matches it; she is consistent across page instances in the rebuild.

---

## 6a. Learned from the client's own printed books (CLIENT_DOC interiors)

Studied three professionally-printed interiors the client supplied — *Bilbo & Obi
V6* (8.125″ square), *Run Sparky Run* (8.625×8.75), *Sheep the Llama* (11×8.75
landscape). Every page, in all three, uses the **same** technique:
- Small text, **no card/border**, drawn straight on the art.
- Placed in **genuine diegetic negative space** — open sky, plain grass/pavement/
  floor, or a dark blurred background — with **adaptive ink** (dark on light, light
  on dark). Position moves to wherever the calm area is.
- Crucially, the **illustration is composed with a high or low horizon** that leaves
  ~35% open sky or open ground; subjects are grouped in the opposite part; one
  focal moment per page. The negative space is designed in, not found afterward.

Our generator was instead packing the frame edge-to-edge, so text had nowhere to go
but on top of characters. Fixes applied:
- **`generate_v3`** now instructs a low/high-horizon composition leaving a genuinely
  open ~38% sky (text-top) or ground (text-bottom) band, subjects grouped opposite,
  "ONE focal moment, generous breathing space, like a printed picture book."
- **`compose_v3`** now places text in the **full-width reserved band** (top or
  bottom, whichever the art left calm), spanning it, with **adaptive ink** chosen
  from the band's luminance; the vision finder is only a fallback when both bands
  are busy.
Verified on the two busiest Ella pages (shelter, kitchen): both went from
text-on-characters to a clean open-floor caption band, matching the reference books.

## 6. Text in genuine negative space (no border, right size)

- **`generate_v3.py`** — the prompt now asks for a **diegetic calm zone**: "compose
  the scene so a natural, uncluttered part of the setting — open sky, a plain wall,
  calm ground/floor or still water — fills roughly the {top/bottom} third **as part
  of the illustration, not a blank border**." An edge-energy check still gates it.
- **`compose_v3.py`** was rewritten:
  - **No scrim card** — just a soft white halo (removes the "border between image
    and text").
  - **One small locked size** (~3% of page height) — the client called the old text
    "huge"; it is now modest and consistent book-wide.
  - **Hard safe margin** (≥5.5% on every side) so text can never clip at the frame.
  - **Grow-to-fit, not shrink-erratic** — the block only shrinks if it truly can't
    fit the safe area, otherwise the size stays constant.
  - **One locked ink colour** (fixes "text is a different colour" pages).

---

## 7. Title, cover & dedication text

`compose_v3` now handles page `role` (emitted by `parse_v3`):
- **cover / title** → the **book title** is drawn in a display serif (and author if
  present). Previously these pages had no title text at all.
- **dedication** → its verbatim text centred on the page.
- **body / backmatter** → the diegetic caption path from §6.

---

## 8. Verbatim text + copyedit

- **`parse_v3`** enforces **MAN-1** (page text copied verbatim, never paraphrased or
  invented) and **MAN-2** (no page invented, none dropped), and a `reconcile()`
  check flags any page whose text isn't found verbatim in the manuscript.
- **`copyedit_v3.copyedit_scenes`** (new v3 entry point) runs the Ballast house
  style over `scenes.toon` (the old `copyedit()` only touched the retired
  `storybook.json`), verbatim-preserving, with an audit report.

---

## 9. Model-behaviour fixes (found during rebuild runs)

The image model (Gemini via OpenRouter) has two habits that broke the square/scene
requirements; both are now handled:

1. **It emits landscape (1408×768), ignoring "1:1" text.** The output aspect
   follows the **reference/base** aspect. Fixes, layered:
   - `editor.blank_square()` — a white square is passed as the **edit base** for
     generation, so the model returns 1:1.
   - **Reference sheets are generated square** (same seed), so the correction stage
     (which conditions on the refs) also stays square.
   - `editor.to_square()` — a **center-crop safety net** applied to every generate
     and correct output, so a stray landscape can never reach the book (it trims
     left/right, keeping the top/bottom text band).
   *Verified:* landscape ref → landscape out, **square ref → square out**; all six
   Ella refs are 1024².
2. **It draws multi-action pages as a bordered 4-panel collage.** `generate_v3` now
   demands "**ONE continuous unified scene — NOT a grid/collage/split panels/
   vignettes, no dividing lines**"; `checklist_v3` IMG-2 and the judge fail
   collages. *Verified:* page 11 went from a 4-panel grid to a single shelter room.

---

## 10. API robustness (from the same session)

`editor.py` (and previously `flux.py`) had no effective request cap — a trickling
connection once hung a whole run for 95 minutes. `editor._post_bytes` now runs each
request in a **daemon worker joined with a hard deadline** (default 240s, env
`EDIT_HARD_DEADLINE`), split into connect (15s) + read (120s) timeouts, feeding the
existing 4-attempt retry loop. A hung/slow call now fails its attempt and the run
continues instead of freezing.

---

## 11. The pipeline & how to run it

Stages (in order), orchestrated by `pipeline/run_v3.py`:

```
parse → copyedit → refs → layout → generate → correct → compose → book
```

- **parse** — manuscript.docx → `characters.toon` (+ `locked_spec`) + `scenes.toon`
  (verbatim, front/back matter, single-page).
- **copyedit** — Ballast house style over the page text.
- **refs** — one canonical **square** reference sheet per high character (+ a group
  sheet for look-alikes).
- **layout** — per-page coordinate layout (calm top/bottom band).
- **generate** — text-to-image, square (blank-square seed), single scene, injects
  the client checklist + exact character locks + reference sheets.
- **correct** — image-to-image: a visual judge compares each page to the reference
  sheet and fixes drift; ref-aware polish.
- **compose** — text set in the in-scene negative space at the locked size; title /
  dedication on front matter.
- **book** — assemble the PDF at one uniform square trim.

**Run it** (from the repo root, using the venv):

```bash
.venv/bin/python -m pipeline.run_v3 --book books/ella-the-animal-shelter-and-you
# resume a stage:      --from generate      restrict pages: --only cover,4,11
# side-by-side version: V3_DIR=v3b ...
```

Flags: `--book, --docx, --from <stage>, --only <pages>, --no-copyedit,
--no-correct, --no-scene-pass`.

---

## 12. Status & known limitations

- **Done:** repo cleanup, single square pages, charspec consistency, text redesign,
  title/dedication, verbatim+copyedit, square-output + single-scene model fixes,
  API robustness.
- **Validated on Ella:** locked spec exact; square reference sheets; page-11 single
  scene; final full run in progress at time of writing.
- **Watch items / next:**
  - A montage page (character shown doing several actions in one room) is one
    coherent scene, not a bordered collage — acceptable, but if the client wants a
    single action per page, the scene *description* should pick one focal action in
    `parse_v3`.
  - A few pages were flagged by `reconcile()` (MAN-2) as not-verbatim — worth a
    manual text check against the manuscript.
  - **Bilbo & Obi** shares all the same failures and should be re-run through this
    pipeline once Ella is approved.
