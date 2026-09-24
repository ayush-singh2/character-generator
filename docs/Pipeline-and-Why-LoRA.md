# Our Pipeline, Where It Fails, and Why Only LoRA Fixes It

## 1. How our current pipeline works

We turn a manuscript into a finished book in a chain of steps. Two of them use AI
image models; the rest are ordinary, reliable text/layout steps.

```
Manuscript (.docx)
   │
   ▼  PARSE      read the story, design each character, plan every page   (text)
   ▼  REFERENCES draw a reference sheet for each character                (AI image)
   ▼  GENERATE   draw each page from the text            << Text-to-Image model >>
   ▼  CORRECT    check each page vs the reference, fix   << Image-to-Image model >>
   ▼  COMPOSE    place the caption text on the art                        (code)
   ▼  BOOK       assemble the PDF                                         (code)
```

The two AI image steps are the only places consistency can go wrong:

- **GENERATE = Text-to-Image.** Draws a whole page from a written description
  ("two dogs at a stadium…"), guided by the reference sheet.
- **CORRECT = Image-to-Image.** Looks at the drawn page, compares each character
  to its reference, and edits the page to fix mistakes.

## 2. Where the Text-to-Image model fails

The generator draws **every page from scratch**. It reads the character
description and the reference sheet as *inspiration*, not as an exact spec — so it
re-invents the character a little each time.

- Coat colour and shade drift between pages.
- The cap or bandana appears, disappears, or changes.
- The character's **size changes** page to page.
- The face and proportions wander.

This is not a quality problem — a fancier model draws *prettier* pages that are
**just as inconsistent**. It is how the tool works: freehand, every time.

## 3. Where the Image-to-Image model fails

The corrector's job is to *rescue* the drift after the fact. It helps, but it
cannot reach perfection, for four reasons:

- **It only has a flat reference sheet**, not "this exact character in this pose."
  So it can match colours and items, but not lock a face or a body it was never
  given for that angle.
- **Editing can't re-impose an identity the model doesn't hold.** To fix a wrong
  face it must partly redraw it — freehand again — so it drifts while fixing.
- **It misses subtle problems.** A slightly wrong ear, a small size change, a soft
  face — the checker often passes these, so they never get fixed.
- **Fixing one thing can break another.** Correcting a colour can nudge a pose;
  correcting a pose can soften a face. The result oscillates instead of settling.

In short: the corrector is a **patch on a leak**, not a fix for the pipe.

## 4. "Can we just add another Image-to-Image pass on top?"

It feels like stacking more correction passes should keep improving the page. It
does not — and here is the honest reason:

- **Every pass is also freehand.** Each edit is another random draw, so it can
  undo the last fix as easily as improve it. We watched it flip a detail back and
  forth between passes.
- **You can't edit your way to a character the model never learned.** No number of
  "make it match the sheet" edits gives the model true knowledge of the face; it is
  always guessing from a flat picture.
- **Each pass costs time and money** and adds new risk (a good page can get worse).

So more image-to-image = **more patches on the same leak**. It plateaus around
"pretty good," never "perfect," and sometimes goes backwards.

## 5. Why only LoRA actually solves it

Everything above is a *cure-after-the-fact*. LoRA fixes the **cause**.

A **LoRA** teaches the image model the character itself — we show it ~10–20
pictures of each character, and it **learns their identity into its own memory**.
After that:

- **The Text-to-Image step draws the character correctly the _first_ time** —
  same face, coat, cap and size on every page — because the model now *knows* them,
  not just reads about them.
- **We barely need the corrector at all**, because there is little drift to fix.
- **Scenes still look natural** — the model paints the learned character freshly
  into each new pose, angle and setting.

| | Text-to-Image | + Image-to-Image | + more I2I passes | **LoRA** |
|---|---|---|---|---|
| Same character every page | No | Closer, not exact | Plateaus | **Yes** |
| Natural, varied scenes | Yes | Yes | Yes | **Yes** |
| Fixes cause or symptom? | — | symptom | symptom | **cause** |
| Converges to "perfect"? | No | No | No | **Yes (≈95%+)** |

**The difference in one line:** text-to-image and image-to-image *describe* or
*patch* the character; **LoRA makes the model _know_ the character** — so it is
right from the start instead of corrected afterwards. That is why it is the
industry-standard way to keep a character identical across many AI images, and the
only method that gives us **consistent characters _and_ natural pictures** at once.

## What it takes

A small pay-as-you-go **fal.ai** (or Replicate) account and one API key —
about **$10 one-time** to teach all five characters, then pennies per page.
Nearly everything else in our pipeline stays exactly as it is.
