# Request: GPU Fine-Tuning Access for Character Consistency
 To make our picture-book characters look identical on every page, we need to fine-tune the image model per character. That needs a small pay-as-you-go GPU training service (~$10 one-time + a few cents per image). Recommended: **fal.ai** or **Replicate** — or our own cloud/GPU if we have one.

---

## The ask
Approval for a **pay-as-you-go account on a GPU/AI fine-tuning service** (no monthly subscription, no lock-in). First choice **fal.ai**; **Replicate.com** is an equivalent alternative. Estimated cost below.

## The problem we're solving
Our tool generates illustrated children's books in which the **same characters** (two dogs, their owners, and a mascot) must appear on **~22 pages and look identical every time** — same coat colour, same cap, same size.

Every off-the-shelf image model draws each picture **from scratch**, so the same character comes out looking different on every page (wrong colour, cap appearing/disappearing, changing size/breed). We have spent considerable effort trying to solve this with detailed prompts and reference images. It has improved, but it **cannot be fully solved that way** — it is a structural limitation of how these models work.

## Why a "better model" does not fix this
This is the key point:

> **It is not a model-quality problem — it is a model-*capability* problem.**

- **Every** text-to-image model — DALL·E, Midjourney, Google Imagen, Flux, Stable Diffusion — shares the same limitation: each image is drawn freehand, so none of them can hold an exact character across many images on their own. A more advanced model produces **prettier** pages but is **just as inconsistent**.
- The proven, industry-standard fix is to **fine-tune the model on each character** (a lightweight add-on known as a "LoRA"). This teaches the model exactly what each character looks like, so it renders them the same on every page — while still painting them naturally into any scene or pose.
- **Fine-tuning requires GPU training infrastructure.** Our current provider (OpenRouter) only *runs* models; it cannot *train* them. That single missing capability is the entire reason for this request.

## What the money buys
| Item | Cost |
|---|---|
| One-time training of all 5 characters | **~$10 total** (~$2 each) |
| Ongoing image generation | **~$0.03–0.05 per page image** |
| Monthly commitment | **None** — pay only for usage |

Training each character takes ~3–5 minutes. This is a one-time setup per book; re-runs cost only pennies.

## Options (any one of these works)
1. **fal.ai** *(recommended)* — fastest and cheapest for this specific task; pay-as-you-go.
2. **Replicate.com** — equivalent capability and price; direct substitute.
3. **Our existing cloud**, if we have one — AWS SageMaker, Google Vertex AI, or Azure ML can all fine-tune image models (preferable if there's already a cloud contract/credits).
4. **A company GPU / workstation** — if we have a machine with a capable NVIDIA GPU, we can train locally at no per-use cost.

## Recommendation
Approve a **pay-as-you-go fal.ai (or Replicate) account**, or point me to our existing cloud/GPU if the company already has one. The total spend to prove this out is **~$10**, and it is the only reliable way to deliver the character consistency the books require.

---


