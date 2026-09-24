# Pipeline Redesign Proposal — Research Findings + Architecture

Companion to `Pipeline-Failure-Analysis.md` (the R1–R7 requirements). This
document summarizes what the research found, ranks the model options, and
proposes the v-next architecture for discussion. Nothing here is built yet.

---

## 1. What the research established

**Verified (adversarially checked):**

- **AnyStory** (Alibaba, arXiv 2501.09503): the research community's answer to
  two look-alike characters blending is **per-subject spatial routing** — each
  character's reference conditions its own region of the image, instead of one
  averaged reference. No public API (SDXL research code), but it validates our
  duo-sheet intuition and points at region-assigned conditioning as the
  mechanism to want from any commercial model.

**Strong unverified leads (primary sources fetched; verification was
rate-limited, treat as probable):**

- **FLUX Kontext scores the HIGHEST raw identity of any method tested
  (CLIP-I 0.9326) — but with a documented copy-paste effect and reduced
  pose/expression diversity** (FreeStory paper's evaluation). This is exactly
  what we observed: sheet-echo collages, rigid poses, style locked to the
  conditioning image on character pages and lost entirely on pages without one.
  Kontext wasn't a bad choice; it's a sharp trade-off we ran into blind.
- **VQAScore** (arXiv 2404.01291): CLIP-style similarity is a bag-of-words and
  cannot check counts/relations. Asking a VLM binary questions ("Does this
  image show exactly two pup cups?") is state-of-the-art for text-image
  fidelity — and implementable today with our existing judge model.
- **HADM** (arXiv 2411.13842): trained detectors localize extra/missing/
  distorted body parts across generators — template for an artifact QA stage
  (we can approximate with targeted VLM probes before self-hosting anything).
- **Audit-and-repair agents** (arXiv 2506.18900): quantitative identity gate —
  DINO-embedding similarity index with a numeric threshold (loop ends at
  CI ≥ 90) rather than a prose judge. This is the "measured, not judged"
  mechanism R1 asks for.
- **Regional-Prompting-FLUX**: per-region prompts on FLUX (caption band as a
  region with a plain-background prompt) — composes with LoRA/identity
  conditioning, but self-hosted only and adherence is tunable, not guaranteed.

## 2. Managed-API model options, ranked for our use case

| Model | Refs | Fit | Cost | Verdict |
|---|---|---|---|---|
| **Gemini 3 image ("Nano Banana 2", `gemini-3-pro-image`)** | up to 14 mixed / ~5 character refs, role-assignable | 93% cross-scene character consistency (ZDNET 2026 bench); understands identity SEMANTICALLY (same character, new pose/age); native multi-character; strong instruction-following (helps counts/states); best-in-class text handling | ~$0.13/img | **Candidate A — likely primary** |
| **Seedream 4.5 (fal `bytedance/seedream/v4.5/edit`)** | up to 10 reference images | unified t2i+edit; multi-reference character consistency marketed for storybooks; 1:1 native; Seedream 5.0 Lite already out (Feb 2026) | $0.04/img | **Candidate B — cheap challenger** |
| FLUX Kontext (+LoRA) | 1 conditioning image (stitch hack) | highest raw identity BUT copy-paste/pose-rigidity trade-off; single-image conditioning forces our fragile sheet-stitching | ~$0.04–0.07 | Demote to fallback |
| Ideogram Character (fal) | 1 photo | photorealistic humans only — wrong domain | — | Rejected |
| Midjourney --cref | 1 | no API at all | — | Rejected |

**Best practice from every Nano-Banana source:** assign one JOB per reference
image ("image 1 = Bilbo's design, image 2 = Obi's design, image 3 = the art
style to match, image 4 = the setting") — dumping references without roles
causes averaging, which is precisely the look-alike blending failure.

**Implication worth savoring:** both candidates make the LoRA stage optional.
If role-assigned references hold identity on their own, we delete LoRA
training entirely: −$6/book, −20 minutes/book, and one fewer
copy-of-a-copy generation in the identity chain (kills half of failure
Class 1 by construction).

## 3. Proposed architecture (maps to R1–R7)

**Phase 0 — Book Bible (once per book).** Canonical assets, all QA'd with the
sheet judge loop we built this week:
- Character turnarounds (per character AND the duo pair sheet) — R1.
- **One style anchor plate**: a single approved image that IS the book's
  rendering finish (e.g. the client's V6 art, or an approved page-1 render).
  Every subsequent generation carries it as the style-role reference — R2.
- Setting plates (existing).
- Source-of-truth precedence encoded in data: client art > client text >
  accepted sheet > generated spec — R7.

**Phase 1 — Page contracts.** For every page, derived from the PRINTED TEXT
(not just the scene description): cast list with counts ("exactly 2 adults"),
countable props ("exactly 2 pup cups"), stated states ("dogs look sleepy"),
caption side. Stored structured; used twice (prompt + verification) — R4.

**Phase 2 — Generation.** ONE route for every page including cover, title,
dedication, about-author: candidate model with role-assigned references
(duo sheet, style plate, setting plate). Matter pages carry the style plate
too, so photorealism drift dies — R2. The page contract is written into the
prompt ("exactly two pup cups — count them").

**Phase 3 — Measured acceptance gate (replaces the prose-judge lottery).**
A page is accepted only when ALL pass:
1. **Identity**: embedding similarity (DINO/CLIP-I) of each character crop vs
   its turnaround ≥ threshold — numeric, calibrated once per book — R1.
2. **Facts**: VQAScore-style binary probes generated from the page contract
   ("exactly two adults? dogs sleepy?") — R4.
3. **Anatomy**: targeted probes (limb counts, attachment, species anatomy,
   duplicated characters) — the known classes from the QA notes — R5.
4. **Style**: similarity vs the style plate + a photorealism probe — R2.
5. **Caption band**: occupancy check (kept from v6.2) — R3.

**Phase 4 — Diagnostic repair (bounded, per failure type)** — R6:
- Identity fail → targeted edit conditioned on that character's sheet
  (Gemini surgical edit — our existing strength).
- Fact/count fail → targeted edit ("remove the third pup cup").
- Anatomy fail → REGENERATE the page (structure can't be patched).
- Style fail → regenerate with style plate weighted up.
- Band fail → **outpaint the band** (extend/repaint the caption zone as calm
  sky/ground with the edit model) — guaranteed by construction, no lottery.
- Hard cap: 2 repair rounds, then flag for human review with the failure list.

**What survives from today's pipeline unchanged:** parse → plan → layout,
the sheet QA loop, panel-page handling, compose (typesetting/ink/scrim),
book build, DEVLOG discipline, 3-page gates before full-book spend.

## 4. Validation plan (before committing the client's book)

1. **Bake-off** (~$3): the SAME 6 hard pages (duo close-up, duo+humans,
   duo+mascot interaction, matter page, count-heavy page, sleepy page) ×
   {Gemini-3-image, Seedream 4.5, current kontext+LoRA} — scored by the
   measured gate, not eyeballs. Winner becomes the route.
2. **LoRA ablation** (free, part of bake-off): winner with vs without LoRA
   references. If no measurable identity gain, LoRA is deleted from the flow.
3. **Full Bilbo v6_b** on the winning configuration, judged page-by-page
   against the client QA list from v6_a.

## 5. Cost sketch (per 19-page book)

- Gemini route: 19 pages × ~1.5 samples × $0.13 ≈ $3.70 + edits ≈ $1.5
- Seedream route: 19 × 1.5 × $0.04 ≈ $1.15 + edits
- Verification probes: ~5 VLM calls/page ≈ $1–2
- No LoRA training: −$6 vs current
- **Total: $5–8/book** — under half the current spend, with measured gates.

## 6. Open decisions (for the design discussion)

1. Primary model: Gemini-3-image vs Seedream 4.5 — or let the bake-off decide
   (recommended).
2. Delete LoRA training entirely, or keep as an opt-in for characters that
   fail the identity gate repeatedly? (Bake-off ablation decides.)
3. Caption band: accept the outpaint-fallback design, or pursue self-hosted
   Regional-Prompting-FLUX for hard layout control? (Outpaint is simpler and
   API-only; recommend starting there.)
4. Identity metric: DINO vs CLIP-I embedding, and what threshold — needs a
   quick calibration experiment on known-good/known-bad pages from v6_a
   (we have labeled data now, courtesy of the client's QA).
5. Bandana policy (already fixed always-on in v6_b data) — confirm with
   client that story pages should match the cover.
