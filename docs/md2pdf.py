"""Render a Markdown file to a cleanly-styled PDF.

    ../.venv/bin/python docs/md2pdf.py docs/Character-Consistency-Tooling-Request.md

Pure-Python (markdown + xhtml2pdf), no system dependencies.
"""

import sys

import markdown
from xhtml2pdf import pisa

CSS = """
@page { size: A4; margin: 2cm 2.2cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10.5pt;
       color: #232323; line-height: 1.45; }
h1 { font-size: 20pt; color: #17365d; margin: 0 0 4pt 0;
     border-bottom: 2pt solid #17365d; padding-bottom: 6pt; }
h2 { font-size: 13pt; color: #17365d; margin: 16pt 0 4pt 0;
     border-bottom: 0.6pt solid #c9d4e3; padding-bottom: 3pt; }
p  { margin: 5pt 0; }
strong { color: #111; }
em { color: #333; }
a { color: #1a5fb4; text-decoration: none; }
ul, ol { margin: 4pt 0 8pt 0; }
li { margin: 3pt 0; }
hr { border: none; border-top: 0.6pt solid #c9d4e3; margin: 14pt 0; }
blockquote { margin: 8pt 0; padding: 8pt 12pt; background: #eef3fa;
             border-left: 3pt solid #17365d; color: #1c2e45; font-size: 11pt; }
table { width: 100%; border-collapse: collapse; margin: 8pt 0; }
th { background: #17365d; color: #ffffff; text-align: left;
     padding: 6pt 8pt; font-size: 10pt; border: 0.6pt solid #17365d; }
td { padding: 6pt 8pt; border: 0.6pt solid #c9d4e3; font-size: 10pt;
     vertical-align: top; }
tr:nth-child(even) td { background: #f4f7fb; }
code { font-family: Courier, monospace; background: #eef1f4;
       padding: 1pt 3pt; font-size: 9.5pt; }
"""


def convert(md_path, pdf_path=None):
    pdf_path = pdf_path or md_path.rsplit(".", 1)[0] + ".pdf"
    md_text = open(md_path, encoding="utf-8").read()
    body = markdown.markdown(
        md_text, extensions=["tables", "extra", "sane_lists", "smarty"])
    html = (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head>"
            f"<body>{body}</body></html>")
    with open(pdf_path, "wb") as f:
        status = pisa.CreatePDF(html, dest=f, encoding="utf-8")
    if status.err:
        raise RuntimeError(f"PDF generation reported {status.err} error(s)")
    print(f"-> {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "docs/Character-Consistency-Tooling-Request.md"
    convert(src, sys.argv[2] if len(sys.argv) > 2 else None)
