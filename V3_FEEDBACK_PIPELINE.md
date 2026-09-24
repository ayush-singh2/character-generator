# V3 Client-Feedback → End-to-End Pipeline

Source feedback: `Client_REVIEW/Client_Reviews(15)_categorized.xlsx` (Bilbo & Obi's
Baseball Adventure, 14 flagged pages) and `Client_REVIEW/Ella_Client_Reviews_categorized.xlsx`
(Ella the Animal Shelter and You, 18 flagged pages).

Every complaint is distilled into a rule code. The image-facing rules live in one
place — `pipeline/checklist_v3.py` — and are injected into **both** model-call
sites (text-to-image and image-to-image) plus the vision judge. Structural / text
rules are enforced by the surrounding non-image stages.

---

## 1. Root-cause buckets

The 32 flagged pages collapse into six failure modes:

| Bucket | What the client saw | Where it's born |
|---|---|---|
| **A. Structure** | missing title/dedication/About-the-Author/fostering pages; extra pages not in manuscript; page dimensions change mid-book | `parse_v3` emits no canonical page list or trim; `book_v3` concatenates whatever art exists at its native size |
| **B. Text fidelity** | invented captions; wrong wording; repeated "Tuesday"; ellipsis where an em-dash was wanted; missing sentences | text is paraphrased, not locked verbatim; copyedit rules not applied everywhere |
| **C. Typography** | text size jumps page-to-page; text crosses / lands in the gutter; arbitrary text colour; illegible text | `compose_v3` auto-fits font per page, places the box anywhere, picks ink per page |
| **D. Consistency** | bandanas redrawn; style drift; human face = Robert Downey Jr.; Ella's shirt/hair/bracelets/face change; Ella gets the shelter-woman's body; "Dad works in the coffee shop" | refs not locked hard enough; judge criteria too narrow; celebrity leakage; style token not pinned |
| **E. Scene logic** | wrong location (field/park instead of stadium; daycare+dogpark instead of shelter); invented props (hotdog stand, safety vest, steam, parade); impossible spatial logic; missing props (leash) | scene descriptions under-constrained; illustration notes not treated as an authoritative shot list |
| **F. Image integrity** | warped characters; scene duplicated side-by-side; art doesn't fill the page; cut off by gutter | full-bleed / anti-duplication / anatomy not enforced; spread handling weak |

---

## 2. The pipeline (stage → what it now guarantees)

```
manuscript.docx
   │
   ▼  parse_v3      A,E  canonical PAGE LIST (front matter + body + back matter),
   │                     verbatim text per page, one trim size, illustration-notes
   │                     shot list per page, setting locked per scene
   ▼  copyedit_v3   B    Ballast house style incl. em-dash/ellipsis, weekday-dedupe,
   │                     verbatim guard (no paraphrase, no invented sentences)
   ▼  charspec /    D    exact locked JSON spec per recurring character (already exists)
   │  refs_v3            + look-alike GROUP sheet + real-photo likeness (no celebrity)
   ▼  layout_v3     C,F  per-page coordinate layout; on spreads, subjects + text zone
   │                     forced off the centre gutter
   ▼  generate_v3   D,E,F  TEXT-TO-IMAGE  ── injects checklist_v3.t2i_block ──┐
   │                                                                          │ same
   ▼  correct_v3    D,E,F  IMAGE-TO-IMAGE ── injects checklist_v3.i2i_block ──┤ rule
   │                       vision JUDGE  ── injects checklist_v3.judge_block ─┘ set
   ▼  compose_v3    C    locked type scale + gutter-safe text box + locked ink colour
   ▼  book_v3       A    assemble in manuscript order at ONE uniform trim size
   ▼  book.pdf
```

`checklist_v3.py` is the single source of truth: editing one rule there changes
what the generator asks for, what the corrector repairs, and what the judge fails
a page for — the three can never drift apart.

---

## 3. The checklist (rule codes)

Image rules — injected into t2i + i2i + judge (`checklist_v3.IMAGE_RULES`):

| Code | Rule |
|---|---|
| STY-1 | One book style — no per-page style/linework/palette drift |
| CHR-1 | Match the reference sheet exactly: face, hair, skin, build |
| CHR-2 | Keep every signature item (bandana pattern+colour, collar, shirt logo, hair tie, bracelets) |
| CHR-3 | Photo characters match the real reference photo — never a celebrity / generic face |
| CHR-4 | Keep co-present look-alikes clearly distinct |
| CHR-5 | No body/role swap — a character keeps their own body, job and place |
| SCN-1 | Stay in the scene's stated location — no drift, no indoor/outdoor mix |
| SCN-2 | Draw only what the scene calls for — invent no extra props |
| SCN-3 | Positions must be physically logical for the action |
| SCN-4 | Include every prop the scene names (e.g. dog leash) |
| IMG-1 | Full-bleed — fills the trim, nothing cut off |
| IMG-2 | Draw the scene once — never mirror/duplicate the subject |
| IMG-3 | Clean anatomy — no warped/melted/extra limbs or faces |
| GUT-1 | Spreads: keep characters/faces/key objects clear of the centre gutter |
| TXT-1 | Zero written text in the art |

Structural / text rules — enforced outside the image models (`checklist_v3.STRUCTURAL`):

| Code | Rule | Owner |
|---|---|---|
| MAN-1 | Page text is verbatim from the manuscript | copyedit_v3 / parse_v3 |
| MAN-2 | No page invented; no manuscript page dropped | parse_v3 / book_v3 |
| FM-1 | Title page present; dedication on its own page | parse_v3 |
| BM-1 | Required back matter present (About the Author, fostering page, …) | parse_v3 |
| DIM-1 | Every page shares one uniform trim size | book_v3 |
| TYP-1 | One locked type scale — same body size every page | compose_v3 |
| TYP-2 | Text box never crosses / lands in the gutter | compose_v3 |
| TYP-3 | One locked text colour/treatment | compose_v3 |
| CPY-1 | House-style copyedit (em-dash vs ellipsis, no repeated weekday) | copyedit_v3 |
| TTL-1 | Title-page uses the central display font | compose_v3 / cover |

---

## 4. Per-page traceability

### Bilbo & Obi's Baseball Adventure
| Pg | Client review (condensed) | Rules |
|---|---|---|
| 1 | Missing title page + dedication | FM-1 |
| 2 | Style + bandanas changed | STY-1, CHR-2 |
| 3 | Dogs should be in stadium; player catches on field | SCN-1, SCN-3 |
| 4 | Wrong specs; hotdog stand in outfield; dogs on field; text tiny | CHR-1, SCN-1, SCN-2, TYP-1 |
| 5 | Face = Robert Downey Jr. not the photo; chars outside not in stadium | CHR-3, SCN-1 |
| 6 | Should read "a friend named Homer. He was the team mascot!" | MAN-1 |
| 7 | Human face illustrated differently | CHR-1 |
| 8 | Location both inside and outside; should stay in stadium | SCN-1 |
| 9 | Verbatim text fix; dog style + both bandanas changed | MAN-1, STY-1, CHR-2 |
| 10 | Text bigger; art doesn't fill page; park not stadium | TYP-1, IMG-1, SCN-1 |
| 11 | Text size changed + runs across gutter; bandana changed again | TYP-1, TYP-2, CHR-2 |
| 12 | Pitcher throwing at dogs, no catcher (illogical); bandanas differ | SCN-3, CHR-2 |
| 13 | Should read "got to play fetch"; style changed | MAN-1, STY-1 |
| 14 | Location changed; text tiny again; missing About-the-Author page | SCN-1, TYP-1, BM-1 |

### Ella the Animal Shelter and You
| Pg | Client review (condensed) | Rules |
|---|---|---|
| 1 | Title font should be central display; doesn't match ref photo | TTL-1, CHR-3 |
| 2 | Text not in manuscript / not the title; dedication needs own page | MAN-2, FM-1 |
| 3 | Text crosses spread → gutter; character warped; text illegible | TYP-2, IMG-3, TYP-1 |
| 4 | Different page dimensions | DIM-1 |
| 5 | Shirt/bracelets/hair-tie differ; text larger + into gutter | CHR-2, TYP-1, TYP-2 |
| 6 | Text large + different colour; shirt differs, safety vest appears; parade not in notes | TYP-1, TYP-3, CHR-2, SCN-2 |
| 7 | Text into gutter; different dims; different hairstyle; art cut off by gutter | TYP-2, DIM-1, CHR-1, GUT-1 |
| 8 | "Tuesday" twice; shirt changes; face differs; text should split across two pages; em-dash "even and especially YOU!" not ellipsis | CPY-1, CHR-2, CHR-1, MAN-1, CPY-1 |
| 9 | N/A (no issue) | — |
| 10 | Different page dimensions | DIM-1 |
| 11 | Dad now works in coffee shop; middle art into gutter; art duplicated side-by-side (one warped); unclear held object; leash missing; verbatim fix "explore dog-friendly businesses together." | CHR-5, GUT-1, IMG-2, IMG-3, SCN-4, MAN-1 |
| 12 | Sectioning hard to follow; illustrations land in gutter | TYP-2, GUT-1 |
| 13 | Dims changed; steam from nowhere; Ella has the shelter-woman's body; text into gutter | DIM-1, SCN-2, CHR-5, TYP-2 |
| 14 | Room blends daycare + dog park not a shelter; style entirely different | SCN-1, STY-1 |
| 15 | Nonsensical invented text; verbatim fix "She connects families with just the right dog so they find their forever home."; Ella an entirely different character | MAN-2, MAN-1, CHR-1 |
| 16 | Dims changed; art cut off in gutter | DIM-1, GUT-1 |
| 17 | Dims changed; missing two sentences ("YOU can volunteer. YOU can make a difference. Together, WE can make a change!"); middle art into gutter | DIM-1, MAN-1, GUT-1 |
| 18 | Page not in manuscript; should carry the fostering-kittens text | MAN-2, BM-1 |

Coverage: every non-"N/A" line maps to at least one rule; every rule traces back to
≥1 client line.

---

## 5. Status

**Done (this change) — the specific ask, "pass the checklist to both model calls":**
- `pipeline/checklist_v3.py` — the shared constraint source.
- `generate_v3.py` (text-to-image) injects `t2i_block(setting)` into the render prompt.
- `correct_v3.py` (image-to-image) injects `i2i_block(setting)` into the fix prompt.
- `correct_v3.py` vision judge injects `judge_block()` so it now fails a page for
  style drift, invented props, wrong location, duplication/warping, gutter
  intrusion and stray text — not only per-character identity drift.

**Done (structural stages):**
- `parse_v3` (MAN-1, MAN-2, FM-1, BM-1): the prompt now demands verbatim page
  text, forbids inventing/dropping pages, and emits front/back matter as roled
  pages (title / dedication-on-its-own-page / about_author / backmatter). A new
  `reconcile()` flags any body-page text not found verbatim in the manuscript.
- `copyedit_v3` (CPY-1): new `copyedit_scenes(data_dir)` runs the Ballast
  house-style pass over the v3 `scenes.toon` (the old `copyedit()` only touched
  `storybook.json`), verbatim-preserving, with an audit report.
- `compose_v3` (TYP-1/2/3): `_lock_scale()` computes ONE type scale (fraction of
  page height) that fits every page and uses it book-wide; `_gutter_safe()` keeps
  spread text off the centre gutter; ink colour is locked to one value.
- `book_v3` (DIM-1): every page is normalised to one uniform trim
  (`SINGLE_TRIM` 2048², `SPREAD_TRIM` 4096×2048, cover-crop) before the PDF.

**Orchestrator:** `pipeline/run_v3.py` runs the whole pipeline in order —
`parse → copyedit → refs → layout → generate → correct → compose → book` —
resumable by stage. `copyedit` runs right after `parse` so corrected text reaches
both the art (compose) and downstream stages. Use the venv; run from the repo root
and point at the book with `--book`:

    .venv/bin/python -m pipeline.run_v3 --book books/ella-the-animal-shelter-and-you
    .venv/bin/python -m pipeline.run_v3 --book books/... --from generate --only 4,11

Flags: `--book`, `--docx`, `--only <pages>`, `--from <stage>`, `--no-copyedit`,
`--no-correct`, `--no-scene-pass`. (`V3_DIR=v3b` for a side-by-side version.)
