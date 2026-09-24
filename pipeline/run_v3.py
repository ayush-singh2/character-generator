"""One-command runner for the picture-book pipeline (v7 generation).

Ties the per-stage modules together in the correct order, resumable by stage,
so the whole feedback-hardened pipeline runs from a single command. The stages
read/write <V3_DIR>/… relative to the cwd, so it runs inside the book dir.

Use the project venv (the stages need docx/PIL/requests). Easiest — run from the
repo ROOT and point at the book with --book:

    .venv/bin/python -m pipeline.run_v3 --book books/ella-the-animal-shelter-and-you
    .venv/bin/python -m pipeline.run_v3 --book books/... --from generate --only 4,11

Or cd into the book dir yourself (then the repo must be importable):

    cd books/ella-the-animal-shelter-and-you
    PYTHONPATH=<repo> <repo>/.venv/bin/python -m pipeline.run_v3
    V3_DIR=v3b PYTHONPATH=<repo> <repo>/.venv/bin/python -m pipeline.run_v3   # side-by-side

Stages (in order):
    parse     manuscript.docx -> characters.toon + scenes.toon (verbatim, front/back matter)
    copyedit  Ballast house-style pass over scenes.toon (verbatim-preserving)
    refs      character reference sheets + look-alike group sheets
    layout    per-page coordinate layout (gutter-aware)
    generate  v7: role-assigned multi-reference Gemini render + measured gate
              (identity/facts/anatomy/style probes) + diagnostic repair loop
    compose   locked type scale + gutter-safe, locked-colour text on the art
    book      assemble the PDF at one uniform trim

Resumable: --from <stage> skips everything before it and reuses on-disk work.
--only restricts the page-capable stages (layout/generate/compose) to a
comma list of page ids; parse/copyedit/refs/book always run whole.
"""

import argparse
import glob
import os

STAGES = ["parse", "copyedit", "refs", "layout", "generate", "compose", "book"]


def _find_docx(arg):
    if arg:
        return arg
    env = os.getenv("STORYBOOK_DOCX")
    if env:
        return env
    hits = sorted(glob.glob("manuscript/*.docx"))
    if not hits:
        raise SystemExit("no manuscript .docx found (looked in manuscript/); "
                         "pass --docx <path>")
    return hits[0]


def main():
    ap = argparse.ArgumentParser(description="Run the picture-book pipeline (v7).")
    ap.add_argument("--book", help="book directory to run in (chdir here first); "
                    "lets you launch from the repo root instead of cd-ing in")
    # Deprecated: there is one engine now (v7 generation). Accepted and ignored
    # so older callers (e.g. a not-yet-synced server/jobs.py) don't crash.
    ap.add_argument("--engine", help=argparse.SUPPRESS)
    ap.add_argument("--from", dest="start", choices=STAGES,
                    default="parse", help="resume from this stage")
    ap.add_argument("--to", dest="stop", choices=STAGES,
                    default=None, help="stop after this stage (inclusive); lets a "
                    "caller pause at the character-approval boundary, e.g. --to refs")
    ap.add_argument("--docx", help="manuscript .docx (else STORYBOOK_DOCX or first in manuscript/)")
    ap.add_argument("--only", help="comma list of page ids for the page-level stages")
    ap.add_argument("--no-copyedit", action="store_true", help="skip the house-style pass (verbatim)")
    args = ap.parse_args()

    if args.no_copyedit:
        os.environ["COPYEDIT"] = "0"

    # The stages read/write <V3_DIR>/… relative to the cwd, so run inside the
    # book dir. --book lets you launch from the repo root; chdir BEFORE importing
    # the stages so their default data_dir= binds to the book's paths.
    if args.book:
        if not os.path.isdir(args.book):
            raise SystemExit(f"--book: not a directory: {args.book}")
        os.chdir(args.book)

    # Import stage modules AFTER env is set so plan_v3's V3_DIR-derived paths and
    # the stages' default data_dir= bind to the right base.
    from . import (book_v3, compose_v3, copyedit_v3, generate_v7,  # noqa: F401
                   layout_v3, parse_v3, plan_v3, refs_v3)

    start = STAGES.index(args.start)
    stop = STAGES.index(args.stop) if args.stop else len(STAGES) - 1
    only = args.only.split(",") if args.only else None

    def active(name):
        return start <= STAGES.index(name) <= stop

    print(f"v7 pipeline — base={plan_v3.BASE}  from={args.start}"
          + (f"  only={only}" if only else ""))

    if active("parse"):
        docx = _find_docx(args.docx)
        print(f"\n== parse == ({docx})")
        parse_v3.parse(docx, plan_v3.DATA)

    if active("copyedit"):
        print("\n== copyedit ==")
        copyedit_v3.copyedit_scenes(plan_v3.DATA)

    if active("refs"):
        print("\n== refs ==")
        refs_v3.generate(data_dir=plan_v3.DATA)

    if active("layout"):
        print("\n== layout ==")
        layout_v3.build(only=only, data_dir=plan_v3.DATA)

    if active("generate"):
        print("\n== generate (v7 multi-ref + gate) ==")
        generate_v7.generate(only=only, data_dir=plan_v3.DATA)

    if active("compose"):
        print("\n== compose (text on art) ==")
        compose_v3.compose(only=only, data_dir=plan_v3.DATA)

    if active("book"):
        print("\n== book ==")
        pdf = book_v3.build(data_dir=plan_v3.DATA)
        if pdf:
            print(f"\ndone -> {pdf}")


if __name__ == "__main__":
    main()
