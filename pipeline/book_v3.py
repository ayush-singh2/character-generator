"""v3 book assembly — composed pages -> a single PDF, in manuscript order."""

import os

from PIL import Image

from . import toon_io

DATA = "v3/data"
PAGES = "v3/output/pages"
OUT = "v3/output"
TITLE = "Bilbo_Obi_s_Baseball_Adventure_v3"


def build():
    scenes = toon_io.load(f"{DATA}/scenes.toon")["scenes"]
    imgs = []
    for s in scenes:
        p = f"{PAGES}/page_{s['page']}.png"
        if os.path.exists(p):
            src = Image.open(p).convert("RGB")
            # paste into a fresh canvas to drop format/JPEG metadata that can
            # trip Pillow's PDF encoder (KeyError 'JPEG').
            clean = Image.new("RGB", src.size, (255, 255, 255))
            clean.paste(src)
            imgs.append(clean)
    if not imgs:
        print("no composed pages to build"); return ""
    os.makedirs(OUT, exist_ok=True)
    pdf = f"{OUT}/{TITLE}.pdf"
    imgs[0].save(pdf, "PDF", save_all=True, append_images=imgs[1:], resolution=150.0)
    print(f"  -> {pdf}  ({len(imgs)} pages)")
    return pdf


if __name__ == "__main__":
    build()
