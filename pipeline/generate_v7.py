"""v7 page generation — role-assigned multi-reference Gemini + measured gate.

The redesign (docs/Pipeline-Redesign-Proposal.md), phases 2-4:

  GENERATE  one route for EVERY page (story, cover, matter): Gemini multi-ref
            generation with role-assigned references — character/duo sheets,
            the book STYLE PLATE (carried by every page so matter pages can't
            drift photoreal), and the setting plate. The page's fact contract
            (from the printed text) is written into the prompt.
  GATE      pipeline.gate_v7 probe scores: identity / facts / anatomy / style
            (0-100 each) + caption-band occupancy.
  REPAIR    diagnostic, per failure type, max V7_REPAIR_ROUNDS:
              anatomy or style fail  -> REGENERATE (structure can't be patched)
              identity fail          -> surgical Gemini edit vs the char sheet
              facts fail             -> surgical Gemini edit from the contract
              band occupied          -> repaint the band as calm negative space
            A page that still fails is kept at its best score and FLAGGED.

Output -> <V3_DIR>/output/art/page_<pg>.png + gate report art/gate_report.json.
Downstream compose/book stages are unchanged. This is the ONLY generation route
(the legacy t2i+i2i, kontext+LoRA and sprite-composite engines are removed);
the client checklist (checklist_v3) and per-page author notes/edits are
injected into the prompt so authored fixes survive a full-pipeline regen.

Config: V7_STYLE_PLATE (path; default: refs.toon group0, else first ref),
V3_DIR, V7_REPAIR_ROUNDS (default 2), V3_WORKERS (default 4), V3_SEED unused
here (Gemini has no seed param; style is pinned by the plate instead).
"""

import io
import json
import os

from PIL import Image, ImageFilter

from . import (audit_v8, canon_rules, checklist_v3, editor, gate_v7, items_v7,
               plan_v3, toon_io)

_CANON_RULES = None


def _canon():
    """Canon rules for this book (cached) — per-character body plans injected
    into the generation prompt so chimeras aren't drawn in the first place."""
    global _CANON_RULES
    if _CANON_RULES is None:
        try:
            _CANON_RULES = canon_rules.load(plan_v3.DATA)
        except Exception:                                    # noqa: BLE001
            _CANON_RULES = {}
    return _CANON_RULES
from .plan_v3 import ART, DATA

# Quality-first default: keep re-rolling a failing page up to this many rounds
# before giving up (was 2 — too few to clear a stubborn anatomy/scale fault).
REPAIR_ROUNDS = int(os.getenv("V7_REPAIR_ROUNDS", "5"))
# `items` (signature outfit/accessory probes) is binary-strict: any single
# missing/invented item on the page must fail it, so 99 ≈ "all probes true".
PASS = {"identity": 80, "items": 99, "facts": 99, "anatomy": 99, "style": 99,
        # binary-strict like items: a child drawn toddler- or adult-sized
        # next to an adult must fail even if every per-character probe passes
        "scale": 99,
        # binary-strict: one character with shortened legs / fattened body /
        # flipped stance must fail the page (Namaste solo-page drift)
        "proportion": 99,
        # v8 per-character comparison audit (presence/size/colours/shape/
        # clothes vs the sheet AND vs previous pages) — any drifted
        # character fails the page
        "audit": 99,
        # location continuity (floor + fixed props) — probes are per-prop, so
        # a single redecorated prop shouldn't sink a page alone
        "setting": 80}


def _band_box(side):
    return {"top": (0, 0, 1, 0.30), "bottom": (0, 0.70, 1, 1),
            "left": (0, 0, 0.30, 1), "right": (0.70, 0, 1, 1)}.get(side, (0, 0, 1, 0.30))


# A page only truly lacks a text home when even compose's clearest-strip
# search (vision-vetoed) can't find a strip calmer than this. Compose placed
# text fine on strips up to e≈47 in practice (bloom + adaptive ink).
BAND_MAX_ENERGY = float(os.getenv("V7_BAND_MAX_ENERGY", "50"))


def _band_occupied(img_bytes, side, text=""):
    """Flag ONLY when the page has no calm caption home AT ALL.

    The old check flagged when the layout's designated side band was busy —
    but compose searches the whole page and almost always finds a clear strip,
    so those flags were noise. Now: designated band calm -> fine; otherwise
    run compose's own clearest-strip search (same metrics + occupancy veto,
    sized with this page's real text) and flag only if its best strip is
    still too busy."""
    im = Image.open(io.BytesIO(img_bytes)).convert("L")
    W, H = im.size
    x0, y0, x1, y1 = _band_box(side)
    band = im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
    px = list(band.filter(ImageFilter.FIND_EDGES).getdata())
    energy = (sum(px) / len(px)) if px else 999.0
    if energy < 22.0:
        return False
    try:
        from . import compose_v3
        rgb = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        bh = compose_v3._body_metrics(rgb, text) if text.strip() else 0.14
        _, _, _, best_e, _ = compose_v3._clearest_strip(rgb, bh, side)
        return best_e > BAND_MAX_ENERGY
    except Exception:
        return True  # busy designated band and no compose answer — keep flag


def _style_plate(refman):
    p = os.getenv("V7_STYLE_PLATE", "")
    if p and os.path.exists(p):
        return open(p, "rb").read()
    for g in refman.get("groups", []):
        if os.path.exists(g.get("path", "")):
            return open(g["path"], "rb").read()
    for r in refman.get("refs", []):
        if os.path.exists(r.get("path", "")):
            return open(r["path"], "rb").read()
    return None


def _roles(plan, present, refman, style_plate, sc, char_items=None):
    """[(role_text, bytes)] in reference order for the prompt."""
    by = {r["name"]: r["path"] for r in refman.get("refs", [])}
    roles, covered = [], set()
    for g in refman.get("groups", []):
        m = g.get("members", [])
        if m and all(x in present for x in m) and os.path.exists(g["path"]):
            roles.append((f"the official character designs of {' and '.join(m)} "
                          f"together — copy each EXACTLY, including their "
                          f"distinguishing items AND their relative SIZES to "
                          f"each other exactly as this sheet shows",
                          open(g["path"], "rb").read()))
            covered.update(m)
    for n in present:
        if n in covered or n not in by or not os.path.exists(by[n]):
            continue
        roles.append((f"{n}'s official character design — copy EXACTLY",
                      open(by[n], "rb").read()))
    # Zoom crops of SMALL signature items (chest logo, bracelet): a few-pixel
    # detail inside a full sheet is exactly what the model re-invents, so it
    # gets its own reference image with an explicit role.
    ncrops = 0
    for n in present:
        for it in (char_items or {}).get(n, []):
            if ncrops >= items_v7.MAX_CROPS_PER_PAGE:
                break
            p = it.get("crop", "")
            if p and os.path.exists(p):
                roles.append((f"CLOSE-UP of {n}'s {it['item']} — reproduce "
                              f"this exact detail whenever it is visible",
                              open(p, "rb").read()))
                ncrops += 1
    if style_plate:
        roles.append(("the book's ART STYLE to match (linework, colour, "
                      "rendering finish) — do NOT copy its scene or layout",
                      style_plate))
    for s in refman.get("settings", []):
        if s.get("key") == sc.get("setting_key") and os.path.exists(s.get("path", "")):
            roles.append(("the recurring LOCATION — same place, architecture "
                          "and colours", open(s["path"], "rb").read()))
            break
    return roles


def _prompt(sc, plan, contract, roles, side, extra="", char_items=None):
    present = sc.get("chars", [])
    cast = ", ".join(present) if present else "no named characters"
    wears = "\n".join(w for w in
                      (items_v7.wears_line(n, (char_items or {}).get(n, []))
                       for n in present) if w)
    features = "\n".join(f for f in
                         (items_v7.features_line(n, (char_items or {}).get(n, []))
                          for n in present) if f)
    role_lines = "\n".join(f"  Image {i}: {r}" for i, (r, _) in enumerate(roles, 1))
    facts = gate_v7.contract_prompt_line(contract)
    distinguish = plan_v3.group_distinguish(plan, present)
    sizes = plan_v3.size_lock_line(plan, present)
    body_plan_line = canon_rules.generation_clause(_canon(), present)
    stances = plan_v3.stance_lines(plan, present)
    setting_lock = plan_v3.setting_lock_line(plan, sc)
    # All-animal casts (Grizzly Greg: five bears) kept rendering background
    # patrons/"everyone staring" as HUMANS — scene text implies a crowd and
    # nothing said the whole WORLD is animal. Derive the rule from the cast.
    species = {(((plan["by"][n].get("locked_spec") or {}).get("identity")
                 or {}).get("species") or "human")
               for n in present if n in plan["by"]}
    world = ""
    if species and all("human" not in s for s in species):
        kinds = ", ".join(sorted(species))
        world = (f"WORLD RULE: every figure in this book is an ANIMAL "
                 f"({kinds} world) — background guests, staff and "
                 f"passers-by included. NO humans anywhere in the image.\n")
    panels = plan_v3.wants_panels(sc)
    unity = ("laid out exactly as the scene describes (its vignette/panel "
             "layout is intentional). Every vignette shows each character at "
             "the SAME body proportions and relative size — a character must "
             "look identical in scale and build in every vignette" if panels
             else
             "ONE continuous unified scene — never a grid, collage or panels")
    return (
        f"Create ONE brand-new square full-bleed children's picture-book "
        f"illustration, {unity}. Do not copy any reference image's composition."
        + (f" {extra}" if extra else "") + "\n"
        + (f"REFERENCE ROLES:\n{role_lines}\n" if roles else "")
        + f"SCENE: {plan_v3.scene_desc(sc)}\n"
        + (f"AUTHOR'S DIRECTION (authoritative): {sc['author_note']}\n"
           if sc.get("author_note") else "")
        + (f"AUTHOR'S REQUESTED FIXES (MANDATORY — apply every one): "
           f"{'; '.join(sc['author_edits'])}\n"
           if sc.get("author_edits") else "")
        + f"CAST — each of these appears exactly ONCE, with the exact design "
          f"from its reference: {cast}.\n"
        + ("CLOSED CAST: these are the ONLY prominent characters. Do NOT add "
           "any other animal or person as a foreground or midground figure — "
           "no extra deer, dogs or sheep. Distant background scenery crowds "
           "only if the scene explicitly calls for them.\n" if present else "")
        + (f"OUTFIT LOCK (a checker verifies every item):\n{wears}\n"
           if wears else "")
        + (f"SIGNATURE FEATURES (a checker verifies direction):\n{features}\n"
           if features else "")
        + (f"KEEP DISTINCT: {distinguish}.\n" if distinguish else "")
        + (f"SIZE LOCK (a checker verifies relative heights): {sizes}\n"
           if sizes else "")
        + (f"{body_plan_line}\n" if body_plan_line else "")
        + (f"POSTURE LOCK (a checker verifies stance): {stances}.\n"
           if stances else "")
        + (f"SETTING LOCK (a checker verifies floor and props): "
           f"{setting_lock}\n" if setting_lock else "")
        + (f"MUST BE TRUE IN THE IMAGE (a checker will verify): {facts}.\n"
           if facts else "")
        + ("THIS PAGE CARRIES A LONG BLOCK OF TEXT: keep the illustration "
           "MINIMAL — one small, simple vignette, a soft plain wash over most "
           "of the page, no furniture/prop clutter, generous empty space.\n"
           if sc.get("role") in ("backmatter", "about_author", "dedication",
                                 "title") else "")
        + world
        + "STYLE: exactly match the art-style reference on every page — "
          "illustrated and painterly, NEVER photorealistic.\n"
        + f"COMPOSITION: keep the {side} ~35% of the frame as calm, empty "
          f"negative space that belongs to the scene (open sky / plain "
          f"ground) — no characters or props inside it.\n"
        + "ANATOMY: every person interacting with a character (petting, "
          "holding, leading) must be visibly and naturally connected to their "
          "own arms and hands — never draw cropped hands, arms reaching in "
          "from off-frame, or bodies hidden so only hands show.\n"
        + "The artwork must contain ZERO written text, letters or signage.\n"
        + checklist_v3.t2i_block(sc.get("setting", ""))
    )


def _failures(score, band_bad):
    f = [k for k, thr in PASS.items()
         if score.get(k) is not None and score[k] < thr]
    if band_bad:
        f.append("band")
    return f


def generate(only=None, data_dir=DATA):
    os.makedirs(ART, exist_ok=True)
    plan = plan_v3.load(data_dir)
    refman = toon_io.load(f"{data_dir}/refs.toon") if os.path.exists(f"{data_dir}/refs.toon") else {}
    lp = f"{data_dir}/layout.toon"
    layouts = {l["page"]: l for l in toon_io.load(lp)["layouts"]} if os.path.exists(lp) else {}
    style_plate = _style_plate(refman)
    report = {}

    def _one(sc):
        pg = plan_v3.page_id(sc)
        if only and pg not in only:
            return
        present = sc.get("chars", [])
        side = (layouts.get(pg) or {}).get("empty_side") or sc.get("text_area") or "top"
        contract = gate_v7.page_contract(sc, plan)
        char_items = items_v7.page_items(
            {n: items_v7.items_for(plan["by"][n]) for n in present
             if n in plan["by"] and items_v7.items_for(plan["by"][n])}, sc)
        roles = _roles(plan, present, refman, style_plate, sc, char_items)
        by = {r["name"]: r["path"] for r in refman.get("refs", [])}
        char_refs = {n: open(by[n], "rb").read() for n in present
                     if n in by and os.path.exists(by[n])}
        stances = plan_v3.stance_map(plan, present)
        setting = plan_v3.scene_setting(plan, sc) or {}
        setting_manifest = {"floor": setting.get("floor", ""),
                            "fixed_props": setting.get("fixed_props", [])}
        setting_ref = None
        for st_ in refman.get("settings", []):
            if (st_.get("key") == sc.get("setting_key")
                    and os.path.exists(st_.get("path", ""))):
                setting_ref = open(st_["path"], "rb").read()
                break

        def render(extra=""):
            return editor.to_square(editor.generate_with_refs(
                _prompt(sc, plan, contract, roles, side, extra, char_items),
                [b for _, b in roles]))

        def score(img):
            # v8 audit first — one comparison call per character (page vs
            # sheet vs canon). It replaces the batched identity/items and
            # proportion probes for sheet characters.
            verdicts, focus = audit_v8.audit_page(img, present, char_refs,
                                                  data_dir)
            s = gate_v7.score_page(img, contract=contract, char_refs=char_refs,
                                   style_plate=style_plate,
                                   char_items=char_items,
                                   size_pairs=plan_v3.size_pairs(plan, present),
                                   stances=stances,
                                   panels=plan_v3.wants_panels(sc),
                                   present=present,
                                   setting_ref=setting_ref,
                                   setting_manifest=setting_manifest,
                                   skip_char_probes=bool(verdicts),
                                   minimal_page=sc.get("role") in (
                                       "title", "dedication", "about_author",
                                       "backmatter"))
            s["audit"] = audit_v8.audit_pct(verdicts)
            s.setdefault("detail", {})["audit"] = verdicts
            # audit is part of the mean total like every other category
            avail = [v for k, v in s.items()
                     if k in PASS and v is not None]
            s["total"] = round(sum(avail) / len(avail)) if avail else None
            band = (not plan_v3.wants_panels(sc)) and _band_occupied(
                img, side, plan_v3.scene_text(sc))
            return s, band, focus

        try:
            img = render()
        except Exception as e:
            print(f"  [{pg}] render failed: {str(e)[:90]}")
            report[pg] = {"error": str(e)[:200]}
            return
        s, band, focus = score(img)
        best = (img, s, band)
        fails = _failures(s, band)
        print(f"  [{pg}] gate: total={s['total']} fails={fails or 'none'}")

        for rnd in range(1, REPAIR_ROUNDS + 1):
            if not fails:
                break
            # setting splits by what failed: a wrong FLOOR is a large-area
            # repaint (regenerate); a wrong/missing prop is surgical.
            sfloor_bad = any(
                not ok for ok in
                (s.get("detail", {}).get("setting_floor") or {}).values())
            # v8 audit failures repair first — the focus block names each
            # drifted character with its concrete differences. Clothes-only
            # drift (character present, right size/shape/colours) is the one
            # audit failure a surgical edit fixes reliably.
            aud_bad = {n: v for n, v in
                       (s.get("detail", {}).get("audit") or {}).items()
                       if not v.get("ok")}
            clothes_only = bool(aud_bad) and all(
                v.get("presence") == "exactly_one"
                and v.get("size") not in ("too_small", "too_big")
                and v.get("colours") != "different"
                and v.get("body_shape") != "different"
                and v.get("head_facing") != "rotated_or_impossible"
                and v.get("vs_previous_pages") != "different_from_previous"
                # an extra leg / cut-off / reversed pose needs a full redraw,
                # never a surgical clothing edit
                and not v.get("extra_limbs")
                and not v.get("cut_off")
                and not v.get("impossible_pose")
                for v in aud_bad.values())
            try:
                if "audit" in fails and clothes_only:
                    fixes = "; ".join(
                        f"{n}: " + ("; ".join(v.get("differences") or
                                              ["outfit does not match the reference"]))
                        for n, v in aud_bad.items())
                    img = editor.to_square(editor.edit(
                        f"Edit this storybook page. Fix ONLY these characters' "
                        f"clothing to match their reference sheets exactly, "
                        f"changing nothing else: {fixes}",
                        [img] + [char_refs[n] for n in aud_bad
                                 if n in char_refs]))
                elif "audit" in fails and focus:
                    img = render("MOST IMPORTANT: " + focus)
                # scale/proportion regenerate rather than edit: resizing or
                # re-proportioning a whole character re-lays-out the scene
                elif ({"anatomy", "style", "scale", "proportion"} & set(fails)
                        or ("setting" in fails and sfloor_bad)):
                    img = render("MOST IMPORTANT: the previous attempt had "
                                 + ("anatomy errors (wrong/extra/floating limbs) "
                                    if "anatomy" in fails else "")
                                 + ("and drifted from the art style "
                                    if "style" in fails else "")
                                 + ("and drew the characters at the WRONG "
                                    "RELATIVE SIZE — obey the SIZE LOCK "
                                    "heights exactly "
                                    if "scale" in fails else "")
                                 + ("and drew a character with the WRONG BODY "
                                    "PROPORTIONS or stance vs their reference "
                                    "sheet (legs too short, body too fat, or "
                                    "two-legged when it must be four-legged) — "
                                    "match each sheet's build and the POSTURE "
                                    "LOCK exactly "
                                    if "proportion" in fails else "")
                                 + ("and changed the location's floor — copy "
                                    "the LOCATION reference's floor exactly "
                                    if ("setting" in fails and sfloor_bad)
                                    else "")
                                 + "— redraw correctly.")
                elif ("identity" in fails or "facts" in fails
                      or "items" in fails or "setting" in fails):
                    problems = []
                    for cat in ("identity", "facts", "items", "setting_props"):
                        for q, ok in (s.get("detail", {}).get(cat) or {}).items():
                            if not ok:
                                problems.append(q)
                    # Failed-item zoom crops ride along so the surgical edit
                    # copies the exact detail (logo motif/position), not a guess.
                    crops = []
                    if "items" in fails:
                        failed = " ".join(q for q, ok in
                                          (s.get("detail", {}).get("items") or {}).items()
                                          if not ok)
                        for n, its in char_items.items():
                            for it in its:
                                p = it.get("crop", "")
                                if (p and os.path.exists(p)
                                        and it["desc"][:60] in failed):
                                    crops.append(open(p, "rb").read())
                    instr = ("Edit this storybook page. Fix ONLY these verified "
                             "problems, changing nothing else: "
                             + " | ".join(p[:200] for p in problems[:6])
                             + ". Match the attached reference sheet(s)"
                             + (" and close-up detail crop(s)" if crops else "")
                             + " exactly.")
                    edit_refs = [img] + list(char_refs.values()) + crops
                    # prop repairs copy the location reference, not a guess
                    if "setting" in fails and setting_ref:
                        edit_refs.append(setting_ref)
                    img = editor.to_square(editor.edit(instr, edit_refs))
                elif fails == ["band"]:
                    img = editor.to_square(editor.edit(
                        f"Edit this illustration: clear the {side} ~35% of the "
                        f"frame into calm, empty negative space that belongs to "
                        f"the scene (open sky / plain ground / soft wash) — "
                        f"move or remove any character or prop there. Change "
                        f"nothing else.", [img]))
            except Exception as e:
                print(f"  [{pg}] repair {rnd} failed: {str(e)[:80]}")
                break
            s, band, focus = score(img)
            fails = _failures(s, band)
            print(f"  [{pg}] repair {rnd}: total={s['total']} fails={fails or 'none'}")
            if (s["total"] or 0) >= (best[1]["total"] or 0):
                best = (img, s, band)

        img, s, band = best
        path = f"{ART}/page_{plan_v3.slug(pg)}.png"
        open(path, "wb").write(img)
        flagged = bool(_failures(s, band))
        # canon: a page whose audit is clean anchors how each character looks
        # for all later pages; a drifted page must never become the anchor
        if not flagged and s.get("audit") is not None:
            try:
                audit_v8.canon_save(img, pg, present, char_refs, data_dir)
            except Exception as e:  # noqa: BLE001
                print(f"  [{pg}] canon save failed: {str(e)[:60]}")
        s.pop("detail", None)
        # `passed` is the hard-gate signal the book stage reads: a page that
        # never cleared the gate after all repair rounds must not ship silently.
        report[pg] = {**s, "band_occupied": band, "flagged": flagged,
                      "passed": not flagged}
        print(f"  [{pg}] -> {path}  (total={s['total']}"
              f"{', FLAGGED' if report[pg]['flagged'] else ''})")

    workers = max(1, int(os.getenv("V3_WORKERS", "4")))
    scenes = plan["scenes"]
    if workers == 1:
        for sc in scenes:
            _one(sc)
    else:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(_one, scenes))
    json.dump(report, open(f"{ART}/gate_report.json", "w"), indent=2)
    flagged = [p for p, r in report.items() if r.get("flagged")]
    print(f"\n  gate report -> {ART}/gate_report.json"
          + (f"  FLAGGED for review: {flagged}" if flagged else "  all pages passed"))
    # Cross-page consistency sweep (full runs only — it audits the whole
    # book against the settled canon; run manually for subsets with
    # `python -m pipeline.audit_v8 <data_dir>`).
    if only is None:
        try:
            print("\n  == canon sweep ==")
            audit_v8.canon_sweep(data_dir)
        except Exception as e:  # noqa: BLE001
            print(f"  ! canon sweep failed: {str(e)[:80]}")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    generate(only=only)
