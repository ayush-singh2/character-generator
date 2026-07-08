"""Snapshot each generation run into a versioned, per-page folder tree.

Every run of the art stage overwrites output/storybook/art/page_NN.png. To keep
a history you can compare, `snapshot()` copies the current pages into

  output/storybook/art/versions/vN/
    page_04/page_04.png
    page_05/page_05.png
    ...
    cover/cover_art.png
    manifest.json

vN auto-increments. Each page gets its own folder so a page's raw art, prompt or
alternates can live alongside it later.

Run: python -m pipeline.versions            # snapshot current art as next vN
     python -m pipeline.versions --migrate  # fold a legacy flat versionN/ in too
"""

import glob
import json
import os
import re
import shutil

ART_DIR = "output/storybook/art"
COVER = "output/storybook/cover_art.png"


def _versions_dir(art_dir: str = ART_DIR) -> str:
    return os.path.join(art_dir, "versions")


def next_version(art_dir: str = ART_DIR) -> int:
    vd = _versions_dir(art_dir)
    if not os.path.isdir(vd):
        return 1
    nums = [int(m.group(1)) for d in os.listdir(vd)
            if (m := re.fullmatch(r"v(\d+)", d))]
    return (max(nums) + 1) if nums else 1


def snapshot(art_dir: str = ART_DIR, cover: str = COVER, label: str = "") -> str:
    """Copy the current pages into the next versions/vN/ (per-page folders)."""
    pages = sorted(glob.glob(os.path.join(art_dir, "page_*.png")))
    if not pages:
        print("nothing to snapshot (no page_*.png)")
        return ""
    v = next_version(art_dir)
    vroot = os.path.join(_versions_dir(art_dir), f"v{v}")
    for p in pages:
        name = os.path.basename(p)                      # page_04.png
        stem = os.path.splitext(name)[0]                # page_04
        dst_dir = os.path.join(vroot, stem)
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copy2(p, os.path.join(dst_dir, name))
    if os.path.exists(cover):
        os.makedirs(os.path.join(vroot, "cover"), exist_ok=True)
        shutil.copy2(cover, os.path.join(vroot, "cover", os.path.basename(cover)))
    json.dump({"version": v, "label": label, "num_pages": len(pages),
               "pages": [os.path.basename(p) for p in pages]},
              open(os.path.join(vroot, "manifest.json"), "w"), indent=2)
    print(f"snapshot -> {vroot}  ({len(pages)} pages"
          + (f", label='{label}'" if label else "") + ")")
    return vroot


def migrate_flat(art_dir: str = ART_DIR) -> None:
    """Fold any legacy flat versionN/ (page_*.png directly inside) into the new
    versions/vN/page_NN/ tree, then remove the flat folder."""
    for d in sorted(glob.glob(os.path.join(art_dir, "version*"))):
        base = os.path.basename(d)
        m = re.fullmatch(r"version(\d+)", base)
        if not m or not os.path.isdir(d):
            continue
        v = int(m.group(1))
        vroot = os.path.join(_versions_dir(art_dir), f"v{v}")
        if os.path.isdir(vroot):
            print(f"skip {base}: v{v} already exists"); continue
        pages = sorted(glob.glob(os.path.join(d, "page_*.png")))
        for p in pages:
            stem = os.path.splitext(os.path.basename(p))[0]
            os.makedirs(os.path.join(vroot, stem), exist_ok=True)
            shutil.copy2(p, os.path.join(vroot, stem, os.path.basename(p)))
        for c in glob.glob(os.path.join(d, "cover_art.png")):
            os.makedirs(os.path.join(vroot, "cover"), exist_ok=True)
            shutil.copy2(c, os.path.join(vroot, "cover", "cover_art.png"))
        shutil.rmtree(d)
        print(f"migrated {base} -> {vroot} ({len(pages)} pages), removed flat dir")


if __name__ == "__main__":
    import sys
    if "--migrate" in sys.argv:
        migrate_flat()
    label = next((a for a in sys.argv[1:] if not a.startswith("--")), "")
    snapshot(label=label)
