"""Thin, path-safe wrappers over the v3 pipeline for the interactive endpoints.

Design rule: the multi-stage pipeline (parse..book) is driven as SUBPROCESSES by
jobs.py because those stages chdir + bind module-level relative paths (V3_DIR).
The functions here are only the *interactive* bits that are a single call and
must run in-process for the request:

  - style override      (rewrite characters.toon `style` after parse)
  - read characters      (for the Characters page)
  - redesign a character (one editor.edit() -> overwrite that ref sheet)
  - list / correct pages (one editor.edit() -> overwrite that page)
  - locate the PDF

All of these use ABSOLUTE paths and never touch the pipeline's cwd-relative
globals, so they're safe to call from request threads.
"""

import glob
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from pipeline import canon_rules, editor, generate_v7, items_v7, plan_v3, toon_io

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Books live under STATE_DIR (persistent disk in prod; repo locally).
STATE_DIR = os.environ.get("BB_STATE_DIR", REPO)
BOOKS = os.path.join(STATE_DIR, "books")

# Map the New Project style dropdown labels to a full style dict that the
# pipeline's plan_v3.style_text() understands. The manuscript-detected style is
# replaced by the author's explicit choice (Author-Control §2a).
STYLE_MAP = {
    "Storybook Illustration": {
        "name": "Warm Storybook Illustration", "medium": "soft painterly digital illustration",
        "linework": "gentle rounded shapes, light outlines", "palette": "warm, saturated storybook colours",
        "lighting": "soft directional light", "mood": "warm, inviting, tender",
        "influences": "classic picture-book illustration",
    },
    "Watercolor": {
        "name": "Watercolour Storybook", "medium": "hand-painted watercolour",
        "linework": "loose wet edges, minimal outline", "palette": "soft translucent washes",
        "lighting": "diffuse natural light", "mood": "calm, gentle, airy",
        "influences": "traditional watercolour picture books",
    },
    "Flat Vector": {
        "name": "Flat Vector", "medium": "clean flat vector illustration",
        "linework": "crisp geometric shapes, no gradients", "palette": "bold flat colour blocks",
        "lighting": "flat, no shading", "mood": "modern, playful, graphic",
        "influences": "contemporary flat editorial illustration",
    },
    "Digital Painting": {
        "name": "Digital Painting", "medium": "rich digital painting",
        "linework": "painterly, no hard outlines", "palette": "deep layered colour",
        "lighting": "dramatic, volumetric", "mood": "immersive, cinematic",
        "influences": "concept-art storybook painting",
    },
    "Line Art": {
        "name": "Line-and-Wash", "medium": "ink line art with light wash",
        "linework": "confident black linework", "palette": "restrained, mostly monochrome with light colour",
        "lighting": "simple flat wash", "mood": "classic, clean, timeless",
        "influences": "vintage line-and-wash children's books",
    },
    "3D Render": {
        "name": "3D Render", "medium": "soft 3D rendered illustration",
        "linework": "no outlines, rounded 3D forms", "palette": "friendly saturated colour",
        "lighting": "soft global illumination", "mood": "cute, tactile, modern",
        "influences": "animated-film picture books",
    },
}


def book_dir(slug):
    return os.path.join(BOOKS, slug)


def data_dir(slug):
    return os.path.join(book_dir(slug), "v3", "data")


def refs_dir(slug):
    return os.path.join(book_dir(slug), "v3", "refs")


def pages_dir(slug):
    return os.path.join(book_dir(slug), "v3", "output", "pages")


def art_dir(slug):
    return os.path.join(book_dir(slug), "v3", "output", "art")


# ---------------------------------------------------------------------------
# Style override
# ---------------------------------------------------------------------------

def apply_style_override(slug, style_label, aesthetic="", palette=None, restrict=False):
    """Replace the manuscript-detected style in characters.toon with the author's
    chosen style. Called right after parse, before refs. No-op if the file or
    label is missing."""
    path = os.path.join(data_dir(slug), "characters.toon")
    if not os.path.exists(path) or not style_label:
        return False
    chars = toon_io.load(path)
    style = dict(STYLE_MAP.get(style_label, {"name": style_label}))
    if aesthetic:
        style["mood"] = (style.get("mood", "") + f"; {aesthetic}").strip("; ")
    if palette:
        hexes = ", ".join(palette)
        style["palette"] = (f"restricted to this palette only: {hexes}"
                            if restrict else f"{style.get('palette','')}; favour {hexes}").strip("; ")
    chars["style"] = style
    toon_io.save(chars, path)
    return True


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------

def read_characters(slug):
    """Characters for the Characters page: name, appearance lock text, whether a
    high-consistency ref sheet is expected, and the ref image url if rendered."""
    dd = data_dir(slug)
    if not os.path.exists(os.path.join(dd, "characters.toon")):
        return []
    plan = plan_v3.load(dd)
    out = []
    for c in plan["characters"]:
        name = c["name"]
        ref = os.path.join(refs_dir(slug), f"{plan_v3.slug(name)}.png")
        out.append({
            "name": name,
            "high": plan_v3.is_high(c),
            "lock": plan_v3.char_lock(c),
            "has_ref": os.path.exists(ref),
            "ref_url": f"/api/projects/{slug}/assets/refs/{plan_v3.slug(name)}.png"
                       if os.path.exists(ref) else None,
        })
    return out


def redesign_character(slug, name, instruction, photo_bytes=None):
    """One instruction-based edit of a character's reference sheet, mirroring
    refs_v3's individual-sheet prompt so style/identity stay coherent. Overwrites
    v3/refs/<slug(name)>.png and returns the new bytes."""
    dd = data_dir(slug)
    plan = plan_v3.load(dd)
    c = plan["by"].get(name)
    lock = plan_v3.char_lock(c) if c else name
    style = plan_v3.style_text(plan)
    base = ("Using the attached reference PHOTO for likeness, " if photo_bytes else "") + \
           f"repaint this square canvas as a clean character REFERENCE SHEET of {name} " \
           f"in this style: {style}."
    instr = (
        f"{base} {lock}. Show a clear front PORTRAIT and a FULL-BODY view side by "
        f"side, plain white background, friendly expression, facing forward. "
        f"Only {name}; no other character. No text. "
        f"Author's requested change: {instruction}"
    )
    imgs = [editor.blank_square()] + ([photo_bytes] if photo_bytes else [])
    out = editor.to_square(editor.edit(instr, imgs))
    os.makedirs(refs_dir(slug), exist_ok=True)
    path = os.path.join(refs_dir(slug), f"{plan_v3.slug(name)}.png")
    with open(path, "wb") as f:
        f.write(out)
    return out


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def _page_id(fname):
    # page_4.png -> "4", page_6-7.png -> "6-7"
    return fname[len("page_"):-len(".png")]


# A real page id is "cover", a number, or a spread range like "6-7". The chat
# feature writes sibling backups next to pages (page_15.preedit.png), which the
# page_*.png glob would otherwise pick up as a phantom "15.preedit" page — and,
# because pages are numbered by reading-order position in the UI, a phantom
# would silently renumber every page after it. Keep only valid ids.
_VALID_PAGE_ID = re.compile(r"^(?:cover|\d+(?:-\d+)?)$")


def _page_order_key(pid):
    """Natural page order: cover first, then by leading page NUMBER (so 2 < 10,
    not the lexicographic 10 < 2 that scrambled the panel), named pages last."""
    if pid == "cover":
        return (0, 0, "")
    m = re.match(r"(\d+)", pid)
    if m:
        return (1, int(m.group(1)), pid)
    return (2, 0, pid)          # any non-numeric named page sorts after the numbered run


def list_pages(slug):
    d = pages_dir(slug)
    if not os.path.isdir(d):
        return []
    files = glob.glob(os.path.join(d, "page_*.png"))
    ids = sorted((pid for p in files
                  if _VALID_PAGE_ID.match(pid := _page_id(os.path.basename(p)))),
                 key=_page_order_key)
    texts = _page_texts(slug)
    adir = art_dir(slug)
    rows = []
    for pid in ids:
        t = texts.get(pid, {})
        has_art = os.path.exists(os.path.join(adir, f"page_{pid}.png"))
        rows.append({
            "id": pid,
            # Baked page (text burned in) — kept for the legacy/full-composite view.
            "url": f"/api/projects/{slug}/assets/pages/page_{pid}.png",
            # Text-free illustration — the editor's page background, so the words
            # above it can be moved/edited. Falls back to the baked page.
            "art_url": (f"/api/projects/{slug}/assets/art/page_{pid}.png"
                        if has_art else f"/api/projects/{slug}/assets/pages/page_{pid}.png"),
            "text": t.get("text", ""),
            "text_area": t.get("text_area", ""),
        })
    return rows


def _page_cast(slug, page_id):
    """Character names present on a page (from scenes.toon). Used to give the
    interactive chat a SHORT identity anchor instead of the full multi-KB locks
    spec, which makes a one-line edit re-render the whole page. Best-effort []."""
    try:
        data = toon_io.load(os.path.join(data_dir(slug), "scenes.toon"))
    except Exception:  # noqa: BLE001
        return []
    for sc in (data.get("scenes") or []) if isinstance(data, dict) else []:
        if str(sc.get("page", "")).strip() == str(page_id):
            return [str(c).strip() for c in (sc.get("chars") or []) if str(c).strip()]
    return []


def _page_texts(slug):
    """Map page id -> {"text", "text_area"} from scenes.toon so the frontend can
    lay each page's words out as an EDITABLE overlay (instead of the baked-in
    copy). ``text_area`` is the pipeline's placement hint ("top"/"bottom"/
    "center"). Best-effort — returns {} if the plan isn't present/parseable."""
    try:
        data = toon_io.load(os.path.join(data_dir(slug), "scenes.toon"))
    except Exception:  # noqa: BLE001 — a missing/invalid plan just means no overlay text
        return {}
    out = {}
    for sc in (data.get("scenes") or []) if isinstance(data, dict) else []:
        pid = str(sc.get("page", "")).strip()
        if pid:
            out[pid] = {"text": (sc.get("text") or "").strip(),
                        "text_area": (sc.get("text_area") or "").strip().lower()}
    return out


def _page_locks_context(slug, page_id):
    """The page's LOCKS (cast/outfit/body-plan/size/setting) as preserve-context
    for an i2i page correction — the same detailed spec the pipeline generates and
    repairs against (pipeline/generate_v7._locks_context), so a manual correction
    fixes toward the locked identities instead of a terse guess.

    Book-scoped on purpose: we load this book's plan AND canon rules and pass the
    canon in explicitly, because generate_v7._canon() caches a single module-global
    that would bind to the wrong book in this long-lived multi-book server.
    Fail-open — a correction must still run if any of this is unavailable."""
    try:
        dd = data_dir(slug)
        spath = os.path.join(dd, "scenes.toon")
        if not os.path.exists(spath):
            return ""
        sc = _find_scene(toon_io.load(spath), page_id)
        if sc is None:
            return ""
        plan = plan_v3.load(dd)
        present = sc.get("chars", [])
        char_items = {n: items_v7.items_for(plan["by"][n]) for n in present
                      if n in plan["by"] and items_v7.items_for(plan["by"][n])}
        canon = canon_rules.load(dd)
        # contract={} skips the LLM pregate facts (not needed for a manual fix);
        # every other lock is derived offline from the book-scoped plan + canon.
        return generate_v7._locks_context(sc, plan, {}, present, char_items, canon)
    except Exception:                                        # noqa: BLE001
        return ""


def correct_page(slug, page_id, instruction):
    """Author-Control §3: targeted, instruction-based edit of ONE composed page.
    Everything not mentioned is preserved. Backs up the first version once."""
    path = os.path.join(pages_dir(slug), f"page_{page_id}.png")
    if not os.path.exists(path):
        raise FileNotFoundError(f"page {page_id} not found")
    with open(path, "rb") as f:
        original = f.read()
    backup = path.replace(".png", ".preedit.png")
    if not os.path.exists(backup):
        with open(backup, "wb") as f:
            f.write(original)
    instr = (
        f"Edit this illustrated storybook page. {instruction}. "
        "Change ONLY what is asked; keep every other part of the illustration, the "
        "characters, the composition and any existing text exactly the same. No new text."
        + _page_locks_context(slug, page_id)
    )
    out = editor.to_square(editor.edit(instr, [original]))
    with open(path, "wb") as f:
        f.write(out)
    return out


def find_pdf(slug):
    hits = sorted(glob.glob(os.path.join(book_dir(slug), "v3", "output", "*.pdf")))
    return hits[0] if hits else None


# ---------------------------------------------------------------------------
# Per-page illustration notes (Author-Control §1) — an authoritative "shot list"
# for one page, stored on the scene so generate_v7 can inject it.
# ---------------------------------------------------------------------------

def set_page_note(slug, page_id, note):
    """Write the author's direction onto the matching scene in scenes.toon so a
    re-illustration of that page treats it as authoritative. Returns True if a
    scene matched."""
    path = os.path.join(data_dir(slug), "scenes.toon")
    if not os.path.exists(path):
        raise FileNotFoundError("manuscript not parsed yet")
    scenes = toon_io.load(path)
    hit = False
    for sc in scenes.get("scenes", []):
        if str(sc.get("page")) == str(page_id):
            sc["author_note"] = note
            hit = True
            break
    if hit:
        toon_io.save(scenes, path)
    return hit


def _find_scene(scenes, page_id):
    for sc in scenes.get("scenes", []):
        if str(sc.get("page")) == str(page_id):
            return sc
    return None


def add_page_edit(slug, page_id, edit):
    """Append one author edit request to the scene's `author_edits` list.
    generate_v7 injects the whole list as MANDATORY fixes into the page prompt, so a full per-page pipeline regen carries the fixes.
    Returns the updated list, or None if no scene matched."""
    path = os.path.join(data_dir(slug), "scenes.toon")
    if not os.path.exists(path):
        raise FileNotFoundError("manuscript not parsed yet")
    scenes = toon_io.load(path)
    sc = _find_scene(scenes, page_id)
    if sc is None:
        return None
    edits = list(sc.get("author_edits") or [])
    edits.append(edit)
    sc["author_edits"] = edits
    toon_io.save(scenes, path)
    return edits


def get_page_edits(slug, page_id):
    path = os.path.join(data_dir(slug), "scenes.toon")
    if not os.path.exists(path):
        return []
    sc = _find_scene(toon_io.load(path), page_id)
    return list((sc or {}).get("author_edits") or [])


def clear_page_edits(slug, page_id):
    path = os.path.join(data_dir(slug), "scenes.toon")
    if not os.path.exists(path):
        return False
    scenes = toon_io.load(path)
    sc = _find_scene(scenes, page_id)
    if sc is None or not sc.get("author_edits"):
        return False
    sc["author_edits"] = []
    toon_io.save(scenes, path)
    return True


def get_page_note(slug, page_id):
    path = os.path.join(data_dir(slug), "scenes.toon")
    if not os.path.exists(path):
        return ""
    for sc in toon_io.load(path).get("scenes", []):
        if str(sc.get("page")) == str(page_id):
            return sc.get("author_note", "")
    return ""


# ---------------------------------------------------------------------------
# Typography + page size → env for the compose/book stages (New Project choices).
# ---------------------------------------------------------------------------

_DEJAVU_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
_DEJAVU_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

# Design font families mapped to the closest .ttf we actually have on disk.
FONT_MAP = {
    "Lora": os.path.join(REPO, "_fonts", "Lora.ttf"),
    "Playfair Display": os.path.join(REPO, "_fonts", "Lora.ttf"),
    "Merriweather": _DEJAVU_SERIF,
    "Inter": os.path.join(REPO, "_fonts", "Poppins-SemiBold.ttf"),
    "Geist": os.path.join(REPO, "_fonts", "Poppins-Medium.ttf"),
    "Geist Mono": _DEJAVU_MONO,
}

# Page sizes in inches (portrait). Orientation "Horizontal" swaps w/h.
PAGE_SIZES_IN = {
    "A3": (11.69, 16.54), "A4": (8.27, 11.69), "A5": (5.83, 8.27),
    "Letter": (8.5, 11.0), "Square": (8.5, 8.5),
}
_MAX_SIDE_PX = 2550   # keep the long edge at 8.5in @300dpi regardless of format


def _resolve_font(family):
    p = FONT_MAP.get(family)
    return p if (p and os.path.exists(p)) else _DEJAVU_SERIF


def _trim_px(size_label, orientation):
    w_in, h_in = PAGE_SIZES_IN.get(size_label, PAGE_SIZES_IN["Square"])
    if str(orientation).lower().startswith("h"):
        w_in, h_in = h_in, w_in
    scale = _MAX_SIDE_PX / max(w_in, h_in)
    return int(round(w_in * scale)), int(round(h_in * scale))


def build_generate_env(project):
    """Translate a project's New Project draft (typography, page size, page
    numbers) into environment variables the compose/book subprocess reads."""
    draft = project.get("draft", {}) or {}
    env = {}

    # --- body font family + size ---
    fonts = draft.get("fonts") or []
    body = next((f for f in fonts if str(f.get("role", "")).lower().startswith("body")),
                fonts[0] if fonts else None)
    if body:
        env["COMPOSE_FONT_PATH"] = _resolve_font(body.get("family"))
        try:
            # baseline body size ~14–16px maps to the default 0.030 frac; scale it.
            frac = 0.030 * (float(body.get("size", 14)) / 14.0)
            env["COMPOSE_BODY_FRAC"] = "%.4f" % max(0.020, min(0.055, frac))
        except (TypeError, ValueError):
            pass

    # --- page numbers ---
    if draft.get("pageNums"):
        env["COMPOSE_PAGENUM"] = "1"

    # --- page size + orientation → uniform trim ---
    size = draft.get("size") or project.get("settings", {}).get("size")
    if size:
        w, h = _trim_px(size, draft.get("orientation", "Vertical"))
        env["BOOK_TRIM_W"], env["BOOK_TRIM_H"] = str(w), str(h)

    return env


# ---------------------------------------------------------------------------
# Style previews — ONE representative scene rendered once per STYLE_MAP style,
# so the author can pick a style by eye instead of by label. Runs in-process
# (each preview is a single editor.edit call on absolute paths), threaded, and
# deliberately does NOT condition on the character reference sheets: those were
# painted in the currently-applied style and would fight the preview style.
# Identity comes from the plan's text locks instead — close enough to compare
# styles, cheap enough to run six of them.
# ---------------------------------------------------------------------------

_preview_locks = {}
_preview_guard = threading.Lock()
_PREVIEW_WORKERS = int(os.environ.get("STYLE_PREVIEW_WORKERS", "3"))


def _preview_lock(slug):
    with _preview_guard:
        lk = _preview_locks.get(slug)
        if lk is None:
            lk = _preview_locks[slug] = threading.Lock()
        return lk


def previews_dir(slug):
    return os.path.join(book_dir(slug), "v3", "output", "style_previews")


def _style_slug(label):
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def _preview_status_path(slug):
    return os.path.join(previews_dir(slug), "status.json")


def preview_status(slug):
    p = _preview_status_path(slug)
    if not os.path.exists(p):
        return {"state": "idle", "page": None, "total": 0, "done": 0, "previews": []}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {"state": "unknown", "page": None, "total": 0, "done": 0, "previews": []}


def _write_preview_status(slug, doc):
    os.makedirs(previews_dir(slug), exist_ok=True)
    doc["updated"] = int(time.time())
    tmp = _preview_status_path(slug) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f)
    os.replace(tmp, _preview_status_path(slug))


def _pick_preview_scene(plan, page_id=None):
    """The scene to preview: the requested page, else the first story scene with
    characters AND a real description (front matter rarely shows off a style)."""
    scenes = plan["scenes"]
    if page_id:
        for sc in scenes:
            if str(plan_v3.page_id(sc)) == str(page_id):
                return sc
    # Prefer a numbered STORY page (cover/front/back matter are unrepresentative
    # style samples), then any scene with characters, then anything drawable.
    def story(sc):
        return (re.match(r"\d", str(plan_v3.page_id(sc)))
                and sc.get("role") not in ("backmatter", "about_author"))
    for pred in (lambda sc: sc.get("chars") and plan_v3.scene_desc(sc) and story(sc),
                 lambda sc: sc.get("chars") and plan_v3.scene_desc(sc),
                 lambda sc: plan_v3.scene_desc(sc)):
        hit = next((sc for sc in scenes if pred(sc)), None)
        if hit is not None:
            return hit
    return None


def _style_text_of(style):
    return plan_v3.style_text({"style": style})


def _render_preview(sc, plan, style_dict):
    desc = plan_v3.scene_desc(sc)
    locks = plan_v3.present_locks(plan, sc.get("chars", []))
    instr = (
        "Repaint this ENTIRE square canvas edge-to-edge as ONE single full-bleed "
        "children's picture-book illustration (1:1 square, no borders, margins or "
        "letterboxing). It must be ONE continuous unified scene — not a grid, "
        "collage or split panels.\n"
        f"STYLE (follow it faithfully — this image is a STYLE SAMPLE): "
        f"{_style_text_of(style_dict)}.\n"
        f"SCENE: {desc}\n"
        + (f"CHARACTERS: {locks}.\n" if locks else "")
        + "Keep the top ~30% of the frame calm and uncluttered so a caption could "
        "sit there. CRITICAL: zero written text — no words, captions, labels, "
        "signs, letters or numbers anywhere in the image. Art only."
    )
    return editor.to_square(editor.edit(instr, [editor.blank_square()]))


def start_style_previews(slug, page_id=None, styles=None):
    """Kick a threaded style-preview run. Returns {"ok": False, ...} if one is
    already running for this slug. Results land in
    v3/output/style_previews/<style-slug>.png + status.json (polled by the UI)."""
    lk = _preview_lock(slug)
    if not lk.acquire(blocking=False):
        return {"ok": False, "reason": "style previews already running"}

    try:
        plan = plan_v3.load(data_dir(slug))
    except Exception as e:  # noqa: BLE001 — parse not done / unreadable plan
        lk.release()
        return {"ok": False, "reason": f"cannot load plan: {str(e)[:120]}"}
    sc = _pick_preview_scene(plan, page_id)
    if sc is None:
        lk.release()
        return {"ok": False, "reason": "no scene with an illustration description yet"}

    labels = [s for s in (styles or list(STYLE_MAP))
              if s in STYLE_MAP] or list(STYLE_MAP)
    pg = plan_v3.page_id(sc)
    doc = {"state": "running", "page": pg, "total": len(labels), "done": 0,
           "previews": [{"style": lb, "slug": _style_slug(lb), "state": "pending",
                         "url": None, "error": None} for lb in labels]}
    _write_preview_status(slug, doc)
    doc_guard = threading.Lock()

    def render_one(i, label):
        try:
            out = _render_preview(sc, plan, STYLE_MAP[label])
            fname = f"{_style_slug(label)}.png"
            with open(os.path.join(previews_dir(slug), fname), "wb") as f:
                f.write(out)
            with doc_guard:
                doc["previews"][i].update(
                    state="done", error=None,
                    url=f"/api/projects/{slug}/assets/previews/{fname}?v={int(time.time())}")
        except Exception as e:  # noqa: BLE001 — one failed style must not kill the rest
            with doc_guard:
                doc["previews"][i].update(state="error", error=str(e)[:200])
        with doc_guard:
            doc["done"] += 1
            _write_preview_status(slug, doc)

    def worker():
        try:
            with ThreadPoolExecutor(max_workers=_PREVIEW_WORKERS) as pool:
                for i, lb in enumerate(labels):
                    pool.submit(render_one, i, lb)
            with doc_guard:
                doc["state"] = ("done" if any(p["state"] == "done"
                                              for p in doc["previews"]) else "error")
                _write_preview_status(slug, doc)
        finally:
            lk.release()

    threading.Thread(target=worker, daemon=True).start()
    return {"ok": True, "page": pg, "total": len(labels)}


# ---------------------------------------------------------------------------
# Shared STYLE SAMPLES — one FIXED generic scene rendered once per style, for the
# New Project form (where no manuscript is parsed yet). The subject is identical
# across styles by design, so the ONLY variable the author compares is the
# style. Results are cached in a project-independent directory and rendered once
# (lazily, on first request), then reused for everyone — a generic sample never
# needs regenerating.
# ---------------------------------------------------------------------------

# A neutral children's-book scene that exercises character, setting, light and
# palette without leaning on any one book's cast.
SAMPLE_SCENE = (
    "A cheerful young child and a small friendly puppy sitting together on a rug "
    "in a cozy sunlit living room, a few picture books and toys scattered nearby, "
    "a window with soft daylight behind them"
)
_sample_guard = threading.Lock()
_sample_run_lock = threading.Lock()


def style_samples_dir():
    return os.path.join(STATE_DIR, "style_samples")


def _sample_status_path():
    return os.path.join(style_samples_dir(), "status.json")


def style_samples_status():
    """Status doc for the shared samples. Reflects what's already cached on disk
    so a fresh server still reports previously-rendered samples as done."""
    doc = {"state": "idle", "total": len(STYLE_MAP), "done": 0, "previews": []}
    saved = {}
    p = _sample_status_path()
    if os.path.exists(p):
        try:
            with open(p) as f:
                for row in (json.load(f).get("previews") or []):
                    saved[row.get("style")] = row
        except Exception:
            pass
    out = []
    for label in STYLE_MAP:
        sl = _style_slug(label)
        fpath = os.path.join(style_samples_dir(), f"{sl}.png")
        if os.path.exists(fpath):
            out.append({"style": label, "slug": sl, "state": "done", "error": None,
                        "url": f"/api/style-samples/{sl}.png"})
        else:
            prev = saved.get(label, {})
            out.append({"style": label, "slug": sl,
                        "state": prev.get("state", "pending"),
                        "error": prev.get("error"), "url": None})
    doc["previews"] = out
    doc["done"] = sum(1 for r in out if r["state"] == "done")
    if doc["done"] == len(out):
        doc["state"] = "done"
    elif any(r["state"] in ("running", "pending") for r in out):
        doc["state"] = "running"
    return doc


def _write_sample_status(doc):
    os.makedirs(style_samples_dir(), exist_ok=True)
    doc["updated"] = int(time.time())
    tmp = _sample_status_path() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f)
    os.replace(tmp, _sample_status_path())


def _render_sample(style_dict):
    """Render the fixed SAMPLE_SCENE in one style. Same builder as the per-book
    preview, minus any character locks (the sample child/puppy are generic)."""
    instr = (
        "Repaint this ENTIRE square canvas edge-to-edge as ONE single full-bleed "
        "children's picture-book illustration (1:1 square, no borders, margins or "
        "letterboxing). It must be ONE continuous unified scene — not a grid, "
        "collage or split panels.\n"
        f"STYLE (follow it faithfully — this image is a STYLE SAMPLE): "
        f"{_style_text_of(style_dict)}.\n"
        f"SCENE: {SAMPLE_SCENE}\n"
        "Keep the top ~30% of the frame calm and uncluttered so a caption could "
        "sit there. CRITICAL: zero written text — no words, captions, labels, "
        "signs, letters or numbers anywhere in the image. Art only."
    )
    return editor.to_square(editor.edit(instr, [editor.blank_square()]))


def start_style_samples(force=False):
    """Render the shared style samples that aren't cached yet (or all, if force).
    Returns {ok, total, rendering} — rendering is how many will actually run."""
    if not _sample_run_lock.acquire(blocking=False):
        return {"ok": False, "reason": "style samples already rendering"}
    try:
        os.makedirs(style_samples_dir(), exist_ok=True)
        labels = list(STYLE_MAP)
        todo = [lb for lb in labels
                if force or not os.path.exists(
                    os.path.join(style_samples_dir(), f"{_style_slug(lb)}.png"))]
        if not todo:
            _sample_run_lock.release()
            return {"ok": True, "total": len(labels), "rendering": 0}

        doc = style_samples_status()
        for row in doc["previews"]:
            if row["style"] in todo:
                row.update(state="pending", url=None, error=None)
        doc["state"] = "running"
        _write_sample_status(doc)
        doc_guard = threading.Lock()

        def render_one(label):
            sl = _style_slug(label)
            try:
                out = _render_sample(STYLE_MAP[label])
                with open(os.path.join(style_samples_dir(), f"{sl}.png"), "wb") as f:
                    f.write(out)
                row = {"state": "done", "url": f"/api/style-samples/{sl}.png", "error": None}
            except Exception as e:  # noqa: BLE001 — one failed style must not stop the rest
                row = {"state": "error", "url": None, "error": str(e)[:200]}
            with doc_guard:
                for r in doc["previews"]:
                    if r["style"] == label:
                        r.update(row)
                doc["done"] = sum(1 for r in doc["previews"] if r["state"] == "done")
                _write_sample_status(doc)

        def worker():
            try:
                with ThreadPoolExecutor(max_workers=_PREVIEW_WORKERS) as pool:
                    for lb in todo:
                        pool.submit(render_one, lb)
                with doc_guard:
                    doc["state"] = ("done" if all(r["state"] == "done"
                                                  for r in doc["previews"]) else "partial")
                    _write_sample_status(doc)
            finally:
                _sample_run_lock.release()

        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True, "total": len(labels), "rendering": len(todo)}
    except Exception:
        if _sample_run_lock.locked():
            _sample_run_lock.release()
        raise
