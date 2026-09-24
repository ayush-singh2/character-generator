"""Shared helpers over a v3 art plan (characters.toon / scenes.toon).

Generic across books: tolerates both the rich parse_v3 schema (style dict,
appearance/outfit/consistency fields, lookalike_groups) and the hand-written
Bilbo schema (style string, species/hat/bandana). Downstream stages
(refs/generate/correct) read the plan through here so none of them hardcode a
particular book.
"""

import os

from . import charspec, toon_io

# Base working dir for a book version; override with V3_DIR to run versions
# side-by-side (e.g. V3_DIR=v3b) without overwriting an existing v3/.
BASE = os.getenv("V3_DIR", "v3")
DATA = f"{BASE}/data"
REFS = f"{BASE}/refs"
ART = f"{BASE}/output/art"
PAGES = f"{BASE}/output/pages"
OUT = f"{BASE}/output"


def slug(name):
    # keep alphanumerics and hyphens (so "6-7" stays "6-7"); others -> "_"
    return "".join(ch.lower() if (ch.isalnum() or ch == "-") else "_"
                   for ch in name).strip("_")


def load(data_dir=DATA):
    chars = toon_io.load(f"{data_dir}/characters.toon")
    scenes = toon_io.load(f"{data_dir}/scenes.toon")
    return {
        "style": chars.get("style", ""),
        "characters": chars.get("characters", []),
        "groups": chars.get("lookalike_groups", []),
        "by": {c["name"]: c for c in chars.get("characters", [])},
        "title": scenes.get("title", ""),
        "author": scenes.get("author", ""),
        "settings": scenes.get("settings", []),
        "settings_by": {s.get("key"): s for s in scenes.get("settings", []) if s.get("key")},
        "scenes": scenes.get("scenes", []),
    }


def scene_setting(plan, sc):
    """The locked setting dict for a scene (by its setting_key), or None."""
    return plan.get("settings_by", {}).get(sc.get("setting_key"))


def style_text(plan):
    s = plan["style"]
    if isinstance(s, str):
        return s
    parts = [s.get(k, "") for k in
             ("name", "medium", "linework", "palette", "lighting", "mood", "influences")]
    return "; ".join(p for p in parts if p)


def _appearance(c):
    """Best available appearance description for any schema."""
    bits = []
    for k in ("appearance", "hair", "outfit", "species", "hat", "bandana"):
        v = c.get(k)
        if v:
            bits.append(v)
    return ", ".join(bits)


def char_lock(c):
    # Prefer the exact locked_spec (deterministic, hex-precise) when present — this
    # is the single identity source every stage (refs/generate/correct/judge)
    # speaks from, so a character can't drift. Fall back to free-text appearance.
    if charspec.has_spec(c):
        return charspec.serialize(c["locked_spec"], c.get("name", ""))
    d = c.get("distinguishing_features") or c.get("distinguish") or ""
    tail = f" ({d})" if d else ""
    return f"{c['name']}: {_appearance(c)}{tail}"


def present_locks(plan, present):
    return "; ".join(char_lock(plan["by"][n]) for n in present if n in plan["by"])


def is_high(c):
    return c.get("consistency", "high") == "high"


def high_characters(plan):
    return [c for c in plan["characters"] if is_high(c)]


def group_for(plan, present):
    """The look-alike group whose members are ALL on this page (or None)."""
    for g in plan["groups"]:
        members = g.get("members", [])
        if members and all(m in present for m in members):
            return g
    return None


def scene_desc(sc):
    """Full illustration description for a scene, across both schemas."""
    parts = [sc.get(k) for k in ("setting", "action", "mood", "camera")]
    combined = ". ".join(p for p in parts if p)
    return combined or sc.get("scene", "")


def scene_text(sc):
    return sc.get("text", "")


def wants_panels(sc):
    """True when the art plan EXPLICITLY calls for a multi-panel page (collage,
    montage, vignettes). The author's shot list is authoritative — on these
    pages the one-unified-scene rule and the split-panel judge must stand down,
    or the pipeline fights its own plan (burning paid retries and 'fixing'
    intended layouts)."""
    d = (scene_desc(sc) + " " + str(sc.get("author_note", ""))).lower()
    # "vignettes"/"panels" (plural or "-panel composition") mean layout; a
    # singular "vignette effect" is a camera/edge-darkening term — not panels.
    # "spot illustrations" is the same intent in different words (Namaste p9's
    # grooming page) — missing it meant the cross-vignette same-proportions
    # check never engaged on exactly the page that needed it.
    import re
    return bool(re.search(
        r"collage|montage|vignettes|\bpanels\b|-panel\b|spot illustration", d))


def page_id(sc):
    return sc.get("page", "")


def is_spread(sc):
    # The book prints one manuscript page per sheet — every page is a single
    # square page. Spreads are retired; kept as a no-op so callers don't break.
    return False


def group_distinguish(plan, present):
    """Text note on how to keep any co-present look-alikes distinct."""
    notes = []
    for g in plan["groups"]:
        members = [m for m in g.get("members", []) if m in present]
        if len(members) >= 2 and g.get("distinguish"):
            notes.append(f"{' vs '.join(members)}: {g['distinguish']}")
    return "; ".join(notes)


# --- relative-height lock ---------------------------------------------------
# A character's height drifts page-to-page (Maya: hip-height on one page,
# shoulder-height on the next) because an absolute height_cm means nothing to
# the image model and no probe compares characters to EACH OTHER. These
# helpers turn the locked heights into a deterministic relative anchor
# ("head reaches his lower chest") used in the prompt AND as a gate probe.

# Median stature by age (cm) — fallback when a spec has age but no height.
_AGE_CM = {1: 75, 2: 87, 3: 95, 4: 102, 5: 109, 6: 115, 7: 122, 8: 128,
           9: 133, 10: 138, 11: 144, 12: 149, 13: 156, 14: 163, 15: 167,
           16: 170, 17: 171}


def char_height_cm(c):
    """Locked standing height for a character.

    An EXPLICIT spec height_cm is trusted for any species — anthropomorphic
    casts (the Grizzly Greg bears) stand upright, so the human landmark
    ladder still reads correctly. The age→height fallback stays human-only:
    a bear cub's age says nothing about its drawn stature."""
    spec = c.get("locked_spec") or {}
    idn = spec.get("identity") or {}
    h = (idn.get("build") or {}).get("height_cm")
    if h:
        return float(h)
    if (idn.get("species") or "human") != "human":
        return None
    age = idn.get("age_years")
    if age is None:
        return None
    return float(_AGE_CM.get(int(age), 170)) if age < 18 else 170.0


# Where the shorter character's head lands on the taller one's body, as a
# fraction of the taller one's standing height (standard figure proportions).
_LANDMARKS = [(0.50, "mid-thigh"), (0.565, "hip"), (0.655, "waist"),
              (0.73, "lower chest"), (0.79, "mid-chest"),
              (0.85, "shoulder"), (0.93, "chin")]

_FRACTIONS = [(0.5, "half"), (0.6, "three-fifths"), (2 / 3, "two-thirds"),
              (0.75, "three-quarters"), (0.8, "four-fifths"),
              (0.9, "nine-tenths")]


def size_pairs(plan, present):
    """Deterministic relative-height facts for every co-present pair of
    high-consistency humans with a meaningful height gap.

    Returns [{"small","big","small_cm","big_cm","landmark","fraction"}]."""
    withh = [(n, char_height_cm(plan["by"][n])) for n in present
             if n in plan["by"] and is_high(plan["by"][n])]
    withh = [(n, h) for n, h in withh if h]
    pairs = []
    for i in range(len(withh)):
        for j in range(i + 1, len(withh)):
            (a, ha), (b, hb) = withh[i], withh[j]
            small, big = (a, b) if ha <= hb else (b, a)
            hs, hg = min(ha, hb), max(ha, hb)
            r = hs / hg

            def _sp(nm):
                return ((((plan["by"][nm].get("locked_spec") or {})
                          .get("identity") or {}).get("species")) or "human")
            if r > 0.93:
                # near-equal heights — no landmark anchor, but the ORDERING
                # is still stated and probed (coarse), so an inversion (pig
                # drawn towering over goat) can't slip through unprobed
                pairs.append({"small": small, "big": big,
                              "small_cm": round(hs), "big_cm": round(hg),
                              "order_only": True,
                              "small_species": _sp(small),
                              "big_species": _sp(big)})
                continue
            landmark = next((l for t, l in _LANDMARKS if r < t), "chin")
            fraction = min(_FRACTIONS, key=lambda f: abs(f[0] - r))[1]
            pairs.append({"small": small, "big": big, "small_cm": round(hs),
                          "big_cm": round(hg), "landmark": landmark,
                          "fraction": fraction,
                          "small_species": _sp(small), "big_species": _sp(big)})
    return pairs


def stance_map(plan, present):
    """{name: 'anthro'|'feral'} for present characters with a locked stance."""
    m = {}
    for n in present:
        c = plan["by"].get(n)
        if not c:
            continue
        st = ((c.get("locked_spec") or {}).get("identity") or {}).get("stance")
        if isinstance(st, dict):
            st = st.get("default")
        st = str(st or "").strip().lower()
        if st.startswith("anthro"):
            m[n] = "anthro"
        elif st.startswith("feral"):
            m[n] = "feral"
    return m


def stance_lines(plan, present):
    """POSTURE LOCK prompt clause — the anthro-vs-feral axis that flips
    between pages (a giraffe upright on one page, on all fours the next).
    A momentary held pose (yoga, jumping) never changes a stance."""
    bits = []
    for n in present:
        c = plan["by"].get(n)
        if not c:
            continue
        idn = ((c.get("locked_spec") or {}).get("identity") or {})
        st = idn.get("stance")
        if isinstance(st, dict):
            st = st.get("default")
        st = str(st or "").strip().lower()
        sp = idn.get("species") or "animal"
        if st.startswith("feral"):
            bits.append(f"{n} is ALWAYS a natural four-legged {sp} — never "
                        f"standing upright like a person (a deliberate held "
                        f"yoga/action pose is fine, but never a biped)")
        elif st.startswith("anthro"):
            bits.append(f"{n} is ALWAYS an upright, person-like biped — "
                        f"never dropping to all fours like a wild animal")
    return "; ".join(bits)


def setting_lock_line(plan, sc):
    """The SETTING LOCK prompt clause — identical on every page drawn at this
    location: exact floor + fixed props (count and design) from the setting
    manifest, so the room can't get redecorated between pages."""
    s = scene_setting(plan, sc)
    if not s:
        return ""
    bits = []
    if s.get("floor"):
        bits.append(f"the floor is {s['floor']} — never a different floor")
    for p in (s.get("fixed_props") or []):
        if not isinstance(p, dict) or not p.get("item"):
            continue
        d = f" ({p['design']})" if p.get("design") else ""
        bits.append(f"exactly {p.get('count', 1)} {p['item']}{d}")
    if not bits:
        return ""
    return ("identical every time this location appears: "
            + "; ".join(bits) + ". Never redecorate, add or remove them.")


def size_lock_line(plan, present):
    """The SIZE LOCK prompt clause — identical text on every page, like the
    locked character spec, so relative scale can't drift between pages."""
    bits = []
    for p in size_pairs(plan, present):
        if p.get("order_only"):
            bits.append(
                f"{p['small']} ({p['small_cm']}cm) and {p['big']} "
                f"({p['big_cm']}cm) are nearly the same height — neither "
                f"ever towers over the other")
            continue
        bits.append(
            f"{p['small']} is {p['small_cm']}cm and {p['big']} is "
            f"{p['big_cm']}cm — standing side by side, the top of "
            f"{p['small']}'s head reaches {p['big']}'s {p['landmark']} "
            f"(about {p['fraction']} of {p['big']}'s height)")
    # The proportion lock rides the same clause and fires even for a SOLO
    # character — leg length and girth drift page-to-page with no co-present
    # pair to anchor them (the Namaste goat shrank and fattened alone).
    prop = ("PROPORTION LOCK: match each character's reference-sheet body "
            "proportions EXACTLY — same leg length relative to body, same "
            "body girth, same head-to-body ratio; never shorter-legged, "
            "stockier, fatter or lankier than the sheet shows.")
    if not bits:
        has_high = any(n in plan["by"] and is_high(plan["by"][n])
                       for n in present)
        return prop if has_high else ""
    return ("; ".join(bits)
            + ". Keep this exact height relationship in every pose — never "
              "draw the shorter character taller or smaller than stated. "
            + prop)
