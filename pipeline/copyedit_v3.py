"""Copyedit stage — bring every word of the book into Ballast house style.

Runs after `parse`, before art/render. Reads data/storybook.json, sends the title
and each page's text through the text model with the FULL house style guide
(style_guide.py) as system prompt, and writes the corrected text back in place.
Every change is logged to output/copyedit_report.md so the edits are auditable
(policy: auto-correct + report).

Design constraints:
- Preserve line breaks exactly. The renderer splits page text on "\n" and lays it
  out; changing the number of lines would shift pagination. The model is told to
  keep the same newline structure and only fix within it.
- Idempotent: re-running on already-clean text yields no changes.
- Degrades gracefully: if the guide is missing or a page fails to parse, that
  page is left untouched and the run continues.

Set COPYEDIT=0 (or pass --no-copyedit through pb_run) to skip entirely for
authors who require verbatim text.
"""

import json
import os
import re

from . import llm, style_guide, toon_io

STORY_PATH = "data/storybook.json"
REPORT_PATH = "output/copyedit_report.md"

# Kinds whose `text` is author prose we should copyedit. Cover/copyright/dedication
# carry generated or boilerplate text and are handled by their own stages.
EDIT_KINDS = ("content", "backmatter")

_SYSTEM = """\
You are a meticulous copy editor for Ballast Books. You are given one text block \
from a children's picture book. Correct it so it fully complies with the house \
style guide below. Rules:
- Fix ONLY what a house-style rule requires (numbers, dates, punctuation, ellipses, \
dashes, possessives, italics-worthy items, the canonical word list, etc.).
- PRESERVE the author's wording, voice, dialogue, and meaning. Do not rewrite, \
paraphrase, shorten, or "improve" style beyond the rules.
- PRESERVE line breaks EXACTLY: the output must have the same number of lines \
(newlines) as the input, in the same places. Correct only within each line.
- Italics cannot be shown in plain text; do NOT insert markup for them — only \
apply rules that change the actual characters.

Return ONLY JSON:
{
  "corrected": "<the full corrected text, same line breaks>",
  "changes": [{"rule": "<rule id e.g. NUM-1>", "before": "<snippet>", "after": "<snippet>"}]
}
If nothing needs changing, return the text unchanged with "changes": []."""


def _mechanical(text: str) -> tuple[str, list[dict]]:
    """Deterministic fixes for the unambiguous rules, applied before/around the
    model so they're guaranteed regardless of model variance."""
    changes: list[dict] = []
    orig = text

    # ELL-4: Unicode ellipsis or bunched dots -> spaced three-dot form ". . .".
    t2 = text.replace("…", ". . .")
    # 3+ periods (not already spaced) -> ". . ."
    t2 = re.sub(r"(?<!\.)\.{3,}(?!\.)", ". . .", t2)
    if t2 != text:
        changes.append({"rule": "ELL-1/ELL-4", "before": "…/...", "after": ". . ."})
        text = t2

    # MISC-2: collapse double (or more) spaces within a line, per line so newlines
    # and leading indentation intent are preserved.
    def _collapse(line):
        return re.sub(r"(?<=\S) {2,}(?=\S)", " ", line)
    t3 = "\n".join(_collapse(l) for l in text.split("\n"))
    if t3 != text:
        changes.append({"rule": "MISC-2", "before": "double spaces", "after": "single space"})
        text = t3

    if text == orig:
        return orig, []
    return text, changes


def _copyedit_block(text: str) -> tuple[str, list[dict]]:
    """Return (corrected_text, changes) for one text block."""
    if not text or not text.strip():
        return text, []

    text, changes = _mechanical(text)
    nlines = text.count("\n")

    system = style_guide.with_guide(_SYSTEM)
    try:
        res = llm.chat_json(system, text, max_tokens=2000, temperature=0.0)
    except Exception as e:  # noqa: BLE001 — never let one page kill the run
        print(f"    copyedit skipped (model error): {e}")
        return text, changes

    corrected = res.get("corrected", text)
    model_changes = res.get("changes", []) or []

    # Guard: if the model altered the line count, distrust it and keep our
    # mechanical-only result so pagination stays intact.
    if corrected.count("\n") != nlines:
        print(f"    copyedit: line-count drift ({corrected.count(chr(10))} vs {nlines}); "
              "keeping mechanical fixes only")
        return text, changes

    return corrected, changes + model_changes


def copyedit(story_path: str = STORY_PATH, report_path: str = REPORT_PATH) -> dict:
    if os.getenv("COPYEDIT", "1") == "0":
        print("  copyedit disabled (COPYEDIT=0)")
        return {}
    if not style_guide.load():
        print("  copyedit skipped: house style guide not available")
        return {}
    if not os.path.exists(story_path):
        print(f"  copyedit skipped: {story_path} not found")
        return {}

    doc = json.load(open(story_path, encoding="utf-8"))
    report: list[str] = [f"# Copyedit report — {doc.get('title','(untitled)')}\n"]
    total = 0

    # Title.
    title = doc.get("title") or ""
    if title.strip():
        new_title, ch = _copyedit_block(title)
        if new_title != title:
            doc["title"] = new_title
            total += len(ch)
            report.append(f"## Title\n- `{title}` -> `{new_title}`")
            for c in ch:
                report.append(f"  - [{c.get('rule')}] {c.get('before')} -> {c.get('after')}")

    # Page units.
    for u in doc.get("units", []):
        if u.get("kind") not in EDIT_KINDS:
            continue
        text = u.get("text", "")
        if not text.strip():
            continue
        new_text, ch = _copyedit_block(text)
        if new_text != text:
            u["text"] = new_text
            u["lines"] = new_text.split("\n")  # keep lines consistent with text
            total += len(ch)
            pg = u.get("pages") or ["?"]
            report.append(f"\n## Page {pg[0]} ({u.get('kind')})")
            for c in ch:
                report.append(f"- [{c.get('rule')}] `{c.get('before')}` -> `{c.get('after')}`")

    json.dump(doc, open(story_path, "w"), indent=2, ensure_ascii=False)

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    if total == 0:
        report.append("\n_No changes — text already conforms to house style._")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")

    print(f"  copyedit: {total} change(s) -> {report_path}")
    return {"changes": total, "report": report_path}


def copyedit_scenes(data_dir: str, report_path: str = None) -> dict:
    """CPY-1 for the v3 TOON flow: copyedit every page's text in scenes.toon in
    place (house style, verbatim-preserving), and write an audit report. Runs
    after parse_v3, before layout/generate — so the text on the art matches the
    corrected manuscript. No-op when COPYEDIT=0 or the guide is unavailable."""
    if os.getenv("COPYEDIT", "1") == "0":
        print("  copyedit disabled (COPYEDIT=0)"); return {}
    if not style_guide.load():
        print("  copyedit skipped: house style guide not available"); return {}
    path = f"{data_dir}/scenes.toon"
    if not os.path.exists(path):
        print(f"  copyedit skipped: {path} not found"); return {}

    doc = toon_io.load(path)
    report_path = report_path or f"{data_dir}/../output/copyedit_report.md"
    report = [f"# Copyedit report — {doc.get('title','(untitled)')}\n"]
    total = 0
    for sc in doc.get("scenes", []):
        text = sc.get("text", "")
        if not text.strip():
            continue
        new_text, ch = _copyedit_block(text)
        if new_text != text:
            sc["text"] = new_text
            total += len(ch)
            report.append(f"\n## Page {sc.get('page','?')}")
            for c in ch:
                report.append(f"- [{c.get('rule')}] `{c.get('before')}` -> `{c.get('after')}`")

    toon_io.save(doc, path)
    if total == 0:
        report.append("\n_No changes — text already conforms to house style._")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print(f"  copyedit (v3): {total} change(s) -> {report_path}")
    return {"changes": total, "report": report_path}


def main():
    copyedit()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:      # `python -m pipeline.copyedit_v3 <book>/v3/data`
        copyedit_scenes(sys.argv[1])
    else:
        main()
