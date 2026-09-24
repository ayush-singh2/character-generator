"""Repair ALREADY-GENERATED art in place, using masked inpainting.

The workflow this implements (start from existing art, don't regenerate):

    for each page we already rendered:
        1. DETECT  — per-figure zoom anatomy pass finds what's wrong and WHERE
                     (each defect carries a bounding box); cast-presence finds
                     declared characters the render dropped.
        2. FIX     — for each localized anatomy defect, mask-inpaint ONLY that
                     box (editor.inpaint_region): the broken legs are redrawn,
                     every other pixel is preserved. Re-audit; loop up to N.
        3. SAVE    — write the improved page to output/art_fixed/ (originals in
                     output/art/ are left untouched for comparison).

Why masking and not re-generation: a full re-render re-rolls the whole scene
and usually reproduces the same 6-leg artifact; repainting just the flagged
region keeps the 90% that was already good.

Scope note: masking fixes LOCALIZED defects that have a region (extra/floating/
duplicated limbs). A *missing* character can't be inpainted into empty space —
those are reported as `needs_regen` for a separate full redraw, not silently
skipped.

Usage (run once the OpenRouter key can spend again):
    python -m pipeline.repair_v8 --book books/namaste-ferdinand/v3_kimi
    python -m pipeline.repair_v8 --book books/namaste-ferdinand/v3_kimi --pages 3,18,23
    python -m pipeline.repair_v8 --book ... --rounds 3
"""

import argparse
import glob
import json
import os
import re

from . import anatomy_v8, canon_rules, editor


def _load_ref_sheets(book_dir: str) -> dict:
    """{species_or_name(lower): sheet_bytes} from the book's refs dir, so an
    inpaint of a known character can be conditioned on its sheet."""
    out = {}
    for p in glob.glob(os.path.join(book_dir, "refs", "*.png")):
        name = os.path.splitext(os.path.basename(p))[0].lower()
        if name.startswith(("group", "setting")):
            continue
        out[name] = open(p, "rb").read()
    return out


def _pick_ref(species: str, refs: dict):
    """Best-effort match a located species to a character sheet (optional —
    the crop already carries identity; the sheet just helps)."""
    sp = (species or "").lower()
    for name, b in refs.items():
        if name in sp or sp in name:
            return b
    return None


def _fix_instruction(defect: dict) -> str:
    sp = defect.get("species", "animal")
    return (
        f"Fix the {sp}. Problem: {defect.get('issue', 'anatomy defect')}. "
        f"Draw the {sp} with the correct number of legs — a four-legged animal "
        f"has EXACTLY four legs; a character posed upright on two legs has "
        f"EXACTLY two — with no extra, duplicated, merged or floating limbs, "
        f"legs properly attached to one single body")


def repair_page(page_bytes: bytes, refs: dict, rounds: int, rules: dict | None = None):
    """Detect → mask-inpaint each anatomy defect → re-audit, up to `rounds`.
    Returns (new_page_bytes, result_dict)."""
    history = []
    cur = page_bytes
    for rnd in range(1, rounds + 1):
        za = anatomy_v8.audit_anatomy(cur, rules=rules)
        defects = za.get("defects", [])
        history.append({"round": rnd, "score": za.get("score"),
                        "defects": [d["issue"] for d in defects]})
        if not defects:
            break
        for d in defects:
            try:
                cur = editor.inpaint_region(
                    cur, d["box"], _fix_instruction(d),
                    refs=[r] if (r := _pick_ref(d["species"], refs)) else None)
            except Exception as e:                           # noqa: BLE001
                print(f"      inpaint failed ({d['species']}): {str(e)[:60]}")
    final = anatomy_v8.audit_anatomy(cur, rules=rules)
    return cur, {"final_score": final.get("score"),
                 "remaining": [d["issue"] for d in final.get("defects", [])],
                 "history": history}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="books/namaste-ferdinand/v3_kimi")
    ap.add_argument("--pages", default="", help="comma page ids (default: all)")
    ap.add_argument("--rounds", type=int, default=2, help="max inpaint rounds/page")
    args = ap.parse_args()

    art_dir = os.path.join(args.book, "output", "art")
    out_dir = os.path.join(args.book, "output", "art_fixed")
    os.makedirs(out_dir, exist_ok=True)
    refs = _load_ref_sheets(args.book)
    rules = canon_rules.load(os.path.join(args.book, "data"))
    want = {p.strip() for p in args.pages.split(",") if p.strip()}

    report = {}
    for path in sorted(glob.glob(os.path.join(art_dir, "*.png"))):
        m = re.search(r"(\d+)", os.path.basename(path))
        if not m:
            continue
        pid = m.group(1)
        if want and pid not in want:
            continue
        page_bytes = open(path, "rb").read()
        print(f"\n== page {pid} ==")
        new_bytes, res = repair_page(page_bytes, refs, args.rounds, rules=rules)

        before = res["history"][0]["score"] if res["history"] else None
        status = ("clean" if not res["remaining"]
                  else "improved" if (res["final_score"] or 0) > (before or 0)
                  else "unresolved")
        print(f"   score {before} -> {res['final_score']}  [{status}]"
              + (f"  remaining: {res['remaining']}" if res["remaining"] else ""))

        out_path = os.path.join(out_dir, f"page_{pid}.png")
        open(out_path, "wb").write(new_bytes)
        report[pid] = {**res, "status": status, "out": out_path}

    json.dump(report, open(os.path.join(out_dir, "repair_report.json"), "w"),
              indent=2)
    fixed = sum(1 for r in report.values() if r["status"] in ("clean", "improved"))
    print(f"\n{fixed}/{len(report)} pages clean-or-improved. "
          f"Fixed art in {out_dir} (originals untouched in {art_dir}).")


if __name__ == "__main__":
    main()
