"""One-command runner for the picture-book pipeline.

    python -m pipeline.pb_run                  # full book
    python -m pipeline.pb_run --from refs       # resume from a stage
    python -m pipeline.pb_run --docx "manuscript/Foo.docx"

Stages: parse -> style -> characters -> refs -> art -> book
Resumable: refs/art skip work already on disk. Edit data/style.json or
data/characters.json between stages to override the auto choices.
"""

import argparse
import json
import os

from . import characters, picturebook, refs, storybook, style
from . import pb_illustrate

STAGES = ["parse", "style", "characters", "refs", "art", "book"]


def _adapter_doc():
    return storybook.as_manuscript_doc(json.load(open(storybook.OUT_PATH)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", choices=STAGES, default="parse")
    ap.add_argument("--docx", help="manuscript .docx (else first in manuscript/)")
    args = ap.parse_args()
    if args.docx:
        os.environ["STORYBOOK_DOCX"] = args.docx
    start = STAGES.index(args.start)

    def active(name):
        return STAGES.index(name) >= start

    if active("parse"):
        print("\n== parse ==")
        storybook.main()

    if active("style"):
        print("\n== style ==")
        st = style.judge(_adapter_doc())
        json.dump(st, open(style.OUT_PATH, "w"), indent=2, ensure_ascii=False)
        print(f"  chosen: {st.get('chosen')} | {st.get('tone')}")
        print(f"  palette: {st.get('palette')}")

    if active("characters"):
        print("\n== characters ==")
        mdoc = _adapter_doc()
        roster = characters.mine_roster(mdoc)
        bible = characters.draft_bible(roster, mdoc)
        out = {"title": mdoc.get("title"), "author": mdoc.get("author"),
               "story_no": None, "roster": roster["characters"], "bible": bible["characters"]}
        json.dump(out, open(characters.OUT_PATH, "w"), indent=2, ensure_ascii=False)
        for c in roster["characters"]:
            print(f"  [{c['weight']:>3}] {c['tier']:<10} {c['name']} — {c['role'][:50]}")
        print(f"  bible: {[c['name'] for c in bible['characters']]}")

    if active("refs"):
        print("\n== refs ==")
        refs.main()

    if active("art"):
        print("\n== cover ==")
        pb_illustrate.make_cover()
        print("\n== art ==")
        pb_illustrate.illustrate()

    if active("book"):
        print("\n== book ==")
        print("  ->", picturebook.build())

    print("\nDone.")


if __name__ == "__main__":
    main()
