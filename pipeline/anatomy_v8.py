"""Per-figure anatomy detection — catches the extra-leg / floating-limb
artifacts the page-scale gate probe misses.

WHY THIS EXISTS
---------------
`gate_v7`'s anatomy probe asks "does every character have the right number of
limbs?" while looking at the WHOLE page (`gate_v7.py:644`, comment: "page
only"). On a wide scene a giraffe/zebra is a small, partly-clothed figure, so
the downscaled full page can't resolve its legs — the model answers "yes" and
the page scores anatomy 100 with a visible 6-legged animal (namaste pages 3,
18). The v8 audit already learned this lesson for identity/coat ("page-scale
audits are blind → per-character zoom crop") but anatomy was never migrated,
AND the per-character audit only runs for cast that HAVE reference sheets — so
incidental background animals (the yoga-class giraffe/zebra) are never checked
at all.

This module fixes both: it LOCATES every prominent figure on the page (sheet
or not) and runs a focused limb-count question on each figure's ZOOM CROP,
where legs are actually countable. Each defect carries its bounding box, so
the repair step can later inpaint just that region instead of regenerating the
whole page.

Design notes
------------
- Two-stage (locate → per-figure check) mirrors audit_v8's zoom machinery.
- Returns a score compatible with gate_v7's 0-100 categories plus a structured
  `defects` list ({species, box, issue, leg_count}) for the repair loop.
- Vision-cost aware: one locate call + one call per prominent figure. Small
  scenes cost 2-3 calls; this is the price of actually seeing the legs.
- Toggle via env ANATOMY_ZOOM (on|off, default on). `off` falls back to the
  old page-only behaviour so nothing breaks if the budget is tight.
"""

import io
import os

from PIL import Image

from . import llm

ENABLED = os.getenv("ANATOMY_ZOOM", "on").strip().lower() != "off"
# a figure smaller than this fraction of the page is background clutter we
# don't hold to a limb count (distant scenery figures the scene calls for).
MIN_PROMINENCE = float(os.getenv("ANATOMY_MIN_PROMINENCE", "0.03"))

_LOCATE_SYSTEM = (
    "You locate every distinct animal or person FIGURE in a children's "
    "picture-book illustration so each can be inspected close-up. Include "
    "clothed/anthropomorphic animals (a zebra or giraffe standing on two legs "
    "in a yoga outfit is still a figure). Exclude plants, props and furniture.")

_CHECK_SYSTEM = (
    "You inspect ONE cropped animal/character from a picture-book for anatomy "
    "artifacts. Look ONLY at this crop and count carefully. A generative model "
    "commonly draws EXTRA or DUPLICATED legs on four-legged animals and "
    "floating/disembodied limbs — your job is to catch exactly that.")


def _box_area(b):
    x0, y0, x1, y1 = b
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _crop(page_bytes: bytes, box, margin=0.12) -> bytes:
    """Crop the page to a figure's normalised box (+margin), return PNG bytes."""
    im = Image.open(io.BytesIO(page_bytes)).convert("RGB")
    W, H = im.size
    x0, y0, x1, y1 = box
    x0 = max(0.0, x0 - margin); y0 = max(0.0, y0 - margin)
    x1 = min(1.0, x1 + margin); y1 = min(1.0, y1 + margin)
    crop = im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
    # upscale small crops so limbs are legible to the VLM
    if min(crop.size) < 320 and min(crop.size) > 0:
        s = 320 / min(crop.size)
        crop = crop.resize((int(crop.width * s), int(crop.height * s)),
                           Image.LANCZOS)
    buf = io.BytesIO(); crop.save(buf, format="PNG")
    return buf.getvalue()


def locate_figures(page_bytes: bytes) -> list[dict]:
    """Return [{species, box:[x0,y0,x1,y1]}] for every distinct figure."""
    user = (
        "List every distinct animal/person figure. For each return its species "
        "and a tight normalised bounding box (0..1, origin top-left). "
        'Return JSON: {"figures":[{"species":"giraffe","box":[x0,y0,x1,y1]}]}')
    try:
        r = llm.chat_json_images(_LOCATE_SYSTEM, user, [page_bytes],
                                 max_tokens=800)
    except Exception as e:                                   # noqa: BLE001
        print(f"    anatomy locate failed: {str(e)[:60]}")
        return []
    figs = r.get("figures") if isinstance(r, dict) else None
    out = []
    for f in figs or []:
        b = f.get("box")
        if not (isinstance(b, list) and len(b) == 4):
            continue
        b = [min(max(float(v), 0.0), 1.0) for v in b]
        if _box_area(b) < MIN_PROMINENCE:          # tiny/distant → skip
            continue
        out.append({"species": str(f.get("species", "figure")), "box": b})
    return out


def _fig_bad(v: dict, expected: str | None = None) -> bool:
    """Is a single per-figure verdict a defect?

    The real artifact is an INCOHERENT BODY PLAN: a human-like torso + arms on
    a full four-legged animal body (4 legs + 2 arms = the "6 legs" the client
    sees). VLMs answer that as a yes/no coherence question (they can't count
    legs past 4). If `expected` (canon plan) is given, a coherent body plan
    that CONTRADICTS canon (drawn quadruped when it must be bipedal) also
    counts — but a floor/yoga pose is tolerated by the prompt, not flagged."""
    if v.get("has_human_torso_and_four_legs") or v.get("extra_body_or_hindquarters"):
        return True
    plan = str(v.get("body_plan", "")).lower()
    if plan in ("incoherent_hybrid", "hybrid"):
        return True
    lc = v.get("leg_count")
    if isinstance(lc, (int, float)) and lc > 4:
        return True
    if v.get("extra_or_floating_limb"):
        return True
    if expected and plan in ("upright_bipedal", "natural_quadruped") \
            and plan != expected:
        return True
    return False


def check_figure(page_bytes: bytes, fig: dict, expected: str | None = None) -> dict:
    """Zoom on one figure and judge its body-plan coherence. `expected` is the
    canon body plan for this character ("upright_bipedal"/"natural_quadruped");
    when given, the check judges the figure AGAINST it and tolerates floor/yoga
    poses — which kills the false positive where a bipedal character on hands
    and knees looked quadrupedal. Returns the verdict + `ok` + `issue` + box."""
    crop = _crop(page_bytes, fig["box"])
    sp = fig["species"]
    exp_line = ""
    if expected == "upright_bipedal":
        exp_line = (
            f"CANON: this {sp} is an UPRIGHT BIPEDAL character — it should have "
            f"exactly TWO legs and TWO arms (human-like torso, animal head). "
            f"A bipedal character in a yoga/floor pose (hands and feet on the "
            f"ground, kneeling, stretching, downward-dog) is STILL upright_"
            f"bipedal and is NOT a defect — do not mistake a floor pose for "
            f"four legs. BUT it IS a defect (even in a floor pose) if the "
            f"character has a SECOND body or an extra animal hindquarters/"
            f"rump with extra legs grafted onto its side or back, or any "
            f"extra/duplicated/floating legs beyond its two.\n")
    elif expected == "natural_quadruped":
        exp_line = (f"CANON: this {sp} is a NATURAL FOUR-LEGGED animal — 4 "
                    f"legs, no human arms. The defect is >4 legs or human arms.\n")
    user = (
        exp_line +
        f"Judge THIS crop's BODY PLAN — a coherent character is ONE of:\n"
        f"  • upright_bipedal: human-like torso, stands/poses on 2 legs, 2 arms\n"
        f"  • natural_quadruped: 4 animal legs, animal body, NO human arms\n"
        f"An INCOHERENT_HYBRID has BOTH at once — a human-like torso with arms "
        f"on top of a full FOUR-LEGGED animal body (so ~4 legs AND 2 arms "
        f"together), or extra/duplicated/floating limbs.\n"
        f'Return JSON: {{"body_plan": "upright_bipedal" | "natural_quadruped" '
        f'| "incoherent_hybrid", '
        f'"has_human_torso_and_four_legs": true|false, '
        f'"extra_body_or_hindquarters": true|false, '
        f'"leg_count": <int>, "extra_or_floating_limb": true|false, '
        f'"note": "<what is wrong, or \'ok\'>"}}\n'
        f"Two key errors to catch: (1) animal hind legs AND human arms on the "
        f"same body; (2) a second body / extra animal rump-and-legs attached "
        f"beside or behind the character.")
    votes = []
    for _ in range(3):                     # majority vote — counting is noisy
        try:
            r = llm.chat_json_images(_CHECK_SYSTEM, user, [crop], max_tokens=400)
        except Exception:                                   # noqa: BLE001
            continue
        if isinstance(r, dict):
            votes.append(r)
        if len(votes) >= 2 and (_fig_bad(votes[0], expected) == _fig_bad(votes[1], expected)):
            break
    if not votes:
        return {"ok": None, "species": sp, "box": fig["box"], "issue": "no verdict"}

    bad_votes = sum(_fig_bad(v, expected) for v in votes)
    bad = bad_votes > len(votes) / 2
    rep = max((v for v in votes if _fig_bad(v, expected) == bad),
              key=lambda v: len(str(v)), default=votes[0])
    lc = rep.get("leg_count")
    issue = None
    if bad:
        parts = []
        if rep.get("has_human_torso_and_four_legs") or \
                str(rep.get("body_plan", "")).lower().startswith(("incoherent", "hybrid")):
            parts.append("incoherent body plan: human torso/arms on a "
                         "four-legged animal body")
        if rep.get("extra_body_or_hindquarters"):
            parts.append("extra second body / hindquarters attached")
        if isinstance(lc, (int, float)) and lc > 4:
            parts.append(f"{int(lc)} legs (max 4)")
        if rep.get("extra_or_floating_limb"):
            parts.append("extra/floating limb")
        issue = f"{sp}: " + (", ".join(parts) or str(rep.get("note", "anatomy defect")))
    return {"ok": not bad, "species": sp, "box": fig["box"],
            "body_plan": rep.get("body_plan"), "leg_count": lc,
            "issue": issue, "raw": rep}


def audit_anatomy(page_bytes: bytes, rules: dict | None = None) -> dict:
    """Full per-figure anatomy pass for a page.

    `rules` = canon_rules dict; when given, each figure is judged against its
    canon body plan (fixes the floor-pose false positive). Returns
    {"score": 0-100|None, "defects": [...], "checked": n, "figures": [...]}.
    score = % of checked figures that are coherent; None if nothing located.
    """
    if not ENABLED:
        return {"score": None, "defects": [], "checked": 0, "figures": []}
    figs = locate_figures(page_bytes)
    if not figs:
        return {"score": None, "defects": [], "checked": 0, "figures": []}
    from . import canon_rules as _cr
    verdicts = [check_figure(
        page_bytes, f,
        expected=_cr.expected_plan(f.get("species", ""), rules) if rules else None)
        for f in figs]
    graded = [v for v in verdicts if v.get("ok") is not None]
    if not graded:
        return {"score": None, "defects": [], "checked": 0, "figures": figs}
    defects = [v for v in graded if v["ok"] is False]
    score = round(100 * (1 - len(defects) / len(graded)))
    for d in defects:
        print(f"    [anatomy-zoom] DEFECT {d['issue']}  box={[round(x,2) for x in d['box']]}")
    return {"score": score, "defects": defects, "checked": len(graded),
            "figures": figs}


def locate_anomaly(page_bytes: bytes, fig: dict, issue: str):
    """Box of ONLY the anomalous part of a defect (e.g. the extra hindquarters/
    legs), so an ERASE repair removes just that and preserves the real
    character. Returns a normalised [x0,y0,x1,y1] or None. Zooms on the figure
    (wide margin) and asks the VLM to box the extra/duplicated part."""
    crop_box = fig["box"]
    user = (
        f"This crop contains a {fig.get('species','animal')} that has an "
        f"ANATOMY DEFECT: {issue}. Return a TIGHT normalised bounding box "
        f"(0..1 over THIS FULL PAGE image) around ONLY the extra/duplicated/"
        f"anomalous part (the extra body, extra legs, or floating limb) — NOT "
        f"the whole correct character, and NOT any neighbouring character.\n"
        f'Return JSON: {{"anomaly_box":[x0,y0,x1,y1]}}')
    try:
        r = llm.chat_json_images(_CHECK_SYSTEM, user, [page_bytes], max_tokens=200)
    except Exception:                                        # noqa: BLE001
        return None
    b = r.get("anomaly_box") if isinstance(r, dict) else None
    if isinstance(b, list) and len(b) == 4:
        return [min(max(float(v), 0.0), 1.0) for v in b]
    return None


def missing_cast(figures: list[dict], expected: list[str],
                 name_to_species: dict | None = None) -> list[str]:
    """Which expected characters are NOT among the located figures.

    Catches the "character silently vanished" defect. CRITICAL: the vision
    locator labels figures by SPECIES ("zebra", "giraffe") while the scene
    cast is by NAME ("Twiggy", "Tallia"), so we must resolve each name to its
    species (via `name_to_species` from canon) before comparing — otherwise
    every named character reads as missing. Falls back to name matching when
    a species isn't known. Matching is loose (substring) so 'giraffe' ≈ 'baby
    giraffe'.
    """
    name_to_species = name_to_species or {}
    located = " ".join(f.get("species", "").lower() for f in figures)
    miss = []
    for name in expected or []:
        nm = str(name).strip()
        if not nm:
            continue
        # what to look for: the character's species if known, else its name
        target = (name_to_species.get(nm) or nm).lower()
        words = [w for w in target.replace("-", " ").split() if len(w) > 2]
        if not any(w in located for w in words) and target not in located:
            miss.append(nm)
    return miss
