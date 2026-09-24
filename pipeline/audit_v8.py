"""v8 character audit — direct comparison verification, replacing yes/no probes.

Why: the v7 gate asked ~20 batched yes/no questions per page and the VLM
agreed with them — pages 16/19 of Namaste passed "does exactly ONE Wooliam
appear?" with Wooliam completely absent; sheep clothes drifted through
occlusion escapes; nothing ever compared a page to the pages before it.

The v8 approach (client-requested):
  AUDIT   one focused VLM call PER CHARACTER (never batched across
          characters): compare the rendered page to that character's
          reference sheet — presence, size vs others, colours, body shape,
          clothes — every aspect a forced choice, plus a free-text list of
          concrete differences that becomes the focused-regen instruction.
  CANON   cross-page memory: when a page passes its audit, each cast
          character is cropped out and saved as that character's "canon"
          appearance. Later pages are audited against the sheet AND the most
          recent canon crops, so the character must match how they already
          look in THIS book, not just the sheet.
  SWEEP   after a full run, every page × character is compared once against
          the final canon -> art/canon_report.json, the human-review list of
          any page where a character diverges from the book's settled look.

gate_v7's facts / anatomy / style / scale / setting probes are unchanged —
they check things the audit doesn't (counts, limbs, style drift, landmark
heights, floor/props). The audit replaces the identity/items/proportion
probes for sheet-holding characters.
"""

import io
import json
import os

from PIL import Image

from . import audit_pregate, gate_v7, llm, plan_v3, toon_io
from .plan_v3 import DATA

CANON_K = 2   # canon crops shown per audit call

_AUDIT_SYSTEM = """\
You are a strict character-consistency inspector for a children's picture
book. You compare ONE character's official reference against a finished page
and report every drift. Judge only what you can see; mentally correct for
pose (sitting, bending, yoga poses) and camera distance — but a character
drawn clearly smaller than their locked size RELATIVE TO THE OTHER
CHARACTERS is a size error even when posed. Pose-correction NEVER excuses an
anatomically impossible head: a head facing the camera while the body faces
away (or any owl-like twist beyond ~90 degrees) is a drift. A garment of the
right colour but the wrong TYPE, length or silhouette (a vest drawn as a
dress, a top drawn as a leotard covering the legs) is a clothes drift. Be
strict: publishers reject books over exactly these drifts."""


def _verdict_ok(v):
    """True when an audit verdict dict reports no drift."""
    return (v.get("presence") == "exactly_one"
            and v.get("size") not in ("too_small", "too_big")
            and v.get("colours") != "different"
            and v.get("body_shape") != "different"
            and v.get("clothes") not in ("changed_or_missing", "extra_added")
            and v.get("head_facing") != "rotated_or_impossible"
            and v.get("vs_previous_pages") != "different_from_previous"
            # anatomy faults the comparative judge misses (see _limb_frame_faults)
            and not v.get("extra_limbs")
            and not v.get("cut_off")
            and not v.get("impossible_pose"))


def _limb_frame_faults(img_bytes, name):
    """Forced-choice anatomy faults for ONE character, judged on a tight crop.

    A single whole-page yes/no 'correct number of limbs?' under-detects a fifth
    leg (grizzly p6/p7 scored anatomy 100 with an extra leg on screen), and has
    no notion of a head cropped by the frame or a mirror-reversed pose. We ask
    three pointed questions about ONLY this character and read booleans in code.
    Run TWICE and OR the faults: for miscounting the VLM's failure mode is
    UNDER-detection, so strict (any-vote-fails) beats majority (same lesson as
    the coat-colour and size locks). Returns a {fault: bool} dict, or None if
    both calls errored (fail-open — an unjudgeable crop is not failed)."""
    q = (f"This image shows the character {name} from a children's picture "
         f"book. Look ONLY at {name} and count carefully. Reply ONLY JSON with "
         f"three booleans:\n"
         f'{{"extra_limbs": true if {name} has MORE limbs than it should — a '
         f"fifth leg, a third arm, a duplicated or floating paw/hand/leg, or a "
         f'limb that does not connect to the body; false if the count is '
         f'normal,\n'
         f' "cut_off": true if {name}\'s head or a large part of its body is '
         f"chopped off by the edge of the frame in a way that looks like a "
         f'mistake rather than a deliberate close-up; false otherwise,\n'
         f' "impossible_pose": true if {name} is drawn anatomically reversed '
         f"or twisted the wrong way — a joint bending backwards, the head or "
         f'limbs mirrored the wrong direction for the body; false otherwise}}\n'
         f"Output ONLY the JSON object — no explanation, no other text.")
    faults = {"extra_limbs": False, "cut_off": False, "impossible_pose": False}
    seen = 0
    for _ in range(2):
        try:
            r = llm.chat_json_images(
                "You are a strict anatomy inspector for children's book art.",
                q, [gate_v7._small(img_bytes, maxpx=768)],
                mime="image/jpeg", max_tokens=150)
        except Exception as e:  # noqa: BLE001
            print(f"    limb/frame {name} failed: {str(e)[:50]}")
            continue
        if not isinstance(r, dict):
            continue
        seen += 1
        for k in faults:
            if str(r.get(k)).strip().lower() in ("true", "1", "yes"):
                faults[k] = True
    return faults if seen else None


def _parse_verdict(r):
    if not isinstance(r, dict):
        return None
    v = {k: str(r.get(k, "")) for k in
         ("presence", "size", "colours", "body_shape", "clothes",
          "head_facing", "vs_previous_pages")}
    v["differences"] = [str(d)[:200] for d in (r.get("differences") or [])
                        if d][:6]
    return v


def _zoom_crop(page_bytes, name, sheet_bytes, margin=0.06):
    """Locate `name` on the page and return an enlarged crop (bytes), or None.
    Full-page images shrink a character to a few hundred pixels — too small
    for the judge to see garment shape or head direction (page 13 regression:
    owl-head sheep passed at page scale). One VLM locate call, same recipe as
    canon_save."""
    try:
        r = llm.chat_json_images(
            "You locate a specific character in an illustration with a "
            "tight bounding box.",
            f"Image 1 is a book page; image 2 is {name}'s official "
            f"reference. Give ONE tight bounding box around {name} in "
            f"image 1 (the full body). Reply ONLY JSON: "
            f'{{"found": true/false, "box": [x0,y0,x1,y1]}} — normalised '
            f"0..1, origin top-left.",
            [gate_v7._small(page_bytes, maxpx=1024),
             gate_v7._small(sheet_bytes, maxpx=768)],
            mime="image/jpeg", max_tokens=120)
    except Exception:  # noqa: BLE001
        return None
    b = r.get("box") if isinstance(r, dict) and r.get("found") else None
    if not (isinstance(b, list) and len(b) == 4):
        return None
    x0, y0, x1, y1 = (min(max(float(v), 0.0), 1.0) for v in b)
    if x1 - x0 < 0.05 or y1 - y0 < 0.05:
        return None
    im = Image.open(io.BytesIO(page_bytes)).convert("RGB")
    W, H = im.size
    crop = im.crop((int(max(x0 - margin, 0) * W), int(max(y0 - margin, 0) * H),
                    int(min(x1 + margin, 1) * W), int(min(y1 + margin, 1) * H)))
    buf = io.BytesIO()
    crop.save(buf, "PNG")
    out = buf.getvalue()
    # Verify the box actually landed on <name> — the locator sometimes boxes
    # a different cast member (p17: Ferdinand's "crop" was mostly Tallia),
    # and a wrong zoom poisons the audit worse than no zoom.
    try:
        r = llm.chat_json_images(
            "You verify whether a cropped figure matches a character design.",
            f"Image 1 is a cropped detail from a book page; image 2 is "
            f"{name}'s official reference sheet. Is the main/central figure "
            f"in image 1 the same character as image 2 — same species and "
            f"same design (ignore pose and clothing differences)? Reply ONLY "
            f'JSON: {{"same_character": true/false}}',
            [gate_v7._small(out, maxpx=768),
             gate_v7._small(sheet_bytes, maxpx=768)],
            mime="image/jpeg", max_tokens=60)
        if not (isinstance(r, dict) and r.get("same_character") is True):
            return None
    except Exception:  # noqa: BLE001
        return None
    return out


_COATS = ("white", "cream", "tan", "light-brown", "dark-brown", "grey",
          "black", "pink", "golden", "other")


def _coat_colour(img_bytes, name):
    """Forced-choice: name the character's main coat/fur colour, one palette
    word. Returns the word or None."""
    try:
        r = llm.chat_json_images(
            "You name the dominant coat colour of an illustrated animal "
            "character.",
            f"What is the MAIN body coat/fur colour of {name} in this image? "
            f"Ignore clothing, stripes, spots/patches and markings — the "
            f"base coat only. Reply ONLY JSON: "
            f'{{"coat": "<one of: {", ".join(_COATS)}>"}}',
            [gate_v7._small(img_bytes, maxpx=768)],
            mime="image/jpeg", max_tokens=60)
        c = str(r.get("coat", "")).strip().lower() if isinstance(r, dict) else ""
        return c if c in _COATS else None
    except Exception:  # noqa: BLE001
        return None


def audit_character(page_bytes, name, sheet_bytes, canon_crops=None,
                    others=None):
    """One focused comparison call for one character. Returns a verdict dict
    (see _parse_verdict) with `ok` set, or None if both attempts errored
    (fail-open: an unauditable character is excluded, not failed)."""
    canon_crops = canon_crops or []
    others = [o for o in (others or []) if o != name]
    imgs = [gate_v7._small(page_bytes, maxpx=1024),
            gate_v7._small(sheet_bytes, maxpx=1024)]
    zoom = _zoom_crop(page_bytes, name, sheet_bytes)
    zoom_note = ""
    if zoom is not None:
        imgs.append(gate_v7._small(zoom, maxpx=768))
        zoom_note = (
            f"\nImage 3 is a zoomed-in crop of {name} cut from the page — "
            f"judge fine details (garment type/length, head direction vs "
            f"body direction) from THIS image, not the small page figure.")
    first_canon = len(imgs) + 1
    for c in canon_crops[:CANON_K]:
        imgs.append(gate_v7._small(c, maxpx=768))
    canon_note = ""
    if len(imgs) >= first_canon:
        canon_note = (
            f"\nImages {first_canon}+ show "
            f"how {name} ALREADY LOOKS on previously accepted pages of this "
            f"same book — {name} must also match those (same build, same "
            f"clothes, same colours).")
    others_note = (f" The other characters on this page should be: "
                   f"{', '.join(others)}." if others else "")
    user = (
        f"Image 1 is the finished page; image 2 is {name}'s official "
        f"reference sheet.{zoom_note}{canon_note}\n"
        f"Find {name} in the page{others_note} Compare {name} to the "
        f"reference on every aspect and reply ONLY JSON:\n"
        f'{{"presence": "exactly_one" | "absent" | "multiple",\n'
        f' "size": "correct_relative_to_others" | "too_small" | "too_big" | '
        f'"alone_cannot_judge",\n'
        f' "colours": "match_reference" | "different",\n'
        f' "body_shape": "match_reference" | "different",\n'
        f' "clothes": "match_reference" | "changed_or_missing" | '
        f'"extra_added" | "cannot_see",\n'
        f' "head_facing": "consistent_with_body" | "rotated_or_impossible" | '
        f'"cannot_see",\n'
        f' "vs_previous_pages": "same_as_previous" | '
        f'"different_from_previous" | "no_previous_provided",\n'
        f' "differences": ["each concrete drift, specific and actionable"]}}\n'
        f"Rules: presence counts ONLY figures matching {name}'s species and "
        f"design — a different animal is NOT {name}. size judges {name}'s "
        f"height/bulk against the OTHER characters on the page vs the locked "
        f"relationship (pose-corrected); use alone_cannot_judge only when "
        f"{name} is the only character. clothes compares every worn item to "
        f"the reference INCLUDING garment type, length and silhouette — the "
        f"right colour on the wrong garment (vest drawn as a dress/leotard, "
        f"top extended to cover legs the reference leaves bare) is "
        f"changed_or_missing. head_facing is rotated_or_impossible when the "
        f"head points somewhere the body's orientation cannot support (e.g. "
        f"face to camera while the body faces away). differences must be [] "
        f"when everything matches.")
    # Majority vote. The old loop retried ONLY failing votes, so one lenient
    # vote passed the character while a strict one got a second chance to be
    # overturned — biasing every borderline call toward PASS (brown-goat
    # page 17 miss). Now: 2 votes; on disagreement a 3rd breaks the tie.
    votes = []
    for _ in range(3):
        try:
            r = llm.chat_json_images(_AUDIT_SYSTEM, user, imgs,
                                     mime="image/jpeg", max_tokens=600)
        except Exception as e:  # noqa: BLE001
            print(f"    audit {name} failed: {str(e)[:60]}")
            continue
        v = _parse_verdict(r)
        if v is None:
            continue
        v["ok"] = _verdict_ok(v)
        votes.append(v)
        if len(votes) == 2 and votes[0]["ok"] == votes[1]["ok"]:
            break
    if not votes:
        return None
    n_ok = sum(1 for v in votes if v["ok"])
    ok = n_ok > len(votes) / 2
    # report the verdict from the majority side (richest differences list)
    side = [v for v in votes if v["ok"] == ok]
    best = max(side, key=lambda v: len(v.get("differences") or []))
    best["ok"] = ok
    # Coat colour by FORCED CHOICE. Comparative "do the colours match?"
    # judgments are lenient (p17: fawn-brown Ferdinand vs cream sheet passed
    # 3 unanimous votes) — naming each image's coat colour independently and
    # comparing in code is not (same lesson as the v7.7 size lock).
    # Gate on the character image only, NOT on `zoom is not None`: when the
    # locator fails to box the character (page 25 brown goat: canon-saved
    # clean because zoom was None so this check was skipped entirely), fall
    # back to the full page so a coat drift is never silently un-checked.
    if best.get("colours") != "different":
        probe = zoom if zoom is not None else gate_v7._small(page_bytes,
                                                             maxpx=1024)
        # LOCAL PRE-GATE (proposal #4): a zero-cost colour-histogram check on
        # the same (crop, sheet) pair. On a confident same-family 'match' we
        # can skip the two VLM forced-choice calls below; drift/ambiguous
        # escalate to the VLM as before. `shadow` logs the local verdict for
        # comparison but keeps the VLM authoritative (no behaviour change).
        pg_mode = audit_pregate.mode()
        pg = audit_pregate.coat_match(probe, sheet_bytes) if pg_mode != "off" else None
        if pg is not None:
            print(f"    [pregate] {name}: {pg['decision']} "
                  f"crop={pg['crop_family']}({pg['crop_frac']}) "
                  f"sheet={pg['sheet_family']}({pg['sheet_frac']}) "
                  f"∩={pg['intersect']}")
        if pg_mode == "on" and pg is not None and pg["decision"] == "match":
            # confident local match — trust it, skip the 2 VLM coat calls
            a = b = None
        else:
            a = _coat_colour(probe, name)
            b = _coat_colour(sheet_bytes, name)
        # neighbouring shades are the same coat (white/cream goat, tan/golden
        # retriever) — only cross-family shifts are drift
        fam = {"white": 0, "cream": 0, "tan": 1, "light-brown": 1,
               "golden": 1, "dark-brown": 2, "grey": 3, "black": 4, "pink": 5}
        if (a and b and "other" not in (a, b)
                and fam.get(a) != fam.get(b)):
            best["colours"] = "different"
            best.setdefault("differences", []).append(
                f"{name}'s coat/fur colour is {a} on the page but {b} on "
                f"the reference sheet")
            best["ok"] = _verdict_ok(best)
    # Anatomy faults the comparative judge is blind to — a fifth leg, a head
    # cropped by the frame, a mirror-reversed pose. Judged on the tight crop
    # (or the full page when the locator missed), read as booleans in code.
    probe = zoom if zoom is not None else gate_v7._small(page_bytes, maxpx=1024)
    faults = _limb_frame_faults(probe, name)
    if faults:
        for key, msg in (
                ("extra_limbs", f"{name} has an extra or floating limb "
                                f"(e.g. a fifth leg) that must be removed"),
                ("cut_off", f"{name}'s head or body is cut off by the frame "
                            f"edge — fit the whole character in frame"),
                ("impossible_pose", f"{name} is in an anatomically reversed or "
                                    f"impossible pose — redraw the pose naturally")):
            if faults.get(key):
                best[key] = True
                best.setdefault("differences", []).append(msg)
        best["ok"] = _verdict_ok(best)
    return best


def audit_page(page_bytes, present, char_refs, data_dir=DATA):
    """Audit every present sheet-holding character. Returns (verdicts, focus):
    verdicts = {name: verdict-with-ok}; focus = regen instruction naming each
    drifted character and its concrete differences ('' when clean)."""
    verdicts = {}
    for name in present:
        if name not in char_refs:
            continue
        v = audit_character(page_bytes, name, char_refs[name],
                            canon_crops=canon_for(name, data_dir),
                            others=present)
        if v is not None:
            verdicts[name] = v
    bits = []
    for name, v in verdicts.items():
        if v["ok"]:
            continue
        why = []
        if v.get("presence") == "absent":
            why.append(f"{name} is MISSING from the page")
        if v.get("presence") == "multiple":
            why.append(f"{name} appears more than once")
        if v.get("size") in ("too_small", "too_big"):
            why.append(f"{name} is drawn {v['size'].replace('_', ' ')}")
        for k, bad in (("colours", "different"), ("body_shape", "different"),
                       ("clothes", "changed_or_missing"),
                       ("clothes", "extra_added"),
                       ("head_facing", "rotated_or_impossible"),
                       ("vs_previous_pages", "different_from_previous")):
            if v.get(k) == bad:
                why.append(f"{name} {k.replace('_', ' ')}: {bad.replace('_', ' ')}")
        why += v.get("differences", [])
        bits.append(f"{name}: " + "; ".join(why[:5]))
    focus = ""
    if bits:
        focus = ("FOCUS — the previous attempt drew these characters WRONG: "
                 + " | ".join(bits)
                 + ". Each named character must be copied EXACTLY from their "
                   "reference sheet: same size relative to the others, same "
                   "colours, same body shape and leg length, same clothes.")
    return verdicts, focus


def audit_pct(verdicts):
    """0-100 score (None if nothing was auditable) for the gate report."""
    if not verdicts:
        return None
    flags = [v["ok"] for v in verdicts.values()]
    return round(100 * sum(flags) / len(flags))


# --- canon library ----------------------------------------------------------

def _canon_index(data_dir):
    p = f"{data_dir}/canon.toon"
    return (toon_io.load(p) if os.path.exists(p) else {"crops": []}), p


def canon_for(name, data_dir=DATA, k=CANON_K):
    """Most recent k canon crop bytes for `name` (newest last)."""
    idx, _ = _canon_index(data_dir)
    paths = [c["path"] for c in idx.get("crops", [])
             if c.get("name") == name and os.path.exists(c.get("path", ""))]
    return [open(p, "rb").read() for p in paths[-k:]]


def canon_save(page_bytes, pg, present, char_refs, data_dir=DATA):
    """Crop each cast character out of a page that PASSED its audit and store
    as canon. One VLM locate call per character (sheet in view so the box is
    for the right figure). Failures are silent — canon is best-effort."""
    idx, p = _canon_index(data_dir)
    cdir = f"{data_dir}/canon"
    im = Image.open(io.BytesIO(page_bytes)).convert("RGB")
    W, H = im.size
    for name in present:
        if name not in char_refs:
            continue
        # one crop per (name, page) — regen of the page replaces it
        idx["crops"] = [c for c in idx.get("crops", [])
                        if not (c.get("name") == name
                                and str(c.get("page")) == str(pg))]
        try:
            r = llm.chat_json_images(
                "You locate a specific character in an illustration with a "
                "tight bounding box.",
                f"Image 1 is a book page; image 2 is {name}'s official "
                f"reference. Give ONE tight bounding box around {name} in "
                f"image 1 (the full body). Reply ONLY JSON: "
                f'{{"found": true/false, "box": [x0,y0,x1,y1]}} — normalised '
                f"0..1, origin top-left.",
                [gate_v7._small(page_bytes, maxpx=1024),
                 gate_v7._small(char_refs[name], maxpx=768)],
                mime="image/jpeg", max_tokens=120)
        except Exception:  # noqa: BLE001
            continue
        b = r.get("box") if isinstance(r, dict) and r.get("found") else None
        if not (isinstance(b, list) and len(b) == 4):
            continue
        x0, y0, x1, y1 = (min(max(float(v), 0.0), 1.0) for v in b)
        if x1 - x0 < 0.05 or y1 - y0 < 0.05:
            continue
        os.makedirs(f"{cdir}/{plan_v3.slug(name)}", exist_ok=True)
        out = f"{cdir}/{plan_v3.slug(name)}/page_{plan_v3.slug(str(pg))}.png"
        im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))).save(out)
        idx["crops"].append({"name": name, "page": str(pg), "path": out})
    toon_io.save(idx, p)


def canon_sweep(data_dir=DATA, art_dir=None):
    """Post-run cross-page consistency report: every page × cast character
    audited once against sheet + final canon. Writes canon_report.json next
    to the art. Report-only — the human-review list."""
    art_dir = art_dir or plan_v3.ART
    plan = plan_v3.load(data_dir)
    refman = toon_io.load(f"{data_dir}/refs.toon") \
        if os.path.exists(f"{data_dir}/refs.toon") else {}
    by = {r["name"]: r["path"] for r in refman.get("refs", [])}
    report = {}
    for sc in plan["scenes"]:
        pg = str(plan_v3.page_id(sc))
        path = f"{art_dir}/page_{plan_v3.slug(pg)}.png"
        present = [n for n in sc.get("chars", [])
                   if n in by and os.path.exists(by[n])]
        if not present or not os.path.exists(path):
            continue
        page = open(path, "rb").read()
        bad = {}
        for name in present:
            v = audit_character(page, name, open(by[name], "rb").read(),
                                canon_crops=canon_for(name, data_dir),
                                others=present)
            if v is not None and not v["ok"]:
                bad[name] = {k: v[k] for k in
                             ("presence", "size", "colours", "body_shape",
                              "clothes", "vs_previous_pages", "differences")}
        report[pg] = {"inconsistent": bad, "ok": not bad}
        state = "ok" if not bad else "DRIFT: " + ", ".join(bad)
        print(f"  sweep [{pg}] {state}")
    out = f"{art_dir}/canon_report.json"
    json.dump(report, open(out, "w"), indent=2)
    drifted = [p for p, r in report.items() if not r["ok"]]
    print(f"  canon report -> {out}"
          + (f"  DRIFTED: {drifted}" if drifted else "  all consistent"))
    return report


if __name__ == "__main__":
    import sys
    canon_sweep(sys.argv[1] if len(sys.argv) > 1 else DATA)
