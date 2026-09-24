# fal.ai — briefing for the senior call

Purpose: get approval + an **API key** for fal.ai, and explain why we're adding it.
Everything below is plain-language so you can talk it through and answer questions.

---

## 1. The one-line ask

> "I need a fal.ai account API key (and billing enabled). fal.ai is a hosted-GPU
> service that lets us **fine-tune (LoRA) a model per character** so the same
> character looks identical on every page — which is the client's #1 complaint.
> OpenRouter, what we use now, cannot train models; fal.ai can."

---

## 2. What is fal.ai (vs OpenRouter)

Both are ways to run AI image models through an API. The difference is **what each
one can do**:

| | **OpenRouter (current)** | **fal.ai (proposed)** |
|---|---|---|
| What it is | A router to many hosted models (chat + image) | A hosted-GPU platform specialized in image/video models |
| Image generation | Yes (we use a Gemini image model) | Yes (FLUX family) |
| **Model fine-tuning / LoRA training** | **No** | **Yes** — this is the reason we want it |
| How we'd use it | Text + surgical image edits | Train character models + generate pages with them |

**Plain analogy:** OpenRouter is renting a finished camera and taking photos.
fal.ai additionally lets us **teach the camera what our character looks like first**,
so every later photo is automatically on-model.

---

## 3. The problem this solves (why it matters commercially)

- The client's #1 rejection reason is **character drift**: the same girl/dog changes
  hair, outfit, or face page-to-page.
- Today we fight this with prompts + after-the-fact "correction" passes — a patch,
  not a fix. It's expensive (multiple retries per page) and never fully reliable.
- **A fine-tuned model (LoRA) bakes the character's identity into the model weights.**
  Once trained, the character comes out consistent on the *first* try. That's a
  structural fix, not a band-aid — and it reduces retry cost too.

---

## 4. How training works on fal.ai (the mechanics)

fal exposes a **training endpoint**. We hand it a small set of images of one
character, it runs on their GPU for a few minutes, and hands back a small model file
(a "LoRA") we then attach to every generation.

Steps:
1. Collect **12–20 images of ONE character** (same character, varied poses/angles).
2. Zip them (optionally with short text captions + a unique "trigger word", e.g.
   `ella_char`).
3. Call fal's `flux-lora-fast-training` with that zip → wait a few minutes.
4. Get back a **LoRA file (URL)**. Attach it to every page render → identity holds.

One LoRA per character. Takes minutes. Costs a few dollars per character.

---

## 5. "But we don't HAVE photos of the characters" — how we train anyway

This is the key thing the senior will ask. **These are invented characters — there
is no real photo.** The technique is **synthetic bootstrapping**:

1. We already have an **exact written spec** per character (hair colour as a hex
   code, outfit, etc. — our `charspec` system).
2. We use the base model to **generate 20–30 images** of that character from that
   spec, in different poses/angles.
3. We **hand-pick the 12–20 that truly match** (we already have an automatic image
   judge that can filter these).
4. We train the LoRA on **those curated generated images** — no real photo needed.

So: spec → generate a "character sheet" → curate → train. The model learns the
character from our own consistent renders.

---

## 6. How we share the training images with fal

We don't email files around. It's all through the API/account:

- The images live **in our repo/run folder** on our machine.
- Our script **uploads the zip to fal** (fal provides an upload helper that returns
  a URL), then passes that URL to the training call.
- Nothing is manual and nothing is public — it goes over our authenticated API key.
- (If the senior prefers, fal also has a web dashboard where images can be uploaded
  by hand — but our flow is script-driven.)

**What this means for access:** we just need the **API key**. No file-sharing setup,
no separate storage account.

---

## 7. Cost (be ready for the money question)

- Characters are **per-book** — each book has 3–4 new characters, not reused.
- Estimate: **~$15–20 per book**, mostly LoRA training (~$3/character).
- We can cut this: **only train the 2–3 recurring characters**; minor characters use
  prompt-only. → **~$12–15/book.**
- Per-image generation is cents ($0.025–0.035). Training is the main cost.
- ⚠️ These are estimates — I'll confirm exact numbers on fal's pricing page once we
  have access.

---

## 8. What I need out of this call (checklist)

- [ ] Approval to use fal.ai.
- [ ] **An API key** (`FAL_KEY`) — team/org account preferred over personal.
- [ ] **Billing enabled** on that account (pay-per-use, card on file).
- [ ] Agreement on scope: **hybrid** (fal for generation + training, keep current
      Gemini edits for touch-ups) vs **fal-only**. My recommendation: hybrid to start.
- [ ] A monthly spend ceiling they're comfortable with (so I can set expectations).

---

## 9. Questions the senior may ask — quick answers

- **"Is our data safe?"** Images go over our authenticated key to fal's GPUs for
  training; we control what's uploaded. No public sharing. (Confirm fal's data-
  retention terms if they want specifics.)
- **"Do we lose what we built on OpenRouter?"** No — we freeze it as
  `previous_pipeline/` and can switch back with an env flag. fal is additive.
- **"Why not just prompt better?"** Prompting can't guarantee identity; we've hit
  its ceiling (that's the current complaint). Fine-tuning is the industry-standard
  fix for character consistency.
- **"How long to see results?"** Training a character is minutes; I can validate on
  3 pages the same day the key is live.
