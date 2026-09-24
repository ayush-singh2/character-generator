"""Backfill v7.9 consistency fields into an EXISTING book's data files.

New generic locks (heights for all recurring cast, stance, feature orientation,
dress_state, setting floor + fixed_props) are produced by parse for new books;
this tool retrofits them into an already-parsed book (characters.toon /
scenes.toon) so it can be re-gated and re-rolled WITHOUT a full re-parse —
approved specs and sheets stay untouched, only missing fields are filled.

Usage:  python -m pipeline.plan_backfill [data_dir]
        (defaults to $V3_DIR/data via plan_v3.DATA)
"""

import json
import sys
from collections import Counter

from . import llm, plan_v3, toon_io

SYSTEM = """\
You maintain locked character and setting specs for a children's picture book.
You are given the book's existing characters (with any locked_spec they already
have), the per-page cast lists, and the recurring settings. Fill ONLY the missing
consistency fields; NEVER change a value that already exists.

Reply ONLY JSON:
{"characters": [{"name": "<exact existing name>",
   "height_cm": 95,
   "stance": "anthro" | "feral",
   "dress_state": "clothed" | "unclothed",
   "distinguishing_add": ["directional feature with explicit direction"]}],
 "settings": [{"key": "<exact existing key>",
   "floor": "ONE exact floor material + colour",
   "fixed_props": [{"item": "", "count": 1, "design": "exact repeatable design"}]}]}

Rules:
- height_cm: standing height, top of head in the character's normal stance. The
  cast's heights must be MUTUALLY plausible so relative sizes read correctly on
  shared pages (a pig clearly shorter than a goat, a giraffe far taller than both).
- stance (animals only, omit for humans): "anthro" = upright person-like biped;
  "feral" = natural four-legged animal. Judge from how the character is described;
  commit to ONE for the whole book.
- dress_state: "clothed" only if the character wears a locked outfit; "unclothed"
  for natural animals wearing nothing.
- distinguishing_add: ONLY for directional features (horns, tail, ears, crest,
  trunk) whose direction is not already stated absolutely in the existing spec,
  e.g. "two horns curving BACKWARD over the head, tips pointing behind — never
  sideways or forward". Empty list if nothing to add.
- settings: floor and fixed_props exact and repeatable — the same floor and the
  same props (same count, same design) every time the location recurs.
- Include ONLY the characters and settings you were given."""


def backfill(data_dir=None):
    data_dir = data_dir or plan_v3.DATA
    cpath, spath = f"{data_dir}/characters.toon", f"{data_dir}/scenes.toon"
    chars_doc = toon_io.load(cpath)
    scenes_doc = toon_io.load(spath)
    scenes = scenes_doc.get("scenes", [])
    settings = scenes_doc.get("settings", []) or []

    counts = Counter(n for sc in scenes for n in (sc.get("chars") or []))
    recurring = [c for c in chars_doc.get("characters", [])
                 if counts.get(c.get("name"), 0) >= 2]
    if not recurring and not settings:
        print("  nothing to backfill"); return

    payload = {
        "characters": [{
            "name": c.get("name"),
            "pages": counts.get(c.get("name"), 0),
            "description": c.get("description", ""),
            "outfit": c.get("outfit", ""),
            "consistency": c.get("consistency", ""),
            "dress_state": c.get("dress_state", ""),
            "locked_spec": c.get("locked_spec") or {},
        } for c in recurring],
        "settings": [{
            "key": s.get("key"), "name": s.get("name", ""),
            "description": s.get("description", ""),
            "floor": s.get("floor", ""),
            "fixed_props": s.get("fixed_props", []),
        } for s in settings],
    }
    r = llm.chat_json(SYSTEM, json.dumps(payload, ensure_ascii=False),
                      max_tokens=8000)

    by_name = {c.get("name"): c for c in recurring}
    filled = []
    for u in (r.get("characters") or []):
        c = by_name.get(u.get("name"))
        if not c:
            continue
        spec = c.setdefault("locked_spec", {})
        idn = spec.setdefault("identity", {})
        build = idn.setdefault("build", {})
        if c.get("consistency") != "high":
            c["consistency"] = "high"; filled.append(f"{c['name']}:high")
        if not build.get("height_cm") and u.get("height_cm"):
            build["height_cm"] = int(u["height_cm"])
            filled.append(f"{c['name']}:height={u['height_cm']}")
        if not idn.get("stance") and u.get("stance"):
            idn["stance"] = u["stance"]; filled.append(f"{c['name']}:{u['stance']}")
        if not c.get("dress_state") and u.get("dress_state"):
            c["dress_state"] = u["dress_state"]
            filled.append(f"{c['name']}:{u['dress_state']}")
        add = [a for a in (u.get("distinguishing_add") or []) if a]
        if add:
            face = spec.setdefault("face", {})
            dist = face.setdefault("distinguishing", [])
            for a in add:
                if a not in dist:
                    dist.append(a); filled.append(f"{c['name']}:+{a[:40]}")

    by_key = {s.get("key"): s for s in settings}
    for u in (r.get("settings") or []):
        s = by_key.get(u.get("key"))
        if not s:
            continue
        if not s.get("floor") and u.get("floor"):
            s["floor"] = u["floor"]; filled.append(f"{s['key']}:floor")
        if not s.get("fixed_props") and u.get("fixed_props"):
            s["fixed_props"] = u["fixed_props"]
            filled.append(f"{s['key']}:{len(u['fixed_props'])} props")

    toon_io.save(chars_doc, cpath)
    toon_io.save(scenes_doc, spath)
    print(f"  backfilled {len(filled)} fields:")
    for f in filled:
        print(f"    {f}")


if __name__ == "__main__":
    backfill(sys.argv[1] if len(sys.argv) > 1 else None)
