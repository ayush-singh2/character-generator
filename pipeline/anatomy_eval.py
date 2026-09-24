"""Validate the per-figure zoom anatomy pass against the old page-scale score.

Proves the fix: pages the page-only probe scored 100 while shipping a
6-legged animal (namaste p3, p18) should now come back with a sub-100 score
and a located defect + bounding box. Run this once OpenRouter budget is
available.

Usage:
    python -m pipeline.anatomy_eval --book books/namaste-ferdinand/v3_kimi
    python -m pipeline.anatomy_eval --book books/namaste-ferdinand/v3_kimi --pages 3,18,23
"""

import argparse
import glob
import json
import os
import re

from . import anatomy_v8, canon_rules


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="books/namaste-ferdinand/v3_kimi")
    ap.add_argument("--pages", default="", help="comma page ids (default: all rendered)")
    args = ap.parse_args()

    art_dir = os.path.join(args.book, "output", "art")
    old = {}
    rep = os.path.join(art_dir, "gate_report.json")
    if os.path.exists(rep):
        old = {str(k): v.get("anatomy") for k, v in json.load(open(rep)).items()
               if isinstance(v, dict)}

    rules = canon_rules.load(os.path.join(args.book, "data"))
    want = set(p.strip() for p in args.pages.split(",") if p.strip())
    paths = sorted(glob.glob(os.path.join(art_dir, "*.png")))
    print(f"{'page':>5} | {'old(page-scale)':>15} | {'new(zoom)':>9} | defects")
    flips = 0
    for path in paths:
        m = re.search(r"(\d+)", os.path.basename(path))
        if not m:
            continue
        pid = m.group(1)
        if want and pid not in want:
            continue
        za = anatomy_v8.audit_anatomy(open(path, "rb").read(), rules=rules)
        new = za.get("score")
        defs = "; ".join(f"{d['issue']}@{[round(x,2) for x in d['box']]}"
                         for d in za.get("defects", [])) or "-"
        o = old.get(pid)
        # a "flip" = old said perfect (100) but new caught a defect
        flip = (o == 100 and new is not None and new < 100)
        flips += flip
        print(f"{pid:>5} | {str(o):>15} | {str(new):>9} | {defs}"
              + ("   <-- CAUGHT (old missed)" if flip else ""))
    print(f"\n{flips} page(s) where the zoom pass caught anatomy the page-scale "
          f"probe scored 100.")


if __name__ == "__main__":
    main()
