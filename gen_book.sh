#!/usr/bin/env bash
# Generate one or more picture books IN PARALLEL, each in its own isolated
# working dir so their data/ and output/ never collide.
#
# Usage:
#   ./gen_book.sh "manuscript/Book A.docx" "manuscript/Book B.docx" ...
#
# Each book lands in   books/<slug>/output/storybook/<Title>.pdf
# and logs to          books/<slug>/run.log
#
# Env you can set:  PB_BODY_SIZE (default 30), TEXTPLACE_VISION (default 1).

set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"

gen_one() {
  local docx="$1"
  local base; base="$(basename "$docx" .docx)"
  local slug; slug="$(echo "$base" | tr ' A-Z' '_a-z' | tr -cd 'a-z0-9_-')"
  local d="$ROOT/books/$slug"

  mkdir -p "$d/data" "$d/output"
  for x in pipeline manuscript Illustration_guide Referance_book .env; do
    ln -sfn "$ROOT/$x" "$d/$x"
  done

  echo "[$slug] starting -> $d/run.log"
  ( cd "$d" \
      && STORYBOOK_DOCX="$docx" PB_BODY_SIZE="${PB_BODY_SIZE:-30}" \
         python3 -m pipeline.pb_run > run.log 2>&1 \
      && echo "[$slug] DONE -> $d/output/storybook/"*.pdf \
      || echo "[$slug] FAILED (see $d/run.log)" )
}

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <manuscript.docx> [more.docx ...]" >&2
  exit 1
fi

for m in "$@"; do gen_one "$m" & done
wait
echo "All done. PDFs are under books/*/output/storybook/"
