"""Stage 1.5 — re-paginate prose into picture-book "beats".

A novel manuscript runs ~400 words per page; a picture book runs ~60-100.
This stage merges each chapter's prose and re-splits it into page-sized beats
on sentence boundaries, so every beat becomes one illustrated page.

Deterministic (no LLM cost): packs whole sentences up to a target word count,
never splitting mid-sentence, and starts a fresh page at each chapter.

Run:  python -m pipeline.paginate [--words 80]
In:   data/manuscript.json
Out:  data/pages.json
"""

import argparse
import json
import re

IN_PATH = "data/manuscript.json"
OUT_PATH = "data/pages.json"

DEFAULT_TARGET = 80   # words per page (picture-book density)
MAX_TARGET = 120      # hard ceiling so no page overflows the text shelf

# Split into sentences while keeping terminal punctuation and closing quotes.
_SENT_RE = re.compile(r"[^.!?]*[.!?]+[\"'”’]?\s*|\S+$")
_CHAPTER_RE = re.compile(r"^\s*Chapter\s+\d+\s*:.*$", re.IGNORECASE | re.MULTILINE)


def _sentences(text: str) -> list[str]:
    text = " ".join(text.split())  # normalise whitespace
    return [s.strip() for s in _SENT_RE.findall(text) if s.strip()]


def _chapter_blocks(doc: dict) -> list[dict]:
    """Group manuscript pages into chapters: {no, title, text}."""
    blocks: list[dict] = []
    for p in doc["pages"]:
        text = _CHAPTER_RE.sub("", p["text"]).strip()  # drop heading lines
        no, title = p.get("chapter_no"), p.get("chapter_title")
        if blocks and blocks[-1]["no"] == no:
            blocks[-1]["text"] += " " + text
        else:
            blocks.append({"no": no, "title": title, "text": text})
    # Drop the title/author front matter that precedes chapter 1.
    return [b for b in blocks if b["no"] is not None]


def _strip_title_author(text: str, doc: dict) -> str:
    """Remove a leading 'Title Author' run that sits before chapter 1's prose."""
    for s in (doc.get("title"), doc.get("author")):
        if s and text.lstrip().lower().startswith(s.strip().lower()):
            text = text.lstrip()[len(s.strip()):].lstrip()
    return text


def paginate(doc: dict, target: int = DEFAULT_TARGET, max_words: int = MAX_TARGET) -> list[dict]:
    pages: list[dict] = []
    blocks = _chapter_blocks(doc)
    if blocks:
        blocks[0]["text"] = _strip_title_author(blocks[0]["text"], doc)
    for block in blocks:
        first_in_chapter = True
        cur, count = [], 0
        for sent in _sentences(block["text"]):
            w = len(sent.split())
            if cur and (count + w > max_words or count >= target):
                pages.append(_mk_page(len(pages) + 1, block, cur, first_in_chapter))
                first_in_chapter = False
                cur, count = [], 0
            cur.append(sent)
            count += w
        if cur:
            pages.append(_mk_page(len(pages) + 1, block, cur, first_in_chapter))
    return pages


def _mk_page(n, block, sentences, first_in_chapter) -> dict:
    text = " ".join(sentences)
    return {
        "page_no": n,
        "chapter_no": block["no"],
        "chapter_title": block["title"],
        "chapter_start": first_in_chapter,  # show the chapter title on this page
        "text": text,
        "word_count": len(text.split()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", type=int, default=DEFAULT_TARGET, help="target words/page")
    args = ap.parse_args()

    doc = json.load(open(IN_PATH))
    pages = paginate(doc, target=args.words)
    out = {"title": doc.get("title"), "author": doc.get("author"),
           "target_words": args.words, "num_pages": len(pages), "pages": pages}
    json.dump(out, open(OUT_PATH, "w"), indent=2, ensure_ascii=False)

    wc = [p["word_count"] for p in pages]
    print(f"{doc.get('title')}: {len(doc['pages'])} manuscript pages -> {len(pages)} book pages")
    print(f"words/page: min={min(wc)} avg={sum(wc)//len(wc)} max={max(wc)}  -> {OUT_PATH}")
    print("\nfirst few beats:")
    for p in pages[:3]:
        tag = f"[ch{p['chapter_no']} start]" if p["chapter_start"] else ""
        print(f"  p{p['page_no']} ({p['word_count']}w) {tag} {p['text'][:80]}...")


if __name__ == "__main__":
    main()
