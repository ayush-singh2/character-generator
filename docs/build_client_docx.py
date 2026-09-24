"""Build the client answers document as a formatted Word (.docx) file.

Mirrors docs/Client-Answers-Author-Control.html in Word's own styling:
brand-teal headings, a "You asked" callout per section, native tables, and
bullet/numbered lists. No external converter needed (python-docx only).

    ../.venv/bin/python docs/build_client_docx.py
"""
import os

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor, Inches

HERE = os.path.dirname(os.path.realpath(__file__))
OUT = os.path.join(HERE, "Client-Answers-Author-Control.docx")

TEAL = RGBColor(0x0E, 0x7C, 0x72)
TEAL_DEEP = RGBColor(0x0C, 0x5D, 0x55)
INK = RGBColor(0x20, 0x29, 0x2B)
MUTED = RGBColor(0x7C, 0x8A, 0x8C)
WASH_HEX = "E9F6F2"
WASH_LINE = "BFE3DA"
HEAD_HEX = "0E7C72"


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:fill"), hex_fill)
    tcPr.append(sh)


def set_cell_border(cell, color="C9D4E3", sz="4"):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), sz)
        el.set(qn("w:color"), color)
        borders.append(el)
    tcPr.append(borders)


def run(p, text, *, size=11, bold=False, italic=False, color=INK, font="Calibri"):
    r = p.add_run(text)
    r.font.name = font
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    r.font.color.rgb = color
    return r


def spacer(doc, pts=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    run(p, "", size=pts)
    return p


def kicker(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    run(p, text, size=9, bold=True, color=TEAL, font="Calibri")


def section_header(doc, numeral, title):
    doc.add_page_break()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    r = run(p, numeral, size=11, bold=True, color=TEAL, font="Calibri")
    # letter spacing
    rPr = r._element.get_or_add_rPr()
    sp = OxmlElement("w:spacing"); sp.set(qn("w:val"), "80"); rPr.append(sp)

    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h.paragraph_format.space_after = Pt(4)
    run(h, title, size=20, bold=True, color=INK, font="Calibri")

    d = doc.add_paragraph()
    d.alignment = WD_ALIGN_PARAGRAPH.CENTER
    d.paragraph_format.space_after = Pt(8)
    run(d, "◆", size=9, color=TEAL)


def intro(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(12)
    run(p, text, size=10.5, italic=True, color=MUTED)


def you_asked(doc, text):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    shade(cell, "FBFDFD")
    set_cell_border(cell, color="17A08F", sz="6")
    p0 = cell.paragraphs[0]
    p0.paragraph_format.space_after = Pt(3)
    run(p0, "YOU ASKED", size=8, bold=True, color=TEAL_DEEP, font="Calibri")
    p1 = cell.add_paragraph()
    run(p1, text, size=10.5, italic=True, color=RGBColor(0x33, 0x40, 0x3F))
    spacer(doc, 6)


def cards(doc, items):
    """items: list of (heading, body). Rendered as a 1-row table of columns."""
    tbl = doc.add_table(rows=1, cols=len(items))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (head, body) in enumerate(items):
        cell = tbl.cell(0, i)
        set_cell_border(cell)
        ph = cell.paragraphs[0]
        ph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ph.paragraph_format.space_after = Pt(4)
        run(ph, head, size=11, bold=True, color=INK, font="Calibri")
        pb = cell.add_paragraph()
        pb.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run(pb, body, size=9.5, color=RGBColor(0x4C, 0x5A, 0x5C))
    spacer(doc, 6)


def wash(doc, heading, body_runs):
    """body_runs: list of (text, bold, italic) tuples for one centered paragraph."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    shade(cell, WASH_HEX)
    set_cell_border(cell, color=WASH_LINE, sz="8")
    ph = cell.paragraphs[0]
    ph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ph.paragraph_format.space_after = Pt(5)
    run(ph, heading, size=12, bold=True, color=TEAL_DEEP, font="Calibri")
    pb = cell.add_paragraph()
    pb.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for text, bold, italic in body_runs:
        run(pb, text, size=10, bold=bold, italic=italic, color=INK)
    spacer(doc, 6)


def main():
    doc = Document()

    # base style
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = INK

    sec = doc.sections[0]
    sec.top_margin = Inches(0.9)
    sec.bottom_margin = Inches(0.9)
    sec.left_margin = Inches(0.9)
    sec.right_margin = Inches(0.9)

    # ---------- COVER ----------
    for _ in range(4):
        spacer(doc, 10)
    kicker(doc, "ILLUSTRATED  ·  BOOK  ·  STUDIO")
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.paragraph_format.space_after = Pt(6)
    run(t, "Your Book, Your Direction", size=34, bold=True, color=INK, font="Calibri")
    s = doc.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    s.paragraph_format.space_after = Pt(10)
    run(s, "How much the author decides — and how the tool works to it",
        size=13, color=RGBColor(0x48, 0x59, 0x6C))
    d = doc.add_paragraph()
    d.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run(d, "◆", size=10, color=TEAL)
    lead = doc.add_paragraph()
    lead.alignment = WD_ALIGN_PARAGRAPH.CENTER
    lead.paragraph_format.space_before = Pt(10)
    run(lead,
        "A plain answer to your four questions: what goes on each page, how style "
        "and fonts are chosen, how a finished spread is corrected, and where the "
        "limits are. In every case the author decides and the tool executes.",
        size=11, color=INK)

    for _ in range(3):
        spacer(doc, 10)

    meta = doc.add_table(rows=1, cols=2)
    meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (k, v, s2) in enumerate([
        ("PREPARED FOR", "The Author", "CREATIVE CONTROL & CAPABILITIES"),
        ("PREPARED BY", "The Development Team", "18 AUGUST 2026"),
    ]):
        cell = meta.cell(0, i)
        set_cell_border(cell)
        pk = cell.paragraphs[0]; pk.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pk.paragraph_format.space_after = Pt(2)
        run(pk, k, size=8, bold=True, color=MUTED, font="Calibri")
        pv = cell.add_paragraph(); pv.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pv.paragraph_format.space_after = Pt(2)
        run(pv, v, size=12, bold=True, color=INK, font="Calibri")
        ps = cell.add_paragraph(); ps.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run(ps, s2, size=8, color=MUTED, font="Calibri")

    # ---------- I ----------
    section_header(doc, "I", "Choice over each page")
    intro(doc, "Full choice. The tool treats the manuscript as the story and your "
               "instructions as the direction — hands-off or hands-on, page by page.")
    you_asked(doc, "How much choice does the author have over what's on each page? Will the "
                   "tool just draw based on the manuscript, or will the author be able to "
                   "provide specific instructions?")
    cards(doc, [
        ("1  Manuscript-driven", "Write nothing extra and you still get a complete, coherent "
         "book. The tool reads each scene and proposes an illustration for every page."),
        ("2  Per-page notes", "For any page, add a shot list in your own words. Your note is "
         "treated as authoritative and the page is built around it."),
        ("3  Design locked first", "You approve how each character looks before any page is "
         "drawn, so choices carry through the book instead of drifting."),
    ])
    wash(doc, "The author decides four things on every page",
         [("What is on it  ·  who is in it  ·  how it is framed  ·  what mood it carries",
           True, False)])

    # ---------- II ----------
    section_header(doc, "II", "Style, character & font choices")
    intro(doc, "Yes to both. Illustration style, character look and every text setting are "
               "author choices — made from clear samples and previews, not decided for you.")
    you_asked(doc, "Will the author pick the illustration style from a set of samples? And the "
                   "font, size, and placement of the text?")
    cards(doc, [
        ("Illustration style", "Chosen from a set of samples — watercolour, flat colour, "
         "painterly, line-and-wash — then applied consistently to the whole book."),
        ("Character look", "Before the book is built you approve each character's face, outfit, "
         "colours and signature items on a reference sheet."),
        ("Fonts & text", "Font from a curated, print-safe set; a comfortable, adjustable size; "
         "and placement into a calm area of the art."),
    ])
    wash(doc, "The character is approved before the book is designed",
         [("Want the cat orange, the dog in a green cap, or a character with freckles? That is "
           "decided and locked at this step — and then honoured on every page.", False, False)])

    # ---------- III ----------
    section_header(doc, "III", "Corrections after a spread exists")
    intro(doc, "A core feature, not an afterthought. Once a page is illustrated you can request "
               "a specific change — and only that change is applied, everything else kept.")
    you_asked(doc, "How will edits work after spreads are created? Say the author wants a hat on "
                   "the character, or the cat to be orange, or a jump rope added — can they "
                   "make those updates and keep everything else as is?")

    edits = [
        ("You want…", "You say…", "What happens"),
        ("A hat on the character", "“Add a red hat to Ella.”",
         "The hat is added; her face, pose, outfit and the whole scene stay the same."),
        ("The cat to be orange", "“Make the cat orange.”",
         "Only the cat's colour changes; everything else is untouched."),
        ("A jump rope in the scene", "“Put a jump rope in her hands.”",
         "The prop is introduced into the existing scene — no redraw from scratch."),
    ]
    tbl = doc.add_table(rows=len(edits), cols=3)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for ri, row in enumerate(edits):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            set_cell_border(cell)
            p = cell.paragraphs[0]
            if ri == 0:
                shade(cell, WASH_HEX)
                run(p, val, size=9.5, bold=True, color=TEAL_DEEP, font="Calibri")
            else:
                run(p, val, size=9.8, italic=(ci == 1),
                    color=(TEAL_DEEP if ci == 1 else INK))
    spacer(doc, 8)
    cards(doc, [
        ("Targeted, not a redo", "Edits are applied on top of the existing art, so the parts you "
         "already approved are preserved. You refine, not restart."),
        ("Page by page", "A change to one page never affects another. Iterate on a single spread "
         "until it is exactly right."),
        ("Consistency-aware", "If a change should carry through, it can be pushed into the locked "
         "look so every page agrees."),
    ])

    # ---------- IV ----------
    section_header(doc, "IV", "Limits, throughput & upkeep")
    intro(doc, "Straight answers on what the tool is and isn't, so expectations are clear.")
    you_asked(doc, "Any limitations on the final tool? How many books can we create a month, and "
                   "how much upkeep will be required?")
    cards(doc, [
        ("How many books a month?", "No fixed cap. A working author can comfortably produce "
         "several books a month — more in batches. Throughput follows your review time and "
         "the per-image cost, not the software."),
        ("How much upkeep?", "Minimal for you: supply a manuscript, make choices, review pages. "
         "Keeping services current and adding styles or fonts is handled on the development side. "
         "No server to run between books."),
    ])
    wash(doc, "Honest limitations",
         [("Directed, not perfect first try — a page may need one correction pass. "
           "Consistency is held by design but supervised via your up-front approval. Throughput "
           "scales with review capacity and image spend. Unusual requests may take one extra round.",
           False, False)])

    # ---------- V ----------
    section_header(doc, "V", "How a project runs, end to end")
    intro(doc, "The four answers put together. At every step marked “you,” the decision "
               "is yours; the tool executes it — quickly, consistently, print-ready.")
    steps = [
        ("You provide the manuscript", " — with any per-page illustration notes you want."),
        ("You choose the illustration style", " from a set of samples."),
        ("You approve each character's look", " on a reference sheet — locked before the book is drawn."),
        ("The tool illustrates every page", ", holding characters consistent and placing readable text in your font."),
        ("You review and request per-page corrections", " — a hat here, an orange cat there — until each page is right."),
        ("The tool assembles the print-ready PDF", " at one uniform, professional trim size."),
    ]
    for i, (b, rest) in enumerate(steps, 1):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        run(p, f"{i}.  ", size=11, bold=True, color=TEAL, font="Calibri")
        run(p, b, size=10.5, bold=True, color=INK)
        run(p, rest, size=10.5, color=INK)
    spacer(doc, 4)
    wash(doc, "In one line",
         [("You stay the author. The tool does the drawing and the production work under your "
           "direction — and lets you change your mind, one page at a time, right up to the "
           "finished book.", False, False)])

    fn = doc.add_paragraph()
    fn.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fn.paragraph_format.space_before = Pt(14)
    run(fn, "We're glad to walk through any of this live, or to run a short sample — one or "
            "two of your pages, in a style of your choosing — so you can see the control and "
            "the correction loop first-hand.", size=9, italic=True, color=MUTED)

    doc.save(OUT)
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
