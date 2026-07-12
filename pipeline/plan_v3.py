"""Shared helpers over a v3 art plan (characters.toon / scenes.toon).

Generic across books: tolerates both the rich parse_v3 schema (style dict,
appearance/outfit/consistency fields, lookalike_groups) and the hand-written
Bilbo schema (style string, species/hat/bandana). Downstream stages
(refs/generate/correct) read the plan through here so none of them hardcode a
particular book.
"""

import os

from . import toon_io

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
        "scenes": scenes.get("scenes", []),
    }


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


def page_id(sc):
    return sc.get("page", "")


def is_spread(sc):
    return sc.get("layout") == "spread"


def group_distinguish(plan, present):
    """Text note on how to keep any co-present look-alikes distinct."""
    notes = []
    for g in plan["groups"]:
        members = [m for m in g.get("members", []) if m in present]
        if len(members) >= 2 and g.get("distinguish"):
            notes.append(f"{' vs '.join(members)}: {g['distinguish']}")
    return "; ".join(notes)
