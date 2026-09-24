"""Auto-mask + surgical repair wrapper (fal Flux inpainting).

Productionises the hand-tuned p23 fix into a reusable pass. For each anatomy
defect on a page it:
  1. classifies the defect  ERASE (extra body/limb) vs REDRAW (wrong/whole body),
  2. derives a TIGHT, NEIGHBOUR-SAFE mask:
       - ERASE  : localise just the anomalous sub-region (anatomy_v8.locate_anomaly),
       - REDRAW : the figure box,
     then shrink it so it never overlaps another located figure's box (this is
     what stopped the giraffe from being erased with the zebra),
  3. inpaints via fal (erase→background / redraw→IP-Adapter on the character),
  4. re-audits; keeps the result only if the defect count did not increase.

Two failure modes this guards against, both learned the hard way:
  - mask too wide  → erases a neighbour (giraffe vanished),
  - strength too high on REDRAW → replaces instead of repairs (identity drift).

Originals are never overwritten: output goes to <book>/output/art_repaired/.

Usage (needs OpenRouter for audit + FAL_KEY for inpaint):
    python -m pipeline.fal_repair --book books/namaste-ferdinand/v3_kimi \\
        --art-dir output/art_prebodyplan --pages 23
"""

import argparse
import glob
import os
import re

from . import anatomy_v8, canon_rules, fal_backend

# We BIAS toward ERASE: it removes only the anomalous part and leaves the real
# character untouched, so it never drifts identity (the REDRAW failure mode).
# ERASE applies whenever there is a good core figure plus an EXTRA part —
# which includes the "human torso on a four-legged animal body" chimera (the
# four-legged half is the extra part to erase, keeping the upright torso).
_ERASE_HINTS = (
    "extra second body", "hindquarters", "extra/floating limb", "floating",
    "duplicated body", "extra/duplicated leg", "6 legs", "extra leg",
    # chimera phrasings — the four-legged lower/rear half is the extra part
    "human torso", "four-legged animal body", "incoherent body plan",
)
# REDRAW is reserved for the case with NO good core to keep: the whole figure
# is simply the wrong body plan (e.g. drawn as a plain quadruped when it should
# be an upright biped) — nothing to erase, must be redrawn.
_REDRAW_HINTS = ("wrong body plan", "natural quadruped", "wrong body")


def _is_erase(issue: str) -> bool:
    s = (issue or "").lower()
    if any(h in s for h in _REDRAW_HINTS) and not any(h in s for h in _ERASE_HINTS):
        return False
    if any(h in s for h in _ERASE_HINTS):
        return True
    # default: prefer ERASE (identity-safe) unless clearly a whole-figure redraw
    return True


def _clip_to_neighbors(box, others, *, pad: float = 0.01):
    """Shrink `box` so it does not overlap any box in `others`. For each
    neighbour that overlaps, push whichever of box's edges is nearest the
    neighbour inward past the neighbour's edge (+pad). Neighbour-safety first:
    better to mask slightly less than to eat an adjacent character."""
    x0, y0, x1, y1 = box
    for o in others:
        ox0, oy0, ox1, oy1 = o
        # skip if no overlap
        if x1 <= ox0 or x0 >= ox1 or y1 <= oy0 or y0 >= oy1:
            continue
        # horizontal push: if neighbour is to our left, raise x0; to our right, lower x1
        ncx = (ox0 + ox1) / 2
        bcx = (x0 + x1) / 2
        if ncx < bcx:                 # neighbour on the left → cut left edge
            x0 = max(x0, ox1 + pad)
        else:                         # neighbour on the right → cut right edge
            x1 = min(x1, ox0 - pad)
    if x1 - x0 < 0.03 or y1 - y0 < 0.03:
        return None                   # nothing safe left to mask
    return [x0, y0, x1, y1]


def repair_defect(page_bytes, defect, figures, refs, *, rounds_note=""):
    """Repair one defect surgically. Returns (new_bytes, info)."""
    from PIL import Image
    import io
    W, H = Image.open(io.BytesIO(page_bytes)).size

    others = [f["box"] for f in figures if f is not defect.get("_fig")]
    erase = _is_erase(defect.get("issue", ""))

    if erase:
        # target only the anomalous sub-region
        target = anatomy_v8.locate_anomaly(page_bytes, defect["_fig"], defect["issue"])
        target = target or defect["box"]
        mode = "ERASE"
    else:
        target = defect["box"]
        mode = "REDRAW"

    safe = _clip_to_neighbors(target, others)
    if safe is None:
        return page_bytes, {"mode": mode, "skipped": "no neighbour-safe mask"}

    mask = fal_backend.make_mask((W, H), safe)
    sp = defect.get("species", "character")
    if erase:
        prompt = (f"clean empty background matching the surrounding scene "
                  f"(floor, wall, plants) — no animal, no extra legs, no {sp} "
                  f"body here; soft watercolour children's book style")
        new = fal_backend.inpaint(page_bytes, mask, prompt, strength=0.95)
    else:
        # REDRAW identity tuning: anchor on BOTH the character sheet (canonical
        # identity, high scale) AND the original in-scene crop (pose/scale/colour
        # of THIS figure) so the species holds ("zebra", not a drifted "cat").
        # Lower strength keeps more of the original structure.
        ref = refs.get(sp) or refs.get(defect.get("name", "").lower())
        ip_refs = []
        if ref:
            ip_refs.append((ref, 1.0))
        crop = _crop_bytes(page_bytes, defect["box"])   # in-scene anchor
        if crop:
            ip_refs.append((crop, 0.6))
        prompt = (f"a single {sp} — clearly a {sp} with its distinctive {sp} "
                  f"markings — standing upright on two legs like a person, two "
                  f"legs and two arms, one coherent body, soft watercolour "
                  f"children's book style, matching the scene")
        new = fal_backend.inpaint(page_bytes, mask, prompt, strength=0.7,
                                  ip_refs=ip_refs)
    return new, {"mode": mode, "box": [round(x, 3) for x in safe]}


def _crop_bytes(page_bytes, box, margin=0.02):
    """The in-scene figure crop as PNG bytes — a REDRAW identity anchor."""
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(page_bytes)).convert("RGB")
    W, H = im.size
    x0 = max(0, int((box[0] - margin) * W)); y0 = max(0, int((box[1] - margin) * H))
    x1 = min(W, int((box[2] + margin) * W)); y1 = min(H, int((box[3] + margin) * H))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    buf = io.BytesIO(); im.crop((x0, y0, x1, y1)).save(buf, "PNG")
    return buf.getvalue()


def _species_refs(book_dir):
    """{species: sheet_bytes} keyed by species word, via canon name→species."""
    dd = os.path.join(book_dir, "data")
    name2sp = canon_rules.species_map(dd)
    out = {}
    for name, sp in name2sp.items():
        p = os.path.join(book_dir, "refs", f"{name.lower()}.png")
        if os.path.exists(p):
            out[sp] = open(p, "rb").read()
    return out


def _detect(page_bytes, rules, passes):
    """Run the anatomy audit up to `passes` times, stopping as soon as a pass
    finds a defect. Detection is stochastic (a subtle chimera is missed on some
    passes) so a single pass under-reports; retrying raises recall without the
    full cost of always unioning N passes."""
    last = anatomy_v8.audit_anatomy(page_bytes, rules=rules)
    for _ in range(max(0, passes - 1)):
        if last.get("defects"):
            break
        last = anatomy_v8.audit_anatomy(page_bytes, rules=rules)
    return last


def repair_page(page_bytes, rules, refs, *, max_defects=4, detect_passes=3):
    """Detect defects, repair each surgically, re-audit. Returns (bytes, report)."""
    za = _detect(page_bytes, rules, detect_passes)
    figures = za.get("figures", [])
    defects = za.get("defects", [])
    for d in defects:                       # attach the figure object for neighbour exclusion
        d["_fig"] = next((f for f in figures
                          if f.get("box") == d.get("box")), {"box": d.get("box")})
    report = {"before_score": za.get("score"), "before_defects": len(defects),
              "actions": []}
    cur = page_bytes
    for d in defects[:max_defects]:
        try:
            cur, info = repair_defect(cur, d, figures, refs)
            report["actions"].append({"issue": d.get("issue", "")[:60], **info})
        except Exception as e:              # noqa: BLE001
            report["actions"].append({"issue": d.get("issue", "")[:60],
                                      "error": str(e)[:80]})
    post = anatomy_v8.audit_anatomy(cur, rules=rules)
    report["after_score"] = post.get("score")
    report["after_defects"] = len(post.get("defects", []))
    # safety: if repair made it worse, keep the original
    if report["after_defects"] > report["before_defects"]:
        report["reverted"] = True
        return page_bytes, report
    return cur, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="books/namaste-ferdinand/v3_kimi")
    ap.add_argument("--art-dir", default="output/art",
                    help="art subdir under book (originals; not overwritten)")
    ap.add_argument("--pages", default="", help="comma page ids")
    args = ap.parse_args()

    dd = os.path.join(args.book, "data")
    rules = canon_rules.load(dd)
    rules["_species_map"] = canon_rules.species_map(dd)
    refs = _species_refs(args.book)
    art_dir = os.path.join(args.book, args.art_dir)
    out_dir = os.path.join(args.book, "output", "art_repaired")
    os.makedirs(out_dir, exist_ok=True)
    want = {p.strip() for p in args.pages.split(",") if p.strip()}

    for path in sorted(glob.glob(os.path.join(art_dir, "*.png"))):
        m = re.search(r"(\d+)", os.path.basename(path))
        if not m or (want and m.group(1) not in want):
            continue
        pid = m.group(1)
        print(f"\n== page {pid} ==")
        new, rep = repair_page(open(path, "rb").read(), rules, refs)
        print(f"  {rep['before_defects']} defect(s) score {rep['before_score']} "
              f"-> {rep['after_defects']} defect(s) score {rep['after_score']}"
              + ("  [REVERTED]" if rep.get("reverted") else ""))
        for a in rep["actions"]:
            print(f"    {a.get('mode','?')}: {a.get('issue','')} "
                  + (a.get('error') or str(a.get('box', ''))))
        outp = os.path.join(out_dir, f"page_{pid}.png")
        open(outp, "wb").write(new)
        print(f"  -> {outp}")


if __name__ == "__main__":
    main()
