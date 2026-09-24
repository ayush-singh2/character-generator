"""v3 book assembly — composed pages -> a single PDF, in manuscript order.

DIM-1 (client feedback): every page is normalised to ONE uniform trim before the
PDF is written, so page dimensions can never change mid-book. The book prints one
manuscript page per sheet, so EVERY page is a single square page (no spreads) at
SINGLE_TRIM. A page is scaled to COVER its trim and centre-cropped, so the book
stays full-bleed and every leaf is the exact same pixel size.
"""

import json
import os

from PIL import Image

from . import plan_v3

from .plan_v3 import ART, DATA, PAGES, OUT  # noqa: F401


def _gate_blockers(art_dir):
    """Pages that never cleared the quality gate (hard-block the PDF build).

    Reads the generate stage's gate_report.json. A page is a blocker if it
    errored, or its `passed` flag is False (or, for older reports without the
    flag, it was `flagged`). Pages absent from the report (e.g. matter pages
    that skip the gate) are treated as fine."""
    path = os.path.join(art_dir, "gate_report.json")
    if not os.path.exists(path):
        return []
    try:
        rep = json.load(open(path))
    except Exception:  # noqa: BLE001
        return []
    bad = []
    for pg, r in rep.items():
        if not isinstance(r, dict):
            continue
        passed = r.get("passed")
        failed = (r.get("error") is not None
                  or passed is False
                  or (passed is None and r.get("flagged")))
        if failed:
            bad.append(pg)
    return sorted(bad, key=lambda p: (p != "cover", int(p) if p.isdigit() else 1e9, p))

# Uniform trim for every page. Square by default (BOOK_TRIM_PX); the backend can
# request a non-square trim (A4/A5/Letter, portrait or landscape) by setting
# BOOK_TRIM_W / BOOK_TRIM_H from the author's chosen page size + orientation.
_TRIM_PX = int(os.getenv("BOOK_TRIM_PX", "2550"))   # 2550=8.5in, 2400=8in @300dpi
_TRIM_W = int(os.getenv("BOOK_TRIM_W", str(_TRIM_PX)))
_TRIM_H = int(os.getenv("BOOK_TRIM_H", str(_TRIM_PX)))
SINGLE_TRIM = (_TRIM_W, _TRIM_H)


def _to_trim(src, trim):
    """Scale src to COVER trim (preserve aspect), then centre-crop to exact size."""
    tw, th = trim
    sw, sh = src.size
    scale = max(tw / sw, th / sh)
    rw, rh = max(tw, int(round(sw * scale))), max(th, int(round(sh * scale)))
    resized = src.resize((rw, rh), Image.LANCZOS)
    left, top = (rw - tw) // 2, (rh - th) // 2
    return resized.crop((left, top, left + tw, top + th))


def build(data_dir=DATA):
    plan = plan_v3.load(data_dir)
    title = plan_v3.slug(plan.get("title") or "book") or "book"

    # HARD GATE: never assemble a PDF that still contains pages which failed the
    # quality gate. A failing page must be re-rolled (generate_v7 --only <pages>)
    # until it passes. Set BB_ALLOW_INCOMPLETE=1 to force a clearly-labelled
    # draft anyway (e.g. to preview layout while art is still being corrected).
    blockers = _gate_blockers(ART)
    if blockers:
        if os.getenv("BB_ALLOW_INCOMPLETE") == "1":
            print(f"  ⚠ BB_ALLOW_INCOMPLETE=1 — building a DRAFT with "
                  f"{len(blockers)} unresolved page(s): {blockers}")
        else:
            print(f"  ✋ BLOCKED: {len(blockers)} page(s) did not pass the gate "
                  f"and would ship with visible defects:\n     {blockers}")
            print(f"  Re-roll them:  V3_DIR={os.getenv('V3_DIR', 'v3')} "
                  f"python -m pipeline.generate_v7 {','.join(blockers)}")
            print("  Then re-run compose + book. To force a draft anyway, set "
                  "BB_ALLOW_INCOMPLETE=1.")
            return ""

    imgs = []
    for sc in plan["scenes"]:
        p = f"{PAGES}/page_{plan_v3.slug(plan_v3.page_id(sc))}.png"
        if os.path.exists(p):
            src = Image.open(p).convert("RGB")
            imgs.append(_to_trim(src, SINGLE_TRIM))
    if not imgs:
        print("no composed pages to build"); return ""
    os.makedirs(OUT, exist_ok=True)
    pdf = f"{OUT}/{title}.pdf"
    imgs[0].save(pdf, "PDF", save_all=True, append_images=imgs[1:], resolution=150.0)
    print(f"  -> {pdf}  ({len(imgs)} pages)")
    return pdf


if __name__ == "__main__":
    build()
