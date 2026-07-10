"""Image-to-image character-consistency correction — Approach 1 (correct-after).

The picture-book pipeline renders each page freehand, so a character can drift
from its approved look. This module closes the loop AFTER rendering:

  1. judge   — a vision model compares every character on the page against its
               approved reference (page + refs stacked into one comparison strip)
               and reports who drifted and how.
  2. correct — each drifted character is repainted IN PLACE via flux.edit: the
               page plus that character's reference go in, and the model is told
               to fix ONLY that character while leaving the background, the other
               characters, the composition and the reserved text space identical.
  3. re-judge — repeat until the page passes or MAX_FIX_TRIES is hit.

This is the incremental, "only touch what's broken" approach. Approach 2
(compose-from-parts) will live alongside it once this is validated.

Run from inside a book dir (books/<slug>/), same CWD convention as pb_run:
    python -m pipeline.consistency --pages 3            # fix first 3 pages
    python -m pipeline.consistency --only page_05        # one page
    python -m pipeline.consistency --pages 3 --dry-run   # judge only, no edits
"""

import argparse
import io
import json
import os

from PIL import Image

from . import flux
from .llm import chat_json_image

SCENES = "data/scenes_split.json"
REFS = "data/refs.json"
CHARACTERS = "data/characters.json"
ART_DIR = "output/storybook/art"

MAX_FIX_TRIES = int(os.getenv("CONSISTENCY_TRIES", "2"))
STRIP_H = 512  # each panel is normalised to this height before stacking


JUDGE_SYSTEM = """\
You are a picture-book art-consistency reviewer. You are shown one horizontal \
strip. The LEFT panel is a rendered storybook PAGE. Each panel to its right is \
the APPROVED REFERENCE for one named character (their correct face, hair, skin \
tone, outfit and colours), given in the order named below.

For every named character, find that character inside the PAGE and compare them \
to their reference. Judge identity only — face/hair/skin/outfit/colours/species \
— NOT pose, expression, camera angle or lighting, which are allowed to differ.

Reply with ONLY a JSON array, one object per named character:
[{"name": "<character>", "consistent": true|false, "issue": "<short reason if \
inconsistent, else empty>"}]
A character that cannot be found in the page is "consistent": false with issue \
"not visible"."""


def _load():
    scenes = json.load(open(SCENES)) if os.path.exists(SCENES) else {}
    refs = json.load(open(REFS)) if os.path.exists(REFS) else {}
    return scenes, refs


def _panel(img_bytes: bytes) -> Image.Image:
    """Decode + normalise one image to STRIP_H tall, preserving aspect."""
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w = max(1, round(im.width * STRIP_H / im.height))
    return im.resize((w, STRIP_H))


def _comparison_strip(page_bytes: bytes, ref_bytes: list[bytes]) -> bytes:
    """Stack the page and each reference side-by-side into one PNG."""
    panels = [_panel(page_bytes)] + [_panel(r) for r in ref_bytes]
    total_w = sum(p.width for p in panels) + 8 * (len(panels) - 1)
    strip = Image.new("RGB", (total_w, STRIP_H), (255, 255, 255))
    x = 0
    for p in panels:
        strip.paste(p, (x, 0))
        x += p.width + 8
    buf = io.BytesIO()
    strip.save(buf, "PNG")
    return buf.getvalue()


def _portrait_bytes(refs: dict, name: str) -> bytes | None:
    """Approved single-character portrait bytes for the judge/fix, or None."""
    p = refs.get(name, {}).get("portrait")
    return open(p, "rb").read() if p and os.path.exists(p) else None


def judge_page(page_bytes: bytes, present: list[str], refs: dict) -> list[dict]:
    """Return the reviewer's per-character verdict list for one page."""
    named = [n for n in present if _portrait_bytes(refs, n)]
    if not named:
        return []
    ref_imgs = [_portrait_bytes(refs, n) for n in named]
    strip = _comparison_strip(page_bytes, ref_imgs)
    user = ("REFERENCE PANELS LEFT-TO-RIGHT (after the page): "
            + ", ".join(named) + ".")
    verdict = chat_json_image(JUDGE_SYSTEM, user, strip)
    return verdict if isinstance(verdict, list) else []


GROUP_REFS = "data/group_refs.json"

GROUP_JUDGE_SYSTEM = """\
You are checking whether two SIMILAR-LOOKING characters have been confused. The \
LEFT panel is a rendered storybook PAGE. The RIGHT panel is the APPROVED \
REFERENCE showing the named characters TOGETHER, correct and clearly distinct \
from each other.

Look at the page and decide, for these look-alike characters:
- are BOTH present?
- is each one's identity correct (matches the reference)?
- most important: are the two clearly DISTINCT from each other, or have they \
collapsed into the same-looking character / been swapped?

Reply with ONLY a JSON object:
{"distinct": true|false, "both_correct": true|false, \
"wrong": ["<names that are wrong, swapped, or a duplicate>"], \
"issue": "<short reason if anything is off, else empty>"}"""


def _load_groups() -> list[dict]:
    """Look-alike groups whose combined reference image exists on disk."""
    if not os.path.exists(GROUP_REFS):
        return []
    groups = json.load(open(GROUP_REFS))
    return [g for g in groups
            if g.get("members") and os.path.exists(g.get("image", ""))]


def discriminate_page(page_bytes: bytes, present: list[str],
                      groups: list[dict]) -> list[dict]:
    """For each look-alike group fully present, judge that its members are distinct.

    Catches the failure the per-character judge cannot: two similar characters
    (e.g. Bilbo & Obi) that each resemble their own portrait but have collapsed
    into one another. Returns [{members, image, verdict}] for present groups.
    """
    out = []
    for g in groups:
        members = g["members"]
        if not all(m in present for m in members):
            continue
        strip = _comparison_strip(page_bytes, [open(g["image"], "rb").read()])
        user = (f"The look-alike characters are: {', '.join(members)}. "
                "The REFERENCE panel shows them together, correct and distinct.")
        verdict = chat_json_image(GROUP_JUDGE_SYSTEM, user, strip)
        if isinstance(verdict, dict):
            out.append({"members": members, "image": g["image"], "verdict": verdict})
    return out


def _group_fix_prompt(members: list[str], bible: dict) -> str:
    locks = "; ".join(
        f"{m}: {json.dumps(bible.get(m, {}), ensure_ascii=False)}" for m in members)
    names = " and ".join(members)
    return (
        "The FIRST image is a storybook page that contains two SIMILAR-LOOKING "
        f"characters ({names}). The next image is the APPROVED REFERENCE showing "
        "them together, correct and clearly DISTINCT from each other.\n"
        f"Repaint the page so that {', '.join(members)} each exactly match their "
        "own identity in the reference AND are unmistakably different from each "
        "other — do NOT let them look like the same animal or swap features. "
        f"Correct looks — {locks}.\n"
        "Keep EVERYTHING else identical: background, composition, lighting, the "
        "other characters, and any empty area reserved for text. Do not move, "
        "resize, add or remove anything else. Output the complete page, same "
        "framing. No text or letters in the image."
    )


def correct_group(page_bytes: bytes, group: dict, bible: dict) -> bytes:
    """Repaint a collapsed/swapped look-alike pair using their DUO reference."""
    members = group["members"]
    duo = open(group["image"], "rb").read()
    prompt = _group_fix_prompt(members, bible)
    print(f"      fixing look-alikes {members} via duo ref ...")
    return flux.edit(prompt, [page_bytes, duo])


def _fix_prompt(name: str, spec: dict | None) -> str:
    lock = ""
    if spec:
        lock = " Their correct look: " + json.dumps(spec, ensure_ascii=False)
    return (
        "The FIRST image is a finished storybook illustration. The image(s) after "
        f"it are the APPROVED REFERENCE for the character '{name}'.{lock}\n"
        f"Repaint the illustration so that {name} EXACTLY matches the reference — "
        "same face, hair, skin tone, clothing and colours. Keep EVERYTHING else "
        "pixel-for-pixel identical: background, composition, lighting, the other "
        "characters, and any empty/quiet area reserved for text. Do not move, "
        "resize, add or remove anything else. Output the complete page, same "
        "framing. No text or letters in the image."
    )


def correct_page(page_bytes: bytes, drifted: list[str], refs: dict,
                 bible: dict) -> bytes:
    """Repaint each drifted character in place, one flux.edit per character."""
    out = page_bytes
    for name in drifted:
        ref = _portrait_bytes(refs, name)
        if not ref:
            print(f"      ! {name}: no reference to fix against — skipped")
            continue
        fb = refs.get(name, {}).get("full_body")
        ref_imgs = [ref] + ([open(fb, "rb").read()] if fb and os.path.exists(fb) else [])
        prompt = _fix_prompt(name, bible.get(name))
        print(f"      fixing {name} ...")
        out = flux.edit(prompt, [out] + ref_imgs)
    return out


def _bible_by_name() -> dict:
    if not os.path.exists(CHARACTERS):
        return {}
    bible = json.load(open(CHARACTERS)).get("bible", [])
    return {c.get("name"): c for c in bible if c.get("name")}


def run(pages: int | None = None, only: str | None = None, dry_run: bool = False):
    scenes, refs = _load()
    bible = _bible_by_name()
    groups = _load_groups()
    # Pages in stable order by their recorded label.
    labels = sorted(scenes.keys())
    if only:
        labels = [l for l in labels if l == only or scenes[l].get("image", "").find(only) >= 0]
    done = 0
    for label in labels:
        if pages and done >= pages:
            break
        spec = scenes[label]
        path = spec.get("image")
        if not path or not os.path.exists(path):
            continue
        present = spec.get("characters_present", [])
        if not present:
            continue
        done += 1
        page_bytes = open(path, "rb").read()
        print(f"[{label}] present: {present}")

        for attempt in range(1, MAX_FIX_TRIES + 1):
            # (a) per-character identity check
            verdict = judge_page(page_bytes, present, refs)
            for v in verdict:
                mark = "ok" if v.get("consistent", True) else f"DRIFT — {v.get('issue','')}"
                print(f"   {v.get('name','?'):<10} {mark}")
            indiv_drift = [v["name"] for v in verdict if not v.get("consistent", True)]

            # (b) look-alike discrimination check (Bilbo vs Obi collapse/swap)
            disc = discriminate_page(page_bytes, present, groups)
            bad_groups = []
            grouped_members = set()
            for d in disc:
                ver = d["verdict"]
                ok = ver.get("distinct", True) and ver.get("both_correct", True)
                tag = "distinct" if ok else f"COLLAPSED/SWAPPED — {ver.get('issue','')}"
                print(f"   {'&'.join(d['members']):<10} {tag}")
                if not ok:
                    bad_groups.append(d)
                    grouped_members.update(d["members"])

            # A character already handled by a group fix shouldn't also be
            # fixed individually (the duo fix repaints both together).
            indiv_drift = [n for n in indiv_drift if n not in grouped_members]

            if not indiv_drift and not bad_groups:
                print("   -> consistent" + (" (already)" if attempt == 1 else " after fix"))
                break
            if dry_run:
                todo = [f"duo:{'&'.join(d['members'])}" for d in bad_groups] + indiv_drift
                print(f"   -> would fix: {todo} (dry-run)")
                break

            # Fix look-alike collapse first (duo ref), then any lone drift.
            for d in bad_groups:
                page_bytes = correct_group(page_bytes, d, bible)
            if indiv_drift:
                page_bytes = correct_page(page_bytes, indiv_drift, refs, bible)

            _save_corrected(path, page_bytes)
            still = [f"duo:{'&'.join(d['members'])}" for d in bad_groups] + indiv_drift
            if attempt == MAX_FIX_TRIES:
                print(f"   -> saved after {attempt} attempt(s) (was: {still})")
            else:
                print(f"   -> corrected + saved, re-judging ...")


def _save_corrected(path: str, page_bytes: bytes):
    """Back up the original once, then overwrite the page with the fix."""
    backup = path.rsplit(".", 1)[0] + ".orig.png"
    if not os.path.exists(backup):  # preserve the very first render once
        with open(backup, "wb") as f:
            f.write(open(path, "rb").read())
    with open(path, "wb") as f:
        f.write(page_bytes)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Approach 1: correct character drift after rendering.")
    ap.add_argument("--pages", type=int, default=None, help="limit to first N pages")
    ap.add_argument("--only", type=str, default=None, help="single page label / filename fragment")
    ap.add_argument("--dry-run", action="store_true", help="judge only, no edits")
    a = ap.parse_args()
    run(pages=a.pages, only=a.only, dry_run=a.dry_run)
