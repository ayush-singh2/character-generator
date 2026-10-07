"""Human-in-the-loop page-correction chatbot (backend core).

After a book is generated, the author opens a per-page chat and says, in plain
language, what is wrong with that page. They can point at a CORRECT page as a
visual reference two ways, interchangeably:

  * drop its image into the chat  -> passed in as `ref_images` (raw PNG bytes),
  * just name it ("like on page 5") -> parsed from the message, OR passed as
    `ref_pages=["5"]`.

Each turn runs ONE instruction-based i2i edit (``pipeline.editor.edit``) on the
CURRENT state of the page, conditioned on:

  * the page being fixed            -> Image 1 (the canvas to modify),
  * every reference page / drop     -> Image 2..N (reference only),
  * the page's locked identity spec -> preserve-context, so identity can't drift.

Because the edit always runs on the latest revision, follow-ups like "a bit
higher" compose naturally on top of the previous change. Nothing is destroyed:
the pre-chat page is backed up once (``.preedit.png``) and every revision is kept
under ``<pages>/.chat/page_<id>/`` so the author can revert.

This module is deliberately framework-free (no FastAPI import) so it can be unit
tested on its own; the server layer wires sessions to HTTP routes later.
"""

import glob
import io
import os
import re

from pipeline import editor

from . import pipeline_api as api

# "page 5", "pg 5", "p5", "page #5" -> "5". Word boundary so "escape" etc. don't hit.
_PAGE_REF_RE = re.compile(r"\b(?:page|pg|p)\s*#?\s*(\d+)\b", re.IGNORECASE)
_COVER_RE = re.compile(r"\bcover\b", re.IGNORECASE)


def parse_page_refs(message: str) -> list[str]:
    """Page ids a free-text message points at: 'make it like page 5 and p12' ->
    ['5','12']; 'match the cover' -> ['cover']. De-duplicated, order preserved."""
    ids = [m.group(1) for m in _PAGE_REF_RE.finditer(message or "")]
    if _COVER_RE.search(message or ""):
        ids.append("cover")
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _page_path(slug: str, page_id: str) -> str:
    """The image the chat edits. We target the TEXT-FREE art layer (not the baked
    page) because the editor now shows the art with the author's words laid over
    it as a movable, editable overlay — so corrections run on the illustration
    alone and can never fight or mangle the text. Older books with no separate
    art fall back to the baked page."""
    art = os.path.join(api.art_dir(slug), f"page_{page_id}.png")
    if os.path.exists(art):
        return art
    return os.path.join(api.pages_dir(slug), f"page_{page_id}.png")


def page_bytes(slug: str, page_id: str) -> bytes | None:
    """The current PNG for a page, or None if that page doesn't exist."""
    p = _page_path(slug, page_id)
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        return f.read()


class PageChatSession:
    """One author conversation about one page. Stateful across turns."""

    def __init__(self, slug: str, page_id: str):
        self.slug = slug
        self.page_id = str(page_id)
        self.path = _page_path(slug, self.page_id)
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"page {self.page_id} not found for {slug}")
        self.turns: list[dict] = []                 # [{role, text, ...}]
        # Keep revisions + the one-time .preedit backup next to the image we
        # actually edit (the art layer), so revert works regardless of layer.
        self._chat_dir = os.path.join(os.path.dirname(self.path), ".chat",
                                      f"page_{self.page_id}")
        os.makedirs(self._chat_dir, exist_ok=True)

    # -- state -------------------------------------------------------------
    def current_bytes(self) -> bytes:
        with open(self.path, "rb") as f:
            return f.read()

    def _revisions(self) -> list[str]:
        return sorted(glob.glob(os.path.join(self._chat_dir, "rev_*.png")))

    def _next_rev_path(self) -> str:
        return os.path.join(self._chat_dir, f"rev_{len(self._revisions()):03d}.png")

    # -- reference resolution ---------------------------------------------
    def _resolve_refs(self, message, ref_pages, ref_images):
        """Collect reference images from (a) explicit ref_pages, (b) page numbers
        named in the message, (c) dropped raw images. A page can't reference
        itself. Returns (ref_page_ids_used, images, missing_ids).

        If the client sends explicit ``ref_pages`` we trust those and do NOT also
        scrape numbers out of the message. This matters because the UI numbers
        pages by their reading-order POSITION, which (on a book whose pages skip
        ids — text-only pages are never illustrated) differs from the backend
        file id. The client resolves "page 11" to the real id and passes it here;
        re-parsing the literal "11" would re-introduce a non-existent page and
        make the whole turn fail. Only when no ref_pages are given (e.g. the
        legacy static UI) do we fall back to parsing the message text."""
        named = list(ref_pages or []) or parse_page_refs(message)
        wanted, seen = [], set()
        for i in named:
            i = str(i)
            if i != self.page_id and i not in seen:
                seen.add(i)
                wanted.append(i)
        used, missing, imgs = [], [], []
        for i in wanted:
            b = page_bytes(self.slug, i)
            if b is not None:
                used.append(i)
                imgs.append(b)
            else:
                missing.append(i)
        imgs += [b for b in (ref_images or []) if b]
        return used, imgs, missing

    # -- request building (pure; no model call) ---------------------------
    def build_request(self, message, ref_pages=None, ref_images=None):
        """Build (instruction, images, meta) for a turn WITHOUT calling the model.
        Split out so the logic can be unit-tested offline."""
        base = self.current_bytes()
        used, ref_imgs, missing = self._resolve_refs(message, ref_pages, ref_images)
        n_dropped = len(ref_imgs) - len(used)

        # Describe each reference part so the model's "Image N" labels (added by
        # editor._labeled_parts) line up with what the author meant.
        ref_desc = ""
        if ref_imgs:
            labels = []
            idx = 2                                   # Image 1 is the page being edited
            for pid in used:
                labels.append(f"Image {idx} is page {pid}")
                idx += 1
            for _ in range(n_dropped):
                labels.append(f"Image {idx} is a reference the author provided")
                idx += 1
            ref_desc = (" The other image(s) are REFERENCE ONLY, showing the "
                        "correct version to match — do NOT copy them wholesale, "
                        "use them only to guide the requested change (" +
                        "; ".join(labels) + ").")

        # Light continuity so relative follow-ups ("a bit higher") have an anchor.
        prior = [t["text"] for t in self.turns if t["role"] == "user"]
        cont = ""
        if prior:
            cont = (" (Continuing edits to the same page; earlier requests were: "
                    + " | ".join(p[:120] for p in prior[-3:]) + ".)")

        # A SHORT identity anchor — just who's on the page. The full multi-KB
        # locks spec (api._page_locks_context) is for the pipeline's blind
        # automated repair; fed to an interactive one-line edit it reads as
        # "here is the whole scene, make it match" and the model RE-RENDERS the
        # entire page. The model can already see Image 1, so naming the cast and
        # saying "keep them as they look, change only X" preserves far better.
        cast = api._page_cast(self.slug, self.page_id)
        who = (" The character(s) in this scene — " + ", ".join(cast) +
               " — must keep the exact same appearance, outfit, colours and "
               "proportions they already have in Image 1." if cast else "")

        instruction = (
            "You are editing an existing children's-book illustration (Image 1). "
            "Make only this change: " + (message or "").strip().rstrip(".") + "."
            + ref_desc
            + " This is a SMALL, LOCAL edit — NOT a redraw. Keep everything else "
              "in Image 1 exactly as it already is: the same composition, framing, "
              "camera, character identities, poses, outfits, colours, lighting, "
              "background, art style and any existing text. Do not re-draw or "
              "re-style the page, do not move or resize anything that was not "
              "mentioned, and add no new text."
            + who
            + cont
        )
        images = [base] + ref_imgs
        meta = {"ref_pages": used, "dropped_refs": n_dropped,
                "missing_pages": missing, "n_images": len(images),
                "has_locks": bool(who)}
        return instruction, images, meta

    # -- a turn ------------------------------------------------------------
    def send(self, message, ref_pages=None, ref_images=None, *,
             box=None, model=None, backend=None, dry_run=False):
        """Run one correction turn. On dry_run, returns the built request without
        touching the model or disk — used by tests and by a 'preview' UI.

        ``box`` (normalised [x0,y0,x1,y1], 0..1) restricts the edit to a region:
        we crop it, fix only that crop and feather-paste it back, so every pixel
        OUTSIDE the box is preserved exactly. This is the surgical path — a
        whole-page i2i edit re-rolls the entire scene and is why an unselected
        edit can come back "completely different"."""
        instruction, images, meta = self.build_request(message, ref_pages, ref_images)
        meta["masked"] = bool(box)
        self.turns.append({"role": "user", "text": message,
                           "ref_pages": meta["ref_pages"],
                           "dropped_refs": meta["dropped_refs"]})

        if meta["missing_pages"]:
            # Tell the author instead of silently editing without the reference.
            reply = ("I couldn't find page(s) " + ", ".join(meta["missing_pages"])
                     + " to use as a reference. Check the page number, or drop the "
                     "image in directly.")
            self.turns.append({"role": "assistant", "text": reply, "error": "missing_ref"})
            return {"ok": False, "reply": reply, "meta": meta}

        if dry_run:
            self.turns.append({"role": "assistant", "text": "(dry-run — not applied)"})
            return {"ok": True, "dry_run": True, "instruction": instruction,
                    "meta": meta, "reply": self._ack(message, meta)}

        # one-time backup of the author's starting point
        backup = self.path.replace(".png", ".preedit.png")
        if not os.path.exists(backup):
            with open(backup, "wb") as f:
                f.write(self.current_bytes())

        if box:
            # Masked repair: only the boxed region is redrawn, the rest is kept
            # pixel-for-pixel. Pass the user's plain request (inpaint_region adds
            # its own "keep framing/identity" wrapper); references ride along.
            out = editor.inpaint_region(images[0], box, message,
                                        refs=images[1:], model=model, backend=backend)
        else:
            out = editor.to_square(editor.edit(instruction, images,
                                               model=model, backend=backend))
        rev = self._next_rev_path()
        with open(rev, "wb") as f:
            f.write(out)
        with open(self.path, "wb") as f:                 # live page = latest revision
            f.write(out)

        reply = self._ack(message, meta)
        self.turns.append({"role": "assistant", "text": reply,
                           "revision": os.path.basename(rev)})
        return {"ok": True, "reply": reply, "revision": os.path.basename(rev),
                "page_url": f"/api/projects/{self.slug}/assets/pages/"
                            f"page_{self.page_id}.png", "meta": meta}

    def revert(self):
        """Undo the last applied revision (back to the previous one, or the
        pre-chat original). Returns True if something was undone."""
        revs = self._revisions()
        if not revs:
            return False
        os.remove(revs[-1])
        remaining = self._revisions()
        src = remaining[-1] if remaining else self.path.replace(".png", ".preedit.png")
        if not os.path.exists(src):
            return False
        with open(src, "rb") as f:
            data = f.read()
        with open(self.path, "wb") as f:
            f.write(data)
        self.turns.append({"role": "system", "text": "Reverted last change."})
        return True

    def _ack(self, message, meta):
        """A short deterministic confirmation (no extra LLM call)."""
        bits = []
        if meta["ref_pages"]:
            bits.append("using page " + ", ".join(meta["ref_pages"]) + " as reference")
        if meta["dropped_refs"]:
            bits.append(f"using {meta['dropped_refs']} dropped image(s) as reference")
        tail = (" (" + ", ".join(bits) + ")") if bits else ""
        return f"Applying: {(message or '').strip()}{tail}."


# -- session registry (so the server can keep a chat alive across requests) --
_SESSIONS: dict[tuple, PageChatSession] = {}


def get_session(slug: str, page_id: str, *, fresh: bool = False) -> PageChatSession:
    key = (slug, str(page_id))
    if fresh or key not in _SESSIONS:
        _SESSIONS[key] = PageChatSession(slug, str(page_id))
    return _SESSIONS[key]


# -- CLI for manual live testing --------------------------------------------
def _main():
    import argparse
    ap = argparse.ArgumentParser(description="Page-correction chatbot (manual test)")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--page", required=True)
    ap.add_argument("--message", required=True)
    ap.add_argument("--ref-page", action="append", default=[],
                    help="reference page id (repeatable)")
    ap.add_argument("--ref-image", action="append", default=[],
                    help="path to a dropped reference image (repeatable)")
    ap.add_argument("--dry-run", action="store_true",
                    help="build the request and print it; do not call the model")
    ap.add_argument("--backend", default=None, help="openrouter | google")
    a = ap.parse_args()

    drops = []
    for p in a.ref_image:
        with open(p, "rb") as f:
            drops.append(f.read())
    s = get_session(a.slug, a.page)
    r = s.send(a.message, ref_pages=a.ref_page, ref_images=drops,
               backend=a.backend, dry_run=a.dry_run)
    print("reply:", r.get("reply"))
    print("meta :", r.get("meta"))
    if r.get("dry_run"):
        print("\n--- instruction ---\n" + r["instruction"])
    elif r.get("ok"):
        print("revision:", r.get("revision"), "->", s.path)


if __name__ == "__main__":
    _main()
