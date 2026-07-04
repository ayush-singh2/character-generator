"""Stage 1 (picture-book) — parse a pre-paginated .docx manuscript.

The new manuscripts are children's picture books that already carry their own
pagination and art direction inline, e.g.:

    I'm Not Different, I'm Unique
    Shakayla Sparks
    Page 1 – title page
    Page 2 – copyright
    Page 3 – dedication
    Pages 4 & 5 – spread
    Hi! My name is Augusteast.
    ...
    Pages 16 & 17 – spread
    (different pictures of kids in different kitchens)
    ...

So unlike the anthology flow we do NOT re-paginate by word count. We honour the
manuscript's own page units. Each unit becomes one rendered landscape page
(a spread or a single page), classified by kind:

    cover | title | copyright | dedication | content | backmatter

Run:  python -m pipeline.storybook
In:   manuscript/<name>.docx   (first .docx found, or $STORYBOOK_DOCX)
Out:  data/storybook.json
"""

import glob
import json
import os
import re
import zipfile
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MANUSCRIPT_DIR = "manuscript"
OUT_PATH = "data/storybook.json"

# A page/spread directive line: "Page 1 – title page", "Pages 4 & 5 – spread",
# "Page 8", "Pages 16 & 17". The en-dash/hyphen and trailing note are optional.
PAGE_RE = re.compile(
    r"^\s*Pages?\s+(\d+)(?:\s*(?:&|and|,|-|–|—|to)\s*(\d+))?\s*(?:[–—-]\s*(.*))?$",
    re.IGNORECASE,
)
COVER_RE = re.compile(r"^\s*Cover\s*[:\-–—]?\s*(.*)$", re.IGNORECASE)
# A parenthetical art-direction aside, e.g. "(different pictures of kids ...)".
PAREN_RE = re.compile(r"^\s*\((.+)\)\s*$")


def _paragraphs(docx_path: str) -> list[str]:
    """Extract non-empty paragraph strings from a .docx in document order."""
    z = zipfile.ZipFile(docx_path)
    root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for para in root.iter(f"{{{W_NS}}}p"):
        text = "".join(t.text or "" for t in para.iter(f"{{{W_NS}}}t"))
        text = text.replace("’", "'").replace("‘", "'").strip()
        if text:
            out.append(text)
    return out


def _classify(note: str) -> str:
    """Map a directive's trailing note to a page kind."""
    n = note.lower()
    if "title" in n:
        return "title"
    if "copyright" in n or "acknowledg" in n:
        return "copyright"
    if "dedication" in n:
        return "dedication"
    return "content"


def parse(docx_path: str) -> dict:
    paras = _paragraphs(docx_path)

    title, author = None, None
    units: list[dict] = []
    cur: dict | None = None
    seen_directive = False

    def push(unit):
        units.append(unit)

    for raw in paras:
        cover_m = COVER_RE.match(raw)
        page_m = PAGE_RE.match(raw)

        # --- a "Cover: ..." line ---
        if cover_m and not seen_directive:
            seen_directive = True
            ctitle = cover_m.group(1).strip()
            if ctitle and not title:
                title = ctitle
            cur = {"kind": "cover", "pages": [], "label": "Cover",
                   "art_direction": "", "lines": []}
            push(cur)
            continue

        # --- a "Page N" / "Pages N & M" directive ---
        if page_m:
            seen_directive = True
            a = int(page_m.group(1))
            b = int(page_m.group(2)) if page_m.group(2) else None
            note = (page_m.group(3) or "").strip()
            pages = [a] if b is None else [a, b]
            cur = {
                "kind": _classify(note),
                "pages": pages,
                "label": f"Page {a}" if b is None else f"Pages {a}–{b}",
                "is_spread": b is not None or "spread" in note.lower(),
                "art_direction": note,
                "lines": [],
            }
            push(cur)
            continue

        # --- leading title / author block, before any directive ---
        if not seen_directive:
            if title is None:
                title = raw
            elif author is None:
                author = raw
            continue

        # --- body line: attach to current unit ---
        if cur is None:
            continue
        pm = PAREN_RE.match(raw)
        if pm:                       # parenthetical = art direction, not page text
            extra = pm.group(1).strip()
            cur["art_direction"] = (cur["art_direction"] + " " + extra).strip() \
                if cur["art_direction"] else extra
        else:
            cur["lines"].append(raw)

    # Drop exact-duplicate content units (the source manuscripts sometimes
    # repeat a block by copy-paste error, e.g. "I'm Unique" has Page 13 twice).
    deduped, seen_text = [], set()
    for u in units:
        # Whitespace/punctuation-insensitive key: source repeats differ only by
        # spacing around an em-dash.
        body = re.sub(r"[\s—–-]+", "", "\n".join(u["lines"]).lower())
        if u["lines"] and body in seen_text:
            print(f"  (skipping duplicate {u['label']})")
            continue
        if u["lines"]:
            seen_text.add(body)
        deduped.append(u)
    units = deduped

    # Mark back matter: content units after the story whose text is prose guides.
    for u in units:
        u["text"] = "\n".join(u["lines"])
        kind = u["kind"]
        if kind == "content":
            joined = u["text"].lower()
            if re.search(r"parent.?s.? guide|informational|tips to support|volunteering ideas", joined):
                u["kind"] = "backmatter"

    # Split each 2-page spread into two single pages (manuscript-faithful 1:1).
    units = expand_spreads(units)

    doc = {
        "source_docx": docx_path,
        "title": title,
        "author": author,
        "num_units": len(units),
        "units": units,
    }
    return doc


def _split_lines(lines: list[str], n: int = 2) -> list[list[str]]:
    """Split text lines into n roughly word-balanced parts at line boundaries."""
    words = [len(l.split()) for l in lines]
    total = sum(words) or 1
    target = total / n
    parts: list[list[str]] = []
    cur: list[str] = []
    cum = 0
    for l, w in zip(lines, words):
        cur.append(l)
        cum += w
        if cum >= target and len(parts) < n - 1:
            parts.append(cur)
            cur, cum = [], 0
    parts.append(cur)
    while len(parts) < n:
        parts.append([])
    return parts


def expand_spreads(units: list[dict]) -> list[dict]:
    """Turn each 2-page 'spread' content unit into TWO single pages, splitting
    its text in half. The first page REUSES the spread's existing illustration;
    the second page needs a NEW illustration. This matches the manuscript's own
    page count (no more cramming a spread's text onto one page)."""
    out = []
    for u in units:
        if u["kind"] == "content" and len(u.get("pages", [])) == 2 and u["lines"]:
            a, b = u["pages"]
            half_a, half_b = _split_lines(u["lines"], 2)
            out.append({
                "kind": "content", "pages": [a], "label": f"Page {a}",
                "is_spread": False, "art_direction": u.get("art_direction", ""),
                "lines": half_a, "text": "\n".join(half_a),
                "art_source": "existing", "art_page": a,  # reuse page_{a}.png
            })
            out.append({
                "kind": "content", "pages": [b], "label": f"Page {b}",
                "is_spread": False, "art_direction": u.get("art_direction", ""),
                "lines": half_b, "text": "\n".join(half_b),
                "art_source": "new", "art_page": b,        # generate page_{b}.png
            })
        else:
            u.setdefault("art_source", "existing" if u["kind"] == "content" else None)
            u.setdefault("art_page", u["pages"][0] if u.get("pages") else None)
            out.append(u)
    return out


def as_manuscript_doc(doc: dict) -> dict:
    """Adapt the picture-book page model to the {title, author, pages:[...]}
    shape the character/style miners expect (they read doc['pages'][i]['text'])."""
    pages = []
    for u in doc["units"]:
        if u["kind"] in ("content", "backmatter") and u.get("text", "").strip():
            pages.append({
                "page_no": u["pages"][0] if u["pages"] else len(pages) + 1,
                "text": u["text"],
                "chapter_no": None,
                "chapter_title": None,
            })
    return {"title": doc.get("title"), "author": doc.get("author"), "pages": pages}


def _find_docx() -> str:
    env = os.getenv("STORYBOOK_DOCX")
    if env:
        return env
    cands = sorted(glob.glob(os.path.join(MANUSCRIPT_DIR, "*.docx")))
    cands = [c for c in cands if not os.path.basename(c).startswith("~")]
    if not cands:
        raise SystemExit("No .docx found in manuscript/. Set STORYBOOK_DOCX.")
    return cands[0]


def main() -> None:
    path = _find_docx()
    doc = parse(path)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    json.dump(doc, open(OUT_PATH, "w"), indent=2, ensure_ascii=False)

    print(f"Parsed: {doc['title']}  by {doc['author']}")
    print(f"Source: {path}")
    print(f"{doc['num_units']} page-units -> {OUT_PATH}\n")
    for u in doc["units"]:
        kind = u["kind"]
        nlines = len(u["lines"])
        art = f"  art:[{u['art_direction'][:40]}]" if u["art_direction"] else ""
        preview = (u["lines"][0][:48] + "…") if u["lines"] else "(no text)"
        print(f"  {u['label']:<14} {kind:<11} {nlines:>2} lines  {preview}{art}")


if __name__ == "__main__":
    main()
