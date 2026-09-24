"""Render a Markdown file to a polished, professionally formatted PDF.

Adds a title/cover block, embedded project fonts (Poppins + Lora), page-numbered
footers, and richer typography on top of the plain md2pdf.py renderer.

    ../.venv/bin/python docs/md2pdf_pro.py docs/<file>.md \
        --title "Main Title" --subtitle "..." --prepared-for "..." \
        --prepared-by "..." --date "18 August 2026"

Pure-Python (markdown + xhtml2pdf), no system dependencies.
"""
import argparse
import os

import markdown
from xhtml2pdf import pisa

HERE = os.path.dirname(os.path.realpath(__file__))
FONTS = os.path.join(HERE, "_fonts")

CSS = f"""
@font-face {{ font-family: 'Poppins'; src: url('{FONTS}/Poppins-Regular.ttf'); }}
@font-face {{ font-family: 'Poppins'; src: url('{FONTS}/Poppins-Bold.ttf'); font-weight: bold; }}
@font-face {{ font-family: 'PoppinsSemi'; src: url('{FONTS}/Poppins-SemiBold.ttf'); }}
@font-face {{ font-family: 'Lora'; src: url('{FONTS}/Lora.ttf'); }}

@page {{
  size: A4;
  margin: 2.3cm 2.2cm 2.6cm 2.2cm;
  @frame footer {{
    -pdf-frame-content: footerContent;
    bottom: 1.2cm; left: 2.2cm; right: 2.2cm; height: 1cm;
  }}
}}

body {{ font-family: 'Lora'; font-size: 10.5pt; color: #262b31; line-height: 1.5; }}

h1 {{
  font-family: 'Poppins'; font-weight: bold; font-size: 19pt; color: #17365d;
  margin: 2pt 0 3pt 0; padding-bottom: 7pt; border-bottom: 2.4pt solid #17365d;
}}
h2 {{
  font-family: 'PoppinsSemi'; font-size: 13.5pt; color: #17365d;
  margin: 20pt 0 5pt 0; padding-bottom: 3pt; border-bottom: 0.7pt solid #c9d4e3;
}}
h3 {{ font-family: 'PoppinsSemi'; font-size: 11.5pt; color: #2b4a73; margin: 13pt 0 3pt 0; }}

p {{ margin: 5pt 0; }}
strong {{ font-family: 'PoppinsSemi'; color: #14202e; }}
em {{ color: #33475b; }}
a {{ color: #1a5fb4; text-decoration: none; }}
ul, ol {{ margin: 4pt 0 9pt 0; }}
li {{ margin: 3pt 0; }}
hr {{ border: none; border-top: 0.7pt solid #c9d4e3; margin: 16pt 0; }}

blockquote {{
  margin: 10pt 0; padding: 9pt 14pt; background: #eef3fa;
  border-left: 3.5pt solid #17365d; color: #1c2e45; font-size: 10.5pt;
}}

table {{ width: 100%; border-collapse: collapse; margin: 10pt 0; }}
th {{
  background: #17365d; color: #ffffff; text-align: left; padding: 7pt 9pt;
  font-family: 'PoppinsSemi'; font-size: 9.5pt; border: 0.7pt solid #17365d;
}}
td {{ padding: 6pt 9pt; border: 0.7pt solid #c9d4e3; font-size: 9.8pt; vertical-align: top; }}
tr:nth-child(even) td {{ background: #f4f7fb; }}

code {{ font-family: monospace; font-size: 9pt; background: #eef1f5; color: #14202e; }}

/* ---- cover ---- */
.cover {{ margin-top: 3.2cm; }}
.cover-kicker {{
  font-family: 'PoppinsSemi'; font-size: 10pt; color: #6b7c93;
  letter-spacing: 2pt; text-transform: uppercase;
}}
.cover-rule {{ border: none; border-top: 3pt solid #17365d; width: 30%; margin: 12pt 0 18pt 0; }}
.cover-title {{ font-family: 'Poppins'; font-weight: bold; font-size: 30pt; color: #17365d; line-height: 1.12; }}
.cover-sub {{ font-family: 'Lora'; font-size: 13pt; color: #48596c; margin-top: 12pt; line-height: 1.4; }}
.cover-meta {{ margin-top: 3.6cm; font-family: 'Poppins'; font-size: 10.5pt; color: #33475b; }}
.cover-meta .lbl {{ font-family: 'PoppinsSemi'; color: #17365d; }}
.footer-txt {{ font-family: 'Poppins'; font-size: 8pt; color: #8593a5; }}
"""

FOOTER = (
    '<div id="footerContent" class="footer-txt">'
    '{doc} &nbsp;·&nbsp; Confidential &nbsp;·&nbsp; Page '
    '<pdf:pagenumber> of <pdf:pagecount>'
    '</div>'
)


def cover_html(a):
    rows = []
    if a.prepared_for:
        rows.append(f'<div><span class="lbl">Prepared for:</span> {a.prepared_for}</div>')
    if a.prepared_by:
        rows.append(f'<div><span class="lbl">Prepared by:</span> {a.prepared_by}</div>')
    if a.date:
        rows.append(f'<div><span class="lbl">Date:</span> {a.date}</div>')
    sub = f'<div class="cover-sub">{a.subtitle}</div>' if a.subtitle else ""
    kicker = f'<div class="cover-kicker">{a.kicker}</div>' if a.kicker else ""
    return (
        '<div class="cover">'
        f'{kicker}'
        '<hr class="cover-rule"/>'
        f'<div class="cover-title">{a.title}</div>'
        f'{sub}'
        f'<div class="cover-meta">{"".join(rows)}</div>'
        '</div>'
        '<pdf:nextpage/>'
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    ap.add_argument("--title", default="")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--kicker", default="")
    ap.add_argument("--prepared-for", dest="prepared_for", default="")
    ap.add_argument("--prepared-by", dest="prepared_by", default="")
    ap.add_argument("--date", default="")
    ap.add_argument("--doc-name", dest="doc_name", default="")
    a = ap.parse_args()

    raw = open(a.md, encoding="utf-8").read()
    body = markdown.markdown(raw, extensions=["tables", "fenced_code", "sane_lists"])

    cover = cover_html(a) if a.title else ""
    footer = FOOTER.format(doc=a.doc_name or a.title or "")
    html = (
        f"<html><head><meta charset='utf-8'><style>{CSS}</style></head>"
        f"<body>{footer}{cover}{body}</body></html>"
    )

    out = a.md.rsplit(".", 1)[0] + ".pdf"
    with open(out, "wb") as f:
        status = pisa.CreatePDF(html, dest=f, encoding="utf-8")
    print("errors" if status.err else f"-> {out}")


if __name__ == "__main__":
    main()
