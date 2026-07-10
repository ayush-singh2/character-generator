"""Layered page compositor.

Assembles a page from three layers:
    Layer 1  background plate   (scene, NO characters — allowed to vary per page)
    Layer 2  character sprites  (reused atlas pixels — IDENTICAL every page)
    Layer 3  text               (deterministic renderer — handled elsewhere)

Because the character pixels come straight from the atlas (sprites.py), a
character looks exactly the same on every page it appears — the coat, cap, collar
and size cannot drift, because it is literally the same PNG scaled and placed.
"""

import os

from PIL import Image, ImageDraw, ImageFilter


def _load_sprite(path):
    return Image.open(path).convert("RGBA")


def _feather(spr, radius=2.0, shrink=1):
    """Soften a sprite's alpha edge so it reads painted-in, not cut-out.

    Shrinks the matte slightly (kills the bright rembg halo) then blurs the edge.
    """
    r, g, b, a = spr.split()
    if shrink:
        a = a.filter(ImageFilter.MinFilter(2 * shrink + 1))
    a = a.filter(ImageFilter.GaussianBlur(radius))
    return Image.merge("RGBA", (r, g, b, a))


def paper_grain(img, strength=10):
    """Overlay a faint uniform grain so sprites and plate share one texture."""
    import random
    W, H = img.size
    noise = Image.effect_noise((W, H), strength).convert("L")
    tint = Image.merge("RGB", (noise, noise, noise))
    return Image.blend(img.convert("RGB"), tint, 0.06)


def _shadow(base, cx, by, width):
    """Soft elliptical contact shadow under a sprite's feet (grounds the paste)."""
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    rw = max(6, int(width * 0.48))
    rh = max(4, int(width * 0.12))
    d.ellipse([cx - rw, by - rh, cx + rw, by + rh], fill=(0, 0, 0, 95))
    sh = sh.filter(ImageFilter.GaussianBlur(max(3, width * 0.05)))
    base.alpha_composite(sh)


def place(plate, sprites, blend=True):
    """Composite sprites onto a background plate.

    plate: RGB/RGBA PIL image (the background).
    sprites: list of placement dicts, painted in the given order (back to front):
        path   : sprite PNG path
        anchor : (fx, fy) fractional position of the sprite's BOTTOM-CENTRE (feet)
        height : sprite height as a fraction of the plate height (locks size ratio)
        flip   : mirror horizontally (default False)
        shadow : draw a contact shadow (default True)
    Returns an RGB PIL image.
    """
    base = plate.convert("RGBA")
    W, H = base.size
    for s in sprites:
        spr = _load_sprite(s["path"])
        if s.get("flip"):
            spr = spr.transpose(Image.FLIP_LEFT_RIGHT)
        target_h = max(1, int(H * s["height"]))
        scale = target_h / spr.height
        target_w = max(1, int(spr.width * scale))
        spr = spr.resize((target_w, target_h), Image.LANCZOS)
        if blend:
            spr = _feather(spr)
        fx, fy = s["anchor"]
        cx, by = int(W * fx), int(H * fy)
        if s.get("shadow", True):
            _shadow(base, cx, by, target_w)
        base.alpha_composite(spr, (cx - target_w // 2, by - target_h))
    out = base.convert("RGB")
    if blend:
        out = paper_grain(out)      # shared grain unifies sprites + plate
    return out


def compose_to(plate, sprites, out_path):
    img = place(plate, sprites)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path)
    return out_path
