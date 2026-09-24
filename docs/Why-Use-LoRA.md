# Why We Should Use LoRA for Character Consistency

## The problem

Our tool makes illustrated children's books where the **same characters** — the
two dogs, their mom and dad, and the mascot — appear on ~22 pages and **must look
identical every time**: same face, same coat, same cap, same size.

Ordinary AI image tools draw every picture **from scratch**, so the same character
comes out slightly different on every page — the coat colour shifts, the cap
appears or disappears, the size changes, the face drifts. We have tried hard to
fix this with detailed prompts, reference pictures, and automatic corrections. It
helped, but it **cannot be fully solved that way** — it is a built-in limitation
of how these tools work.

## Why the two methods we already tried each fall short

We built and tested both realistic in-house approaches. Each fixes one half of the
problem and breaks the other:

| Approach | Same character every page? | Natural-looking scenes? |
|---|---|---|
| **Draw each page from scratch** | No — the character drifts | Yes — scenes look natural |
| **Reuse the same cut-out character** | Yes — identical | No — looks pasted / stiffly placed |

So we are stuck choosing between *consistent characters* **or** *natural pictures*.
We cannot get both this way.

## What LoRA is (in plain terms)

A **LoRA** is a small "memory add-on" for the image tool. We show it about
10–20 pictures of one character, and it **teaches the tool what that character
looks like** — one small add-on per character (five in total for this book).

After that, whenever we ask for a picture, the tool **already knows** the
character and paints them the same way every time, while still drawing each scene
freshly and naturally.

## Why LoRA gives the best result

It is the only method that delivers **both** at once:

| Approach | Same character | Natural scenes |
|---|---|---|
| Draw from scratch | No | Yes |
| Reuse cut-outs | Yes | No |
| **LoRA** | **Yes** | **Yes** |

The reason is simple: with LoRA the character's identity is **learned by the tool
itself**, not re-described in words (which it interprets loosely) or pasted in as a
fixed picture (which it can't re-pose). So the character is **painted fresh into
every scene** — correct pose, angle, lighting, and interaction — **and** still
comes out looking like the same character. This is the **industry-standard way**
professionals keep a character consistent across many AI images.

## What it costs and what we need

- **A pay-as-you-go account** on a fine-tuning service (**fal.ai** recommended, or
  Replicate) — no monthly fee, no lock-in. This is the one thing we don't have yet;
  our current provider can only *run* models, not *teach* them.
- **One API key** added to our settings.
- **Training pictures** — we already have most of these from work we've done.

| Item | Cost |
|---|---|
| Teach all five characters (one-time) | **~$10 total** (~$2 each) |
| Each finished page | **~$0.03–0.05** |
| Monthly commitment | **None** — pay only for what we use |

A full book re-render costs about **$1–2**, and re-runs after that cost pennies.

## The honest caveats

- It needs that small external service (**~$10**) — that is the only real blocker.
- It is **very** consistent (~95%+), not a guaranteed 100%; a rare page may still
  need a quick redo. But it is by far the most reliable option available.
- We will re-establish the art style once, since LoRA runs on a different (equally
  capable) image engine.

## Recommendation

Approve a small **pay-as-you-go fal.ai (or Replicate) account**. It is the only
proven way to get **consistent characters _and_ natural illustrations** — exactly
what the books require — and the total spend to prove it out is about **$10**.
Almost everything else is already built; we just need the account and key to begin.
