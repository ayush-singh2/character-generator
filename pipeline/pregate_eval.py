"""Validate the local coat pre-gate against the authoritative VLM.

Before we let `AUDIT_PREGATE=on` skip any VLM calls, we must know: when the
local gate says "match" (and would skip the VLM), does the VLM actually
agree the coat family matches? A single disagreement in that cell means the
gate would ship a real coat drift — unacceptable given consistency is the
client's #1 grievance.

For each (page, present character) in a book this runs BOTH:
  - the local `coat_match(page, sheet)`  (free)
  - the VLM forced-choice `_coat_colour` on page-crop and on the sheet
    (the real ground truth; sheet result cached per character)
and cross-tabulates them. The key output is the confusion between the local
decision and whether the VLM saw the same coat family, plus the resulting
skip-rate (= estimated VLM coat calls saved) and — critically — the count of
DANGEROUS skips (local "match" while the VLM says the family differs).

Usage:
    python -m pipeline.pregate_eval --book books/namaste-ferdinand/v3
    python -m pipeline.pregate_eval --book books/namaste-ferdinand/v3 --pages 8
"""

import argparse
import glob
import os
import re

from . import audit_pregate, audit_v8, plan_v3, toon_io

# same family map the audit uses to decide cross-family drift
_FAM = {"white": 0, "cream": 0, "tan": 1, "light-brown": 1, "golden": 1,
        "dark-brown": 2, "grey": 3, "black": 4, "pink": 5}


def _present_by_page(data_dir):
    """page-id -> list of character names present (from the scene plan)."""
    plan = plan_v3.load(data_dir)
    out = {}
    for sc in plan["scenes"]:
        out[str(plan_v3.page_id(sc))] = sc.get("chars", []) or []
    return out


def _sheet_path(refs_dir, name):
    for cand in (name.lower(), name.lower().replace(" ", "_")):
        p = os.path.join(refs_dir, f"{cand}.png")
        if os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="books/namaste-ferdinand/v3")
    ap.add_argument("--pages", type=int, default=0, help="limit pages (0 = all)")
    args = ap.parse_args()

    data_dir = os.path.join(args.book, "data")
    refs_dir = os.path.join(args.book, "refs")
    art = sorted(glob.glob(os.path.join(args.book, "output", "art", "*.png")))
    if args.pages:
        art = art[:args.pages]
    present = _present_by_page(data_dir)

    sheet_fam_cache = {}   # name -> VLM sheet coat family index (cached)
    rows = []
    for path in art:
        m = re.search(r"(\d+)", os.path.basename(path))
        if not m:
            continue
        pid = m.group(1)
        page_bytes = open(path, "rb").read()
        for name in present.get(pid, []):
            sp = _sheet_path(refs_dir, name)
            if not sp:
                continue
            sheet_bytes = open(sp, "rb").read()

            # Match the real audit: probe the ISOLATED zoom crop of the
            # character, not the full page (whose background dominates a
            # colour histogram). Fall back to the full page when the locator
            # misses — exactly what audit_character does.
            zoom = audit_v8._zoom_crop(page_bytes, name, sheet_bytes)
            probe = zoom if zoom is not None else page_bytes
            probe_kind = "zoom" if zoom is not None else "page"

            local = audit_pregate.coat_match(probe, sheet_bytes)

            # VLM ground truth on the SAME probe, family-mapped
            vlm_crop = audit_v8._coat_colour(probe, name)
            if name not in sheet_fam_cache:
                w = audit_v8._coat_colour(sheet_bytes, name)
                sheet_fam_cache[name] = _FAM.get(w) if w and w != "other" else None
            cf, sfam = _FAM.get(vlm_crop) if vlm_crop and vlm_crop != "other" else None, sheet_fam_cache[name]
            vlm_same = (cf is not None and sfam is not None and cf == sfam)
            vlm_known = (cf is not None and sfam is not None)

            rows.append({"page": pid, "name": name, "local": local["decision"],
                         "vlm_crop": vlm_crop, "vlm_same": vlm_same,
                         "vlm_known": vlm_known})
            print(f"  p{pid:>3} {name:12s} [{probe_kind}] local={local['decision']:9s} "
                  f"(crop={local['crop_family']} sheet={local['sheet_family']} "
                  f"∩={local['intersect']})  vlm_crop={vlm_crop} "
                  f"same_family={'?' if not vlm_known else vlm_same}")

    # ---- report ----
    n = len(rows)
    if not n:
        print("no rows — check book path / refs / scene chars")
        return
    match = [r for r in rows if r["local"] == "match"]
    # dangerous = local said match (would skip VLM) but VLM saw a different family
    dangerous = [r for r in match if r["vlm_known"] and not r["vlm_same"]]
    safe_match = [r for r in match if r["vlm_known"] and r["vlm_same"]]
    escalated = [r for r in rows if r["local"] != "match"]
    # of escalations, how many were genuine drift the VLM caught
    caught = [r for r in escalated if r["vlm_known"] and not r["vlm_same"]]

    print("\n=== PRE-GATE VALIDATION ===")
    print(f"characters audited      : {n}")
    print(f"local 'match' (skip VLM): {len(match)}  → skip-rate {len(match)/n:.0%}"
          f"  (≈ {2*len(match)} VLM coat calls saved)")
    print(f"  ├─ VLM agrees (safe)  : {len(safe_match)}")
    print(f"  └─ VLM DISAGREES      : {len(dangerous)}   <-- must be 0 to enable 'on'")
    print(f"local escalated to VLM  : {len(escalated)}")
    print(f"  └─ real drift caught  : {len(caught)}  (correctly NOT skipped)")
    if dangerous:
        print("\n!! DANGEROUS SKIPS (local match but VLM cross-family):")
        for r in dangerous:
            print(f"   p{r['page']} {r['name']}: vlm_crop={r['vlm_crop']}")
        print("   → tighten PREGATE_CONF_FRACTION / PREGATE_MATCH_INTERSECT before 'on'.")
    else:
        print("\nOK: no dangerous skips on this book — 'on' would be safe here.")


if __name__ == "__main__":
    main()
