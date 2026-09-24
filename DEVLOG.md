# Development Journal — Picture-Book Generator

The journey of building the manuscript → illustrated-book pipeline and the
character-generator app. Newest version on top. Each entry: what changed, why,
and the files touched.

---

## v8.4 — Per-figure zoom anatomy + cast presence; cost cuts (Kimi text, coat pre-gate) (2026-09-22)
The page-scale anatomy probe was BLIND to per-character leg counts: namaste
p3/p18 shipped 6-legged giraffe/zebra while the gate scored anatomy 100. Two
root causes — anatomy was the one axis never moved to zoom crops, and the v8
per-character audit only inspects cast WITH reference sheets, so background
animals (the yoga-class giraffe/zebra) were never checked at all.

- **anatomy_v8.py (new):** two-stage per-figure pass — locate every figure
  (sheet or not) → zoom + upscale each → count legs vs expected IN CODE
  (legs_visible > expected ⇒ defect), plus floating-limb / duplicated-body.
  Each defect carries its bounding box (handoff for masked inpainting next).
  Wired into gate_v7 as the stricter (min) anatomy score; toggle ANATOMY_ZOOM.
  Mascot loophole tightened (posture may be human-like; extra/duplicated legs
  still fail). Fixes the latent extra_limbs flag the repair router read but
  the audit never produced.
- **Cast presence:** missing_cast reuses the located figures (no extra call)
  to flag a declared character the render DROPPED (vanishing background
  animal); folds into facts; records cast_located per page for a future
  cross-page continuity check.
- **Cost work (this session):** TEXT_MODEL→Kimi K2.6 (text stages ~5× cheaper,
  validated JSON parity via pipeline/ab_models.py; VISION_MODEL kept on Sonnet
  — Kimi is blind on OpenRouter). reasoning.enabled=false + provider.
  require_parameters=true added to llm._post_chat for reasoning models. Local
  coat pre-gate (audit_pregate.py) skips the 2 VLM coat calls on a confident
  colour-histogram match: 68% skip-rate, 0 dangerous skips (AUDIT_PREGATE=on).
  Finding: image generation is ~85-90% of book cost; text/audit are the small
  slices. hybrid image backend is a no-op (editor always routes to OpenRouter).

Validation of the anatomy/cast changes is BUDGET-BLOCKED (OpenRouter weekly
$50 exhausted mid-run; pages 27-29 failed to render, 21 pages gate-blocked).
Pure-Python logic unit-tested offline; anatomy_eval.py ready to run on budget.
Files: anatomy_v8.py, anatomy_eval.py, gate_v7.py, audit_pregate.py,
ab_models.py, pregate_eval.py, llm.py, .env.

## v8.5 — Surgical fal repair: auto-mask + IP-Adapter inpainting (2026-09-23)
Pivoted from "rebuild the page" to "fix only the broken pixels". Text
prevention (v8.4 body-plan clause) and full compositing both failed — the
first because image models ignore negation/counting, the second because
harmonizing a pasted composite drifts characters into generic mush. The
original Gemini art was actually good (well-integrated, not pasted); it just
had ONE localized chimera. So: keep it, mask only the defect, inpaint that.

- **fal_backend.py (new):** working fal-ai/flux-general integration —
  text_to_image (background plate) + masked inpaint. Hard-won params:
  enable_safety_checker=False (checker blacks out benign images; guard on
  mean<8), IP-Adapter needs weights (InstantX/FLUX.1-dev-IP-Adapter + siglip
  encoder), white mask=repaint. Background plate quality is excellent and
  matches the approved watercolour style (style-risk low).
- **fal_repair.py (new):** auto-mask + repair wrapper. Detect (multi-pass,
  since detection is stochastic) → classify ERASE vs REDRAW → NEIGHBOUR-SAFE
  mask (_clip_to_neighbors shrinks away from other figures' boxes) → fal
  inpaint → re-audit → revert-if-worse. Originals never overwritten
  (output/art_repaired/).
- **anatomy_v8.locate_anomaly (new):** boxes just the extra/duplicated part so
  ERASE removes only the anomaly and preserves the character.
- Proven on p23: ERASE (manual) fixed the chimera AND preserved the zebra +
  giraffe (anatomy 100, 5/5 cast). Wrapper (auto) reproduced end-to-end but
  REDRAW mode drifted identity (zebra→cat, Twiggy flagged missing) — the
  open quality gap.

Two bugs encoded against, both learned by breaking p23: mask-too-wide erased
the giraffe (→ neighbour-safe clip); strength-too-high on REDRAW replaced
instead of repaired (→ prefer ERASE). Open: REDRAW identity drift (IP-Adapter
scale/anchor), stochastic detection recall. Cost this session ~$8 OpenRouter
+ ~$3 fal.
Files: fal_backend.py, fal_repair.py, anatomy_v8.py, canon_rules.py.

## v8.4 — Per-figure zoom anatomy + cast presence; cost cuts (Kimi text, coat pre-gate) (2026-09-22)
(see below; superseded generation-prevention approach by v8.5 surgical repair)

## v8.3 — Audit de-biased: majority vote, verified zoom, forced-choice coat colour (2026-09-17)
Namaste p17 regression: fawn-BROWN Ferdinand (canon: cream) passed the
audit 3 votes straight; the oversized sheep passed too. Three judge
defects found and fixed in audit_v8:

- **Pass-biased retry loop:** the old loop retried only FAILING votes —
  one lenient vote passed a character while a strict one got overturned
  on retry. Now majority vote: 2 votes, 3rd breaks disagreement.
- **Unverified zoom crops:** the locator sometimes boxes the wrong cast
  member (Ferdinand's "zoom" was mostly Tallia) — a wrong zoom poisons
  the audit worse than none. New verification call (crop vs sheet: same
  character?) discards bad crops; fail-open to page-scale.
- **Comparative colour judgment is lenient:** "do the colours match?"
  passed brown-vs-cream unanimously. Coat colour now judged by FORCED
  CHOICE (same lesson as the v7.7 size lock): name the coat colour of
  page-zoom and sheet independently from a fixed palette, compare in
  code; shade families (white/cream, tan/golden) equal, cross-family =
  drift. Regression: p17 goat now fails "tan vs cream"; p18 control
  passes.

Files: audit_v8.py. Pages 10-14,17,19,21-23,29 re-rolled.

## v8.2 — Namaste outfit canon repair: one source of truth for clothing (2026-09-17)
The zoom-crop audit (v8.1) exposed the same drift on 14 pages — Tallia/
Twiggy/Wooliam in leotards/leggings vs sheets showing short tops + bare
legs. Root cause was NOT the generator: the character data itself
disagreed with the sheets. Twiggy/Tallia's nested charspec — serialized
into EVERY page prompt — carried `bottom: athletic leggings` and a
`leggings` sig_item; Wooliam's said `bottom: part of one-piece suit` +
"one-piece spandex suit (full body)". The pages were obeying the prompt;
the audit was obeying the sheet. The sheets themselves were also
internally split (bust view crop-top vs full-body view unitard).

Repair (canon locked = crop top/vest + all four legs bare, per client):
- characters.toon: outfit/appearance strings rewritten; `leggings`
  sig_items pruned; every `bottom` garment → explicit NONE + bare-hide
  text; Wooliam's one-piece references excised.
- Sheets: fresh t2i regen re-drew leggings anyway (athletic-wear
  attractor) — the reliable recipe is editor.edit garment REMOVAL on the
  sheet ("remove everything below the ribcage, keep all else identical"),
  then rebuild group0 via generate_with_refs FROM the fixed member
  sheets, never from text.
- Lesson: when one drift recurs across many pages, diff every text
  source (outfit string, nested clothing dict, sig_items, group specs)
  against the sheet before blaming the generator. And back up sheets
  before regenerating them (the originals were unversioned and are gone).

Files: books/namaste-ferdinand/v3/data/characters.toon, refs/{twiggy,
tallia,group0}.png. Pages 10-14,16,17,19,21-23,25,27,29 re-rolled.

## v8.1 — Audit zoom crops + head-facing axis + garment-silhouette rule (2026-09-17)
Namaste p13 regression: the sheep sat with an owl-rotated head in a purple
DRESS (canon: short vest, legs bare) yet the v8.0 audit passed him — at full
page scale the judge cannot see garment shape, and no schema axis even asks
about head/body orientation. Three generic fixes in audit_v8:

- **Zoom crop (audit_v8._zoom_crop):** one VLM locate call per audited
  character (same recipe as canon_save), the crop appended as image 3 with
  "judge fine details from THIS image". Regression-proven: p13 Wooliam
  clothes flip from match_reference → changed_or_missing with the correct
  dress-vs-vest difference named.
- **`head_facing` axis:** consistent_with_body | rotated_or_impossible |
  cannot_see; pose-correction explicitly never excuses an owl head. Wired
  through _parse_verdict, _verdict_ok, the focus builder, and generate_v7's
  clothes_only routing (a rotated head is structural → regenerate, never a
  surgical clothing edit).
- **Garment-silhouette rule:** clothes now compares TYPE/length/silhouette,
  not just colour — right colour on the wrong garment is changed_or_missing.

Cost: +1 locate call per character per audit. Files: audit_v8.py,
generate_v7.py.

## v8.0 — Character audit: comparison verification replaces yes/no probes (2026-09-16)
The v7.10 gate passed pages at 100 with characters entirely ABSENT (Namaste
p14/16/19), drifted clothes (p14/22/27) and duplicated sheep (p28). Root
cause: ~20 batched yes/no identity/items questions per call — agreement
bias at batch scale, occlusion escapes leaking, and no page-to-page memory.
Client-requested redesign, implemented as pipeline/audit_v8.py:

- **AUDIT** — ONE focused VLM call per character: page vs the character's
  sheet vs canon crops. Forced-choice per axis (presence / size vs others /
  colours / body_shape / clothes / vs_previous_pages) + a concrete
  `differences` list; code decides pass/fail. Regression-proven: page-16
  art that scored 100 under probes scores 50 under the audit ("Boaris
  missing pink headband..."); page-14 caught with Ferdinand absent.
- **FOCUSED REPAIR** — the differences list becomes the regen prompt
  ("FOCUS — the previous attempt drew these characters WRONG: ...");
  clothes-only drift routes to a surgical edit with the sheet attached.
- **CANON** — cross-page memory: cast characters cropped from each
  audit-clean page into data/canon/<char>/; later audits must also match
  the 2 most recent canon crops. Only clean pages become canon; missing
  canon passes (no deadlock). Post-run canon_sweep re-audits every page
  against the settled canon -> art/canon_report.json.
- **Gate integration** — new `audit` category (PASS 99) first in repair
  priority; score_page(skip_char_probes=True) retires the batched
  identity/items probes + proportion probe for sheet characters; facts /
  anatomy / style / scale / setting probes unchanged (phantoms, limbs,
  floors still covered). Net cost ≈ neutral.
- Data: Namaste p21 cast +Boaris,Wooliam (parse under-listed the friends).

Files: audit_v8.py (new), generate_v7.py, gate_v7.py.

## v7.10 — The ten consistency locks from the Namaste page-wise review (2026-09-16)
The client's page-by-page Namaste review clustered into 10 generic root
causes; each got the full lock→prompt→probe treatment (nothing page-specific
— every future book benefits). Test regen on pp 7/13/18: p18 100 clean, the
new proportion probe correctly caught and flagged 7/13.

- **`proportion` gate category (gate_v7._proportion_probe):** forced-choice
  per character vs their OWN sheet (leg length / girth / head ratio) —
  catches solo-page drift the pair-based scale gate is blind to. Stance and
  per-vignette consistency ride the same call. PASS 99, fails → regenerate.
- **Stance lock:** `identity.stance` = anthro|feral in the locked spec
  (deliberately NOT two-vs-four-legs — yoga poses would false-fail;
  `mid_pose_cannot_tell` passes). charspec serializes it; POSTURE LOCK line.
- **Ordering coverage (plan_v3.size_pairs):** near-equal pairs (r>0.93) now
  emit `order_only` entries → the coarse ordering probe always runs, so a
  pig can't tower over a goat unprobed. Parse requires height_cm + high
  consistency for any character on 2+ pages.
- **Feature orientation:** items_v7 catalogues directional anatomy as
  `kind:"feature"` items ("horns curving BACKWARD..."); features_line() in
  the prompt; probed in the items loop with the ref in view.
- **Outfit continuity:** `dress_state` clothed|unclothed; explicit
  "(no clothing)" item stops the model dressing naked animals; _spec_items
  text fallback for sheetless recurring cast (probed via the facts call).
- **Closed cast:** CLOSED CAST prompt clause + contract state (no unlisted
  prominent figures; scene-called background crowds exempt) + presence-probe
  union with the plan cast so a contract miss can't drop "exactly ONE pig".
- **Setting manifest:** locations treated like characters — floor + fixed
  props (count+design) locked from the rendered setting sheet
  (items_v7.build_settings), SETTING LOCK prompt line, `setting` gate
  category (floor forced-choice → regenerate; props occlusion-first →
  surgical edit with the setting sheet attached). PASS 80.
- **Compose face-safety:** _locate_figures also returns head boxes (cache
  stamped src=vlm_v8); face overlap ×5000 penalty + hard skip; `face` answer
  in veto/post-draw probes; a face hit earns an extra retry; bottom-third
  bonus prefers feet-side strips.
- **Compose contrast:** deterministic _contrast_level (ink-vs-strip
  luminance delta + busyness) — flips ink, escalates halo, last-resort soft
  blurred scrim (still no hard card). Zero API cost.
- **Retrofit tool (pipeline/plan_backfill.py):** fills ONLY missing fields
  into an existing book's toons (never overwrites approved values). Namaste:
  28 fields + 6 setting manifests + feature items, no re-parse.

Files: gate_v7.py, generate_v7.py, plan_v3.py, items_v7.py, compose_v3.py,
parse_v3.py, charspec.py, refs_v3.py, plan_backfill.py (new).

## v7.9 — World/togetherness probes + cross-species scale (2026-09-15/16)
Grizzly client review + first Namaste run exposed three gate blind spots;
each got a probe (the recurring lesson: a rule only in the generation
prompt is a suggestion — it becomes real when a probe verifies it).

- **World probe (gate_v7.page_contract):** all-animal casts get a contract
  state "zero human faces/bodies anywhere INCLUDING posters/pictures/toys"
  — rides the facts category. Caught Grizzly p10's human posters on the
  first regen roll; a 33-page offline audit found 4 human pages (5, 7, 9,
  11) that regen'd clean.
- **Togetherness probe:** 3+ named characters on a page must be ONE group
  at the same spot — no listed character exiled to a background table
  (Grizzly p20: every count probe passed while the family sat at separate
  tables).
- **Cross-species scale (gate_v7._scale_order_probe):** the landmark ladder
  assumes humanoid proportions (hip ≈ 52% of height) — a giraffe's hip is
  ≈35%, so "goat's head at giraffe's hip" false-failed EVERY Namaste yoga
  page. Same-species pairs keep the exact landmark; cross-species pairs now
  get coarse forced-choice ordering (shorter-as-expected | similar | taller
  | far_too_tiny; near-equal pairs accept "similar"). Offline re-score of
  15 flagged pages: 6 were probe artifacts, 9 real (Boaris tiny/towering,
  Twiggy shrunken) — those 9 regen'd against the fixed probe.
- Namaste Ferdinand (30pp) generated end-to-end unattended as the first
  fully-probed book: v3/output/namaste_ferdinand.pdf.

## v7.8.1 — Spread text balancing + group-sheet size role (2026-09-15)
Client feedback on Grizzly Greg: a two-page spread carried ALL its text on
the left page (walls up to 382 chars) while the right page was a no-text
stub ("continuation of the spread; no separate illustration needed").

- **parse_v3.balance_spreads (new, runs at parse end + idempotent on
  existing scenes.toon):** detects continuation stubs via the extractor's
  own marker, splits the A-page text at the sentence boundary nearest the
  midpoint, moves the second half to B, and promotes B to a real companion
  scene (same cast/setting, "same moment a beat later, different angle").
  Grizzly: all 8 spreads balanced (e.g. 18: 382 -> 180/201).
- **generate_v7._roles:** group-sheet role text now demands the members'
  relative SIZES be copied from the sheet — the cub trio sheet carries the
  correct size gradient and is attached on every family page, but nothing
  told the model to honour its proportions (part of the lingering
  Greg-drawn-too-big drift on teatime pages).

## v7.8 — Caption/figure avoidance: live the dead 600× penalty (2026-09-15)
Captions could land on characters: compose's 600× box-collision penalty read
staging.toon, which NOTHING in v7 wrote — dead code; placement leaned on
edge energy (blind to flat-shaded figures) + a 3-candidate yes/no veto that
fell back to "best score anyway" when all were occupied.

- **compose_v3._locate_figures (new):** one enumerate-then-locate VLM call
  per body page on the FINAL art → tight normalized boxes (count-first stops
  background-figure dropping; found 7 figs incl. 5 tiny soccer kids on p5).
  Clamp/de-sliver/pad 0.02; fail-open [].
- **staging.toon now written**, cached by art mtime (page regen → auto
  re-detect on next compose; `--only` reruns re-detect only changed pages).
- **Veto hardened:** forced-choice (background_only|partial_figure|figure),
  energy-conditional fail-open, doomed candidates (box overlap >0.15) skip
  the probe, all-occupied fallback re-ranks by (collide, energy).
- **Post-draw closed loop (_caption_overlaps):** forced-choice probe on the
  drawn caption region; one retry with the failed strip excluded; result in
  output/pages/compose_report.json {y, energy, collide, retried,
  residual_overlap}. residual_overlap=true = art has NO text-safe band →
  send back through generate --only (band repair); compose never edits art.
- Verified on grizzly-greg: clean pages collide=0.00; p22 (Greg fills the
  frame) retried + honestly flagged residual; rerun = 100% cache hits,
  identical placement; offline degrades to old behavior exactly.

## v7.7 — SIZE LOCK: relative-height anchor + forced-choice scale gate (2026-09-14)
Maya's size vs Grandpa Leo drifted across the book (hip-height on p5,
near-adult on p3, chest-height on p2) yet every page scored 100 — every
gate probe compares a character to their OWN reference, so cross-character
scale was never measured. Absolute `height_cm` in the locked spec means
nothing to the image model; only in-frame relationships are drawable.

- **plan_v3 size anchor (new):** `char_height_cm` (spec height, age-table
  fallback), `size_pairs` (co-present high-consistency humans → ratio →
  body landmark via standard figure proportions; 122/172 = 0.71 → "head
  reaches lower chest"), `size_lock_line` — one deterministic sentence,
  identical on every page, same trick as the locked character spec.
- **generate_v7:** SIZE LOCK clause in every page prompt; new `scale`
  category in PASS (binary-strict, 99); scale failures route to full
  regeneration, not surgical i2i (resizing a character re-lays-out the
  scene anyway).
- **checklist_v3 PRO-2:** child stays child-sized next to an adult — rides
  into every t2i/i2i call.
- **gate_v7._scale_probe (new):** forced-choice measurement, NOT yes/no.
  Tested first on the shipped Maya pages: yes/no probes with a pose escape
  clause passed every page including the hip-height one (VLM agreement
  bias + escape-clause abuse). The probe now makes the VLM PICK which of
  10 body landmarks the small character's head reaches (correcting for
  stoop/depth) and code compares to the locked landmark ±1 rung; retry on
  miss like _second_opinion; fail-open on errors. Stable across runs,
  exact on the known-good page, fails the worst page.
- **3-page test (p3/p5/p9 regen):** all 100 incl. scale=100, proportions
  visibly correct; old art backed up in `output/art_pre_sizelock/`.
  Gotcha rediscovered: generate_v7 must run from the BOOK dir (refs.toon
  paths are book-relative) — from repo root it silently loads zero refs
  and identity/scale score None.

## v7.6 — Fool-proof loop: double-vote gate, full-bleed probe, audit tool (2026-09-11)
Maya book driven from 12-of-15-flagged to a fully clean audit: EVERY page
scores 100 on identity/items/facts/anatomy/style, would-fail: none.

- **scripts/audit_gate_v7.py (new):** offline full-book re-score with the
  CURRENT gate (probes only, no generation) — apply a pipeline upgrade to a
  finished book and find where it matters without paying for regens.
- **Double-vote probes (gate_v7._second_opinion):** a probe must fail TWICE
  to count — failures (only) are re-asked once per category. Killed the
  volatile false negatives ("tongues out" failing when both tongues are out;
  "shirt at neckline" failing under a scarf) without loosening real checks.
- **Full-bleed anatomy probe:** catches drawn borders/3D canvas mock-up
  edges (page 5's first render was literally a book mock-up; page 8 had a
  blank bottom band the surgical edge-fix could not fill -> regen to 100).
- **Contract rules tightened:** no transient micro-states (incl. nose
  pressed on glass), no expressions inferred from dialogue tone, no counts
  of ambient features (puddles in rain!), no counts of worn garments.
- **Hair = signature item:** extraction now catalogues hairline/facial hair
  with explicit fullness ("full coverage, NO bald or thinning crown") —
  caught and fixed Grandpa's bald crown on pages 3/5/11; re-extraction
  preserves hand-authored pages:/setting: scopes.
- **Compose-aware band check:** band flags only when compose's own
  clearest-strip search (real text size, occupancy veto) finds nothing
  calmer than V7_BAND_MAX_ENERGY=50 — band flag noise went to zero.
- **Story-logic via author_edits:** pages 1-2 drew the raincoat before the
  story fetches it; author_edits + regen fixed both (p2=100).
- Surgical edits for point defects: p10 Maya tongue, p5 grand-halt palm,
  p11 crown, p1 nose-to-glass. Composed pages + PDF rebuilt from clean art.

## v7.5 — First full book on the hardened pipeline: Maya (2026-09-10)
New 12-page human-lead test book "Maya and the Rain Parade" (manuscript
written in-repo) ran manuscript→PDF on the v7-only pipeline with item
enforcement: `books/maya-and-the-rain-parade/v3/output/maya_and_the_rain_parade.pdf`.

- **Outfit consistency held book-wide** (cloud patch, glasses, boots, scarf,
  umbrella; items=100 on spot checks) — the Bilbo flicker class is gone.
- **Sheet QA in practice:** first Maya sheet showed the cloud patch in only
  one view → one surgical sheet edit (patch in BOTH views) before items
  extraction; re-extraction produced a verified crop.
- **Conditional outfits:** `when` now supports deterministic scopes
  (`pages:3-11`, `setting:<key>`); items_v7.page_items() gives the per-page
  view (matched scope = fully gate-enforced; wrong scope = absent; free text
  = prompt hint only). Maya's rain outfit scoped 3-11, Leo's umbrella 3-9.
- **Gate cleanup:** the coarse "every signature item (hat/cap, bandana)?"
  identity probe false-failed hatless humans and is redundant next to
  per-item probes — now asked only for characters without a manifest.
- **Author-edit loop validated:** page 12 drew raincoat+boots indoors;
  two author_edits + one-page regen fixed it and the page passed (98).
  Final report: all pages passed. Known residuals: contract extractor still
  invents transient states ("glasses sliding down nose") and miscounts
  shared props ("exactly 2 boots" with two wearers); band flags fire even
  when compose finds a clear strip (planned refinement).

---

## v7.4 — Signature-item manifest: full outfit/accessory consistency (2026-09-10)
Client complaint: Dad's t-shirt logo flickers page-to-page. Root causes: the
v7 prompt never named worn items in text; the gate had ONE coarse
"every signature item?" probe (a missed logo still averaged >=80 identity on
multi-char pages, so repair never fired); small details are a few pixels in a
downscaled sheet, exactly what the model re-invents.

- **pipeline/items_v7.py (new):** vision-reads each APPROVED sheet (ground
  truth over the written spec — Dad's spec said plain shirt, the sheet has a
  paw logo) into a closed `sig_items` list on the character in
  characters.toon. Every printable garment records its logo EXPLICITLY —
  present (motif/colour/position) or "NO logo" — so both dropped AND invented
  logos are catchable. Small items get a zoom crop from the full-res sheet
  (v6_b/refs/items/): tight box → verify → wide retry (>=45% of sheet) →
  verify → else DROP (a wrong "close-up" crop would teach the model the
  wrong design; the first Dad crop showed plain collar fabric and the
  garment-phrased verifier passed it — verification must name the DETAIL
  alone, "white paw print logo", never the garment). Runs at the end of the
  refs stage (fail-open) and standalone: `python -m pipeline.items_v7`.
- **generate_v7:** OUTFIT LOCK prompt block (deterministic WEARS line per
  present character) + zoom crops as extra role-assigned references
  ("CLOSE-UP of Dad's polo shirt — reproduce this exact detail", cap 4/page).
- **gate_v7:** new `items` category — ONE binary probe PER item, riding in
  the same batched identity call (near-zero cost), with an occlusion escape
  clause (true if the spot is genuinely hidden by pose) and both failure
  directions (missing item OR uncalled-for logo added). `when`-conditional
  items are skipped. PASS["items"]=99: any single miss fails the page.
  Identity/items call now probes at 1024px (768 hid chest logos).
- **repair:** items-fail joins the surgical-edit branch; the failed items'
  zoom crops are attached so the edit copies the exact motif, not a guess.
- Bilbo v6_b manifest extracted: 5 chars, incl. Dad "white paw print logo on
  left chest" with a verified zoom crop; Mom's shirt recorded as "completely
  plain, NO logo" (catches the invented-logo direction).
- **3-page validation (v6_c scratch, pages 9/13/20):** Dad's paw logo present
  on EVERY page where his chest is visible (the original flicker is gone);
  on p9 (waist-down framing) the item probe initially false-failed →
  restructured probe puts the occlusion check FIRST ("is the spot visible?
  out of frame → true"), after which double-scoring both trials agreed
  (volatility gone). The gate also made a REAL catch: bandana "white baseball
  print" had drifted to generic blobs on all 3 pages → new extraction rule
  (repeating garment prints are `small` → zoom crop) + p13 regen produced
  clear baseballs-with-stitching on both bandanas (items 91, total 96).
  Residual flag = cap shade strictness — honest review flag, not a block.

---

## v7.3 — v7 is the ONLY pipeline; legacy engines removed (2026-09-10)
The bake-off is settled: the v7 route (role-assigned multi-ref Gemini +
measured gate + diagnostic repair) gives our best character consistency, so
it is now the single generation route and every alternative is gone.

- **run_v3.py rewritten single-engine:** stages are now
  `parse → copyedit → refs → layout → generate(v7) → compose → book`.
  `--engine`, `--train-loras`, `--no-correct/--no-scene-pass/--no-harmonize`
  removed (`--engine` still *accepted* silently so a not-yet-synced deploy
  jobs.py can't crash). The `correct` i2i stage is gone — v7's gate+repair
  loop replaces it.
- **Deleted legacy engines:** `generate_v3.py` (t2i), `correct_v3.py`
  (i2i + judge), `lora_v3.py` + `fal_backend.py` (kontext+LoRA fallback),
  `sprites_v3.py`/`stage_v3.py`/`render_v3.py`/`composite_v3.py` (sprite
  compositor), plus scripts `ab_lora_eval.py`, `kontext_lora_test.py`,
  `bakeoff_v7.py`. All recoverable from git history.
- **Ported into generate_v7 so no client feature was lost:**
  `author_edits` (workspace per-page fix requests) now injected as
  MANDATORY fixes, and `checklist_v3.t2i_block` (the client-complaint
  rule source) appended to every v7 prompt.
- **editor.py:** `IMAGE_BACKEND` fal/hybrid routing removed — one
  OpenRouter/Gemini path.
- **eval_v3:** `_small` now comes from `gate_v7` (was `correct_v3`).
- **server/jobs.py:** drops `--engine generate`; progress ORDER loses
  `correct`. `pipeline_api` comments updated.
- Verified: all modules import; run_v3 CLI ok (incl. deprecated `--engine`);
  offline prompt-assembly test on the Bilbo book confirms roles + checklist +
  author_edits all present.

---

## v7.2 — Client-review round: compose veto, age drift, edit verification (2026-09-08)
Live review of the v6_b book with Ayush; each finding produced a permanent rule:

- **Caption on a background figure (their p7):** compose's clearest-strip
  search shared the edge-energy blindness to flat-shaded characters, and
  background figures aren't in the layout `avoid` boxes. `_strip_occupied`
  vision veto added — top 3 well-separated candidates probed, first
  unoccupied wins.
- **Adult age drift (Mom older on 2 pages):** identity probe sharpened
  ("not visibly OLDER, heavier-set or more aged than the reference").
  Mom's sheet regenerated head-to-toe via the Gemini route (FLUX failed
  full-body 3x) — her white sneakers are now DEFINED, ending shoe-colour
  drift.
- **Cut/floating hands on the petting page:** generation-side ANATOMY rule
  (interacting people must be visibly connected — no cropped hands, no
  bodies hidden so only hands show) + a hands-belong-to-someone probe.
- **Surgical-edit regression (de-age edit turned Mom's shirt orange):**
  edits are now verified on ALL signature attributes before saving, not
  just the attribute being fixed. A verifier that checks only the delta
  approves collateral damage.
- Page numbering convention with the client = PDF positions (cover = 1).

## v7.1 — First full v7 book (Bilbo v6_b) + gate calibration (2026-09-08)
Full 19-page Bilbo book through the v7 route:
`v6_b/output/bilbo___obi_s_baseball_adventure.pdf`.

- **Style drift is DEAD: style=100 on every page** (the always-on style plate).
  Bandana'd sheets regenerated first (charspec fix: `collar/bandana/neckwear`
  now serialize into the lock — omitting them made the judge treat the bandana
  as an unauthorized item).
- **Two gate probe bugs found via score volatility:** (1) "exactly 1 Bilbo"
  was asked WITHOUT the reference sheet attached — unanswerable for
  look-alikes, failed every duo page from uncertainty → named-char counts
  moved into the identity call (sheets in view); (2) contracts invented
  counts ("2 humans" from "some new humans") and motion states ("tails
  wagging") → STRICT RULES added (exact-count words only; frozen-moment
  states only). After fixes: 13/19 pages pass outright.
- Targeted v7 re-run on the 6 flagged pages: 12 (the extra-hands mascot page)
  68→94 and visually clean; 19→97; 6→91. Residual flags are honest: p15's
  "sleepy" still reads weak (the client's original note — needs a
  posture-explicit scene prompt, not a repair edit), plus band flags on
  by-design close-ups where compose already found calm strips (refinement:
  don't flag band when compose succeeds).
- Threshold sanity-check on client-labeled v6_a pages: p9 (flagged
  "realistic") → identity 100 but style 50 — categories separate cleanly;
  identity threshold 80 stands.

## v7.0 — Redesigned pipeline: role-assigned multi-ref Gemini + measured gate (2026-09-08)
Built from `docs/Pipeline-Failure-Analysis.md` (six failure classes → R1–R7)
and `docs/Pipeline-Redesign-Proposal.md` (research: FLUX Kontext's documented
copy-paste/pose-rigidity trade-off explains our drift; AnyStory's verified
per-subject routing says references need assigned roles, or models average
look-alikes; VQAScore says binary VLM probes beat similarity for counts).

- **6-page bake-off** (`scripts/bakeoff_v7.py`, hardest pages from client QA,
  identical role-assigned refs): avg totals — control (shipped v6_a,
  post-correction) 67, **Gemini-3-image 79** (style 92, anatomy 97),
  Seedream 4.5 75 (identity 93, facts 64, style 58). Both candidates beat the
  corrected control while RAW. Gemini chosen (wins the two loudest client
  complaints: style drift + anatomy); Seedream kept as identity-strong backup
  (`fal_backend.seedream_edit`).
- **`pipeline/gate_v7.py`**: page CONTRACT (verifiable facts extracted from
  the PRINTED text: cast counts, prop counts, visible states) + batched binary
  probe scoring — identity vs sheets / facts vs contract / anatomy artifact
  classes / style vs style plate, each 0–100.
- **`pipeline/generate_v7.py`**: ONE route for every page incl. matter pages —
  `editor.generate_with_refs` (new; Gemini multi-ref generation, roles named
  per image: character sheets, STYLE PLATE on every page, setting plate).
  Gate → diagnostic repair (anatomy/style→regenerate; identity/facts→surgical
  edit citing the exact failed probes; band→repaint into negative space),
  max 2 rounds, then keep-best + FLAG. `gate_report.json` per run.
- **Smoke (v6_b, pages 12+22):** p22 — the page that shipped PHOTOREALISTIC
  in v6_a — scored 100/100 first try, on-style watercolor. p12 (extra-hands
  mascot page) repaired 64→75, zero anatomy fails, correctly flagged.
- Cost: no LoRA training needed on this route (−$6/book); pages ~$0.13 + ~4
  probe calls.
- **Before the full v6_b book:** regenerate Bilbo/Obi sheets with bandanas
  (data now says always-on but the sheets predate it), and decide flag-review
  workflow. correct_v3 is now optional; compose/book unchanged.

## v6.5 — Style previews moved to the New Project form (fixed sample scene) (2026-09-08)
Client wanted the style comparison right at the "Illustration style" dropdown on
the New Project form — before any manuscript is parsed. Since no book scene
exists yet at that step, previews now render ONE **fixed generic scene** (a child
+ puppy in a cozy sunlit room) once per style. Same subject across all styles by
design, so the only variable the author compares is the style itself.

- **Project-independent shared samples**, cached under
  `STATE_DIR/style_samples/<style>.png` and rendered ONCE (lazily, on first
  request), then reused for everyone — a generic sample never needs
  regenerating. `start_style_samples(force=False)` renders only the styles not
  already on disk; threaded (3 workers), atomic `status.json`, one failed style
  can't stop the rest.
- Endpoints: `POST/GET /api/style-previews` (no slug) +
  `GET /api/style-samples/{fname}`. api.js:
  `startStyleSamples/getStyleSamples/pollStyleSamples`.
- New Project.html: a "Preview styles" button under the style dropdown opens a
  modal grid; "Use" selects that style. Removed the per-book preview panel from
  the Characters page per the client's "here only" request (the per-book preview
  backend + `restyle` job group from v6.3 remain, just unmounted).
- Files: `server/app.py`, `server/pipeline_api.py`, `server/static/api.js`,
  `Frontend_DESIGN/.../New Project.html`, `Characters.html`. Verified: real
  one-style render produced a clean watercolour sample; caching skips re-renders;
  live on Render (bb-illustrator-kjvd.onrender.com).

## v6.4 — Bilbo end-to-end on the kontext+LoRA pipeline (2026-09-08)
Full manuscript→PDF run of "Bilbo & Obi's Baseball Adventure" on the v6 path:
`v6/output/bilbo___obi_s_baseball_adventure.pdf` (19 pages). The green/blue cap
contrast held on every sampled page — the historical duo-collapse defect did
not reappear. Fixes made along the way, in pipeline order:

- **parse:** 12k max_tokens truncated the plan JSON mid-flight → 32k.
- **refs:** three failure modes found and fixed. (1) Sheets shipped unverified —
  new `_render_checked()` vision QA + retry loop per sheet (wrong character
  count / missing signature items feed back into the redraw instruction).
  (2) The book style text is subject-saturated ("warm golds for the
  retrievers") and made FLUX draw DOGS on Mom's and the mascot's sheets → new
  `_style_technique()` gives sheets medium/linework/lighting only, plus an
  explicit "never photorealistic" requirement after human sheets came out
  photo-real. (3) Partial `--only` regens rebuilt the manifest from scratch,
  silently dropping every other sheet → merge via `_put()`.
  Client's V6 interior art (`manuscript_media/v6-0*.png`) is wired in as the
  likeness anchor via `photo` fields (Bilbo→v6-03 after v6-04's blue-heavy caps
  flipped his green one). Secondary-char spec colours synced to accepted
  sheets so correct_v3 doesn't fight them page after page.
- **lora:** curation judge HALLUCINATED a collar (described differently every
  call: red 'B' tag / heart pendant / harness) and rejected 17/20 views →
  `_keep()` now ignores "missing X" complaints for wearables the LOCK doesn't
  name (`_PHANTOM` list) and grounding complaints on white-void training views
  (jumping poses legitimately float). Trained `bilbotok` + `obitok` from the
  saved views without a third paid generation round.
- **generate:** cast line ("Every one of these characters MUST appear:
  Bilbo (golden retriever), …") after a mascot page rendered ZERO dogs; pages
  now render in a 4-worker thread pool (V3_WORKERS, 3 gate pages: 4min→52s);
  occupancy-veto retries capped at 2 — a close-up/interior can't empty its
  band, compose adapts instead.
- **3-page gate (3/4/8):** raw renders had correctable defects (dropped/
  swapped caps); correct_v3 converged on all three → gate passed → full book.
- **Residuals for client review:** p8 Homer breathes fire + jersey lettering;
  slight fluffiness variance between the dogs on p9; Ballast copyedit skipped
  (guide file missing from data/).

---

## v6.3 — Style previews + author page-edit → full-pipeline regen (2026-09-08)
Two author-control features for the web app, backend + pipeline side:

- **Style previews** (pick a style by eye): `POST/GET
  /api/projects/{slug}/style-previews` renders ONE representative story scene
  once per `STYLE_MAP` style (threaded in-process, 3 workers, per-slug lock,
  status.json polled by the UI) into `v3/output/style_previews/`. Deliberately
  NOT conditioned on ref sheets (they carry the old style); identity comes from
  the plan's text locks. `POST /api/projects/{slug}/style` applies the winner
  via `apply_style_override` and kicks a new `restyle` job group
  (`refs..refs`) so the reference sheets are repainted in the chosen style.
- **Author edit button → pipeline regen**: `POST
  /api/projects/{slug}/pages/{id}/edit` appends the free-text fix to the
  scene's new `author_edits` list in scenes.toon (edits ACCUMULATE — a second
  request can't lose the first) and re-runs the full generate group
  (`layout..book --only <page>`). `generate_v3` injects the list as
  "AUTHOR'S REQUESTED FIXES (MANDATORY)" on both the reference and LoRA
  prompt paths; `correct_v3`'s judge/fixer/polish now receive the author
  direction (note + edits) as AUTHORITATIVE so the identity pass can't revert
  a requested change. GET lists edits, DELETE clears them.
- Files: `server/app.py`, `server/pipeline_api.py`, `server/jobs.py`,
  `pipeline/generate_v3.py`, `pipeline/correct_v3.py`. Also restored missing
  `fastapi`/`python-multipart` in the venv (rebuilt venv had dropped them).

## v6.2 — Tone/accessory/negative-space fixes + honor the author's panel pages (2026-09-07)
Client feedback on the first full v3_klora book: tone drifts between pages,
Ella's bracelet flips wrist / goes missing, and no negative space for text.
Diagnosis + fixes, validated live on the three worst pages (2, 9, 15):

- **Root cause of the "collage defects": the pipeline was fighting its own
  plan.** Pages 2/9 EXPLICITLY call for a collage / four-panel montage in the
  art plan, while our prompts and the SPLIT judge forbade panels — retries
  burned and "fixes" broke intended layouts. New `plan_v3.wants_panels(sc)`
  (regex: collage|montage|vignettes|N-panel; a singular "vignette effect" is a
  camera term and does NOT match). On panel pages: anti-grid wall dropped,
  1 render attempt, occupancy veto off, correct_v3's composition/SPLIT pass
  skipped. Pages 2 and 9 now match the author's shot list.
- **Negative space:** the edge-energy band check passed flat-shaded characters
  (few edges). New `_band_occupied()` vision veto (downscaled JPEG, cheap
  judge call, fail-open) — an "occupied" frame gets +100 score so best-of
  never prefers it. Close-up pages (p15's hug) legitimately fill the band;
  compose already falls back to the clearest strip elsewhere on the page.
- **Accessories:** new `_sig_line()` puts a COMPACT signature-items clause in
  the short LoRA prompt from locked_spec — hair shape, hair ties, "charm
  bracelet (always on left wrist)" — plus "show each named character exactly
  ONCE at their correct relative size" after p15 rendered two Ellas. Wrist-side
  flips remain a Flux mirroring limit; correct_v3 stays the backstop.
- **Tone:** `V3_SEED` env → fixed seed (+attempt on retries) passed through
  `fal_backend.kontext_with_loras(seed=)`, plus "use the exact same palette,
  lighting and rendering finish as every other page" in the prompt.
- **Cleanup:** repo scan — every pipeline module is referenced; composite
  engine (composite/sprites/stage/render_v3) kept (Bilbo baseline still uses
  it). Removed smoke-test PNGs + a stray .bak. Old v1/v2 pipeline files were
  already deleted on disk (pending in git status).
- Fixed pages live in `v3_fix/output/art/` (scratch, seed 1000). Full-book
  re-render with all fixes is the next step.

---

## v6.1 — Kontext+LoRA wired into generate_v3 as THE LoRA path (2026-09-07)
The v6.0 recipe is now the real `V3_USE_LORA=1` render path in
`pipeline/generate_v3.py`, replacing the losing pure-t2i branch.

- **Selection:** main character = the present char with the LARGEST layout box
  that has trained weights (`_char_area`); only THAT character's LoRA is applied
  (scale default now 1.0). Co-stars ride in the conditioning image:
  `_stitch_refs()` joins all present sheets side-by-side at equal height
  (a single sheet passes through untouched). No trained main char or no sheets
  → clean fallback to the reference baseline.
- **Prompt is SHORT** (trigger + scene + author note + "keep designs exactly as
  shown" + style + negative-space side) — the long instruction block with
  hex-locks/checklist stays baseline-only, since the A/B showed trigger tokens
  drown in it. Retry attempts prepend a brief "too busy, redraw simpler" line;
  the band-energy NS loop is unchanged.
- **3-page validation (same A/B pages, judged art-only D1):** 85 / 95 / 95 vs
  baseline 45 / 85 / 75. First p15 roll scored 45 (missing bracelet + crowd) —
  a re-roll hit 95, so that was variance, not wiring. Ella's LoRA was correctly
  chosen as main on every page.
- **Residuals:** p4 leaked a misspelled in-art sign (correct_v3's job); on p15
  the hug occupies the bottom band yet edge-energy read 16 "clear" — flat-shaded
  characters fool the metric; a character-mask/vision band check is a candidate
  upgrade.
- Ran in a scratch `V3_DIR=v3_klora` (data copied from v3/) so baseline art
  stayed untouched. Full-book render kicked off next.

---

## v6.0 — Kontext+LoRA: the winning consistency recipe (2026-09-07)
Retried the 3 A/B pages via `fal-ai/flux-kontext-lora` — reference-image
conditioning AND trained LoRA weights in ONE call, with a SHORT prompt (no
hex-locks/checklist; sheet + weights carry identity). New
`fal_backend.kontext_with_loras()`; runner `scripts/kontext_lora_test.py`.

- **D1 scores (baseline / pure-LoRA / kontext+LoRA):**
  p1 45/45/**95** · p4 85/45/**85** · p15 75/45/**75**.
  Kontext+LoRA ≥ baseline on every page — a +50 blowout on p1, ties elsewhere,
  and visually the exact outfit/hair/sneakers everywhere.
- **Stacking is the poison, confirmed in isolation:** p15 with BOTH LoRAs merged
  scored 45 even with conditioning; the SAME page with only Ella's LoRA (Biscuit
  carried by the stitched sheet) scored 75. Rule: **ONE LoRA per page** (the
  main character); co-stars ride in the conditioning image.
- **Recipe:** conditioning image = character sheet (solo) or side-by-side
  stitched sheets (multi-char); main character's LoRA at scale 1.0; short prompt
  = trigger + scene + "keep designs exactly as shown" + style + negative-space
  side; resolution_mode 1:1.
- Residual issues are the correctable kind (missing bracelet, one leaked in-art
  sign) — exactly what correct_v3's loop already fixes.
- **Next:** wire this recipe into generate_v3 as the LoRA path (replacing the
  losing pure-t2i branch), then a full-book run.

---

## v5.9 — 3-page LoRA A/B: baseline WINS, LoRA path not adopted yet (2026-09-07)
The validation gate did its job. Trained Biscuit (`biscuittok`, 9 curated views)
alongside Ella, rendered pages 1 / 4 / 15 of the Ella book with `V3_USE_LORA=1`,
and scored both variants with the eval judge (art-only, D1 consistency).

- **Result: baseline 45 / 85 / 75 vs LoRA 45 / 45 / 45.** The reference-
  conditioned path won both multi-character pages and tied page 1.
- **Failure mode:** in full-pipeline conditions the LoRA identity DILUTES —
  wrong outfit (orange tee/jeans instead of yellow tee/overalls on p4), wrong
  hair (high puffs / headband), and on p15 broken proportions. The solo smoke
  test was perfect, so the gap is (a) two stacked LoRAs at 0.9 interfering and
  (b) trigger tokens drowning in the long page prompt (placement + checklist +
  locks + style ≈ hundreds of words).
- **Verdict: keep reference-conditioned generation as the default.** LoRAs stay
  trained + registered; the path stays opt-in behind `V3_USE_LORA=1`. Ideas
  before the next A/B: scale 1.0–1.1, a much shorter LoRA-path prompt, single-
  LoRA pages only, or fal's flux-kontext-lora (LoRA + reference conditioning
  together — best of both).
- **Also fixed `eval_v3`:** it sent the page + refs as full-size PNGs and the
  provider 400'd; now downscales to small JPEGs like correct_v3's judge (this
  bug made all six initial scores error out).
- Artifacts: `books/ella.../v3/ab_lora/` — baseline_/lora_page_{1,4,15}.png,
  contact_sheet.png, ab_scores.json; runner `scripts/ab_lora_eval.py`.

---

## v5.8 — LoRA bootstrap: per-character trained identity on fal (2026-09-07)
Character consistency by WEIGHTS instead of reference images — the migration
plan's step 7+. New stage + wiring, validated end-to-end with a real training run.

- **`pipeline/lora_v3.py` (new):** per high-consistency character:
  ~10 varied views (poses/angles/framings) generated ALONE on white from the
  character's reference sheet via fal Kontext → each view CURATED by the strict
  `correct_v3.judge` vs the sheet (off-model views dropped, kept on disk with
  `_dropped` suffix for inspection) → curated set zipped → fal fast LoRA
  training with a deterministic trigger token (`Ella` → `ellatok`) → registry
  `v3/data/loras.toon`. Saves after every character so a crash can't lose a
  paid training. `--dry-run`, `--only`, `--force`; knobs `V3_LORA_VIEWS/`
  `MIN_KEEP/STEPS/SCALE`.
- **`fal_backend` fixes:** `train_lora` now takes ZIP bytes and uploads them as
  the single `images_data_url` fal's trainer actually expects (the old stub
  passed a URL list — would have failed on first use); new multi-LoRA
  `generate_with_loras(prompt, loras)`.
- **`generate_v3` wiring (opt-in `V3_USE_LORA=1`):** a page whose present cast
  is FULLY covered by trained LoRAs renders as pure t2i with all its LoRAs
  stacked (scale 0.9) and trigger tokens in the prompt; any untrained character
  present → whole page falls back to the reference path (a mixed render would
  leave that character unanchored). `run_v3 --train-loras` runs the stage after
  refs.
- **Validated for real on Ella** (ella-the-animal-shelter-and-you): 9/10 views
  kept — the judge correctly DROPPED the one view missing her charm bracelet,
  proving curation earns its keep — trained on fal (~$3), then a token-only
  smoke render reproduced her exactly (face, pigtails+red ties, yellow tee,
  overalls, purple sneakers) with NO reference attached.
  Artifacts: `books/ella.../v3/lora/ella/` + `loras.toon`.
- **Known trade-off:** the LoRA path is t2i, so setting-reference conditioning
  is lost on those pages; `correct_v3` still judges/fixes them afterwards.
  Next: 3-page `eval_v3` A/B vs the reference baseline before any full book.

---

## v5.7 — fal.ai backend live: env rebuilt + both image paths verified (2026-09-07)
The fal.ai account is recharged and `FAL_KEY` is in `.env` (`IMAGE_BACKEND=hybrid`).
Unblocked the paused migration (`FAL_MIGRATION_RESUME.md`) and validated the seam:

- **Rebuilt the Python env.** The project `.venv/` was gone (system python3 had
  none of the deps). Recreated `.venv` and installed `requirements.txt` —
  fal-client 1.0.1, python-dotenv, python-toon, pillow etc. all in.
- **Smoke-tested both fal paths with real API calls:**
  1. Pure t2i (`python -m pipeline.fal_backend` → `fal_smoke.png`, FLUX Pro v1.1).
  2. Kontext multi-image reference-conditioned generation via
     `fal_backend.edit(blank + ref)` → `fal_smoke_kontext.png`; the reference
     puppy (green cap) carried over intact — the consistency behaviour we want.
- **Hybrid routing confirmed in code:** `editor.edit` already dispatches
  generation calls (blank-square first image) to fal and keeps surgical i2i
  edits on Gemini. Nothing else needed changing.
- **Next per the migration plan:** LoRA bootstrap (charspec → sheet → curate →
  `train_lora`), wire `generate_with_lora` into `generate_v3`, 3-page validation
  vs baseline before a full book.
Three issues reported after a real production book generation, all in
`workspace.js`, all verified headless with the 23-page Bilbo book:

- **Pages clipped in the left panel.** Thumbnail `<img>` rendered ~281px tall
  inside a 150px `overflow:hidden` grid wrap (`maxHeight:100%` didn't resolve
  against the grid area), so only the top strip of each page showed. Capped the
  thumb at an explicit `146px` + white background → whole square page visible
  (measured 146×146, aspect preserved).
- **Slow page switching.** `src()` used `bust(url)` with `Date.now()` computed
  PER RENDER, so every re-render minted a new URL and the browser re-downloaded
  every full-size PNG. Switched to a stable per-reload version token (`ver`,
  bumped only in `loadPages`) so images cache — verified **0 network refetches**
  across 4 page switches (was refetching all pages each time).
- **PDF wouldn't download.** The export used `fetch → blob → a.click()`; the
  click fired after an `await`, which browsers block as a non-user-gesture
  download. Replaced with a real `<a href={pdfUrl} download>` (same-origin, direct
  gesture); shows a disabled state + "generate first" hint when there are no pages.

File: `workspace.js`. Deployed to `bb-illustrator-deploy`.

## v5.5 — Author-experience features from prod review (2026-08-31)
After the first full production run, three gaps surfaced in real use — all in the
front-end (`Frontend_DESIGN/Blue Balloon Craftman Login/`), tested headless and
deployed to prod:

- **Custom page count.** `New Project.html` (and the Workspace Story-settings
  panel in `workspace.js`) capped book length to a fixed dropdown. Replaced with a
  free numeric input (4–200) plus quick-pick preset chips; still stored as the
  "N pages" string so downstream parsing is unchanged.
- **Skip on the character carousel.** `Characters.html` required *every* character
  fully specified before "Create storybook" — one fussy character blocked the
  whole book. Added a per-card **Skip** (and a footer **Skip remaining**) that
  accepts a character's auto-generated reference sheet (marks it ready with a
  "Skipped" pill; still Replaceable). Verified: 3 "Needs design" → Skip → all
  "Skipped", Create storybook enabled.
- **Live book-building screen.** The generation view was near-blank. The running
  card now shows the stage title, a Layout→Illustrate→Consistency→Text→PDF step
  tracker (done ✓ / active / pending), a % progress bar, and a live pipeline
  **log tail** (last 8 lines) so the author sees exactly what's happening. Fixed a
  tracker bug (`indexOf` on an array of objects → all-✓) to use the map index.

Files: `New Project.html`, `Characters.html`, `workspace.js`. All three verified
with Playwright (zero console errors) and pushed to `bb-illustrator-deploy`.

## v5.4 — Ship v5.1–v5.3 to production + persistent-disk fix (2026-08-31)
Client upgraded Render to a paid plan (new URL bb-illustrator-kjvd.onrender.com;
fast, no cold-start). But production deploys from the separate `bb-illustrator-deploy`
repo (Docker) which still had the OLD mock — none of v5.1–v5.3 was live. Synced the
changed files (`server/{app,db,jobs,pipeline_api}.py`, `workspace.js`,
`Workspace.html`, `Characters.html`, `Design with AI.html`) into that repo and pushed.

**Persistent-disk safety fix:** the deploy repo's `render.yaml` comment said to mount
the disk at `/app` — but the Dockerfile does `WORKDIR /app` + `COPY . .`, so a disk
there would SHADOW the whole app and break boot. Instead made all writable state
configurable via `BB_STATE_DIR` (server app/db/jobs/pipeline_api; defaults to the repo
locally, verified via a temp-dir smoke test) and set `render.yaml` to `plan: starter`
with a 5GB disk at **`/data`** + `BB_STATE_DIR=/data`, so `books/` and the SQLite DB
live on the disk and survive restarts without touching the code at `/app`.

Verified live after redeploy: Login 200 (~1s), workspace.js = real (0 old-mock
markers), Design-with-AI Ram mock gone (buildInsights present), `Cache-Control:
no-store` on pages. OPEN ITEM (dashboard-only, can't verify via HTTP): confirm the
`bb-data` disk is actually attached + `BB_STATE_DIR=/data` is set on the service — if
the service isn't Blueprint-managed, render.yaml disk/plan changes must be applied
manually in the Render dashboard.

## v5.3 — Generation "never completes": .env not loaded + silent job errors (2026-08-30)
User: on the Render production site (https://bb-illustrator.onrender.com) book
generation ran ~30 min then the Workspace said "nothing generated yet". Diagnosed:

- **Root code gaps (fixed here):**
  1. **Nothing loaded `.env`.** `server/jobs.py` runs the pipeline as a subprocess
     with `env = dict(os.environ)`, but neither the server, `serve_app.sh`, nor the
     pipeline ever called `load_dotenv` (python-dotenv isn't installed). So unless
     `OPENROUTER_API_KEY` was manually exported, every `editor.edit()`/`llm` call
     raised `OPENROUTER_API_KEY not set` and generation failed. Added a
     dependency-free `_load_dotenv()` in `server/app.py` (real env wins) + a
     startup WARNING when the key is missing. Verified the key now propagates to
     child processes.
  2. **The Workspace hid job failures.** When the generate job errored, the stage
     fell through to the silent "No pages yet" empty state — exactly the user's
     symptom. Added a `jobFailed` branch that shows the real `job.error` + the last
     ~12 pipeline log lines + a "Try again" button. Verified with a synthetic
     errored `job.json` (Playwright).
- **Confirmed the pipeline itself works** locally with the key set (ran the
  `layout` stage on bilbo → `layout.toon`, 23 pages, exit 0).
- **Production is Render free-tier** — probing showed a cold start (first request
  502/timeout, second 200 in 0.77s). The heavier root cause for "never completes"
  is deployment shape, NOT code: free-tier instances **spin down when idle**
  (killing the in-process background generation thread) and have an **ephemeral
  filesystem** (every restart wipes `books/` pages and `server/data/app.db`).
  A 23-page, ~30-min OpenRouter job cannot survive that. Guidance recorded for the
  separate `bb-illustrator-deploy` repo: set `OPENROUTER_API_KEY` in Render env,
  attach a persistent disk for `books/` + `server/data/`, disable spin-down / use a
  paid instance, and ideally move long jobs off the web dyno to a worker.

Files: `server/app.py` (.env loader + warning), `workspace.js` (job-error UI).

## v5.2 — Kill the "Ram" mock in character design + stop stale caching (2026-08-30)
User report: designing any book's character with AI opened a screen about **"Ram"**
(a fabricated fantasy protagonist with an ancestral sword / indigo cloak),
unrelated to their manuscript — and the old Workspace mock kept reappearing "no
matter which book." Root causes were three subtle mocks (the page *looked* wired):

- **`Design with AI.html` fell back to fiction.** It *did* call the real
  `designCharacter` API, but its display read `meta = CHAR_META[char] || CHAR_META.ram`
  and `INSIGHTS[char] || INSIGHTS.ram` — hard-coded ram/shyam/gita/sita tables. Any
  real character (no table entry) rendered as **Ram** with invented "manuscript
  details". Fixed: deleted `CHAR_META`/`INSIGHTS`; added a container `App` that
  fetches the real character via `getCharacters(project)` (match by name, then
  slug), splits into a synchronous `Studio` (`key={name}` to remount per
  character); labels/role/hue now derive from the real character; the insights
  panel is built from the real `lock` description (fake `p.N` page-refs dropped)
  and hidden when empty; the live preview opens on the real `ref_url` sheet.
- **Character UI state used a global localStorage key** `"bb_characters"`, so
  designs bled across books. Namespaced to `"bb_characters:<slug>"` in both
  `Design with AI.html` and `Characters.html`.
- **Stale browser cache** kept serving the pre-v5.1 Workspace. Added a
  `no_cache_pages` middleware in `server/app.py` setting `Cache-Control: no-store`
  on `.html/.js/.css` (page images keep their own `?v=` busting).

Verified with headless Playwright against the real `bilbo-obi-baseball-adventure`
book: Design-with-AI for `?name=Bilbo` and `?name=Obi` shows the real character +
real reference sheet, **no "Ram"**, no fabricated details, zero console errors;
`Cache-Control: no-store` confirmed on the design pages. Files:
`Design with AI.html`, `Characters.html`, `server/app.py`.

## v5.1 — Workspace editor wired to the real backend (2026-08-30)
The client web app's Workspace (book editor) was still a Figma-exported **mock**:
`workspace.js` invented a fake "The Lantern Boy" book with CSS-gradient
placeholders for illustrations, a hard-coded `Ram/Shyam/Gita/Sita` cast, a fake
teammate list, an in-browser AI chat (`window.claude.complete`), and a
canvas-drawn PNG "export". None of it touched the pipeline. (Login/Home/New
Project/Characters/Design-with-AI were already real.)

Scope agreed with the user: **Workspace canvas only**, and **replace the fake
element-editing surface with a real page view** (the pipeline bakes text/layout
into the page PNG, so there is nothing to element-edit client-side).

Rewrote `Frontend_DESIGN/Blue Balloon Craftman Login/workspace.js` (~600 lines of
drag/marquee/effects machinery deleted) to drive everything off `BB.api`:
- **Pages panel + canvas** → real `getPages(slug)` images; per-page cache-busting
  after edits (`?v=`), since corrections overwrite the PNG in place.
- **Characters panel** → real `getCharacters(slug)` (name, ref sheet, lock text).
- **Story settings** → editable `draft` buffer; **Save** = `saveDraft`,
  **Save & regenerate** = `saveDraft` + `startGenerate` + job poll, plus Revert.
- **Edit with AI** → real per-page `correctPage`; shot-list box → `setPageNote` +
  re-illustrate job.
- **Export** → streams the real pipeline PDF (`pdfUrl`) via fetch→blob→download,
  with a graceful "no PDF yet" error.
- **Job lifecycle** → on load, polls `getJob` and shows a live progress card
  (layout→generate→correct→compose→book), auto-refreshing pages when done.
- Empty/edge states: no-project screen, no-pages "Generate the book" CTA.
- `Workspace.html`: dropped the now-redundant `workspace-book.js` floating panel
  and the unused `workspace-panels.js` mock includes.

Verified against the real `bilbo-obi-baseball-adventure` book (23 pages, 8
characters, PDF) with a headless Playwright run: 23 real thumbnails, real cover in
the canvas, real character names, real title in settings, AI dock opens, **zero
console errors**. Files: `workspace.js` (rewrite), `Workspace.html`.

---

## v5.0 — Layered compositing engine (deterministic character consistency) (2026-07-21)
Prompt-tuning + reference sheets + i2i correction could never fully fix character
drift (size/appearance changing page to page) — it's the structural limit of
text-to-image, confirmed by the project's own prior tooling analysis (git cfbe16c).
Rebuilt character rendering as LAYERED COMPOSITING (revived the shelved engine +
added the missing AI-harmonize step):
- **sprites_v3.py** (port of sprites.py): generate a small pose atlas per high
  character ONCE, conditioned on the approved reference sheet; rembg cut to
  transparent PNGs in v3/assets/<slug>/. Validated: clean cutouts, on-model.
- **composite_v3.py** (port of compositor.py + NEW `harmonize()`): paste the exact
  sprite pixels onto a plate at a controlled size/position (identity + size
  DETERMINISTIC), then `editor.edit` harmonizes the composite into one painted
  scene while told to keep appearance/size exactly — fixes the "pasted" look that
  shelved the original engine.
- **stage_v3.py** (port of compose_book director): LLM stages each page —
  pose/x/y/height/flip per character (same-type chars get equal height) + a
  character-free background desc → staging.toon.
- **render_v3.py**: per page — generate a character-free plate (locked to the
  location ref), composite the atlas sprites, harmonize, and record each
  character's box for text placement.
Phase-3 validation (page 9: Mom, Dad, both dogs): the two dogs came out identical
and the SAME size, and harmonization made it read as one painted illustration, not
pasted. This is the structural fix for the client's #1 issue. Next: box-aware text
(uses the known character boxes) + orchestrate the full compositing book run.

---

## v4.3 — Composition judging + signature-item consistency (general) (2026-07-21)
Client QA on Bilbo surfaced failures the i2i correction never caught: dogs at
inconsistent SCALE, a dog "sitting on air" (ungrounded), parents cropped to just
legs, and bandanas vanishing on some pages. Root diagnosis: the correction judge
only checked character IDENTITY (matched the white-bg reference sheet), had NO
composition criteria, the fix instruction literally said "keep composition
unchanged", and a parse-invented per-page conditional ("bandana on cover/pg4/pg12
only") made the judge flip-flop and strip bandanas. All fixed generally:
- **checklist_v3**: new IMAGE_RULES PRO-1 (consistent scale), GRD-1 (grounded, no
  floating), CRP-1 (no legs-only/headless crops) — injected into BOTH generation
  and the judge. `SIGNATURE_ALWAYS` rewritten: the judge does NOT know the page
  number, so it must IGNORE "only on page X" conditions and judge signature items
  purely against the reference sheet image.
- **correct_v3**: JUDGE_SYSTEM now also judges scale/grounding/crop; new dedicated
  `composition_check()` critic (separate vision pass focused only on staging) runs
  after the identity loop and feeds the same fix; `fix_chars` now MAY adjust a
  character's size/grounding/framing when the flagged problem is compositional
  (previously forbidden).
- **parse_v3**: LOCKED_SPEC rule forbids restricting a worn item to specific page
  numbers — signature items are marked worn "always"; only genuinely situational
  items get a condition. Prevents the flip-flop at the source.
- Data: Bilbo/Obi bandana `when` corrected to "always"; cower-scene action rewritten
  to show Mom/Dad full-body (was "behind the legs" → legs-only art); dragon action
  clarified to stand on the ground (v4.2).
Validated on Bilbo pages: judge now catches "Obi floating in mid-air (GRD-1)" and
keeps bandanas consistently required. These are pipeline-wide, not Bilbo-specific.

---

## v4.0 — Rebuild after client rejection: single pages, locked characters, clean text (2026-07-20)
The v3 Ella build was rejected on sight (wide spreads, text in a bordered strip
that clipped/overlapped, Ella's hair changing every page). Root causes were traced
and fixed; the repo is now v3-only.
- **Deleted ~21 legacy modules + gen_book.sh** (ancient `run.py` flow + old
  `pb_run` flow + one-off scripts + unused `flux.py`). Live set is 16 modules:
  `run_v3` + the `*_v3` stages + `plan_v3, checklist_v3, charspec, editor, llm,
  toon_io, style_guide`.
- **Single square pages (no spreads).** Every manuscript page prints as one
  8.5×8.5 sheet. Killed the spread/gutter branches in `book_v3` (SINGLE_TRIM
  2550²), `generate_v3` (aspect always square), `compose_v3` (removed
  `_gutter_safe`), `plan_v3.is_spread`→False, `parse_v3`/`layout_v3` prompts, and
  `checklist_v3` (dropped GUT-1).
- **Character lock via charspec (was orphaned).** `parse_v3` now emits a
  `locked_spec` per high character (one value per trait, hex colours, no "X or Y").
  `plan_v3.char_lock` serializes that exact spec, so refs/generate/correct/judge
  all speak from it. Judge now **compares the page to the reference IMAGE**
  (`llm.chat_json_images`, new), fix redraws to match the sheet, and `perfect_scene`
  gets the refs so it stops reverting fixes.
- **Text in diegetic negative space.** `generate_v3` asks for a calm in-scene area
  (sky/wall/ground), not a blank edge band. `compose_v3` rewritten: no scrim card
  (halo only), one small locked size (~3% page height), hard safe margin so text
  never clips, grow-to-fit not shrink-erratic. Cover/title pages now render the
  book title; the dedication page renders its text centred.
- First full Ella build surfaced two model-behaviour bugs, both fixed:
  1. **Landscape output.** Gemini ignored the "1:1 square" text and emitted
     1408×768 for 11/19 pages, which the square trim then cropped (chopped the
     cover title). Fix: `editor.blank_square()` — pass a white square as the EDIT
     BASE so the model returns 1024² (verified: square even with refs attached).
     Wired into `generate_v3` (correction already edits the now-square page).
  2. **4-panel collage.** Multi-action page text made the model draw a bordered
     grid. Fix: `generate_v3` prompt now demands "ONE continuous unified scene —
     NOT a grid/collage/panels/vignettes, no dividing lines"; `checklist_v3`
     IMG-2 + judge updated to fail collages. Verified on page 11 (now one shelter
     room, clear floor band for text, Ella on-model).
  Character consistency confirmed working from the locked_spec (Ella identical
  across instances). Re-running the full book with both fixes.

---

## v3.4 — API hard-deadline (no more hung book runs) (2026-07-20)
An Ella run hung 95 min mid-correction on page 13: the process was alive but had
consumed ~15s CPU, holding one ESTABLISHED socket to the image API. `requests`
`timeout=300` is a per-read gap, not a total cap, so a server trickling bytes
under the gap never trips it. Fixed in both API clients.
- **pipeline/editor.py**, **pipeline/flux.py**: new `_post_bytes()` runs the POST
  in a daemon worker thread and `join()`s with a HARD_DEADLINE (default 240s,
  env `EDIT_/IMAGE_HARD_DEADLINE`); if it overruns, the thread is abandoned (dies
  with the process) and a `Timeout` is raised into the existing retry loop.
  Also split into CONNECT_TIMEOUT (15s) + READ_TIMEOUT (120s). Closing the socket
  from a watchdog was tried first but doesn't reliably wake a blocked read on
  Linux — the join-and-abandon pattern does. Verified: a trickling test server
  now raises at the deadline; a normal response still parses in ~0.01s.
Net: one dead/slow connection can no longer freeze a whole book; the page just
fails its attempt, retries, and the run continues.

---

## v3.3 — Client V3 feedback → shared generation checklist (2026-07-20)
Went through every per-page client review for the two V3 books (Bilbo & Obi, 14
pages; Ella, 18 pages) and turned all 32 pages of complaints into one enforced
rule set. Root causes collapse into six buckets: structure, text fidelity,
typography, character consistency, scene logic, image integrity.
- **pipeline/checklist_v3.py**: single source of truth. 15 IMAGE_RULES (STY/CHR/
  SCN/IMG/GUT/TXT) + a named BANNED_PROPS list (the hallucinated hotdog stand,
  safety vest, steam, parade…) + STRUCTURAL rules (MAN/FM/BM/DIM/TYP/CPY/TTL).
  `t2i_block`, `i2i_block`, `judge_block` render the same rules for each caller.
- **pipeline/generate_v3.py** (text-to-image): injects `t2i_block(setting)`.
- **pipeline/correct_v3.py** (image-to-image): injects `i2i_block(setting)` into
  the identity-fix edit, and `judge_block()` into the vision judge so it now fails
  a page for style drift, invented props, wrong location, duplication/warping,
  gutter intrusion or stray text — not just per-character identity drift.
- **V3_FEEDBACK_PIPELINE.md**: root-cause buckets, stage-by-stage pipeline,
  full rule table, and per-page traceability (every client line → rule code).
Structural stages (parse/copyedit/compose/book) are specified there as the next
step; the image-model wiring — the specific ask — is done.

**Structural stages (same day):** implemented the non-image half of the checklist.
- **parse_v3** (MAN-1/MAN-2/FM-1/BM-1): prompt now demands verbatim page text,
  forbids inventing/dropping pages, emits front/back matter as roled pages; new
  `reconcile()` flags body text not found verbatim in the manuscript.
- **copyedit_v3** (CPY-1): new `copyedit_scenes(data_dir)` runs Ballast house style
  over the v3 `scenes.toon` (old `copyedit()` only touched storybook.json).
- **compose_v3** (TYP-1/2/3): `_lock_scale()` = one book-wide type scale (fraction
  of page height, fits every page); `_gutter_safe()` keeps spread text off the
  gutter; ink locked to one colour (was per-page dark/light flip).
- **book_v3** (DIM-1): every page normalised to one uniform trim (SINGLE 2048²,
  SPREAD 4096×2048, cover-crop) before the PDF — kills "dimensions changed".
Verified deterministic helpers against real book data (reconcile, gutter clamp,
trim, locked scale step-down). Stage order: parse → copyedit_scenes → layout →
generate → correct → compose → book.

**pipeline/run_v3.py:** one-command orchestrator for the whole v3 flow (parse →
copyedit → refs → layout → generate → correct → compose → book), resumable via
`--from <stage>`, `--only <pages>` for the page-capable stages, plus
`--docx / --no-copyedit / --no-correct / --no-scene-pass`. Run from a book dir;
lazy-imports stages after setting env so `V3_DIR` (e.g. v3b) binds correctly.
Fills the gap that v3 modules only had per-stage `__main__` entrypoints.

> Append a new `## vX.Y` block at the top whenever we make a change.

---

## v3.2 — Ballast house-style copyedit pass (2026-07-16)
Made the Ballast Books / Blue Balloon **prose style guide** govern every book. The
guide is a Chicago-Manual copyediting standard (numbers, dates, ellipses `. . .`,
em/en dashes, possessives, italics, race & military terms, a canonical word list),
so it applies to the *text*, not the art.
- **data/ballast_style_guide.md**: the docx distilled into a numbered, model-facing
  rule checklist (NUM-*, DATE-*, ELL-*, … WORD-*). Single source of truth.
- **pipeline/style_guide.py**: loads the guide once (path resolved via realpath so
  it works from gen_book.sh's per-book dirs) and exposes `with_guide(system)` to
  append the FULL guide to any prompt — no snippet retrieval, every point every run.
- **pipeline/copyedit_v3.py**: new stage. Auto-corrects the title + every page/
  backmatter `text` in data/storybook.json to house style (model gets the full
  guide as system prompt, temperature 0), and writes an auditable
  `output/copyedit_report.md` (page → before/after → rule id). Preserves line breaks
  (rejects any model output that changes line count, so pagination is safe) and has
  a deterministic mechanical layer (ellipsis spacing, double-space collapse) that
  runs regardless of the model.
- **pb_run**: `copyedit` inserted between `parse` and `style`, so corrected text
  flows into every downstream stage. `--no-copyedit` (or `COPYEDIT=0`) keeps text
  verbatim for authors who require it.
- Note: cover/scene prompts render NO text, so the guide is *not* injected there —
  the copyedit stage is the enforcement point for all reader-facing prose.

## v3.1 — Generic manuscript-driven pipeline + Ella book from scratch (2026-07-12)
Generalised v3 so ANY manuscript .docx runs end-to-end, and fixed the Bilbo text
overlap.
- **parse_v3**: manuscript .docx -> rich art plan (per-book STYLE chosen by an art
  director, designed characters w/ appearance/palette/outfit/consistency,
  look-alike groups, per-page scenes). Addresses "TOON too low content".
- **plan_v3**: shared helpers; all stages now data-driven (no Bilbo hardcoding).
- **compose_v3**: VISION-based text placement (finds the genuinely empty region)
  -> fixes the text/character overlap on Bilbo pages 3/4/8/15; soft bloom, no seam.
  generate_v3 also reserves the text band harder.
- **toon_io**: python-toon's strict decoder trips on deeply-nested data (scene
  chars[], group members[]); store canonical JSON + `.view.toon` sidecar, use TOON
  via for_prompt() where token savings matter. Also: tab delimiter (comma-safe),
  downscale images for vision calls (fewer empty-response failures).
- Reliability: 0 crashes / 0 skipped pages on the Ella run (vs Bilbo run's API hiccups).
**Result:** `books/ella-the-animal-shelter-and-you/v3/output/ella__the_animal_shelter__and_you.pdf`
— 18 pages, brand-new book from ONLY the manuscript. Distinct warm inclusive style
(Christian Robinson / Vashti Harrison influences), consistent Ella + Ms. Rosa +
named dogs, inclusive incidental kids (incl. wheelchair user), clean text, good
cover. Run cost ~$4. See [[img2img-consistency-pivot]], [[toon-data-format]].

## v3.0 — Full TOON rebuild: correct character model, coordinate scenes, complete book (2026-07-11)
Client rejected v5 (every page wrong). Root cause found: **the character model was
wrong** — manuscript + author's real photo + client's V6 interior say Bilbo & Obi
are BOTH golden retrievers, distinguished ONLY by hat colour (Bilbo=green,
Obi=blue) + baseball bandanas. v4/v5 had invented "red B cap / brown beagle Obi".
Rebuilt from scratch per client spec:
- **TOON not JSON** (`toon_io.py`, python-toon) for all data.
- **Fresh refs from the manuscript** (`refs_v3.py`) — stylise the real photo into a
  DUO sheet (green vs blue hat) + individual sheets + Homer + Mom/Dad from photos.
- **Coordinate scenes** (`layout_v3.py`) — per-scene character boxes + text zone.
- **Generate** (`generate_v3.py`) via Gemini from refs + textual coordinates
  (dropped the drawn sketch after it leaked boxes into the art) with hat-colour +
  golden-tone identity locks.
- **Correct** (`correct_v3.py`) — client's flow: match characters → regenerate from
  reference (DUO sheet) if wrong → guarded scene-perfect pass.
- **Compose** (`compose_v3.py`) — text with a soft white bloom, NO card/border seam.
- **Book** (`book_v3.py`) — 15 pages (11 single + 4 spread) → PDF.
Hardened editor/llm retries (no-image + empty-body) + per-page resilient correction.
**Result:** `v3/output/Bilbo_Obi_s_Baseball_Adventure_v3.pdf` — 15 pages, correct &
consistent golden retrievers (green=Bilbo/blue=Obi), consistent Mom/Dad, on-script
scenes, clean text. Big improvement over v4/v5. Some correction calls hit provider
400s and were skipped (base art already good). See [[bilbo-character-model-corrected]],
[[v6-interior-reference]], [[toon-data-format]].

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
