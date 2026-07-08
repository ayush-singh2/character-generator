"""Regenerate art for specific content pages, reserving a large empty side.

The auto-generated art for a few pages crowded characters across the whole
frame, leaving no wall for the text card. This re-illustrates just the named
pages (by printed page number) with the normal scene planner PLUS a firm
reinforcement that the empty side must stay clear — and conditioned on the
character reference sheets so faces/outfits stay consistent.

Old art is backed up to page_NN.png.bak first.

Run: python -m pipeline.regen_pages 10 19
"""

import json
import os
import shutil
import sys

from . import flux
from .pb_illustrate import (ART_DIR, CHARACTERS, REFS, SCENES, STORYBOOK,
                            _compose_prompt, _gather_refs, _locks_for, _render,
                            plan_scene)
from .style import load_style_prompt


def _empty_side_by_page(doc):
    """Map printed page number -> empty_side, matching illustrate()'s rhythm."""
    out, idx = {}, 0
    for u in doc["units"]:
        if u["kind"] != "content" or not u.get("text", "").strip():
            continue
        out[u["pages"][0]] = "left" if idx % 2 == 0 else "right"
        idx += 1
    return out


def regen(pages):
    doc = json.load(open(STORYBOOK))
    bible = json.load(open(CHARACTERS))["bible"]
    refs = json.load(open(REFS)) if os.path.exists(REFS) else {}
    style_prompt = load_style_prompt()
    scenes = json.load(open(SCENES)) if os.path.exists(SCENES) else {}
    sides = _empty_side_by_page(doc)

    for pg in pages:
        unit = next((u for u in doc["units"] if u.get("pages") == [pg]
                     and u["kind"] == "content"), None)
        if not unit:
            print(f"[page {pg}] no content unit — skipping")
            continue
        empty_side = sides.get(pg, "left")
        other = "right" if empty_side == "left" else "left"
        path = os.path.join(ART_DIR, f"page_{pg:02d}.png")
        if os.path.exists(path):
            shutil.copy(path, path + ".bak")

        print(f"[page {pg}] planning (empty side: {empty_side}) ...")
        spec = plan_scene(unit, empty_side, bible, style_prompt)
        # Firm reinforcement appended to the Flux prompt: keep the empty side a
        # large clear background band, cluster everyone on the other side.
        spec["scene_prompt"] += (
            f" CRITICAL COMPOSITION: keep the entire {empty_side} 45% of the frame "
            f"as calm OPEN BACKGROUND (plain wall / sky / bare floor) with NO people, "
            f"faces, furniture, toys or props in it — only the softly-painted "
            f"continued environment, so a block of text can sit there cleanly. "
            f"Place BOTH characters and every object together on the {other} side, "
            f"framed from roughly the knees up so they do not sprawl across the page. "
            f"Full-bleed, one seamless scene, no panel divide. No text in the image."
        )
        present = spec.get("characters_present", [])
        print(f"   present: {present or '(none)'} | {spec.get('moment','')[:70]}")
        # Pin every present character to its EXACT locked spec (deterministic).
        lock = _locks_for(present, bible)
        prompt = _compose_prompt(spec["scene_prompt"], lock, present, refs)
        if lock:
            print(f"   locked spec applied for: "
                  f"{[n for n in present if any(c['name']==n and c.get('locked_spec') for c in bible)]}")
        img = _render(prompt, _gather_refs(present, refs))
        flux.save(img, path)
        spec["image"] = path
        scenes[unit["label"]] = spec
        json.dump(scenes, open(SCENES, "w"), indent=2, ensure_ascii=False)
        print(f"   -> {path} (backup at {path}.bak)")


if __name__ == "__main__":
    nums = [int(a) for a in sys.argv[1:]] or [10, 19]
    regen(nums)
