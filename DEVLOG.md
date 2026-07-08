# Development Journal — Picture-Book Generator

The journey of building the manuscript → illustrated-book pipeline and the
character-generator app. Newest version on top. Each entry: what changed, why,
and the files touched.

> Append a new `## vX.Y` block at the top whenever we make a change.

---

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
