"""Archive the current book before a new one overwrites it.

The picture-book pipeline writes into two working folders at the project root:
  data/    — parsed manuscript, style, character bible, refs manifest
  output/  — reference sheets, page art, composited pages, the final PDF

Generating a new book would clobber both. `archive_current()` moves the whole
current book — every page, its data, and the final PDF — into

  .archive_books/<book-name>__<timestamp>/

named after the book it belongs to, then leaves clean empty data/ and output/
folders for the next run. Nothing is deleted; old books stack up in the archive.

Run standalone:  python -m pipeline.archive        # archive whatever is present
"""

import datetime
import glob
import json
import os
import re
import shutil

DATA_DIR = "data"
OUTPUT_DIR = "output"
ARCHIVE_ROOT = ".archive_books"


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-") or "untitled"


def current_book_name() -> str | None:
    """Best-effort name of the book currently sitting in data/ + output/."""
    sb = os.path.join(DATA_DIR, "storybook.json")
    if os.path.exists(sb):
        try:
            title = json.load(open(sb)).get("title")
            if title:
                return title
        except Exception:  # noqa: BLE001
            pass
    # fall back to the assembled PDF's name
    pdfs = glob.glob(os.path.join(OUTPUT_DIR, "storybook", "*.pdf"))
    if pdfs:
        return os.path.splitext(os.path.basename(pdfs[0]))[0]
    return None


def _has_content() -> bool:
    """Is there an actual book worth archiving (not just empty scaffolding)?"""
    if glob.glob(os.path.join(OUTPUT_DIR, "**", "*.png"), recursive=True):
        return True
    if glob.glob(os.path.join(OUTPUT_DIR, "**", "*.pdf"), recursive=True):
        return True
    return False


def archive_current(reason: str = "new book") -> str | None:
    """Move the current data/ + output/ into the archive. Returns the archive
    path, or None if there was nothing to archive. Recreates clean folders."""
    if not _has_content():
        return None

    name = current_book_name()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(ARCHIVE_ROOT, f"{_slug(name)}__{stamp}")
    os.makedirs(dest, exist_ok=True)

    moved = []
    for folder in (DATA_DIR, OUTPUT_DIR):
        if os.path.isdir(folder) and os.listdir(folder):
            shutil.move(folder, os.path.join(dest, folder))
            moved.append(folder)

    # manifest so the archive is self-describing
    pdfs = glob.glob(os.path.join(dest, OUTPUT_DIR, "storybook", "*.pdf"))
    pages = glob.glob(os.path.join(dest, OUTPUT_DIR, "storybook", "art", "page_*.png"))
    json.dump(
        {
            "book": name,
            "archived_at": stamp,
            "reason": reason,
            "pdf": os.path.basename(pdfs[0]) if pdfs else None,
            "num_pages": len(pages),
            "folders": moved,
        },
        open(os.path.join(dest, "book.json"), "w"),
        indent=2,
        ensure_ascii=False,
    )

    # leave clean working folders for the next book
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return dest


def main() -> None:
    dest = archive_current(reason="manual")
    if dest:
        print(f"Archived current book -> {dest}")
    else:
        print("Nothing to archive (output/ is empty).")


if __name__ == "__main__":
    main()
