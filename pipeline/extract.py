"""Stage 1 — PDF text extraction.

Reads a manuscript PDF and produces a structured JSON of pages and chapters.
This is the raw input that every later stage (character mining, per-page scene
prompts) reads from, so we keep it dumb and lossless: just text + light
structure, no interpretation.
"""

import glob
import json
import os
import re
from dataclasses import asdict, dataclass

import pdfplumber

MANUSCRIPT_DIR = "manuscript"
OUT_PATH = "data/manuscript.json"

# A chapter heading like "Chapter 1: The Weight of the Gaze"
CHAPTER_RE = re.compile(r"^\s*Chapter\s+(\d+)\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass
class Page:
    page_no: int            # 1-based page index in the PDF
    text: str
    chapter_no: int | None  # chapter this page belongs to, if known
    chapter_title: str | None


def find_manuscript() -> str:
    pdfs = sorted(glob.glob(os.path.join(MANUSCRIPT_DIR, "*.pdf")))
    if not pdfs:
        raise FileNotFoundError(f"No PDF found in {MANUSCRIPT_DIR}/")
    return pdfs[0]


def _norm(s: str) -> str:
    """Normalise a heading for matching: lowercase, strip punctuation/quotes."""
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _toc_titles(page_texts: list[str]) -> list[str]:
    """Read story titles from the Contents page (between 'Contents' and the end)."""
    for text in page_texts:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines and _norm(lines[0]) == "contents":
            titles = []
            for ln in lines[1:]:
                if _norm(ln) in ("follow penguin", "copyright"):
                    break
                titles.append(ln)
            return titles
    return []


def extract(pdf_path: str, *, apply_meta: bool = True) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        page_texts = [(p.extract_text() or "").strip() for p in pdf.pages]

    pages: list[Page] = []
    toc = _toc_titles(page_texts)
    toc_norm = {_norm(t): t for t in toc}
    seen: set[str] = set()

    cur_no: int | None = None
    cur_title: str | None = None
    for i, text in enumerate(page_texts):
        first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")

        # Mode A: explicit "Chapter N:" headings (novels).
        m = CHAPTER_RE.search(text)
        if m:
            cur_no, cur_title = int(m.group(1)), m.group(2).strip()
        # Mode B: anthology — a page whose first line matches a Contents title.
        elif toc_norm and len(first) <= 60 and _norm(first) in toc_norm and _norm(first) not in seen:
            seen.add(_norm(first))
            cur_no = len(seen)
            cur_title = toc_norm[_norm(first)]

        pages.append(Page(page_no=i + 1, text=text, chapter_no=cur_no, chapter_title=cur_title))

    title, author = _guess_title_author(page_texts)
    # Manual override for cases where PDF extraction garbles the title
    # (e.g. dropped apostrophes). Edit manuscript/meta.json to set these.
    # Only applied for the fixed-manuscript CLI pipeline — callers extracting
    # arbitrary uploads (e.g. the Streamlit app) pass apply_meta=False so the
    # real extracted title/author is used instead of this single override.
    meta_path = os.path.join(MANUSCRIPT_DIR, "meta.json")
    if apply_meta and os.path.exists(meta_path):
        meta = json.load(open(meta_path))
        title = meta.get("title", title)
        author = meta.get("author", author)

    return {
        "source_pdf": os.path.basename(pdf_path),
        "title": title,
        "author": author,
        "num_pages": len(pages),
        "num_stories": len(seen) if toc else None,
        "pages": [asdict(p) for p in pages],
    }


_NOISE = {"puffin books", "illustrations by", "contents", "copyright", "puffin"}


def _guess_title_author(page_texts: list[str]) -> tuple[str | None, str | None]:
    """Title/author from the first text-bearing page; skip blank/boilerplate lines."""
    for text in page_texts:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        good = [ln for ln in lines if not any(n in ln.lower() for n in _NOISE)
                and not ln.lower().startswith("illustrat")]
        if len(good) >= 2:
            # An ALL-CAPS line is usually the title; the name line is the author.
            caps = [ln for ln in good if ln.isupper()]
            title = max(caps, key=len).title() if caps else good[0]
            author = next((ln for ln in good if ln != title and ln.replace(".", "").replace(" ", "").isalpha()
                           and ln.isupper()), None)
            author = author.title() if author else (good[0] if good[0] != title else good[1])
            return title, author
    return None, None


def main() -> None:
    pdf_path = find_manuscript()
    doc = extract(pdf_path)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)

    chapters = sorted({(p["chapter_no"], p["chapter_title"]) for p in doc["pages"] if p["chapter_no"]})
    label = "Stories" if doc.get("num_stories") else "Chapters"
    print(f"Title : {doc['title']}")
    print(f"Author: {doc['author']}")
    print(f"Pages : {doc['num_pages']}  ->  {OUT_PATH}")
    print(f"{label} ({len(chapters)}):")
    for no, t in chapters:
        print(f"  {no}. {t}")


if __name__ == "__main__":
    main()
