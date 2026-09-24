"""v7 measured acceptance gate — replaces prose judging with binary probes.

Design (see docs/Pipeline-Redesign-Proposal.md):
  * page CONTRACT: countable narrative facts extracted from the PRINTED page
    text + scene (cast with counts, prop counts, stated states). Used twice —
    injected into the generation prompt AND verified against the final art.
  * probe scoring: batched yes/no VLM questions per category
      - identity  (page + each character's reference sheet)
      - facts     (from the contract: counts, states)
      - anatomy   (the known artifact classes: extra/floating limbs, human
                   limbs on animals, duplicated characters)
      - style     (page + style plate: same rendering family, not photoreal)
    Each category scores 0..100 = fraction of probes answered correctly.
    Binary probes beat similarity scores for counts/relations (VQAScore,
    arXiv 2404.01291) and beat prose judges for consistency (no hallucinated
    collars — every question is anchored to a spec fact).
"""

import io
import os

from PIL import Image

from . import anatomy_v8, canon_rules, llm, plan_v3, toon_io

_CANON_RULES = None


def _canon():
    """Canon rules for the current book (cached); body plans for the anatomy
    detector so figures are judged against their expected plan."""
    global _CANON_RULES
    if _CANON_RULES is None:
        try:
            _CANON_RULES = canon_rules.load(plan_v3.DATA)
            _CANON_RULES["_species_map"] = canon_rules.species_map(plan_v3.DATA)
        except Exception:                                    # noqa: BLE001
            _CANON_RULES = {}
    return _CANON_RULES


def _small(img_bytes, maxpx=768):
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    if max(im.size) > maxpx:
        s = maxpx / max(im.size)
        im = im.resize((int(im.width * s), int(im.height * s)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue()


# --- page contract ----------------------------------------------------------

_CONTRACT_SYSTEM = """\
You extract VERIFIABLE facts from a picture-book page so an illustration can
be checked against them. From the page TEXT (authoritative) and the scene
description, produce ONLY facts a viewer could verify by looking:
- how many of each character/kind of person must appear (exact counts)
- countable props the text implies (e.g. "they each got a pup cup" + two
  characters => exactly 2 pup cups)
- visible states/moods the text asserts (e.g. "became very sleepy" => the
  characters must LOOK sleepy)
STRICT RULES:
- Emit a count ONLY when the text makes it exact — a number, "each", "both",
  or a closed list of names. "Some people", "many dogs", "new humans" have NO
  exact count: leave them OUT entirely.
- Named main characters get count 1 each. Do NOT add background/crowd entries.
- A state must be verifiable from ONE still image by an ordinary viewer
  ("the dogs look sleepy" yes; "they are having a special day" no). NO motion
  states (wagging, running, reaching toward) — only frozen-moment facts:
  posture, expression, position.
- NO transient micro-states, even if the text mentions them: laughter,
  smiles, open mouths, glasses sliding down a nose, a nose pressed against
  glass, a gust of wind, blinks. An illustrator may legitimately freeze a
  nearby instant without them. A state qualifies ONLY if drawing the page
  without it would contradict the text (e.g. "the umbrella turned inside
  out" => inside-out umbrella; "caught raindrops on their tongues" =>
  tongues out).
- NO facial-expression states unless the TEXT itself names that character's
  emotion or expression ("gasped", "looked sleepy"). NEVER infer an
  expression from dialogue tone, punctuation, or the scene description
  ('"Halt!" cried Maya' does NOT mean a serious determined face).
- NO counts for AMBIENT/NATURAL features (puddles, raindrops, clouds, leaves,
  stars, cobblestones, flowers): weather and scenery multiply them freely —
  "a puddle as wide as a lake" does NOT mean the street has exactly 1 puddle.
- NO counts for WORN items (clothing, footwear, glasses, hats, scarves):
  several characters may wear the same kind of garment, so such counts
  false-fail ("exactly 2 boots" fails when two people each wear a pair).
  Worn items are checked by a separate per-character system. Count only
  free-standing props (umbrellas, mugs, balls, leashes).
- When in doubt, omit — a missing fact is safe, an invented one causes a
  false failure.
Reply ONLY JSON:
{"cast":[{"who":"<name or description>","count":<int>}],
 "props":[{"item":"<prop>","count":<int>}],
 "states":["<visible state the image must show>", ...]}"""


def page_contract(sc, plan):
    """Structured verifiable facts for one scene. Cached by callers."""
    present = sc.get("chars", [])
    user = (f"PAGE TEXT: {plan_v3.scene_text(sc) or '(no text on this page)'}\n"
            f"SCENE: {plan_v3.scene_desc(sc)}\n"
            f"NAMED CHARACTERS ON THIS PAGE: {', '.join(present) or 'none'}")
    # All-animal world probe (Grizzly Greg misses: bedroom POSTERS of human
    # footballers on p10, the toddler drawn as a human girl on p19). The
    # WORLD RULE was generation-prompt-only — nothing ever ASKED the page
    # "any humans?", so violations sailed through. As a contract state it
    # rides the existing facts category with zero extra calls.
    world_state = None
    species = {(((plan["by"][n].get("locked_spec") or {}).get("identity")
                 or {}).get("species") or "human")
               for n in present if n in plan.get("by", {})}
    if species and all("human" not in s for s in species):
        world_state = ("every figure in the image is an animal — ZERO human "
                       "faces or human bodies anywhere, INCLUDING inside "
                       "posters, pictures, toys and background")
    # Togetherness probe (Grizzly p20: father and sisters drifted to separate
    # background tables — every per-character count probe passed because each
    # bear appears exactly once; nothing asserted they share ONE group).
    extra_states = [world_state] if world_state else []
    # Closed-cast probe (Namaste misses: phantom deer on p13, a dog on p18,
    # an extra sheep on p23). The cast clause was generation-prompt-only —
    # nothing ever ASKED the page "anyone else?". Rides the facts call.
    if present:
        extra_states.append(
            f"besides {', '.join(present)}, there is NO additional prominent "
            f"animal or person character in the foreground or midground — no "
            f"extra deer, dog, sheep or other invented companion (distant "
            f"background scenery figures the scene itself calls for are fine)")
    if len(present) >= 3:
        extra_states.append(
            f"{', '.join(present)} are TOGETHER as one group in the same "
            f"spot (same table/area), sharing the same moment — no listed "
            f"character is placed alone at a separate background table or "
            f"corner")
    try:
        c = llm.chat_json(_CONTRACT_SYSTEM, user, max_tokens=800)
        if isinstance(c, dict):
            return {"cast": c.get("cast") or [], "props": c.get("props") or [],
                    "states": (c.get("states") or []) + extra_states}
    except Exception as e:
        print(f"    contract extraction failed ({str(e)[:60]}) — empty contract")
    return {"cast": [], "props": [], "states": extra_states}


def contract_prompt_line(contract):
    """The contract as a compact prompt clause (used at generation time)."""
    bits = []
    for c in contract["cast"]:
        bits.append(f"exactly {c['count']} {c['who']}")
    for p in contract["props"]:
        bits.append(f"exactly {p['count']} {p['item']}")
    bits += contract["states"]
    return ("; ".join(bits)) if bits else ""


# --- probe scoring ----------------------------------------------------------

def _ask(system, questions, images, maxpx=768):
    """One batched VLM call: numbered yes/no questions -> list of booleans.
    Fail-open: an errored category returns None (excluded from the total)."""
    if not questions:
        return []
    qtext = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
    user = (f"Answer each question with true or false, judged ONLY from the "
            f"image(s).\n{qtext}\n"
            'Reply ONLY JSON: {"answers": [true/false, ...]} in question order.')
    try:
        r = llm.chat_json_images(system, user,
                                 [_small(b, maxpx=maxpx) for b in images],
                                 mime="image/jpeg")
        a = r.get("answers") if isinstance(r, dict) else None
        if isinstance(a, list) and len(a) == len(questions):
            return [bool(x) for x in a]
    except Exception as e:
        print(f"    probe call failed: {str(e)[:60]}")
    return None


def _pct(flags):
    return round(100 * sum(flags) / len(flags)) if flags else None


def _second_opinion(system, qa, images, maxpx=768):
    """Re-ask ONLY the probes that failed; a probe must fail TWICE to count.

    Single yes/no VLM votes are volatile (observed: 'tongues out' failing on a
    page where both tongues are clearly out; 'shirt at neckline' failing when
    a scarf covers it). One retry of failures kills those one-off false
    negatives at negligible cost, without loosening real checks — a genuine
    defect fails both votes. Mutates and returns `qa`."""
    failed = [q for q, ok in qa.items() if not ok]
    if not failed:
        return qa
    a2 = _ask(system, failed, images, maxpx=maxpx)
    if a2:
        for q, ok in zip(failed, a2):
            if ok:
                qa[q] = True
    return qa


# Body landmarks bottom-to-top — the answer space for the forced-choice
# relative-height probe. Must contain every landmark plan_v3 can emit.
_LADDER = ["knee", "mid thigh", "hip", "waist", "lower chest", "mid chest",
           "shoulder", "chin", "eye level", "same height or taller"]


def _scale_order_probe(page_bytes, char_refs, p):
    """Coarse relative-height ordering for one cross-species pair.
    Forced-choice on the RELATION, retried once on a miss like the landmark
    probe. Catches the client-visible failures (sheep towering over giraffe,
    goat drawn tiny) without pretending humanoid landmarks apply."""
    small, big = p["small"], p["big"]
    imgs = [_small(page_bytes, maxpx=1024),
            _small(char_refs[small], maxpx=1024),
            _small(char_refs[big], maxpx=1024)]
    expect = (f"{small} should be the shorter one (about {p['fraction']} of "
              f"{big}'s height)." if p.get("fraction") else
              f"{small} and {big} should be nearly the same height — "
              f"neither towers over the other.")
    user = (
        f"Image 1 is a picture-book page; image 2 is {small}'s official "
        f"reference; image 3 is {big}'s.\n"
        f"Locate both in image 1 and judge their OVERALL BODY SCALE relative "
        f"to each other, mentally correcting for pose (bending, sitting, "
        f"yoga poses) and camera distance. {expect}\n"
        f'Reply ONLY JSON: {{"judgeable": true/false, "relation": '
        f'"{small}_shorter_as_expected" | "similar_heights" | '
        f'"{small}_taller" | "{small}_far_too_tiny"}}. judgeable=false ONLY '
        f"if one of them is absent or too hidden to compare.")
    verdict, got = None, "?"
    for _ in range(2):
        try:
            r = llm.chat_json_images(
                "You measure relative character heights in picture-book "
                "illustrations.", user, imgs, mime="image/jpeg")
        except Exception as e:
            print(f"    scale probe failed: {str(e)[:60]}")
            continue
        if not isinstance(r, dict):
            continue
        if r.get("judgeable") is False:
            verdict, got = True, "unjudgeable"
            break
        got = str(r.get("relation", ""))
        ok = {f"{small}_shorter_as_expected"}
        if p["small_cm"] / max(p["big_cm"], 1) >= 0.8:  # near-equal pair —
            ok.add("similar_heights")                   # "similar" is fair
        verdict = got in ok
        if verdict:
            break
    if verdict is None:
        return {}
    return {f"{small} shorter than {big} as expected (measured: {got})": verdict}


def _scale_probe(page_bytes, char_refs, size_pairs):
    """{question: bool} for each co-present pair's relative height.

    Forced-choice, not yes/no: the VLM must PICK which of `big`'s body
    landmarks the top of `small`'s head reaches, and code compares that to
    the locked landmark (±1 step for pose/perspective slack). Asked twice on
    a miss, like _second_opinion, so one volatile vote can't fail a page."""
    out = {}
    for p in (size_pairs or []):
        small, big = p["small"], p["big"]
        if small not in char_refs or big not in char_refs:
            continue
        # Near-equal pairs (order_only, no landmark) still get the coarse
        # ordering probe — an inversion (pig towering over goat) must not
        # slip through just because the gap was too small for a landmark.
        if p.get("order_only"):
            out.update(_scale_order_probe(page_bytes, char_refs, p))
            continue
        # Cross-species pairs get a COARSE ordering probe, not a landmark:
        # the ladder assumes humanoid proportions (hip at ~52% of height) —
        # a giraffe's hip sits at ~35%, so "goat's head at giraffe's hip"
        # is unanswerable and false-failed every Namaste yoga page.
        if p.get("small_species") and p.get("big_species") \
                and p["small_species"] != p["big_species"]:
            out.update(_scale_order_probe(page_bytes, char_refs, p))
            continue
        want_lm = p["landmark"].replace("-", " ")
        if want_lm not in _LADDER:
            continue
        want = _LADDER.index(want_lm)
        imgs = [_small(page_bytes, maxpx=1024),
                _small(char_refs[small], maxpx=1024),
                _small(char_refs[big], maxpx=1024)]
        opts = ", ".join(f'"{l}"' for l in _LADDER)
        user = (
            f"Image 1 is a picture-book page; image 2 is {small}'s official "
            f"reference sheet; image 3 is {big}'s.\n"
            f"Locate {small} and {big} in image 1. Imagine both standing "
            f"fully upright side by side on the same ground plane — mentally "
            f"correct for stooping, bent knees, sitting, running pose, and "
            f"for one being nearer the camera than the other.\n"
            f"Standing like that, where would the TOP of {small}'s head "
            f"reach on {big}'s body?\n"
            f'Reply ONLY JSON: {{"judgeable": true/false, "landmark": one of '
            f"[{opts}]}}. judgeable=false ONLY if one of them is absent or "
            f"too hidden to compare.")
        verdict, got = None, "?"
        for _ in range(2):  # a pass on either vote passes (volatility guard)
            try:
                r = llm.chat_json_images(
                    "You measure relative character heights in "
                    "picture-book illustrations.", user, imgs,
                    mime="image/jpeg")
            except Exception as e:
                print(f"    scale probe failed: {str(e)[:60]}")
                continue
            if not isinstance(r, dict):
                continue
            if r.get("judgeable") is False:
                verdict, got = True, "unjudgeable"
                break
            lm = (str(r.get("landmark", "")).strip().lower()
                  .replace("_", " ").replace("-", " "))
            lm = {"chest": "mid chest", "neck": "chin",
                  "head": "same height or taller"}.get(lm, lm)
            got = lm
            idx = _LADDER.index(lm) if lm in _LADDER else None
            verdict = idx is not None and abs(idx - want) <= 1
            if verdict:
                break
        if verdict is not None:  # both calls errored -> excluded (fail-open)
            out[f"{small}'s head reaches {big}'s {want_lm} "
                f"(measured: {got})"] = verdict
    return out


_STANCE_EXPECT = {"feral": "natural_four_legged_animal",
                  "anthro": "upright_person_like_biped"}


def _proportion_probe(page_bytes, char_refs, stances=None, panels=False):
    """{question: bool} — each character's BODY PROPORTIONS vs their OWN
    reference sheet. Catches the solo-page drift the pair-based scale gate
    can't see (Namaste: the goat's legs shortened and body fattened on pages
    where nothing else anchored him). Forced-choice with one retry (yes/no
    probes agree with themselves). The stance lock (anthro vs feral — with a
    mid-pose escape so yoga poses can't false-fail) and the per-vignette
    consistency check ride the same call."""
    out = {}
    stances = stances or {}
    for name, ref in char_refs.items():
        imgs = [_small(page_bytes, maxpx=1024), _small(ref, maxpx=1024)]
        want_st = _STANCE_EXPECT.get(str(stances.get(name, "")).strip().lower())
        user = (
            f"Image 1 is a picture-book page; image 2 is {name}'s official "
            f"reference sheet.\n"
            f"Compare {name}'s BODY PROPORTIONS in the page to the reference "
            f"— leg length relative to body, body girth, head-to-body ratio "
            f"— mentally correcting for pose and camera distance.\n"
            f'Reply ONLY JSON: {{"judgeable": true/false, '
            f'"build": "same_as_reference" | "legs_shorter_or_stockier" | '
            f'"noticeably_fatter" | "noticeably_thinner_or_lankier" | '
            f'"head_too_large_or_small"'
            + (f', "stance": "natural_four_legged_animal" | '
               f'"upright_person_like_biped" | "mid_pose_cannot_tell" — '
               f"judge {name}'s NATURAL carriage; if {name} is deliberately "
               f"performing a yoga pose, stretch or exercise (on or near a "
               f'mat), answer "mid_pose_cannot_tell"'
               if want_st else "")
            + (', "consistent_across_vignettes": "same_in_all" | '
               '"differs_between_vignettes" | "appears_once"'
               if panels else "")
            + f'}}. judgeable=false ONLY if {name} is absent or too hidden '
              f'to judge.')
        vb = vs = vv = None
        gb = gs = gv = "?"
        for _ in range(2):  # a pass on either vote passes (volatility guard)
            try:
                r = llm.chat_json_images(
                    "You measure character body proportions in picture-book "
                    "illustrations.", user, imgs, mime="image/jpeg")
            except Exception as e:
                print(f"    proportion probe failed: {str(e)[:60]}")
                continue
            if not isinstance(r, dict):
                continue
            if r.get("judgeable") is False:
                vb = vs = vv = True
                gb = gs = gv = "unjudgeable"
                break
            gb = str(r.get("build", ""))
            vb = vb or (gb == "same_as_reference")
            if want_st:
                gs = str(r.get("stance", ""))
                vs = vs or (gs in (want_st, "mid_pose_cannot_tell"))
            if panels:
                gv = str(r.get("consistent_across_vignettes", ""))
                vv = vv or (gv in ("same_in_all", "appears_once"))
            if vb and (vs or not want_st) and (vv or not panels):
                break
        if vb is not None:
            out[f"{name} proportions match the sheet "
                f"(measured: {gb})"] = bool(vb)
        if want_st and vs is not None:
            out[f"{name} stance is {stances[name]} "
                f"(measured: {gs})"] = bool(vs)
        if panels and vv is not None:
            out[f"{name} identical in every vignette "
                f"(measured: {gv})"] = bool(vv)
    return out


def _setting_probe(page_bytes, setting_ref, manifest):
    """(floor_qa, props_qa) — the page vs the location's locked manifest.
    Floor is a forced-choice degree judgment against the setting reference;
    fixed props are occlusion-first yes/no probes (the items pattern) with a
    second opinion. Catches the Namaste drift: floor changing almost every
    page, covered candles turning open and multiplying."""
    sysm = "You verify location continuity in picture books."
    out_floor, out_props = {}, {}
    imgs = [page_bytes] + ([setting_ref] if setting_ref else [])
    floor = (manifest or {}).get("floor")
    if floor and setting_ref:
        user = (
            f"Image 1 is a picture-book page; image 2 is the official "
            f"reference of the same location. The locked floor is: {floor}.\n"
            f"Judge the FLOOR shown in the page against the reference, "
            f"correcting for camera angle and lighting.\n"
            f'Reply ONLY JSON: {{"floor": '
            f'"same_material_and_colour_as_reference" | "different_material" '
            f'| "different_colour" | "floor_not_visible"}}')
        got = None
        for _ in range(2):
            try:
                r = llm.chat_json_images(
                    sysm, user, [_small(b, maxpx=1024) for b in imgs],
                    mime="image/jpeg")
            except Exception as e:
                print(f"    setting probe failed: {str(e)[:60]}")
                continue
            if isinstance(r, dict):
                got = str(r.get("floor", ""))
                if got in ("same_material_and_colour_as_reference",
                           "floor_not_visible"):
                    break
        if got is not None:
            out_floor[f"floor matches locked spec (measured: {got})"] = (
                got in ("same_material_and_colour_as_reference",
                        "floor_not_visible"))
    pq = []
    for p in (manifest or {}).get("fixed_props") or []:
        if not isinstance(p, dict) or not p.get("item"):
            continue
        d = f" ({p['design']})" if p.get("design") else ""
        pq.append(
            f"FIRST check: is the spot where the {p['item']} belong visible "
            f"in the page (the framing may crop it out)? If out of frame, "
            f"answer true (cannot be judged). ONLY if visible: does the page "
            f"show exactly {p.get('count', 1)} {p['item']}{d}, matching the "
            f"locked design — not more, not fewer, not a redesigned version?")
    if pq:
        pa = _ask(sysm, pq, imgs, maxpx=1024)
        if pa is not None:
            out_props = _second_opinion(sysm, dict(zip(pq, pa)), imgs,
                                        maxpx=1024)
    return out_floor, out_props


def score_page(page_bytes, *, contract, char_refs, style_plate=None,
               char_items=None, minimal_page=False, size_pairs=None,
               stances=None, panels=False, present=None,
               setting_ref=None, setting_manifest=None,
               skip_char_probes=False):
    """Probe-based scores for one page.

    char_refs: {name: sheet_bytes} for present high-consistency characters.
    char_items: {name: [sig_item dict, ...]} from items_v7 — one binary probe
    PER item, scored as its own `items` category so a single missing chest
    logo can't hide inside a passing identity average.
    size_pairs: plan_v3.size_pairs output — cross-character relative-height
    probes, scored as their own `scale` category. Every other probe compares
    a character to their OWN reference, so a correctly-drawn Maya rendered
    at toddler size next to Grandpa passed the gate (Maya book, v7.6).
    Returns {"identity": 0-100|None, "items": ..., "facts": ..., "anatomy": ...,
             "style": ..., "scale": ..., "total": mean of available categories,
             "detail": {...}}."""
    detail = {}
    char_items = char_items or {}

    # identity — page first, then each reference sheet, with roles in the text.
    # Named-character COUNT probes live here too: "exactly one Bilbo" is only
    # answerable with Bilbo's sheet in view — asked image-free (in the facts
    # call) the VLM can't tell two look-alikes apart and fails from
    # uncertainty (observed: every duo page failing 'exactly 1 Bilbo').
    # Per-item probes ride in the SAME batched call (same images, near-zero
    # extra cost) but are scored separately.
    # Union with the plan's cast list: a contract-extraction miss must not
    # silently drop the "exactly ONE pig" presence probe for a listed
    # character (Namaste p13: the pig simply vanished).
    named = ({c["who"] for c in contract["cast"]}
             | set(present or [])) & set(char_refs)
    idq, itq = [], []
    # skip_char_probes: the v8 per-character comparison audit (audit_v8)
    # replaces the batched identity/items yes-no probes AND the proportion
    # probe for sheet-holding characters — those yes-no probes passed pages
    # with characters entirely absent (agreement bias).
    for i, name in enumerate(char_refs if not skip_char_probes else {}, 2):
        if name in named:
            idq.append(
                f"Image 1 is the page; image {i} is {name}'s official "
                f"reference. Does exactly ONE character matching image {i}'s "
                f"design appear in the page (not zero, not two)?")
        idq += [
            f"Image 1 is the page; image {i} is {name}'s official reference. "
            f"Does {name} in the page have the SAME face/muzzle shape and head "
            f"proportions as the reference (not merely the same species)?",
            f"Comparing image 1 to image {i}: is {name}'s body build and "
            f"apparent age the SAME as the reference — not younger/more "
            f"puppy-like, and not visibly OLDER, heavier-set or more aged in "
            f"the face than the reference shows?",
        ]
        # Coarse catch-all item probe ONLY for characters without a sig_items
        # manifest — with per-item probes it is redundant, and its dog-shaped
        # examples ("hat/cap, bandana") false-fail hatless humans.
        if not char_items.get(name):
            idq.append(
                f"Comparing image 1 to image {i}: does {name} wear every "
                f"signature item shown in the reference (hat/cap in the same "
                f"colour, bandana, accessories)?")
        # `when`-conditional items (helmet only when riding) are skipped — the
        # gate cannot verify the condition from one page.
        for it in char_items.get(name, []):
            if it.get("when"):
                continue
            # Occlusion branch FIRST: phrased item-first ("does X correctly
            # show...?") the VLM answered false for body parts cropped out of
            # frame, ignoring a trailing escape clause (page 9: Dad framed
            # from the waist down -> chest logo "missing").
            itq.append(
                f"Image 1 is the page; image {i} is {name}'s official "
                f"reference. FIRST check: is the body spot where this item "
                f"sits visible for {name} in the page? If it is out of frame, "
                f"turned away or blocked by something, answer true (cannot "
                f"be judged). ONLY if the spot is clearly visible, judge: "
                f"does it correctly show {it['desc']} — true if it matches, "
                f"false if the item is wrong, missing, or an uncalled-for "
                f"logo/print was added.")
        # The manifest guards listed items' PRESENCE; this guards against
        # INVENTED extras (observed: a flat cap + chunky muffler appearing
        # on a bare-headed character for one page).
        if char_items.get(name):
            # Accessories only — a scene-appropriate garment change (indoor
            # clothes) is legitimate; an invented hat/eyewear/neckwear is not.
            itq.append(
                f"Image 1 is the page; image {i} is {name}'s official "
                f"reference. Is {name} FREE of invented ACCESSORIES the "
                f"reference does not show — no added hat/cap, no added "
                f"eyeglasses/sunglasses, and no added scarf/muffler/neckwear "
                f"that {name} does not wear in the reference?")
    # 1024px so small worn details (a chest logo) stay legible to the probes.
    ans = _ask("You verify character consistency for a picture book.",
               idq + itq, [page_bytes] + list(char_refs.values()), maxpx=1024)
    ida = ans[:len(idq)] if ans is not None else None
    ita = ans[len(idq):] if ans is not None else None
    identity, items = None, None
    # scale — cross-character relative height, its own category: page 5 of
    # the Maya book drew a spec-perfect Maya at Grandpa's HIP and every
    # per-character probe passed. Uses a forced-choice measurement call, not
    # yes/no probes — tested on the Maya book, yes/no phrasing passed every
    # page including the hip-height one (VLM agreement bias).
    scale = None
    if size_pairs:
        detail["scale"] = _scale_probe(page_bytes, char_refs, size_pairs)
        if detail["scale"]:
            scale = _pct(list(detail["scale"].values()))
    # proportion — each character vs their OWN sheet (solo-page drift the
    # pair-based scale category can't see), + stance lock + vignette
    # consistency. Its own category: failures need a full regenerate, not a
    # surgical edit.
    proportion = None
    if char_refs and not skip_char_probes:
        pd = _proportion_probe(page_bytes, char_refs, stances=stances,
                               panels=panels)
        if pd:
            detail["proportion"] = pd
            proportion = _pct(list(pd.values()))
    if ida is not None:
        detail["identity"] = _second_opinion(
            "You verify character consistency for a picture book.",
            dict(zip(idq, ida)), [page_bytes] + list(char_refs.values()), maxpx=1024)
        identity = _pct(list(detail["identity"].values())) if idq else None
    if ita is not None and itq:
        detail["items"] = _second_opinion(
            "You verify character consistency for a picture book.",
            dict(zip(itq, ita)), [page_bytes] + list(char_refs.values()), maxpx=1024)
        items = _pct(list(detail["items"].values()))

    # facts — from the contract, page only. Named characters with reference
    # sheets are counted in the identity call above; only descriptor-based
    # cast entries ("adults", "children") are countable without a reference.
    fq = []
    for c in contract["cast"]:
        if c["who"] in named:
            continue
        fq.append(f"Does the image contain exactly {c['count']} {c['who']} "
                  f"(count carefully — not {c['count'] - 1}, not {c['count'] + 1})?")
    for p in contract["props"]:
        fq.append(f"Does the image contain exactly {p['count']} {p['item']}?")
    for s in contract["states"]:
        fq.append(f"Does the image clearly show: {s}?")
    # Spec-anchored outfit probes for present characters WITHOUT a sheet
    # (sig_items src='spec' — e.g. a backfilled recurring sheep): text-only,
    # so they ride the page-only facts call instead of the sheet batch.
    for name, its in (char_items or {}).items():
        if name in char_refs:
            continue
        for it in its:
            if it.get("when"):
                continue
            fq.append(
                f"FIRST check: is {name} visible in the image? If absent or "
                f"too hidden, answer true (cannot be judged). ONLY if "
                f"visible: does {name} correctly show {it['desc']}?")
    fa = _ask("You verify that an illustration matches its story text.",
              fq, [page_bytes])
    facts = None
    if fa is not None:
        detail["facts"] = _second_opinion(
            "You verify that an illustration matches its story text.",
            dict(zip(fq, fa)), [page_bytes])
        facts = _pct(list(detail["facts"].values())) if fq else None

    # anatomy — the known artifact classes, page only (questions phrased so
    # TRUE = good, matching the other categories)
    aq = [
        "Does every character have the correct number of limbs (no extra or "
        "missing arms, legs, paws, hands)?",
        "Is every limb attached to a body (no floating or disembodied hands, "
        "legs or body parts anywhere in the image)?",
        "Does every hand or arm in the image visibly belong to a person who "
        "is at least partially in frame (no hands reaching in from nowhere, "
        "and no leashes/objects held by nobody)?",
        "Do all REAL animals have animal anatomy (no human-like arms, hands or "
        "legs on any real animal)? A costumed MASCOT standing or waving like a "
        "person is fine FOR POSTURE ONLY — but EXTRA, duplicated or floating "
        "legs still count as WRONG even on a mascot.",
        "Does each distinct character appear only once (no duplicated copies "
        "of the same character)?",
        "Is the image free of READABLE written words, numbers and legible "
        "signage inside the artwork? A single-letter emblem that is part of a "
        "character's official design (e.g. a cap logo) and unreadable "
        "background scribbles do NOT count as text.",
    ]
    if not minimal_page:
        # Matter pages (title/dedication/about/backmatter) are deliberately
        # minimal — a small vignette in calm empty space is their DESIGN, so
        # the full-bleed requirement applies to story pages only.
        aq.append(
            "Does the artwork fill the ENTIRE square edge-to-edge — no "
            "margins, frames, drawn borders, drop shadows, or 3D book/canvas "
            "mock-up edges around the scene?")
    aa = _ask("You inspect AI illustrations for anatomy artifacts.",
              aq, [page_bytes])
    anatomy = None
    if aa is not None:
        detail["anatomy"] = _second_opinion(
            "You inspect AI illustrations for anatomy artifacts.",
            dict(zip(aq, aa)), [page_bytes])
        anatomy = _pct(list(detail["anatomy"].values()))

    # Per-figure ZOOM anatomy pass — catches extra/floating limbs the page-scale
    # probe above is blind to on small/clothed figures (giraffe/zebra 6 legs on
    # pages the page-probe scored 100). Runs for EVERY located figure, including
    # background animals without reference sheets. Takes the stricter (min)
    # score and records each defect's bounding box for masked inpainting repair.
    za = anatomy_v8.audit_anatomy(page_bytes, rules=_canon())
    if za.get("score") is not None:
        anatomy = za["score"] if anatomy is None else min(anatomy, za["score"])
        if za["defects"]:
            detail["anatomy_zoom_defects"] = [
                {"species": d["species"], "box": d["box"], "issue": d["issue"]}
                for d in za["defects"]]

    # Cast presence — reuse the figures the anatomy pass already located (no
    # extra VLM call) to catch a declared character that the render DROPPED
    # (the "background giraffe silently vanished on a later page" defect). The
    # located species are also recorded so a cross-page continuity pass can
    # later flag a figure that was present earlier and disappeared.
    if za.get("figures"):
        detail["cast_located"] = [f.get("species") for f in za["figures"]]
        miss = anatomy_v8.missing_cast(
            za["figures"], present or [],
            name_to_species=(_canon() or {}).get("_species_map"))
        if miss:
            detail["cast_missing"] = miss
            print(f"    [cast] MISSING declared character(s): {', '.join(miss)}")
            # a dropped character is a factual defect — fold into facts
            drop = round(100 * len(miss) / max(len(present or []), 1))
            facts = (100 - drop) if facts is None else min(facts, 100 - drop)

    # style — page + style plate
    style = None
    if style_plate:
        sq = [
            "Image 1 is the page, image 2 is the book's style reference. Is "
            "the page in the SAME rendering style family (linework, shading, "
            "colour handling) as the reference?",
            "Is image 1 an illustrated/painterly image and NOT photorealistic "
            "or 3D-render-like?",
        ]
        sa = _ask("You compare illustration styles.", sq,
                  [page_bytes, style_plate])
        style = None
        if sa is not None:
            detail["style"] = _second_opinion(
                "You compare illustration styles.",
                dict(zip(sq, sa)), [page_bytes, style_plate])
            style = _pct(list(detail["style"].values()))

    # setting — page vs the location's locked floor + fixed-prop manifest.
    setting = None
    if setting_manifest and (setting_manifest.get("floor")
                             or setting_manifest.get("fixed_props")):
        fl, pr = _setting_probe(page_bytes, setting_ref, setting_manifest)
        if fl or pr:
            detail["setting_floor"] = fl
            detail["setting_props"] = pr
            setting = _pct(list(fl.values()) + list(pr.values()))

    cats = {"identity": identity, "items": items, "facts": facts,
            "anatomy": anatomy, "style": style, "scale": scale,
            "proportion": proportion, "setting": setting}
    avail = [v for v in cats.values() if v is not None]
    return {**cats,
            "total": round(sum(avail) / len(avail)) if avail else None,
            "detail": detail}
