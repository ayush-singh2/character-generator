"""v7 signature-item manifest — full outfit/accessory consistency per character.

Why: small worn details (a chest logo, a bracelet) flickered page-to-page (Dad's
t-shirt logo present on some pages, gone on others). Three gaps caused it:
the v7 prompt never named the items in text, the gate had ONE coarse
"every signature item?" probe (a miss still scored >=80 on multi-char pages),
and so the surgical repair never fired.

This module builds the single ground truth both sides speak from:

  EXTRACT  vision-read the APPROVED reference sheet (ground truth — the client
           approved those pixels; the written spec only helps name colours) into
           a closed list of signature items per character. Each garment that
           could carry a print records the logo EXPLICITLY — present (motif,
           colour, position) or "NO logo" — so the gate catches both a dropped
           logo and an invented one.
  CROP     small items (logo, bracelet, ear tag) additionally get a zoomed
           crop from the sheet saved to <REFS>/items/ — passed to generation as
           an extra role-assigned reference, because a few-pixel detail in a
           downscaled sheet is exactly what the model re-invents.
  STORE    written onto the character in characters.toon as `sig_items`;
           generate_v7 renders a deterministic WEARS line from it and gate_v7
           asks one binary probe PER item (threshold: any miss fails the page).

Run standalone from the book dir (refs must exist):
    PYTHONPATH=<repo> python -m pipeline.items_v7 [Dad,Mom]
It also runs automatically at the end of the refs stage.
"""

import io
import os

from PIL import Image

from . import gate_v7, llm, plan_v3, toon_io
from .plan_v3 import DATA, REFS

MAX_CROPS_PER_PAGE = 4   # cap on zoom-crop references added to one page prompt

_EXTRACT_SYSTEM = """\
You catalogue a picture-book character's SIGNATURE ITEMS from their official
reference sheet, so every page can be checked against them.

The SHEET IMAGE is the ground truth (it is the approved design). The written
spec below it helps you name colours precisely, but when they disagree,
describe what the SHEET shows.

List every worn/carried item: headwear, neckwear (collar, bandana), top,
bottom, footwear, wrist/hand items, always-carried props. ALSO include the
character's distinctive HEAD features as items — these drift most between
pages: hairstyle + hairline (state fullness EXPLICITLY, e.g. "full head of
thick white hair combed back, NO bald or thinning crown"), facial hair
(moustache/beard shape), and glasses. ALSO include directional ANATOMY
features as items with "kind":"feature" — horns, tail, ears, crest, trunk —
whose desc states the direction absolutely as the sheet shows it (e.g. "two
horns curving BACKWARD over the head, tips pointing behind — never sideways
or forward"); their direction drifts between pages unless pinned. Worn or
carried items have "kind":"worn". Rules:
- For every garment that could carry a print (shirt, cap, bag): state
  EXPLICITLY either the logo/print (motif, colour, position on the garment)
  or that it is PLAIN with NO logo/print/text. Never leave it unstated.
- desc is one self-contained phrase a checker can verify from a page image
  alone, e.g. "cream-white short-sleeve t-shirt, completely plain, NO logo or
  print" or "navy baseball cap with a small white B on the front".
- small=true for details a viewer could miss at full-page scale (a chest
  logo, bracelet, ear tag, small emblem) AND for any repeating print/pattern
  on a garment (e.g. baseballs printed on a bandana — the motif drifts into
  generic blobs unless referenced close-up); for those give box_pct
  [x0,y0,x1,y1] as 0-100 percentages of the WHOLE sheet image, tightly
  around the detail, AND "detail": the distinctive small detail ALONE in a
  few words (e.g. "white paw print logo"), naming only the detail — not the
  garment it sits on.
- "when" ONLY if the item is genuinely conditional ("only when riding");
  otherwise "".
- 3-8 items is typical. This is a CLOSED list — no vague entries.
Reply ONLY JSON:
{"items":[{"item":"<short name>","desc":"<verifiable phrase>",
           "kind":"worn|feature","small":true/false,
           "detail":"<small detail alone>" or "",
           "box_pct":[x0,y0,x1,y1] or null,"when":""}]}"""


def _extract(sheet_bytes, char):
    spec = plan_v3.char_lock(char)
    user = (f"Character: {char.get('name', '')}\nWritten spec (colour names "
            f"only; the sheet wins on disagreement): {spec}\n"
            f"Catalogue the signature items from the attached sheet.")
    # 1024px keeps small logos legible for cataloguing; crops still cut from
    # the full-resolution sheet afterwards.
    r = llm.chat_json_images(_EXTRACT_SYSTEM, user,
                             [gate_v7._small(sheet_bytes, maxpx=1024)],
                             mime="image/jpeg", max_tokens=1200)
    items = []
    for it in (r.get("items") or []) if isinstance(r, dict) else []:
        if not isinstance(it, dict) or not it.get("desc"):
            continue
        items.append({"item": str(it.get("item", "item")),
                      "desc": str(it["desc"]),
                      "kind": ("feature" if str(it.get("kind", "")) == "feature"
                               else "worn"),
                      "small": bool(it.get("small")),
                      "detail": str(it.get("detail", "") or ""),
                      "box_pct": it.get("box_pct") or None,
                      "when": str(it.get("when", "") or "")})
    return items


def _no_clothing_item():
    """Explicit lock for an unclothed character — naming the absence is what
    stops the model dressing a naked sheep on one page and stripping it on
    the next."""
    return {"item": "(no clothing)", "kind": "worn", "small": False,
            "detail": "", "when": "", "crop": "",
            "desc": "wears NO clothing or accessories at all — a natural "
                    "animal with bare fur/hide on every page"}


def _spec_items(char):
    """Deterministic sig_items for a recurring character WITHOUT a reference
    sheet, synthesized from the locked spec text (src='spec'): no zoom crops,
    but the WEARS line and text-anchored gate probes still fire, so the outfit
    can't silently vanish or change between pages."""
    if (char.get("dress_state") or "").strip().lower() == "unclothed":
        return [dict(_no_clothing_item(), src="spec")]
    o = (char.get("outfit") or "").strip()
    if not o:
        return []
    return [{"item": "outfit", "kind": "worn", "small": False, "detail": "",
             "when": "", "crop": "", "src": "spec",
             "desc": f"complete locked outfit, exactly: {o} — never a "
                     f"different outfit, never undressed"}]


def _crop(sheet_bytes, box_pct, out_path, pad=0.15, minpx=200, minfrac=0.0):
    """Save a padded zoom-crop of one small item from the sheet. `minfrac`
    grows the window to at least that fraction of the sheet per axis (centred
    on the box) — the wide-retry when the VLM's box was off."""
    im = Image.open(io.BytesIO(sheet_bytes)).convert("RGB")
    W, H = im.size
    x0, y0, x1, y1 = [max(0.0, min(100.0, float(v))) / 100 for v in box_pct]
    if x1 <= x0 or y1 <= y0:
        return False
    px, py = (x1 - x0) * pad, (y1 - y0) * pad
    x0, y0, x1, y1 = x0 - px, y0 - py, x1 + px, y1 + py
    if minfrac:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, h = max(x1 - x0, minfrac), max(y1 - y0, minfrac)
        x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
    box = (int(max(0, x0) * W), int(max(0, y0) * H),
           int(min(1, x1) * W), int(min(1, y1) * H))
    if box[2] <= box[0] or box[3] <= box[1]:
        return False
    c = im.crop(box)
    if min(c.size) < minpx:   # keep the detail legible as a reference image
        s = minpx / min(c.size)
        c = c.resize((int(c.width * s), int(c.height * s)))
    c.save(out_path, "PNG")
    return True


def _crop_shows_detail(crop_path, it):
    """One cheap yes/no: does the crop actually contain the item's distinctive
    detail? VLM bounding boxes are unreliable — a crop of plain fabric labelled
    'close-up of the logo' would TEACH the generator the wrong design, so a
    failed check drops the crop (the WEARS line and gate probes still cover
    the item)."""
    what = it.get("detail") or it["item"]
    user = (f"Does this image clearly and unmistakably contain this specific "
            f"detail: {what}? Judge ONLY that exact detail — the surrounding "
            f"garment or fabric alone does NOT count.\n"
            'Reply ONLY JSON: {"visible": true/false}')
    try:
        r = llm.chat_json_images("You verify reference image crops.", user,
                                 [open(crop_path, "rb").read()], max_tokens=60)
        return bool(r.get("visible")) if isinstance(r, dict) else False
    except Exception:  # noqa: BLE001 — unverifiable = don't trust it
        return False


def build(only=None, data_dir=DATA):
    """Extract sig_items for every high-consistency character with a sheet and
    write them back into characters.toon. Merges on partial runs (`only`)."""
    cpath = f"{data_dir}/characters.toon"
    rpath = f"{data_dir}/refs.toon"
    if not (os.path.exists(cpath) and os.path.exists(rpath)):
        print("  items: characters.toon / refs.toon missing — skipped")
        return
    chars = toon_io.load(cpath)
    refman = toon_io.load(rpath)
    sheets = {r["name"]: r["path"] for r in refman.get("refs", [])}
    crops_dir = f"{REFS}/items"
    os.makedirs(crops_dir, exist_ok=True)

    n = 0
    for c in chars.get("characters", []):
        name = c.get("name", "")
        # a sheet (not is_high) is the criterion — backfilled old books can
        # have sheetless high characters (handled by the spec fallback below)
        if name not in sheets:
            continue
        if only is not None and name not in only:
            continue
        if not os.path.exists(sheets[name]):
            continue
        sheet = open(sheets[name], "rb").read()
        try:
            items = _extract(sheet, c)
        except Exception as e:  # noqa: BLE001 — one char must not kill the run
            print(f"  ! items for {name} failed: {str(e)[:80]}")
            continue
        if ((c.get("dress_state") or "").strip().lower() == "unclothed"
                and not any(i["item"] == "(no clothing)" for i in items)):
            items.append(dict(_no_clothing_item()))
        # Re-extraction must not lose hand-authored deterministic scopes
        # (when='pages:...'/'setting:...') — carry them over by item name.
        prev = {p.get("item", ""): p for p in (c.get("sig_items") or [])
                if isinstance(p, dict)}
        for it in items:
            old = prev.get(it["item"])
            if old and str(old.get("when", "")).startswith(("pages:", "setting:")):
                it["when"] = old["when"]
        for i, it in enumerate(items):
            it["crop"] = ""
            if it["small"] and it.get("box_pct"):
                p = f"{crops_dir}/{plan_v3.slug(name)}_{i}_{plan_v3.slug(it['item'])}.png"
                try:
                    # tight crop -> verify; wide retry (>=45% of sheet) -> verify;
                    # else drop — an unverified crop must never become a reference.
                    if _crop(sheet, it["box_pct"], p) and _crop_shows_detail(p, it):
                        it["crop"] = p
                    elif (_crop(sheet, it["box_pct"], p, pad=0.5, minfrac=0.45)
                          and _crop_shows_detail(p, it)):
                        it["crop"] = p
                        print(f"    crop {name}/{it['item']}: wide retry used")
                    else:
                        if os.path.exists(p):
                            os.unlink(p)
                        print(f"    crop {name}/{it['item']}: could not verify "
                              f"the detail — crop dropped")
                except Exception as e:  # noqa: BLE001
                    print(f"    crop {name}/{it['item']}: {str(e)[:60]}")
            it.pop("box_pct", None)
        c["sig_items"] = items
        n += 1
        crops = sum(1 for it in items if it["crop"])
        print(f"  items {name}: {len(items)} ({crops} zoom crops) — "
              + "; ".join(it["item"] for it in items))
    # Fallback: recurring/high characters WITHOUT a sheet still get
    # spec-derived items so their outfit is locked in the prompt and probed
    # from text — a sheep's dress must not vanish just because it never got
    # a reference sheet.
    for c in chars.get("characters", []):
        name = c.get("name", "")
        if name in sheets or not plan_v3.is_high(c) or c.get("sig_items"):
            continue
        if only is not None and name not in only:
            continue
        si = _spec_items(c)
        if si:
            c["sig_items"] = si
            n += 1
            print(f"  items {name}: {len(si)} from spec (no sheet)")
    toon_io.save(chars, cpath)
    print(f"  -> sig_items on {n} characters in {cpath}")


def items_for(char):
    """The character's signature-item list (always-on items first)."""
    its = char.get("sig_items") or []
    return [it for it in its if isinstance(it, dict) and it.get("desc")]


def applies(it, sc):
    """Does this item apply on this page?
    when=''              -> True  (always; fully enforced)
    when='setting:<keys>'-> True/False by the scene's setting_key — deterministic,
                            so a matched page is FULLY enforced (gate included).
                            Use for outfit changes ("raincoat only outdoors").
    when='pages:<ids>'   -> True/False by page id; ids are a comma list, ranges
                            allowed for numeric pages ("pages:3-11,cover").
    any other free text  -> None  (generation-time hint only; the gate cannot
                            verify the condition from one page and skips it).
    """
    w = (it.get("when") or "").strip()
    if not w:
        return True
    if w.startswith("setting:"):
        keys = [k.strip() for k in w[len("setting:"):].split(",") if k.strip()]
        return sc.get("setting_key") in keys
    if w.startswith("pages:"):
        pg = str(sc.get("page", ""))
        for part in w[len("pages:"):].split(","):
            part = part.strip()
            a, _, b = part.partition("-")
            if _ and a.strip().isdigit() and b.strip().isdigit():
                if pg.isdigit() and int(a) <= int(pg) <= int(b):
                    return True
            elif part == pg:
                return True
        return False
    return None


def page_items(char_items, sc):
    """Per-page view of {name: [items]}: wrong-setting items removed entirely;
    matched setting-scoped items become unconditional (gate-enforceable);
    free-text `when` items stay conditional (prompt hint, gate skips)."""
    out = {}
    for name, its in (char_items or {}).items():
        keep = []
        for it in its:
            a = applies(it, sc)
            if a is False:
                continue
            if a is True and it.get("when"):
                it = {**it, "when": ""}
            keep.append(it)
        if keep:
            out[name] = keep
    return out


def wears_line(name, items):
    """Deterministic OUTFIT LOCK prompt line for one character (worn items
    only — directional anatomy goes in features_line)."""
    items = [it for it in items if it.get("kind", "worn") != "feature"]
    if not items:
        return ""
    bits = [it["desc"] + (f" [{it['when']}]" if it.get("when") else "")
            for it in items]
    return (f"{name} WEARS on every page, exactly as on the reference — never "
            f"re-invent, drop or add items: " + "; ".join(bits) + ".")


def features_line(name, items):
    """Deterministic SIGNATURE FEATURES prompt line — directional anatomy
    (horn curve, tail carriage, ear set) whose direction drifts unless pinned.
    Kept separate from the outfit lock so WEARS stays a pure clothing list."""
    feats = [it for it in items if it.get("kind") == "feature"]
    if not feats:
        return ""
    return (f"{name}'s SIGNATURE FEATURES — exact shape and direction, never "
            f"mirrored or re-angled: "
            + "; ".join(it["desc"] for it in feats) + ".")


_SETTING_SYSTEM = """\
You catalogue a picture-book LOCATION's fixed, repeatable details from its
official setting reference sheet, so every page drawn in this location can be
checked against them. The SHEET IMAGE is ground truth; the seed notes only help
you name things — when they disagree, describe what the sheet shows.

Reply ONLY JSON:
{"floor": "ONE exact floor material + colour as shown",
 "fixed_props": [{"item": "<short name>", "count": 2,
                  "design": "one committed, repeatable design phrase"}]}
Rules:
- fixed_props are the recurring furniture/props of the PLACE (never characters,
  never carried items): window, rug, shelf, candles, mats...
- counts exact as drawn on the sheet; design one committed phrase (e.g.
  "covered glass lantern candles"). 2-6 props is typical. Closed list."""


def build_settings(data_dir=DATA):
    """Lock each recurring setting's floor + fixed props from its rendered
    sheet (approved pixels win over the parse seed) — the manifest generate_v7
    puts in the SETTING LOCK line and gate_v7 verifies per page. Mirrors the
    sig-item philosophy for locations."""
    import json as _json
    spath = f"{data_dir}/scenes.toon"
    rpath = f"{data_dir}/refs.toon"
    if not (os.path.exists(spath) and os.path.exists(rpath)):
        print("  settings: scenes.toon / refs.toon missing — skipped")
        return
    scenes_doc = toon_io.load(spath)
    refman = toon_io.load(rpath)
    sheets = {s.get("key"): s.get("path") for s in refman.get("settings", [])}
    n = 0
    for s in scenes_doc.get("settings", []) or []:
        key = s.get("key")
        path = sheets.get(key)
        if not path or not os.path.exists(path):
            continue
        seed = {"floor": s.get("floor", ""),
                "fixed_props": s.get("fixed_props", [])}
        user = (f"Location: {s.get('name') or key}\n"
                f"Seed notes (sheet wins on disagreement): "
                f"{_json.dumps(seed, ensure_ascii=False)}\n"
                f"Catalogue the floor and fixed props from the attached sheet.")
        try:
            r = llm.chat_json_images(
                _SETTING_SYSTEM, user,
                [gate_v7._small(open(path, "rb").read(), maxpx=1024)],
                mime="image/jpeg", max_tokens=800)
        except Exception as e:  # noqa: BLE001 — one setting must not kill refs
            print(f"  ! setting manifest {key} failed: {str(e)[:80]}")
            continue
        if not isinstance(r, dict):
            continue
        if r.get("floor"):
            s["floor"] = str(r["floor"])
        props = [{"item": str(p["item"]),
                  "count": int(p.get("count") or 1),
                  "design": str(p.get("design", "") or "")}
                 for p in (r.get("fixed_props") or [])
                 if isinstance(p, dict) and p.get("item")]
        if props:
            s["fixed_props"] = props
        n += 1
        print(f"  setting {key}: floor='{s.get('floor', '')[:50]}', "
              f"{len(s.get('fixed_props') or [])} fixed props")
    toon_io.save(scenes_doc, spath)
    print(f"  -> setting manifests on {n} settings in {spath}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "settings":
        build_settings()
    else:
        only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
        build(only=only)
