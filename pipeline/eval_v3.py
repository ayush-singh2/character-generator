"""External evaluation harness (12-week plan, Week 1).

An INDEPENDENT, skeptical scorecard for a finished book. It scores every page
against the character reference sheets on the five defect dimensions the client
audit uses (D1-D5), as an *external* pass that is deliberately SEPARATE from
the v7 gate — so it can disagree with the generator instead of trusting
the pipeline's own "100%" self-report.

Dimensions (match the Week-0 audit table):
  D1 consistency     — characters match their reference sheets (no drift/dupes/hat-loss)
  D2 negative_space  — a genuinely calm, low-detail zone for the text
  D3 legibility      — crisp, correctly-spelled, high-contrast captions
  D4 structure       — no leaked placeholder/instruction text; clean front/back matter
  D5 bubbles         — speech/thought bubbles where dialogue needs them

Inputs are generic (references + page images), so it scores ANY book/manuscript
with zero changes. Page images come from the composed PNGs if present, otherwise
a rasterized PDF. Emits eval_report.md + eval_scores.json + eval_human_review.csv.

Run:
  python -m pipeline.eval_v3 --book books/<slug>
  python -m pipeline.eval_v3 --book books/<slug> --pdf books/<slug>/v3/output/x.pdf
"""

import csv
import io
import json
import os

from . import plan_v3, toon_io
from .llm import chat_json_images

DATA = plan_v3.DATA
REFS = plan_v3.REFS
PAGES = plan_v3.PAGES
OUT = plan_v3.OUT

# Optional model override so the eval judge can be a DIFFERENT model from the one
# the generator/gate uses — reinforcing independence. Defaults to the
# configured vision model when unset.
EVAL_MODEL = os.getenv("EVAL_MODEL") or None

# (json key, human label, Week-12 target %). Order is the report column order.
DIMENSIONS = [
    ("consistency",    "D1 Character consistency",       98),
    ("negative_space", "D2 Negative space",              97),
    ("legibility",     "D3 Text legibility",             98),
    ("structure",      "D4 Structure / no leaks",       100),
    ("bubbles",        "D5 Speech/thought bubbles",      95),
]

JUDGE_SYSTEM = """You are an EXTERNAL, skeptical art director doing a print QA audit
of one finished children's picture-book page. You are INDEPENDENT of the tool that
made it: do not give it the benefit of the doubt, and score only what you actually
see. A generous score you cannot defend is worse than a harsh one.

You are given the PAGE image FIRST, then zero or more CHARACTER REFERENCE SHEETS —
the agreed, correct look of each named character on this page. Score the page from
0 to 100 on each dimension:

- consistency: do the characters on the page match their reference sheets EXACTLY —
  species/build, hair shape+colour+length, skin tone, the exact outfit garments and
  colours, and signature accessories (hats, collars, bracelets)? Penalise hard for
  scale/appearance/wardrobe drift, a duplicated protagonist, a missing hat/accessory,
  or two look-alike characters drawn the same. If NO named character is present,
  score 100.
- negative_space: is there a genuinely calm, low-detail region where the caption
  sits, or does the text fight busy artwork? Judge the ACTUAL text area.
- legibility: is every word crisp, correctly spelled, sensibly wrapped, and high
  contrast against whatever is behind it? Penalise garbled or broken words, letters
  fused together, and low-contrast text.
- structure: is this a clean, intentional finished page with NO leaked placeholder
  or instruction text, prompt fragments, stray labels, or duplicated/garbage copy?
  Front/back matter must look deliberate. 100 = clean; drop steeply if any
  non-story or instruction-like text appears in the art.
- bubbles: if the scene has spoken/thought dialogue that belongs in a speech or
  thought bubble, are proper bubbles present and well formed? If the scene needs no
  bubble at all, set bubbles_applicable=false and score 100.

Return STRICT JSON and nothing else:
{"consistency":<int>,"negative_space":<int>,"legibility":<int>,"structure":<int>,
 "bubbles":<int>,"bubbles_applicable":<true|false>,
 "issues":["one short concrete defect", "..."]}"""


# --------------------------------------------------------------------------- #
# Page-image resolution: composed PNGs if present, else rasterize the PDF.
# --------------------------------------------------------------------------- #
def _page_png_bytes(pages_dir, page_id):
    p = os.path.join(pages_dir, f"page_{plan_v3.slug(page_id)}.png")
    if os.path.exists(p):
        with open(p, "rb") as f:
            return f.read()
    return None


def _rasterize_pdf(pdf_path, dpi=150):
    """Return a list of PNG bytes, one per PDF page (in order)."""
    import pymupdf  # lazy: only needed for PDF-only books
    doc = pymupdf.open(pdf_path)
    out = []
    zoom = dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        out.append(pix.tobytes("png"))
    doc.close()
    return out


def _resolve_pages(scenes, pdf_path, pages_dir):
    """Yield (page_id, role, chars, text, image_bytes) for every printable page.

    Prefers composed PNGs (named by page id). Falls back to rasterizing the PDF
    and mapping page N to the N-th scene in order."""
    have_png = any(_page_png_bytes(pages_dir, s.get("page")) is not None for s in scenes)
    if have_png:
        for s in scenes:
            img = _page_png_bytes(pages_dir, s.get("page"))
            if img is not None:
                yield (s.get("page"), s.get("role", "body"),
                       s.get("chars", []) or [], s.get("text", ""), img)
        return
    if not pdf_path or not os.path.exists(pdf_path):
        return
    rasters = _rasterize_pdf(pdf_path)
    for i, img in enumerate(rasters):
        s = scenes[i] if i < len(scenes) else {}
        yield (s.get("page", str(i + 1)), s.get("role", "body"),
               s.get("chars", []) or [], s.get("text", ""), img)


# --------------------------------------------------------------------------- #
# Reference-sheet selection for a page (present characters + any group sheet).
# --------------------------------------------------------------------------- #
def _refs_for(chars, refman, book_dir):
    """Reference-sheet bytes for the characters present on a page. Ref paths in
    refs.toon are stored relative to the book dir, so resolve them against it."""
    def resolve(p):
        return p if os.path.isabs(p) else os.path.join(book_dir, p)
    by_name = {r["name"]: r["path"] for r in refman.get("refs", [])}
    paths, seen = [], set()
    # group sheets first when all their members are present (disambiguates look-alikes)
    for g in refman.get("groups", []):
        members = g.get("members", [])
        rp = resolve(g.get("path", ""))
        if members and all(m in chars for m in members) and os.path.exists(rp) and rp not in seen:
            paths.append(rp); seen.add(rp)
    for name in chars:
        p = by_name.get(name)
        if p:
            rp = resolve(p)
            if os.path.exists(rp) and rp not in seen:
                paths.append(rp); seen.add(rp)
    # llm cap is 6 images total; page is one, so at most 5 references
    imgs = []
    for p in paths[:5]:
        with open(p, "rb") as f:
            imgs.append(f.read())
    return imgs


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def _score_page(page_id, role, chars, text, page_bytes, refman, book_dir):
    ref_imgs = _refs_for(chars, refman, book_dir)
    user = (
        f"PAGE role: {role}. Named characters expected on this page: "
        f"{', '.join(chars) if chars else 'none'}. "
        + (f"The intended caption text is: \"{text[:400]}\". "
           if text else "This page has no caption text. ")
        + f"The first image is the page; the following {len(ref_imgs)} image(s) are "
          "the character reference sheet(s). Audit and score it."
    )
    # Downscale to small JPEGs like the v7 gate's probes do — a page plus refs as
    # full-size PNGs overflows the provider's request limit (observed 400s).
    from .gate_v7 import _small
    try:
        res = chat_json_images(JUDGE_SYSTEM, user,
                               [_small(b) for b in [page_bytes] + ref_imgs],
                               mime="image/jpeg", model=EVAL_MODEL, max_tokens=900)
    except Exception as e:  # noqa: BLE001 — a failed page is recorded, not fatal
        return {"page": page_id, "role": role, "error": str(e)[:200],
                "scores": {}, "issues": [f"eval error: {str(e)[:120]}"]}
    scores = {}
    for k, _lbl, _t in DIMENSIONS:
        try:
            scores[k] = max(0, min(100, int(round(float(res.get(k, 0))))))
        except (TypeError, ValueError):
            scores[k] = 0
    return {
        "page": page_id, "role": role, "chars": chars,
        "scores": scores,
        "bubbles_applicable": bool(res.get("bubbles_applicable", False)),
        "issues": [str(x)[:200] for x in (res.get("issues") or [])][:6],
    }


def _aggregate(pages):
    """Per-dimension mean over the pages where that dimension is meaningful.
    consistency: pages with a named character; bubbles: only where applicable;
    the rest: every scored page."""
    agg = {}
    for k, _lbl, _t in DIMENSIONS:
        vals = []
        for p in pages:
            if not p.get("scores"):
                continue
            if k == "consistency" and not p.get("chars"):
                continue
            if k == "bubbles" and not p.get("bubbles_applicable"):
                continue
            vals.append(p["scores"][k])
        agg[k] = round(sum(vals) / len(vals), 1) if vals else None
    return agg


# --------------------------------------------------------------------------- #
# Report emitters
# --------------------------------------------------------------------------- #
def _write_report(md_path, title, agg, pages):
    L = ["# Eval report — external QA scorecard", "",
         f"**Book:** {title}", f"**Pages scored:** {sum(1 for p in pages if p.get('scores'))}",
         "", "_Independent vision-judge pass — separate from the pipeline's own "
         "correction judge, so it can disagree with the generator._", "",
         "## Summary (vs Week-12 targets)", "",
         "| Dimension | Score | Target | Gap |", "|---|---|---|---|"]
    for k, lbl, target in DIMENSIONS:
        s = agg.get(k)
        if s is None:
            L.append(f"| {lbl} | n/a | {target}% | — |")
        else:
            gap = round(s - target, 1)
            L.append(f"| {lbl} | **{s}%** | {target}% | {'+' if gap >= 0 else ''}{gap} |")
    L += ["", "## Per-page detail", "",
          "| Page | Role | " + " | ".join(k.upper() for k, _l, _t in DIMENSIONS) + " | Issues |",
          "|---|---|" + "---|" * len(DIMENSIONS) + "---|"]
    for p in pages:
        sc = p.get("scores", {})
        cells = "".join(f" {sc.get(k, '—')} |" for k, _l, _t in DIMENSIONS)
        issues = "; ".join(p.get("issues", []))[:180] or ("ERROR" if p.get("error") else "")
        L.append(f"| {p['page']} | {p.get('role','')} |{cells} {issues} |")
    with open(md_path, "w") as f:
        f.write("\n".join(L) + "\n")


def _write_human_sheet(csv_path, title, pages):
    """A blank sheet for the dimensions models judge poorly (legibility taste,
    overall taste) — filled in by a human reviewer per page."""
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["book", "page", "role", "legibility_human(PASS/PARTIAL/FAIL)",
                    "taste_human(PASS/PARTIAL/FAIL)", "note"])
        for p in pages:
            w.writerow([title, p["page"], p.get("role", ""), "", "", ""])


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def evaluate(data_dir=DATA, pdf=None, only=None, out_dir=None):
    """Score a finished book and write eval_report.md + eval_scores.json +
    eval_human_review.csv. Returns the scores dict.

    `data_dir` may be relative (run from inside the book dir) or absolute (called
    from the server); all other paths are derived from it, so no chdir is needed."""
    v3dir = os.path.dirname(os.path.abspath(data_dir))     # <book>/v3
    book_dir = os.path.dirname(v3dir)                       # <book>
    pages_dir = os.path.join(v3dir, "output", "pages")
    out_dir = out_dir or os.path.join(v3dir, "output")
    os.makedirs(out_dir, exist_ok=True)

    scenes = toon_io.load(f"{data_dir}/scenes.toon")
    title = scenes.get("title", "") or "(untitled)"
    all_scenes = scenes.get("scenes", [])
    refs_path = f"{data_dir}/refs.toon"
    refman = toon_io.load(refs_path) if os.path.exists(refs_path) else {"refs": [], "groups": []}

    only = set(only) if only else None
    pages = []
    for page_id, role, chars, text, img in _resolve_pages(all_scenes, pdf, pages_dir):
        if only is not None and str(page_id) not in only:
            continue
        print(f"  scoring page {page_id} ({role})…")
        pages.append(_score_page(page_id, role, chars, text, img, refman, book_dir))

    agg = _aggregate(pages)
    result = {"book": title, "dimensions": agg,
              "pages_scored": sum(1 for p in pages if p.get("scores")),
              "pages": pages, "targets": {k: t for k, _l, t in DIMENSIONS}}

    md = os.path.join(out_dir, "eval_report.md")
    js = os.path.join(out_dir, "eval_scores.json")
    hs = os.path.join(out_dir, "eval_human_review.csv")
    _write_report(md, title, agg, pages)
    _write_human_sheet(hs, title, pages)
    with open(js, "w") as f:
        json.dump(result, f, indent=2)
    print(f"  -> {md}")
    print(f"  -> {js}")
    print(f"  -> {hs}")
    print("  summary: " + ", ".join(
        f"{k}={agg[k]}%" for k, _l, _t in DIMENSIONS if agg.get(k) is not None))
    return result


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="External book eval (Week-1 harness).")
    ap.add_argument("--book", help="book dir to chdir into first (like run_v3)")
    ap.add_argument("--pdf", help="score this PDF (else composed pages, else the "
                    "book's own PDF)")
    ap.add_argument("--only", help="comma list of page ids")
    args = ap.parse_args()
    base = os.getenv("V3_DIR", "v3")
    data_dir = os.path.join(args.book, base, "data") if args.book else DATA
    if not os.path.exists(f"{data_dir}/scenes.toon"):
        raise SystemExit(f"no scenes.toon under {data_dir} — parse the book first")

    v3dir = os.path.dirname(os.path.abspath(data_dir))
    pages_dir = os.path.join(v3dir, "output", "pages")
    pdf = args.pdf
    if not pdf:
        scenes = toon_io.load(f"{data_dir}/scenes.toon").get("scenes", [])
        has_png = any(os.path.exists(os.path.join(pages_dir, f"page_{plan_v3.slug(s.get('page'))}.png"))
                      for s in scenes)
        if not has_png:      # PDF-only book (e.g. Bilbo) — score its rasterized PDF
            import glob as _glob
            hits = sorted(_glob.glob(os.path.join(v3dir, "output", "*.pdf")))
            pdf = hits[0] if hits else None
    evaluate(data_dir=data_dir, pdf=pdf,
             only=args.only.split(",") if args.only else None)
