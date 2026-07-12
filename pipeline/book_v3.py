"""v3 book assembly — composed pages -> a single PDF, in manuscript order."""

import os

from PIL import Image

from . import plan_v3

from .plan_v3 import DATA, PAGES, OUT  # noqa: F401


def build(data_dir=DATA):
    plan = plan_v3.load(data_dir)
    title = plan_v3.slug(plan.get("title") or "book") or "book"
    imgs = []
    for sc in plan["scenes"]:
        p = f"{PAGES}/page_{plan_v3.slug(plan_v3.page_id(sc))}.png"
        if os.path.exists(p):
            src = Image.open(p).convert("RGB")
            clean = Image.new("RGB", src.size, (255, 255, 255))
            clean.paste(src)
            imgs.append(clean)
    if not imgs:
        print("no composed pages to build"); return ""
    os.makedirs(OUT, exist_ok=True)
    pdf = f"{OUT}/{title}.pdf"
    imgs[0].save(pdf, "PDF", save_all=True, append_images=imgs[1:], resolution=150.0)
    print(f"  -> {pdf}  ({len(imgs)} pages)")
    return pdf


if __name__ == "__main__":
    build()
