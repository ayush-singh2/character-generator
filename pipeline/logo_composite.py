"""Composite a fixed logo onto a character's shirt after generation.

Diffusion models won't reproduce a small chest logo identically page to page
(position, size and even the motif drift). The only way to make it pixel-exact
is to draw the page with a PLAIN shirt and paste ONE canonical logo asset onto
the detected chest region every time.

Pipeline per page:
  1. locate the character's chest (vision model → box + facing) — skip if the
     chest isn't clearly front-facing/visible;
  2. paste the fixed logo PNG, scaled into that box and tinted to sit on cloth.

Logo assets live in data/logos/<character-slug>.png (RGBA, transparent bg). A
paw print is generated procedurally if none is supplied.

Run: python -m pipeline.logo_composite Ella          # composite one character
"""

import json
import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter

from .llm import chat_json_image

LOGO_DIR = "data/logos"
ART_DIR = "output/storybook/art"
STORYBOOK = "data/storybook.json"


def _slug(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ── canonical logo asset ─────────────────────────────────────────────────────
def make_paw(size: int = 512, color=(25, 25, 25, 255)) -> Image.Image:
    """Draw a clean black paw-print on a transparent canvas."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size
    # heel pad — a rounded, slightly heart-shaped blob
    d.ellipse([s * 0.28, s * 0.46, s * 0.72, s * 0.86], fill=color)
    d.ellipse([s * 0.34, s * 0.40, s * 0.66, s * 0.70], fill=color)
    # four toe beans in a gentle arc
    toes = [(0.20, 0.30, 0.14), (0.38, 0.16, 0.15),
            (0.57, 0.16, 0.15), (0.74, 0.30, 0.14)]
    for cx, cy, r in toes:
        d.ellipse([s * (cx - r / 2), s * (cy - r / 2 + 0.02),
                   s * (cx + r / 2), s * (cy + r / 2 + 0.10)], fill=color)
    return img


def load_logo(character: str) -> Image.Image:
    """Load the character's logo asset, generating a paw if none on disk."""
    path = os.path.join(LOGO_DIR, _slug(character) + ".png")
    if os.path.exists(path):
        return Image.open(path).convert("RGBA")
    os.makedirs(LOGO_DIR, exist_ok=True)
    paw = make_paw()
    paw.save(path)
    print(f"[logo] generated default paw asset -> {path}")
    return paw


# ── chest detection ──────────────────────────────────────────────────────────
def detect_chest(image_bytes: bytes, character: str, logo_hint: str) -> dict:
    """Vision-locate where the logo should sit. Returns {visible, facing, box%}.

    box is [x, y, w, h] as PERCENT of the image (x,y = top-left of the chest
    area). visible=False when the chest isn't a clear front/three-quarter view.
    """
    system = (
        "You place a fixed chest logo on a character in a children's-book "
        "illustration. Find the character's upper-front torso — the flat shirt "
        "area where a chest logo sits.")
    user = (
        f"The character is {character} (look for their shirt: {logo_hint}). "
        "Return JSON {\"visible\": true|false, \"facing\": \"front|three-quarter|"
        "side|back\", \"box\": [x, y, w, h]} where box is the shirt chest panel "
        "as PERCENT of the image (x,y = top-left corner, w,h = size). Set "
        "visible=false if the chest is turned away, occluded, tiny, or not a "
        "clear front/three-quarter view.")
    try:
        r = chat_json_image(system, user, image_bytes, mime="image/png")
        return r if isinstance(r, dict) else {"visible": False}
    except Exception as e:  # noqa: BLE001
        print(f"   [detect_chest] {character}: {str(e)[:80]}")
        return {"visible": False}


# ── compositing ──────────────────────────────────────────────────────────────
def paste_logo(page: Image.Image, logo: Image.Image, box_pct, scale: float = 0.5,
               opacity: float = 0.92) -> Image.Image:
    """Paste the logo centred in the chest box, sized to `scale` of the box width."""
    W, H = page.size
    x, y, w, h = box_pct
    bx, by, bw, bh = x / 100 * W, y / 100 * H, w / 100 * W, h / 100 * H
    target = max(8, int(bw * scale))
    lg = logo.copy()
    lg.thumbnail((target, target), Image.LANCZOS)
    # slightly soften edges + apply opacity so it reads as printed on cloth
    alpha = lg.split()[3].point(lambda a: int(a * opacity))
    lg.putalpha(alpha.filter(ImageFilter.GaussianBlur(0.4)))
    px = int(bx + (bw - lg.width) / 2)
    py = int(by + (bh - lg.height) / 2)
    out = page.convert("RGBA")
    out.alpha_composite(lg, (px, py))
    return out.convert("RGB")


def composite_page(page_path: str, character: str, logo: Image.Image,
                   logo_hint: str, scale: float = 0.5) -> bool:
    """Composite the logo onto one page in place. Returns True if applied."""
    page = Image.open(page_path).convert("RGB")
    buf = BytesIO(); page.save(buf, format="PNG")
    det = detect_chest(buf.getvalue(), character, logo_hint)
    box = det.get("box")
    # Only skip a genuinely unusable chest: back-turned, or no/near-zero box.
    # Front and three-quarter both take a logo fine; a small chest still should.
    if det.get("facing") == "back" or not box or len(box) != 4 or box[2] < 4:
        print(f"   {os.path.basename(page_path)}: chest not usable "
              f"({det.get('facing')}, box={box}) — skipped")
        return False
    out = paste_logo(page, logo, det["box"], scale=scale)
    out.save(page_path)
    print(f"   {os.path.basename(page_path)}: logo composited at {det['box']}")
    return True


def run(character: str, logo_hint: str = "purple t-shirt", scale: float = 0.5):
    """Composite the character's logo onto every page where they appear."""
    logo = load_logo(character)
    scenes_path = "data/scenes_split.json"
    scenes = json.load(open(scenes_path)) if os.path.exists(scenes_path) else {}
    pages = []
    for key, spec in scenes.items():
        if character in (spec.get("characters_present") or []):
            n = key.replace("Page ", "").strip()
            p = os.path.join(ART_DIR, f"page_{int(n):02d}.png")
            if os.path.exists(p):
                pages.append(p)
    print(f"[logo] {character}: {len(pages)} candidate pages")
    applied = 0
    for p in sorted(pages):
        applied += composite_page(p, character, logo, logo_hint, scale)
    print(f"[logo] composited on {applied}/{len(pages)} pages")


if __name__ == "__main__":
    import sys
    who = sys.argv[1] if len(sys.argv) > 1 else "Ella"
    run(who)
