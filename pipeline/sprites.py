"""Character sprite atlas — the pixel source of truth for the compositing engine.

Diffusion models (flux) redraw every character freehand from noise on each call,
so page-to-page PIXEL consistency is impossible with plain text-to-image, no
matter how good the prompt or reference. This module takes the opposite approach:

    generate a SMALL, human-vetted set of pose sprites per character ONCE,
    cut them to transparent PNGs, and REUSE those exact pixels on every page.

Consistency then becomes a deterministic paste (compositor.py), not a gamble.
The hard consistency problem is moved to a one-time, ~6-10-image, approvable
asset set instead of being re-rolled on all 20 pages.

Layout on disk:
    output/assets/<slug>/<pose>.png        # RGBA, background removed
    output/assets/<slug>/<pose>.raw.png     # original (pre-cutout), for re-cut
    output/assets/manifest.json
"""

import json
import os

from PIL import Image

from . import flux, refs as R

ASSETS_DIR = "output/assets"
MANIFEST = os.path.join(ASSETS_DIR, "manifest.json")
CHARACTERS = "data/characters.json"

# Core pose vocabulary. key -> natural-language pose description. Extend per book
# from the shot list; the compositor picks a pose per character per page.
POSES = {
    # --- four-legged (dogs) ---
    "stand":  "standing on all fours in a calm neutral pose, full side three-quarter view",
    "sit":    "sitting upright on its haunches, front three-quarter view, facing the viewer",
    "walk":   "walking forward mid-stride, side three-quarter view",
    "run":    "running fast mid-stride, legs extended, dynamic side view",
    "lookup": "sitting and looking up in wonder, head tilted upward, mouth open",
    "leap":   "leaping up into the air, front legs reaching upward",
    "sleep":  "curled up asleep on the ground, eyes closed",
    "sniff":  "standing on all fours with nose lifted, sniffing the air, side view",
    # --- mascot (Homer, bipedal) ---
    "mascot_stand": "standing upright on two legs like a friendly sports mascot, facing forward, waving",
    "hold":         "standing upright on two legs, both arms stretched out wide open for a big friendly hug, facing forward",
    # --- humans ---
    "stand_person": "standing upright in a relaxed natural pose, facing forward, arms at sides",
    "walk_person":  "walking forward mid-stride, natural gait, facing forward",
    "crouch":       "crouching down on one knee, leaning forward with a warm smile, both hands reaching gently forward",
    "sit_person":   "sitting on the grass cross-legged, relaxed, facing forward",
}

# A flat, even background with NO cast shadow and NO ground gives rembg a clean
# silhouette to cut. Full body, generous margin so nothing is clipped.
_PLATE_BG = ("standing alone on a completely plain flat solid white background, "
             "no scenery, no floor, no ground line, no cast shadow, even soft "
             "lighting, the whole body fully visible and centred with margin "
             "around it, nothing cropped")


def _char(name, bible):
    for c in bible:
        if c["name"] == name:
            return c
    raise KeyError(name)


def sprite_prompt(char, pose_desc, style_prompt):
    subj = R._subject(char)
    animal = R._is_animal(char)
    return (
        f"A SINGLE solo {subj}"
        + (" (an animal, not a human)" if animal else "")
        + f", full body, {pose_desc}. "
        f"EXACTLY ONE {subj}, no other figures. "
        f"{R._identity(char)}. "
        f"{_PLATE_BG}. "
        f"Consistent canonical character design. Art style: {R._style(style_prompt)}"
    )


def cutout(img_bytes):
    """Return an RGBA PIL image with the background removed.

    Uses rembg (u2net saliency) when available; falls back to a white-key so the
    pipeline still runs without the optional dependency (rougher edges).
    """
    try:
        from rembg import remove  # optional heavy dep
        out = remove(img_bytes)   # returns PNG bytes with alpha
        import io
        return Image.open(io.BytesIO(out)).convert("RGBA")
    except Exception as e:
        print(f"   [cutout] rembg unavailable ({str(e)[:60]}) — white-key fallback")
        import io
        im = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        px = im.load()
        w, h = im.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if r > 244 and g > 244 and b > 244:
                    px[x, y] = (r, g, b, 0)
        return im


def _trim(im, pad=8):
    """Crop transparent margins, then add a small uniform pad."""
    bbox = im.split()[-1].getbbox()
    if bbox:
        im = im.crop(bbox)
    if pad:
        w, h = im.size
        canvas = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
        canvas.paste(im, (pad, pad))
        im = canvas
    return im


def build_pose(name, pose, bible, style_prompt, refs, force=False):
    """Generate + cut one pose sprite for one character. Returns the sprite path."""
    slug = next((r["slug"] for n, r in refs.items() if n == name), name.lower())
    out_dir = os.path.join(ASSETS_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{pose}.png")
    if os.path.exists(out_path) and not force:
        return out_path

    char = _char(name, bible)
    pose_desc = POSES.get(pose, pose)
    prompt = sprite_prompt(char, pose_desc, style_prompt)

    # Condition on the approved reference sheets so the sprite matches the design
    # the client already signed off on.
    ref_imgs = []
    if name in refs:
        for k in ("portrait", "full_body"):
            p = refs[name].get(k)
            if p and os.path.exists(p):
                ref_imgs.append(open(p, "rb").read())

    raw = flux.edit(prompt, ref_imgs) if ref_imgs else flux.generate(prompt)
    open(os.path.join(out_dir, f"{pose}.raw.png"), "wb").write(raw)
    sprite = _trim(cutout(raw))
    sprite.save(out_path)
    print(f"   [sprite] {name}/{pose} -> {out_path} ({sprite.size[0]}x{sprite.size[1]})")
    return out_path


def build_atlas(names, poses, force=False):
    """Build a set of pose sprites for the given characters."""
    bible = json.load(open(CHARACTERS))["bible"]
    refs = json.load(open(R.MANIFEST)) if os.path.exists(R.MANIFEST) else {}
    style_prompt = R.load_style_prompt()
    manifest = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {}
    os.makedirs(ASSETS_DIR, exist_ok=True)
    for name in names:
        manifest.setdefault(name, {})
        for pose in poses:
            path = build_pose(name, pose, bible, style_prompt, refs, force=force)
            manifest[name][pose] = path
    json.dump(manifest, open(MANIFEST, "w"), indent=2)
    return manifest
