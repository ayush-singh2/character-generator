"""One-off clean rebuild for the Ella book into art version3.

Reuses the tuned character specs (keeps the corrected left-wrist watch), but
redoes the art so everything is consistent and the new reference-book text/
negative-space finish is applied:

  1. Regenerate ONLY Ella's reference sheet (force) so the watch is locked to
     the LEFT wrist on the canonical turnaround the pages condition on. The
     other approved character sheets are left untouched.
  2. Regenerate the cover + every story page (force) against the refs + locked
     specs, using the calm-negative-space scene planner.
  3. Rebuild the PDF with the new text-on-art renderer.
  4. Snapshot the art into  <root>/runs/output/storybook/art/versions/version3
     (per-page folders + cover + the PDF), the location the user asked for.

Run from the Ella run dir:
    cd runs/ella-the-animal-shelter-and-you
    python -m pipeline.rebuild_v3
"""

import glob
import json
import os
import shutil

from . import pb_illustrate, picturebook, refs

# The literal output location requested (relative to the repo root, which is two
# levels up from this run dir: runs/<slug>/ -> repo root).
REPO_ROOT = os.path.abspath(os.path.join(os.getcwd(), "..", ".."))
V3_DIR = os.path.join(REPO_ROOT, "runs", "output", "storybook",
                      "art", "versions", "version3")


def _snapshot_v3(pdf_path: str) -> None:
    art_dir = "output/storybook/art"
    cover = "output/storybook/cover_art.png"
    os.makedirs(V3_DIR, exist_ok=True)
    pages = sorted(glob.glob(os.path.join(art_dir, "page_*.png")))
    for p in pages:
        stem = os.path.splitext(os.path.basename(p))[0]      # page_04
        d = os.path.join(V3_DIR, stem)
        os.makedirs(d, exist_ok=True)
        shutil.copy2(p, os.path.join(d, os.path.basename(p)))
    if os.path.exists(cover):
        os.makedirs(os.path.join(V3_DIR, "cover"), exist_ok=True)
        shutil.copy2(cover, os.path.join(V3_DIR, "cover", "cover_art.png"))
    if pdf_path and os.path.exists(pdf_path):
        shutil.copy2(pdf_path, os.path.join(V3_DIR, os.path.basename(pdf_path)))
    json.dump({"version": 3, "num_pages": len(pages),
               "pages": [os.path.basename(p) for p in pages]},
              open(os.path.join(V3_DIR, "manifest.json"), "w"), indent=2)
    print(f"\n[v3] snapshot -> {V3_DIR} ({len(pages)} pages)")


def main() -> None:
    print("== 1/4 refs: regenerating Ella's reference sheet (left-wrist watch) ==")
    refs.build_refs(only=["Ella"], force=True)

    print("\n== 2/4 cover ==")
    pb_illustrate.make_cover(force=True)

    print("\n== 2/4 art: regenerating every page (calm negative space) ==")
    pb_illustrate.illustrate(force=True)

    print("\n== 3/4 book: rebuilding PDF with text-on-art renderer ==")
    pdf = picturebook.build()
    print("  ->", pdf)

    print("\n== 4/4 snapshot to version3 ==")
    _snapshot_v3(pdf)
    print("\nDone.")


if __name__ == "__main__":
    main()
