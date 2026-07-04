"""One-command pipeline runner.

Drop a manuscript PDF into manuscript/ and run:

    python -m pipeline.run                 # full book
    python -m pipeline.run --pages 1-6     # just the first 6 pages (cheap test)
    python -m pipeline.run --from refs      # resume from a later stage
    python -m pipeline.run --words 70       # tune words/page

Stages, in order:
  extract -> paginate -> characters -> style -> refs -> cover -> illustrate -> book

Stages are resumable: refs/illustrate skip work already on disk, so a re-run
after a crash or an edit is cheap. The style choice is written to
data/style.json after the 'style' stage — review/edit it before 'refs' if you
want to override the auto-selected look.
"""

import argparse
import json
import os
import shutil

from . import book, characters, cover, extract, illustrate, paginate, refs, style

STAGES = ["extract", "paginate", "characters", "style", "refs", "cover", "illustrate", "book"]


def _range(s):
    if not s:
        return None
    if "-" in s:
        a, b = s.split("-")
        return range(int(a), int(b) + 1)
    return range(int(s), int(s) + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", choices=STAGES, default="extract")
    ap.add_argument("--pages", help="limit illustrate/book to a page range, e.g. 1-6")
    ap.add_argument("--story", type=int, help="scope whole run to one story number")
    ap.add_argument("--all-stories", action="store_true",
                    help="anthology mode: loop every story (per-story characters)")
    ap.add_argument("--words", type=int, default=paginate.DEFAULT_TARGET)
    args = ap.parse_args()

    start_i = STAGES.index(args.start)
    rng = _range(args.pages)

    # --story scopes characters to that story and derives its page range.
    if args.story is not None:
        pdata = json.load(open(paginate.OUT_PATH))
        nums = [p["page_no"] for p in pdata["pages"] if p["chapter_no"] == args.story]
        if not nums:
            raise SystemExit(f"No pages found for story {args.story}")
        rng = range(min(nums), max(nums) + 1)
        title = next(p["chapter_title"] for p in pdata["pages"] if p["chapter_no"] == args.story)
        print(f"Scoped to story {args.story}: '{title}' (pages {rng.start}-{rng.stop - 1})")

    def active(name):
        return STAGES.index(name) >= start_i

    if active("extract"):
        print("\n== extract ==");      extract.main()
    if active("paginate"):
        print("\n== paginate ==")
        doc = json.load(open(paginate.IN_PATH))
        pages = paginate.paginate(doc, target=args.words)
        json.dump({"title": doc.get("title"), "author": doc.get("author"),
                   "num_pages": len(pages), "pages": pages},
                  open(paginate.OUT_PATH, "w"), indent=2, ensure_ascii=False)
        print(f"  {len(pages)} book pages -> {paginate.OUT_PATH}")
    if active("style"):
        print("\n== style ==");      style.main()

    if args.all_stories:
        _run_all_stories()
    else:
        if active("characters"):
            print("\n== characters =="); characters.build_characters(args.story)
        if active("refs"):
            print("\n== refs ==");       refs.main()
        if active("cover"):
            print("\n== cover ==");      cover.main()
        if active("illustrate"):
            print("\n== illustrate =="); illustrate.illustrate(rng)
        if active("book"):
            print("\n== book ==")
            print("  ->", book.build(page_range=rng))

    print("\nDone.")


def _run_all_stories():
    """Anthology mode: process every story end-to-end (per-story characters,
    refs reused across stories by name), one cover, one final book.

    Resumable: per-story bibles are cached in data/stories/, refs/illustrate
    skip work already on disk, so a re-run continues where it left off.
    """
    pdata = json.load(open(paginate.OUT_PATH))
    story_nums = sorted({p["chapter_no"] for p in pdata["pages"] if p["chapter_no"]})
    os.makedirs("data/stories", exist_ok=True)
    cover_done = os.path.exists(os.path.join(book.BOOK_DIR, "cover_art.png"))

    for n in story_nums:
        nums = [p["page_no"] for p in pdata["pages"] if p["chapter_no"] == n]
        rng = range(min(nums), max(nums) + 1)
        title = next(p["chapter_title"] for p in pdata["pages"] if p["chapter_no"] == n)
        print(f"\n#### Story {n}/{story_nums[-1]}: {title} (pages {rng.start}-{rng.stop - 1}) ####")

        cache = f"data/stories/characters_{n}.json"
        if os.path.exists(cache):
            shutil.copy(cache, characters.OUT_PATH)
            print("  (cached characters)")
        else:
            characters.build_characters(n)
            shutil.copy(characters.OUT_PATH, cache)

        refs.main()
        if not cover_done:           # cover from story 1, where Ajji leads
            print("\n== cover =="); cover.main(); cover_done = True
        illustrate.illustrate(rng)

    print("\n== book ==")
    print("  ->", book.build())


if __name__ == "__main__":
    main()
