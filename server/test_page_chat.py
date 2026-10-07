"""Offline tests for the page-correction chatbot core (server/page_chat.py).

Runs with the project venv, no pytest, no network:
    .venv/bin/python -m server.test_page_chat

It builds a throwaway "book" of solid-colour pages under a temp dir, points the
chatbot's path helpers at it, and exercises everything that does NOT need the
image model: page-reference parsing, reference resolution (named + dropped +
missing), multi-image interleaving, the locks/preserve-framing, multi-turn
continuity, and revert. The single model-calling line (editor.edit) is only hit
when dry_run=False, which we stub so a live key isn't required.
"""

import io
import os
import tempfile

from PIL import Image

from . import page_chat, pipeline_api as api


def _png(color):
    b = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(b, "PNG")
    return b.getvalue()


def _check(name, cond):
    print(("  PASS " if cond else "  FAIL ") + name)
    assert cond, name


def main():
    tmp = tempfile.mkdtemp(prefix="pagechat_test_")
    pages = os.path.join(tmp, "books", "demo", "v3", "output", "pages")
    os.makedirs(pages, exist_ok=True)
    for pid, col in (("1", "red"), ("2", "green"), ("5", "blue"), ("cover", "black")):
        with open(os.path.join(pages, f"page_{pid}.png"), "wb") as f:
            f.write(_png(col))

    # Point the API path helpers + the (unused here) locks loader at our temp book.
    api.BOOKS = os.path.join(tmp, "books")
    # No scenes/plan in the fake book -> locks come back "" (fail-open). Good: it
    # proves the chatbot works even before a book has a parsed plan.
    page_chat.api = api  # ensure the module sees our patched BOOKS

    print("parse_page_refs:")
    _check("named pages", page_chat.parse_page_refs("make it like page 5 and p12")
           == ["5", "12"])
    _check("cover + dedupe", page_chat.parse_page_refs("match the cover, page 5, p5")
           == ["5", "cover"])
    _check("no false hit on words", page_chat.parse_page_refs("the puppy escaped") == [])

    print("session + build_request (named reference):")
    s = page_chat.PageChatSession("demo", "1")
    instr, images, meta = s.build_request(
        "the logo should be on the chest, like on page 5")
    _check("base + 1 reference image", len(images) == 2 and meta["n_images"] == 2)
    _check("resolved page 5", meta["ref_pages"] == ["5"])
    _check("no missing", meta["missing_pages"] == [])
    _check("reference described in instruction", "Image 2 is page 5" in instr)
    _check("preserve-framing present",
           "SMALL, LOCAL edit" in instr and "Keep everything else" in instr)
    _check("self not referenced",
           "1" not in page_chat.PageChatSession("1" if False else "demo", "1")
           ._resolve_refs("edit page 1 please", None, None)[0])

    print("dropped-image reference:")
    instr2, images2, meta2 = s.build_request("match this colour", ref_images=[_png("purple")])
    _check("base + dropped", len(images2) == 2 and meta2["dropped_refs"] == 1)
    _check("dropped described", "a reference the author provided" in instr2)

    print("missing reference is reported, not silently edited:")
    r = s.send("make it like page 99", dry_run=True)
    _check("missing flagged", r["ok"] is False and r["meta"]["missing_pages"] == ["99"])
    _check("friendly reply", "couldn't find page" in r["reply"])

    print("multi-turn continuity:")
    s2 = page_chat.PageChatSession("demo", "2")
    s2.send("move the hat up", dry_run=True)
    instr3, _, _ = s2.build_request("a bit higher")
    _check("prior turn carried as context", "earlier requests were" in instr3
           and "move the hat up" in instr3)

    print("apply + revert (model stubbed):")
    s3 = page_chat.PageChatSession("demo", "5")
    orig = s3.current_bytes()
    page_chat.editor.edit = lambda instruction, imgs, **k: _png("yellow")  # stub
    page_chat.editor.to_square = lambda b: b
    out = s3.send("brighten it", model=None)
    _check("applied ok", out["ok"] and out.get("revision") == "rev_000.png")
    _check("backup made", os.path.exists(s3.path.replace(".png", ".preedit.png")))
    _check("live page changed", s3.current_bytes() != orig)
    s3.send("more", model=None)
    _check("second revision", out2 := True and os.path.exists(
        os.path.join(s3._chat_dir, "rev_001.png")))
    _check("revert undoes last", s3.revert())
    _check("revert restored prev revision", os.path.exists(
        os.path.join(s3._chat_dir, "rev_000.png"))
        and not os.path.exists(os.path.join(s3._chat_dir, "rev_001.png")))

    print("\nALL PAGE-CHAT CORE TESTS PASSED")


if __name__ == "__main__":
    main()
