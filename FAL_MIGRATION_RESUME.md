# RESUME DRAFT — fal.ai pipeline migration

**Status:** RESUMED 2026-09-07 — key live, backend verified. `fal_backend.py` exists,
`editor.edit` hybrid routing is in place, `.venv` rebuilt, and t2i + Kontext smoke
tests passed (`fal_smoke.png`, `fal_smoke_kontext.png`). Next: LoRA bootstrap (step 7+).
**Owner:** Ayush · **Paused:** 2026-08-27
**Why paused:** need fal.ai API key from senior first (call pending).

---

## The goal (what we agreed to build)

1. Rename existing `pipeline/` → `previous_pipeline/` (freeze the working OpenRouter flow).
2. Create a fresh `pipeline/` that reuses the good logic files but swaps the
   **image backend** to **fal.ai**, and adds **LoRA training** for character consistency.

Nothing has been executed yet — this doc is the plan to pick up from.

---

## KEY FINDING — where fal.ai plugs in (the one seam)

Every image in the pipeline funnels through **`pipeline/editor.py`** via three functions:

- `editor.blank_square()` — white base so output is 1:1
- `editor.edit(instruction, images)` — the actual generate/edit call (OpenRouter → Gemini image model)
- `editor.to_square()` — safety crop

Callers (all image work routes here):
`refs_v3`, `sprites_v3`, `composite_v3`, `generate_v3`, `correct_v3`, `render_v3`.

**Implication:** we do NOT rewrite every stage. We add a fal backend with the same
interface + new `generate()` / `train_lora()` / `generate_with_lora()`, and route
`editor` to it. Minimal churn.

Package has **no `__init__.py`** (namespace package). Invoked as
`python -m pipeline.run_v3 --book books/<slug>`.

Current API key in `.env`: `OPENROUTER_API_KEY` only. Need to add `FAL_KEY`.

---

## File inventory (reuse vs replace)

**Reuse as-is (backend-agnostic logic):**
`llm.py`, `toon_io.py`, `charspec.py`, `style_guide.py`, `checklist_v3.py`,
`plan_v3.py`, `parse_v3.py`, `copyedit_v3.py`, `layout_v3.py`, `book_v3.py`,
`compose_v3.py`, `eval_v3.py`, `run_v3.py`.

**Replace / augment (image backend):**
`editor.py` (add fal dispatch) + NEW `fal_backend.py` (fal implementation).

**Regenerate against fal:** `refs_v3`, `sprites_v3`, `composite_v3`, `generate_v3`,
`correct_v3`, `render_v3` — only their image calls; logic stays.

---

## Execution steps (resume from here once we have the key)

1. `git mv pipeline previous_pipeline`  → freeze old flow.
2. `cp -r previous_pipeline pipeline`   → new working copy.
3. `pip install fal-client`; add `fal-client` to `requirements.txt`.
4. Add `FAL_KEY=...` to `.env`.
5. NEW `pipeline/fal_backend.py`: `blank_square`, `to_square`, `generate` (t2i),
   `edit` (i2i), `upload_images`, `train_lora`, `generate_with_lora`, `__main__` smoke test.
6. Route `editor.edit` → fal when `IMAGE_BACKEND=fal` (keep OpenRouter default so
   nothing breaks with no key). Decide: hybrid (t2i+LoRA on fal, surgical i2i edits
   stay on Gemini) vs fal-only. **Leaning hybrid.**
7. Add LoRA bootstrap script: charspec → generate character sheet → curate (reuse
   `correct_v3.judge`) → zip → `train_lora` → save LoRA url per character.
8. Wire `generate_with_lora` into `generate_v3` page render.
9. Validate on 3 pages, score with `eval_v3` vs baseline, THEN full book.
10. Learning doc: LoRA-without-photos logic + fal integration.

**Open decision for senior call:** hybrid vs fal-only backend; who owns billing.

---

## Cost recap (per our estimate — VERIFY on fal pricing page)

- Characters are **per-book** (3–4 new chars each book, no reuse across books).
- **~$15–20 per book**, dominated by LoRA training (~$3/char × 3–4).
- Realistic rule: **LoRA-train only 2–3 recurring characters; charspec-prompt the
  rest** → ~$12–15/book.
- fal FLUX ≈ $0.025–0.035 / 1MP image; LoRA train ≈ $2–5/run (CONFIRM).

See `docs/fal-ai-briefing-for-senior.md` for the call talking points.
