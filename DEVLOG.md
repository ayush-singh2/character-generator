# Development Journal — Picture-Book Generator

The journey of building the manuscript → illustrated-book pipeline and the
character-generator app. Newest version on top. Each entry: what changed, why,
and the files touched.

> Append a new `## vX.Y` block at the top whenever we make a change.

---

## v2.3 — Approach 1 built + correction backend found (2026-07-10)
Built and validated Approach 1 (correct-after) end-to-end on a fresh render of
pages 3–10 (isolated demo `books/bilbo-approach1-demo/`, reuses Bilbo data/refs,
v4 deliverable untouched).
- **`consistency.py`** — closed loop: vision **judge** (per-character vs its
  reference) + **look-alike discrimination** (Bilbo vs Obi collapse, judged
  against the duo ref) → **correct** → re-judge up to `CONSISTENCY_TRIES`. Backs
  up each original to `page_NN.orig.png`.
- **Detection works** (caught "Obi missing green O cap", "Mom wrong hair").
- **Correction backend — three tries:**
  1. `flux.edit` whole-page → *reimagined the frame* (a page became a full-frame
     dragon). Rejected.
  2. mask-based crop-inpaint (`inpaint.py`: locate→crop→regen→feather-paste) →
     preserved background but the reference-generator **redrew** the character
     (beagle→golden-retriever twin of Bilbo) and **doubled** it. Rejected.
  3. **instruction-based image editor** (`editor.py`, OpenRouter
     `google/gemini-3-pro-image`) → edits IN PLACE, preserves everything
     unmentioned. **Winner.** The judge's issue text becomes the edit instruction.
     Page 8: Obi's cap added, same beagle/pose, rest identical, re-judge "Obi ok".
- **Guards:** never fix a "not visible" character (that caused the dragon).
- **Files:** `pipeline/editor.py` (new), `pipeline/consistency.py`;
  `inpaint.py` removed (superseded). On branch/`origin/dev`.
- **Next:** run full book through Approach 1; then build **Approach 2**
  (compose-from-parts) to A/B. See [[img2img-consistency-pivot]].

## v2.2 — Pivot to img2img correction + repo restructure into books/ (2026-07-10)
**Decision:** dropped BOTH prior consistency bets — LoRA fine-tune (v2.1) and the
compositing engine (v2.0). New direction is **image-to-image correction**, two
approaches to A/B test:
- **Approach 1 (correct-after):** refs → scene with reserved text space → composed
  page (scene+text) → *if* a character drifts, feed the page + that character's
  existing reference(s) to an img2img model and tell it to replace only the
  inconsistent character(s).
- **Approach 2 (compose-from-parts):** generate character ref + per-page scene +
  text, send all three to an img2img model with a detailed per-page scene prompt
  and let it assemble the page.
Both reuse the current `pb_run` chain (refs → pb_illustrate/picturebook → textplace);
the differentiator is a new img2img/edit correction step on top of `flux`.

**Repo cleanup (this commit):**
- Removed abandoned code: `lora.py`, `sprites.py`, `compositor.py`, `compose_book.py`
  (preserved in git checkpoint `cfbe16c` on branch `cleanup-restructure`).
- **New layout: `books/<slug>/{data,output}`** — one folder per generated book, its
  `output/` holds `versions/`, `storybook/`, `assets/`, `refs/`. Migrated:
  bilbo-obi-baseball-adventure (was root data/+output/), ella-the-animal-shelter-and-you,
  sparky (+ its partial illustration-notes run archived inside), i-m-not-different-i-m-unique.
  `runs/` retired; `gen_book.sh` + `.gitignore` now target `books/`.
- Junk removed: duplicate `venv/` (kept working `.venv/`), root `*.log`,
  `pipeline/__pycache__`, empty `image.py`, `output/{_demo,_poc,lora_train,_atlas_sheet}`.
- Kept per decision: legacy v1 flow (run/book/illustrate/…) and the Streamlit
  `client_app.py` + its dep chain.
**Next:** wire the img2img correction step and prototype both approaches on 3 pages
of one book before any full regen. See [[compositing-engine]], [[character-consistency-priority]].

## v2.1 — Per-character LoRA path + Colab-Pro training feasibility (2026-07-10)
**Context:** compositing (v2.0) gives pixel-perfect consistency but sprites read
slightly "pasted." Next bet is a **per-character Flux LoRA** so the model LEARNS
each character and paints them naturally into any pose — consistent AND painterly.
`pipeline/lora.py` implements prepare→train→generate on fal.ai
(`flux-lora-fast-training` + `flux-lora`, cached in `data/loras.json` with a rare
trigger word per character). Client asked whether **Google Colab Pro** could host
the GPU for training to avoid the fal.ai training fee.
**Answer (documented for client):** yes for *training*, no for *hosting*.
- Colab Pro can train a Flux LoRA, but VRAM is unpredictable (T4 16 GB / L4 24 GB /
  A100 40 GB — you don't get to pick); on a T4 you must use a mem-optimized
  trainer (ostris ai-toolkit / kohya) with fp8 + gradient checkpointing (~1–2 h/char).
- Colab is a **session, not a host**: ephemeral VM wiped on disconnect, ~24 h
  ceiling — must export `.safetensors` to Drive/HF immediately, and it CANNOT
  serve inference to our local CLI pipeline.
- **Recommended split:** train on Colab (save the fee) → store weights on Drive/HF
  → run inference on fal.ai `flux-lora` (accepts an arbitrary LoRA `path`, so
  `generate()` barely changes).
- LoRA quality depends on training-set pose/angle variety — audit
  `output/assets/<char>/*.raw.png` + `output/refs/<char>/` before spending GPU time.
**Next steps:** (1) audit per-character training sets, (2) Colab ai-toolkit
training notebook, (3) refactor `lora.py` so `train()` can consume externally
trained LoRA URLs (skip fal training, keep fal inference).
**Files:** `pipeline/lora.py`, `docs/Colab-Pro-for-LoRA-Training.md` (+ rendered
`.pdf`). See [[compositing-engine]], [[character-consistency-priority]].

## v2.0 — Compositing engine: true pixel-to-pixel character consistency (2026-07-09)
**Problem:** after v1.6 the client was still unhappy — Obi looked like a
different dog/species on nearly every page, his green cap dropped, Mom/Dad
didn't match their refs. Root reality finally named: **diffusion text-to-image
(flux) redraws every character freehand from noise on each call**, so reference
+ prompt conditioning can only reduce variance, never reach pixel consistency.
We were hitting that ceiling repeatedly. A controlled test (single Obi ref vs
none) confirmed refs ARE honoured — the book failure was cross-character
contamination + freehand redraw. Client asked to stop hit-and-trial and build a
proper multi-layer engine with pixel-to-pixel consistency.
**New architecture (approved: compositing, OpenRouter-only):** stop letting the
model redraw characters; REUSE the same character pixels.
- `pipeline/sprites.py` — **character atlas**: generate a small, human-vetted set
  of pose sprites per character ONCE from the approved refs, cut to transparent
  PNGs with rembg (u2net), store in `output/assets/<char>/<pose>.png`. 24 sprites
  built for Bilbo/Obi/Homer/Mom/Dad. The client APPROVED the atlas before any
  page was built (contact sheet gate).
- `pipeline/compositor.py` — **layered assembly**: background plate + reused
  sprites (locked size ratio, contact shadow) + a painterly blend pass (edge
  feather + shared paper grain) so sprites sit in the scene.
- `pipeline/compose_book.py` — **director + build**: per page, an LLM stages the
  shot (which atlas pose each character strikes, position, size, facing) + a
  CHARACTER-FREE background description; generate the plate; composite; save to
  the standard `art/page_NN.png`. Then the EXISTING `picturebook.build()` adds
  text + page numbers + PDF unchanged (client already liked the text placement).
**Result:** characters are IDENTICAL on every page (same PNG) — Obi keeps his
green O cap everywhere, Bilbo his red B cap, size ratio fixed, Homer always the
dragon, Mom/Dad stable. Only backgrounds vary (desired). Book saved as v4
(`output/versions/bilbo_v4/`). Known limits: composited chars read slightly
crisper than the painted plate (blend mitigates); no fire-breathing Homer pose
in the atlas yet; Page 11 stays a blank placeholder (empty manuscript text);
poses limited to the atlas (extend as needed). Deps added: rembg[cpu],
onnxruntime.
**Files:** `pipeline/sprites.py`, `pipeline/compositor.py`,
`pipeline/compose_book.py`. See [[duo-group-reference]] (superseded for
characters), [[character-consistency-priority]].

## v1.6 — Duo reference stops Obi/Bilbo collapsing (2026-07-09)
**Problem (client review of v2):** Obi looked like a different dog/species on
every page (coat rust→golden, green "O" cap dropped everywhere), both dogs'
size varied, Mom/Dad drifted from their refs, and pages 7–8 had a hard seam
between art and the text wash. Locked specs (v1.5) weren't enough — the refs
"weren't being utilised".
**Diagnosis (cheap controlled test, not guessing):** generated a single dog
from ONLY Obi's portrait vs no ref. With-ref reproduced his amber coat, white
blaze and cap; no-ref gave a generic golden puppy. So references ARE honoured —
the book failure is **cross-character contamination**: when Bilbo's dominant
"generic golden retriever" sheet is passed alongside Obi's, `flux.2-max`
averages the two dogs and Obi loses his identity. On 5-char pages refs were
also dropped (cap was 4).
**Fixes:**
- **Duo/group reference**: one combined image showing BOTH dogs together with
  the correct contrast (`output/refs/duo_dogs.png`), configured in
  `data/group_refs.json`. `_gather_refs` prepends any group image whose members
  are all present and drops their individual sheets; other characters keep their
  own portrait+full_body. This anchors the contrast so the model can't merge
  them. See [[duo-group-reference]].
- `MAX_REF_IMAGES` 4→8 (flux.2 takes ~10) so crowded pages keep everyone.
- Portrait-first gathering; punchy per-character `_ref_binding` clause (cap ON
  the head, coat colour, anti-generic) restating the lock briefly after it.
- `_NO_SEAM` clause on every scene prompt to kill the art/text hard border.
**Result (verified on pages 12/16/20 before full regen):** Obi's coat, size and
species now consistent; Homer renders as a dragon again (was a brown bear).
Residual: the green cap still drifts (red/absent ~half the pages) — a model
limit the client accepted for now. Full regen → v3; v2 kept in
`output/versions/bilbo_v2/`.
**Files:** `pipeline/pb_illustrate.py`, `data/group_refs.json`,
`output/refs/duo_dogs.png`.

## v1.5 — Bilbo v2: dog identity lock + text-off-subject + regen (2026-07-09)
**Problem (client review of Bilbo v1):** three defects. (1) Text on ONE page
sat on top of Homer the dragon — his smooth green belly read as calm to the
edge/vision placer, so a card landed on the subject. (2) Bilbo & Obi swapped
SIZE and coat colour between pages (both were specced identically as
"medium golden retriever"), so mid-book the smaller dog became the bigger one.
(3) The logos on their caps kept changing page to page. Client loved page 21's
look — subjects emerging from full art into soft white/cream negative space.
**Root cause:** Bilbo/Obi/Homer had NO `locked_spec` (unlike Ella), so nothing
deterministic was pinned — only reference images + loose "keep consistent"
wording. And `textplace` eroded only *detailed* cells of a character body, so a
large smooth subject stayed "placeable"; animals/mascots weren't even in
`HARD_LABELS`.
**Fixes:**
- `data/characters.json`: added exact `locked_spec` for **Bilbo** (large, pale
  cream coat, RED cap with white **B**, blue collar), **Obi** (clearly SMALLER,
  darker reddish-amber coat + white chest blaze, GREEN cap with yellow **O**,
  red collar) and **Homer** (green dragon, navy-pinstripe **#00** jersey, navy
  cap between horns). The serialised block bakes the size/coat CONTRAST
  ("the LARGER…", "the SMALLER…", "PALER"/"DARKER") into every ref and page.
- `pipeline/textplace.py`: animals/pets/mascots/dragons/bodies added to
  `HARD_LABELS`; each subject box's solid **core** (`CORE_INSET`) is now
  hard-forbidden regardless of edge detail, so a smooth belly/costume can never
  carry text (loose box margins stay reclaimable as plain wall). Vision SYSTEM
  prompt now tells the model to box the WHOLE creature.
- `pipeline/picturebook.py`: stronger preference (0.72) for the art's
  guaranteed-empty reserved side when seating text.
- Regenerated the 3 character reference sheets from the new specs, then
  re-illustrated all 19 pages + cover and rebuilt the PDF. v1 archived to
  `output/versions/bilbo_v1/`; v2 to `output/versions/bilbo_v2/`.
**Result:** dragon page text now sits on the calm stadium wash clear of Homer;
Bilbo stays the larger cream red-**B**-cap dog and Obi the smaller darker
green-**O**-cap dog across pages; cap letters are stable. (Note: "Page 11" has
empty manuscript text so it stays a blank placeholder page, same as v1 — a
pagination artifact, not part of this change.)
**Files:** `data/characters.json`, `pipeline/textplace.py`,
`pipeline/picturebook.py`.

## v1.4 — Closed-loop negative space + white-blur text + watch audit (2026-07-08)
**Problem:** after v1.3 the full-bleed text-on-art still (a) overlapped subjects
on pages whose art filled the whole frame (no empty band existed), and (b) sat
too bare on the background — the client wanted the "slight white blur" behind
text seen in the reference interiors. The watch also still flipped wrists on
some poses.
**Fixes:**
- `picturebook.py`: `_adaptive_scrim` now lays a soft, always-on **light bloom**
  behind text (subtle on calm art, stronger on busy art) — the reference "white
  blur", never a boxed card. `render_content` seats text on the **calmest** of
  {vision box, all four third-zones} so it stops overriding faces/dogs.
- `pb_illustrate.py`: **closed-loop negative space**. After each page is
  rendered, `_reserved_side_calm` measures edge-energy of the reserved text band
  vs the subject band; if the band isn't genuinely empty the page is regenerated
  with an escalated `_emptiness_boost` directive (up to `PB_NS_TRIES`). Every
  Ella page now converged to a clean text band. Added an `only=[labels]` arg to
  `illustrate` for targeted single-page regen (used for the watch).
- Watch: audited all 15 Ella pages; style (pink square screen, periwinkle strap)
  is consistent, but handedness follows Flux's pose-mirroring. Targeted-regen of
  the flipped pages (Page 23) landed the watch back on the LEFT wrist. NOTE: a
  perfect left-wrist guarantee is not achievable by prompt alone — the model
  mirrors handedness with the pose.
**Tunables (env):** `PB_CALM_MAX`, `PB_NS_FLOOR`, `PB_NS_RATIO`, `PB_NS_TRIES`.
**Output:** clean rebuild snapshotted to
`runs/output/storybook/art/versions/version3/` (19 pages + cover + PDF).
**Files:** `pipeline/picturebook.py`, `pipeline/pb_illustrate.py`,
`pipeline/rebuild_v3.py`.

## v1.3 — Reference-matched text-on-art + pinned watch (2026-07-08)
**Problem 1 (text/image balance):** the body text was being laid on an opaque
cream card (`_draw_card_soft`), which reads as a pasted slab — nothing like the
three client interiors (Run Sparky Run, Bilbo & Obi, Sheep the Llama), which
place text DIRECTLY on a calm patch of full-bleed art with no box.
**Fix:** new `_draw_text_on_art` in `picturebook.py`. It measures the local art
luminance/contrast under the text box, picks deep ink over light art or
near-white over dark art, and lays a soft feathered halo of the opposite tone
behind the glyphs so they stay crisp with no rectangle. `render_content` now
calls it instead of `_draw_card_soft`.
**Problem 2 (Ella's watch):** the watch flipped left↔right wrist between pages
and its styling drifted. Root cause: `charspec._accessories` silently dropped
the `details` field and buried "left wrist" in a comma list, so Flux was free
to mirror it and re-invent the strap/face.
**Fix:** `_accessories` now emits `details`, and when an item pins a wrist/hand
it restates the side emphatically ("ALWAYS on her LEFT wrist and NEVER the
right … identical style, strap and face on every page"). Ella's `locked_spec`
watch is enriched to a fully-pinned design (square rounded face, pink/magenta
digital screen, periwinkle silicone strap). Requires page regen to take effect.
**Files:** `pipeline/picturebook.py`, `pipeline/charspec.py`,
`runs/ella-the-animal-shelter-and-you/data/characters.json`.

## v1.2 — Per-run versioned art folders (2026-07-08)
**Change:** `pipeline/versions.py` snapshots each art run into
`output/storybook/art/versions/vN/page_NN/page_NN.png` (+ `cover/`, `manifest.json`),
auto-incrementing vN. `--migrate` folds legacy flat `versionN/` folders in.
Replaces scattered `.bak` files with clean, comparable per-run history.
**Files:** `pipeline/versions.py` (new).

## v1.1 — Best prompt-based consistency method (2026-07-08)
**Problem:** even with the locked spec, Ella's logo/shoe/shirt-colour drifted
between pages. Tried post-compositing a fixed logo PNG (`logo_composite.py`) but
it was too inaccurate (occluded chests, double-logos, mis-placement) — reverted.
**Change:** the realistic best is prompt-based, built from four levers:
1. **Reference-image conditioning** — every page uses `flux.edit` with the
   character's reference sheets as input images (strongest lever).
2. **Lead-with-design** — `_compose_prompt` puts the exact CHARACTER DESIGN
   block + a consistency reminder FIRST, then the scene (models weight the
   opening most); the lock was previously appended at the weak end.
3. **Full-body-first refs** — `_gather_refs` sends full-bodies before portraits,
   so on crowded pages (cap 4) the outfit/logo reference isn't bumped out.
4. **BFL-safe wording** — dropped "copy the reference exactly / reproduce
   identically" (trips BFL "Protected Content" moderation) for "keep the design
   consistent — same outfit and colours".
Gives strong outfit/colour/logo-presence consistency; not pixel-identical logos
(model redraws freehand each page — an architecture limit, not a prompt gap).
**Files:** `pipeline/pb_illustrate.py` (`_compose_prompt`, full-body-first
`_gather_refs`), `pipeline/regen_pages.py`, `pipeline/charspec.py` (softer lock
wording), `pipeline/logo_composite.py` (kept as optional tool, not default).

## v1.0 — Apply locked spec to an existing book; regen pages 8–9 (2026-07-08)
**Change:** to give an already-generated book cross-page consistency,
`refs.locked_spec_from_ref` vision-reads a character's existing reference sheet
and derives an exact `locked_spec` (real hex, garments, logo) — so re-illustrated
pages match the established design instead of drifting. `regen_pages` now appends
each present character's lock to the page prompt (deterministic), same as the
main loop. Demo: regenerated Ella pages 8–9; page 9's Ella now matches her ref
(purple paw-logo tee, headband, ponytail, denim shorts). Old art backed up to
`page_NN.png.bak`.
**Files:** `pipeline/refs.py` (`locked_spec_from_ref`),
`pipeline/regen_pages.py` (lock injection).

## v0.9 — Locked character spec for cross-page consistency (2026-07-08)
**Problem:** a character (e.g. Ella) drifted between pages — t-shirt logo, shoe
colour, hair shade and face wrinkles changed — because vague descriptions
("favourite colour", "mid-size") were re-invented on every render.
**Change:** a canonical nested-JSON `locked_spec` per character with EXACT values
only (`#RRGGBB` for every colour, logo motif + `coords_pct` + `size_pct`,
enumerated garments). A deterministic serialiser renders it to identical text
every time, and that block is injected into **every page prompt directly** (not
via the LLM planner, which paraphrases and loses detail).
**Files:** `pipeline/charspec.py` (new), `pipeline/characters.py` (bible emits
`locked_spec` + no-approximation rule), `pipeline/refs.py` (`_identity` uses the
lock), `pipeline/pb_illustrate.py` (`_locks_for` appends lock per page).

## v0.8 — Guaranteed close-up view (2026-07-08)
**Problem:** the app sometimes showed "Close view not available" — the close-up
API call was moderated (non-retryable) or rate-limited past its retries.
**Change:** on any close-up failure, crop the head from the full-body (which
almost always succeeded) so a close view is always shown, labelled
"(from full-body)".
**Files:** `client_app.py` (`crop_face`, close-up fallback).

## v0.7 — Exact likeness in the full-book pipeline (2026-07-07)
**Change:** extended the exact-likeness recipe to the CLI book pipeline. Drop a
clean crop in `data/char_refs/<name>.png` → it is vision-captioned, the literal
attributes are injected into a lean prompt, and Flux is conditioned on the crop.
Character ref sheets feed page generation, so the likeness propagates to every
page. Validated: "Dad" regained his long wavy hair + beard.
**Files:** `pipeline/refs.py` (`char_ref_image`, `describe_reference`,
`_exact_likeness`, lean prompts, `build_refs` per-character path).

## v0.6 — Per-character reference photos + exact-likeness recipe (app) (2026-07-07)
**Problem:** generated humans didn't match the real people (woman had no
ponytail, man's long hair missing). Conditioning on the photo alone loses
details — a strong style prompt overrides hat/glasses/outfit.
**Change:** upload a reference photo per extracted character; **vision-caption**
it (Claude) into literal attributes, inject them into the prompt, and condition
Flux (`edit`) on the photo. Validated: cap, sunglasses, braids, outfit colours
all reproduced. Also added `.docx` manuscript upload tab and `python-docx` to
requirements. App deploys to Streamlit Cloud from GitHub.
**Files:** `client_app.py`, `requirements.txt`.

## v0.5 — Calm text zone (2026-07-07)
**Problem:** text overlapped busy art — the scene prompt said "fill the frame
edge to edge, no blank areas", so the text side was packed with texture.
**Change:** the scene prompt now requires the text side to be a genuinely calm,
simplified, low-detail, evenly-toned area (open sky / soft wash / blurred
distance), like the human reference books — while still full-bleed (no white box
or seam). Validated on Bilbo p3 (left 40% became a clean sky wash).
**Files:** `pipeline/pb_illustrate.py` (SCENE_SYSTEM + scene_prompt template).

## v0.4 — Photo-likeness from embedded manuscript photos (2026-07-07)
**Change:** manuscripts embed real photos (Bilbo & Obi at the stadium) under
`media/`. `storybook.extract_media` pulls them out and flags the "pictured
below" characters; `refs.py` conditions Flux on them for ~90% likeness. Falls
back to text-only when no photo.
**Files:** `pipeline/storybook.py`, `pipeline/refs.py`.

## v0.3 — Book archiving + PDF-assembly fix (2026-07-07)
**Change:** a fresh generation archives the previous book to
`.archive_books/<name>__<timestamp>/` (all pages, PDF, data + manifest) so
`output/` starts clean; runs only from the `parse` stage, never on a resume.
Fixed `picturebook.build` crashing on a unit with an empty `pages` list (cover).
**Files:** `pipeline/archive.py` (new), `pipeline/pb_run.py`, `pipeline/picturebook.py`.

## v0.2 — Moderation resilience + first full Sparky book (2026-07-07)
**Problem:** Black Forest Labs moderated an innocent baby-animal ref prompt
(`newborn`+`female`+`wearing none`), and moderation is non-retryable, so one bad
prompt killed the whole run.
**Change:** `_sanitize` strips the trigger words and retries; full-body falls
back to the portrait if still refused. Generated the first complete book
(Run, Sparky, Run — 32 pages) end to end.
**Files:** `pipeline/refs.py`.

## v0.1 — Client manuscript parser + motifs + scene learnings (2026-07-07)
**Change:** studied a human-illustrated pair to learn text alignment, two-page
spreads, and how faithfully art follows the `Illustration:` notes. Rebuilt the
parser for the client "Illustration Notes" format (was returning 0 units):
colon/bare page notes, art-direction separated from story text, spot/spread
layout detection, character bible + illustrator note capture. Added an action
motif library (smell/run/fear/…) that injects visual cues so verbs read, and
made the `Illustration:` note authoritative staging in scene planning.
**Files:** `pipeline/storybook.py`, `pipeline/motifs.py` (new),
`pipeline/pb_illustrate.py`; analysis in `CLIENT_DOC/ANALYSIS_sparky.md`.
