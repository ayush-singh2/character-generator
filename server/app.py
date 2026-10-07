"""FastAPI app: serves the BB-artists design and wires it to the v3 pipeline.

Run:  ./serve_app.sh   (uvicorn server.app:app --reload)

Auth is a single shared-password gate (parity with client_app.py) — not real
multi-user auth, which is out of the agreed scope. Everything under /api except
/api/login requires the session cookie.
"""

import hashlib
import hmac
import json
import os
import re
import shutil

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from pipeline import plan_v3
from server import db, jobs, page_chat, pipeline_api

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Writable state (generated books + SQLite DB) lives under STATE_DIR. Locally it
# defaults to the repo; in production point BB_STATE_DIR at a persistent disk
# (e.g. /data on Render) so output survives restarts. NEVER the code dir (/app).
STATE_DIR = os.environ.get("BB_STATE_DIR", REPO)
# The deployed UI is the Vite React SPA; we serve its production build (dist/).
# Built locally by `npm run build` or in the Docker image's node stage.
SPA_DIR = os.path.join(REPO, "frontend", "frontend", "blue-balloon", "dist")
STATIC_DIR = os.path.join(REPO, "server", "static")
BOOKS = os.path.join(STATE_DIR, "books")


def _load_dotenv():
    """Load REPO/.env into os.environ (without clobbering real env vars) so the
    pipeline SUBPROCESS — which inherits this process's env in jobs.py — can see
    OPENROUTER_API_KEY etc. On Render, set these as real env vars instead; this
    is just a convenience for local runs. Dependency-free (no python-dotenv)."""
    path = os.path.join(REPO, ".env")
    if not os.path.exists(path):
        return
    try:
        with open(path) as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:      # real env wins
                    os.environ[key] = val
    except Exception:
        pass


_load_dotenv()

# Any job left "running" from a previous process is a zombie (its worker thread
# died on restart); mark those interrupted so the UI shows a retry path instead of
# a frozen "running" bar that never resolves.
jobs.recover_stale_jobs()

# Fail loudly at startup if the one key the pipeline can't run without is missing,
# so a misconfigured deploy is obvious in the logs instead of surfacing as a
# silent "nothing generated yet" much later.
if not os.getenv("OPENROUTER_API_KEY"):
    import sys
    print("WARNING: OPENROUTER_API_KEY is not set — book generation will fail. "
          "Set it in .env (local) or the Render environment (production).",
          file=sys.stderr, flush=True)

# .strip() so a stray trailing newline/space in the dashboard env var (a very
# common paste artifact) can't silently lock everyone out — the value the app
# compares against is the visible password, nothing more.
APP_PASSWORD = os.getenv("APP_PASSWORD", "bbartists").strip()
SECRET = os.getenv("APP_SECRET", "bb-dev-secret").strip()
COOKIE = "bb_session"

app = FastAPI(title="BB artists")


@app.middleware("http")
async def no_cache_pages(request: Request, call_next):
    """Serve the design pages/scripts with no-store so a rebuilt front-end never
    gets shadowed by a stale mock cached in the browser. API JSON is dynamic
    anyway; page images keep their own ?v= cache-busting."""
    resp = await call_next(request)
    path = request.url.path
    if path.endswith((".html", ".js", ".css")) or path == "/":
        resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def _token():
    return hmac.new(SECRET.encode(), APP_PASSWORD.encode(), hashlib.sha256).hexdigest()


def require_auth(request: Request):
    if request.cookies.get(COOKIE) != _token():
        raise HTTPException(status_code=401, detail="login required")
    return True


@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    if (body or {}).get("password") != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="wrong password")
    resp = JSONResponse({"ok": True})
    resp.set_cookie(COOKIE, _token(), httponly=True, samesite="lax")
    return resp


@app.post("/api/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE)
    return resp


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "untitled"


def _unique_slug(base):
    slug, i = base, 2
    while db.get_by_slug(slug):
        slug = f"{base}-{i}"
        i += 1
    return slug


def _card(p):
    """Shape a project row into what Home.html expects on a card."""
    return {
        "id": p["slug"], "title": p["title"], "author": p.get("author", ""),
        "status": p.get("status", "Draft"),
        "pages": p.get("pages", 0), "bookType": p.get("book_type", ""),
        "style": p.get("style", ""), "tags": p.get("tags", []),
        "progress": p.get("progress", 0),
        "editedTs": p.get("edited_ts", 0), "createdTs": p.get("created_ts", 0),
        "shared": False, "members": [p["author"]] if p.get("author") else [],
        "draft": p.get("draft", {}), "settings": p.get("settings", {}),
    }


def _require_project(slug):
    p = db.get_by_slug(slug)
    if not p:
        raise HTTPException(status_code=404, detail="project not found")
    return p


# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #
@app.get("/api/projects")
def api_projects(_: bool = Depends(require_auth)):
    return {"projects": [_card(p) for p in db.list_projects()]}


@app.post("/api/projects")
async def api_create_project(request: Request, _: bool = Depends(require_auth)):
    body = await request.json()
    title = (body.get("title") or "Untitled storybook").strip()
    slug = _unique_slug(_slugify(title))
    os.makedirs(os.path.join(BOOKS, slug, "manuscript"), exist_ok=True)
    p = db.create_project(
        slug, slug, title,
        author=body.get("author", ""),
        book_type=body.get("bookType", body.get("style", "")),
        style=body.get("style", ""),
        pages=body.get("pages", 0),
        tags=body.get("tags", []),
        draft=body.get("draft", {}),
    )
    return _card(p)


@app.get("/api/projects/{slug}")
def api_get_project(slug: str, _: bool = Depends(require_auth)):
    return _card(_require_project(slug))


@app.patch("/api/projects/{slug}")
async def api_update_project(slug: str, request: Request, _: bool = Depends(require_auth)):
    _require_project(slug)
    body = await request.json()
    allowed = {k: body[k] for k in
               ("title", "author", "status", "book_type", "pages", "style",
                "tags", "draft", "settings", "progress", "stage") if k in body}
    return _card(db.update_project(slug, **allowed))


@app.post("/api/projects/{slug}/duplicate")
def api_duplicate(slug: str, _: bool = Depends(require_auth)):
    src = _require_project(slug)
    new_slug = _unique_slug(_slugify(src["title"] + "-copy"))
    if os.path.isdir(os.path.join(BOOKS, slug)):
        shutil.copytree(os.path.join(BOOKS, slug), os.path.join(BOOKS, new_slug))
    p = db.create_project(new_slug, new_slug, src["title"] + " (copy)",
                          author=src.get("author", ""), book_type=src.get("book_type", ""),
                          style=src.get("style", ""), pages=src.get("pages", 0),
                          tags=src.get("tags", []), draft=src.get("draft", {}))
    return _card(p)


@app.delete("/api/projects/{slug}")
def api_delete_project(slug: str, _: bool = Depends(require_auth)):
    _require_project(slug)
    db.delete_project(slug)
    shutil.rmtree(os.path.join(BOOKS, slug), ignore_errors=True)
    return {"ok": True}


@app.put("/api/projects/{slug}/draft")
async def api_save_draft(slug: str, request: Request, _: bool = Depends(require_auth)):
    _require_project(slug)
    body = await request.json()
    fields = {"draft": body}
    # mirror a few top-level fields the dashboard sorts on
    if "style" in body:
        fields["style"] = body["style"]
        fields["book_type"] = body["style"]
    if "pages" in body:
        fields["pages"] = int(re.sub(r"\D", "", str(body["pages"])) or 0)
    if "title" in body:
        fields["title"] = body["title"]
    return _card(db.update_project(slug, **fields))


# --------------------------------------------------------------------------- #
# Manuscript -> parse/copyedit/refs job (stops at character approval)
# --------------------------------------------------------------------------- #
@app.post("/api/projects/{slug}/manuscript")
async def api_upload_manuscript(slug: str, file: UploadFile = File(...),
                                _: bool = Depends(require_auth)):
    _require_project(slug)
    mdir = os.path.join(BOOKS, slug, "manuscript")
    os.makedirs(mdir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1].lower() or ".docx"
    dest = os.path.join(mdir, f"manuscript{ext}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    p = db.update_project(slug, status="In Progress")

    style = p.get("draft", {})
    style_kwargs = {
        "style_label": style.get("style", p.get("style", "")),
        "aesthetic": style.get("aesthetic", ""),
        "palette": style.get("palette", []),
        "restrict": bool(style.get("restrictPalette", False)),
    }
    r = jobs.start(slug, "parse", style=style_kwargs,
                   env_extra={"STORYBOOK_DOCX": dest})
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=r.get("reason", "busy"))
    return {"ok": True, "manuscript": os.path.basename(dest)}


# --------------------------------------------------------------------------- #
# Characters
# --------------------------------------------------------------------------- #
@app.get("/api/projects/{slug}/characters")
def api_characters(slug: str, _: bool = Depends(require_auth)):
    _require_project(slug)
    return {"characters": pipeline_api.read_characters(slug)}


@app.post("/api/projects/{slug}/characters/{name}/design")
async def api_design_character(slug: str, name: str,
                               instruction: str = Form(...),
                               photo: UploadFile = File(None),
                               _: bool = Depends(require_auth)):
    _require_project(slug)
    if not os.path.exists(os.path.join(pipeline_api.data_dir(slug), "characters.toon")):
        raise HTTPException(status_code=409, detail="parse the manuscript first")
    photo_bytes = await photo.read() if photo is not None else None
    try:
        pipeline_api.redesign_character(slug, name, instruction, photo_bytes)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)[:300])
    return {"ok": True,
            "ref_url": f"/api/projects/{slug}/assets/refs/{plan_v3.slug(name)}.png"}


@app.post("/api/projects/{slug}/characters/{name}/approve")
async def api_approve_character(slug: str, name: str, _: bool = Depends(require_auth)):
    p = _require_project(slug)
    settings = p.get("settings", {})
    approved = set(settings.get("approved_characters", []))
    approved.add(name)
    settings["approved_characters"] = sorted(approved)
    db.update_project(slug, settings=settings)
    return {"ok": True, "approved": settings["approved_characters"]}


# --------------------------------------------------------------------------- #
# Style SAMPLES — project-independent. One fixed generic scene rendered once per
# style (cached globally), so the author can compare styles on the New Project
# form BEFORE a manuscript is parsed. Same subject across styles by design.
# --------------------------------------------------------------------------- #
@app.post("/api/style-previews")
async def api_start_style_samples(request: Request, _: bool = Depends(require_auth)):
    force = False
    try:
        body = await request.json()
        force = bool((body or {}).get("force"))
    except Exception:
        pass
    r = pipeline_api.start_style_samples(force=force)
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=r.get("reason", "busy"))
    return r


@app.get("/api/style-previews")
def api_style_samples_status(_: bool = Depends(require_auth)):
    return pipeline_api.style_samples_status()


@app.get("/api/style-samples/{fname}")
def api_style_sample_asset(fname: str, _: bool = Depends(require_auth)):
    if "/" in fname or ".." in fname:
        raise HTTPException(status_code=400, detail="bad asset path")
    path = os.path.join(pipeline_api.style_samples_dir(), fname)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="sample not found")
    return FileResponse(path)


# --------------------------------------------------------------------------- #
# Per-book style previews — same scene from THIS book rendered once per style
# (used on the Characters page, post-parse). POST kicks; GET polls; /style
# applies the winner + re-renders the ref sheets.
# --------------------------------------------------------------------------- #
@app.post("/api/projects/{slug}/style-previews")
async def api_start_style_previews(slug: str, request: Request,
                                   _: bool = Depends(require_auth)):
    _require_project(slug)
    if not os.path.exists(os.path.join(pipeline_api.data_dir(slug), "scenes.toon")):
        raise HTTPException(status_code=409, detail="parse the manuscript first")
    page = None
    try:
        body = await request.json()
        page = (body or {}).get("page")
    except Exception:
        pass
    r = pipeline_api.start_style_previews(slug, page_id=page)
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=r.get("reason", "busy"))
    return r


@app.get("/api/projects/{slug}/style-previews")
def api_style_previews_status(slug: str, _: bool = Depends(require_auth)):
    _require_project(slug)
    return pipeline_api.preview_status(slug)


@app.post("/api/projects/{slug}/style")
async def api_pick_style(slug: str, request: Request, _: bool = Depends(require_auth)):
    """Apply the style the author picked from the previews and re-render the
    character reference sheets in it (refs consume characters.toon's style)."""
    _require_project(slug)
    body = await request.json() or {}
    label = (body.get("style") or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="style required")
    applied = pipeline_api.apply_style_override(
        slug, label, aesthetic=body.get("aesthetic", ""),
        palette=body.get("palette"), restrict=bool(body.get("restrictPalette")))
    if not applied:
        raise HTTPException(status_code=409, detail="parse the manuscript first")
    db.update_project(slug, style=label, book_type=label)
    r = jobs.start(slug, "restyle")
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=r.get("reason", "busy"))
    return {"ok": True, "style": label, "rebuilding_refs": True}


# --------------------------------------------------------------------------- #
# Generate -> layout..book
# --------------------------------------------------------------------------- #
@app.post("/api/projects/{slug}/generate")
async def api_generate(slug: str, request: Request, _: bool = Depends(require_auth)):
    p = _require_project(slug)
    if not os.path.exists(os.path.join(pipeline_api.data_dir(slug), "characters.toon")):
        raise HTTPException(status_code=409, detail="parse the manuscript first")
    only = None
    try:
        body = await request.json()
        only = (body or {}).get("only")
    except Exception:
        pass
    r = jobs.start(slug, "generate", only=only,
                   env_extra=pipeline_api.build_generate_env(p))
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=r.get("reason", "busy"))
    db.update_project(slug, status="In Progress")
    return {"ok": True}


@app.get("/api/projects/{slug}/pages/{page_id}/note")
def api_get_note(slug: str, page_id: str, _: bool = Depends(require_auth)):
    _require_project(slug)
    return {"note": pipeline_api.get_page_note(slug, page_id)}


@app.post("/api/projects/{slug}/pages/{page_id}/note")
async def api_set_note(slug: str, page_id: str, request: Request,
                       _: bool = Depends(require_auth)):
    """Store an authoritative per-page direction (Author-Control §1) and
    re-illustrate just that page with it."""
    p = _require_project(slug)
    body = await request.json()
    note = (body or {}).get("note", "").strip()
    try:
        hit = pipeline_api.set_page_note(slug, page_id, note)
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail="parse the manuscript first")
    if not hit:
        raise HTTPException(status_code=404, detail="page not found")
    r = jobs.start(slug, "generate", only=page_id,
                   env_extra=pipeline_api.build_generate_env(p))
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=r.get("reason", "busy"))
    return {"ok": True, "reillustrating": page_id}


# --------------------------------------------------------------------------- #
# Per-page author edits — free-text fixes that regenerate the page through the
# FULL pipeline (layout..book for that page), unlike /correct's quick i2i edit.
# Edits accumulate on the scene so a second request doesn't lose the first fix.
# --------------------------------------------------------------------------- #
@app.get("/api/projects/{slug}/pages/{page_id}/edit")
def api_get_page_edits(slug: str, page_id: str, _: bool = Depends(require_auth)):
    _require_project(slug)
    return {"edits": pipeline_api.get_page_edits(slug, page_id)}


@app.post("/api/projects/{slug}/pages/{page_id}/edit")
async def api_page_edit(slug: str, page_id: str, request: Request,
                        _: bool = Depends(require_auth)):
    p = _require_project(slug)
    body = await request.json()
    instruction = (body or {}).get("instruction", "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction required")
    try:
        edits = pipeline_api.add_page_edit(slug, page_id, instruction)
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail="parse the manuscript first")
    if edits is None:
        raise HTTPException(status_code=404, detail="page not found")
    r = jobs.start(slug, "generate", only=page_id,
                   env_extra=pipeline_api.build_generate_env(p))
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=r.get("reason", "busy"))
    return {"ok": True, "regenerating": page_id, "edits": edits}


@app.delete("/api/projects/{slug}/pages/{page_id}/edit")
def api_clear_page_edits(slug: str, page_id: str, _: bool = Depends(require_auth)):
    _require_project(slug)
    return {"ok": True, "cleared": pipeline_api.clear_page_edits(slug, page_id)}


# --------------------------------------------------------------------------- #
# Pages + per-page correction
# --------------------------------------------------------------------------- #
@app.get("/api/projects/{slug}/pages")
def api_pages(slug: str, _: bool = Depends(require_auth)):
    _require_project(slug)
    pages = pipeline_api.list_pages(slug)
    if pages:
        db.update_project(slug, pages=len(pages))
    return {"pages": pages}


@app.post("/api/projects/{slug}/pages/{page_id}/correct")
async def api_correct_page(slug: str, page_id: str, request: Request,
                           _: bool = Depends(require_auth)):
    _require_project(slug)
    body = await request.json()
    instruction = (body or {}).get("instruction", "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction required")
    try:
        pipeline_api.correct_page(slug, page_id, instruction)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)[:300])
    # cache-bust the client image
    return {"ok": True,
            "url": f"/api/projects/{slug}/assets/pages/page_{page_id}.png?v={db.now_ms()}"}


# --- Per-page correction CHAT (human-in-the-loop, server/page_chat.py) ------- #
# A stateful, multi-turn version of /correct: the author says what's wrong and
# can reference a correct page either by dropping its image (`refs` files) or by
# naming it (`ref_pages`, or just "page 5" in the message, parsed server-side).

def _page_url(slug, page_id):
    # Point at the ART layer (text-free) when it exists — that's what the editor
    # shows and what the chat edits — otherwise the baked page. ?v= cache-busts
    # so the browser picks up the freshly-written revision.
    art = os.path.join(pipeline_api.art_dir(slug), f"page_{page_id}.png")
    kind = "art" if os.path.exists(art) else "pages"
    return f"/api/projects/{slug}/assets/{kind}/page_{page_id}.png?v={db.now_ms()}"


@app.get("/api/projects/{slug}/pages/{page_id}/chat")
def api_chat_history(slug: str, page_id: str, _: bool = Depends(require_auth)):
    _require_project(slug)
    try:
        sess = page_chat.get_session(slug, page_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")
    return {"turns": sess.turns}


@app.post("/api/projects/{slug}/pages/{page_id}/chat")
async def api_chat_page(slug: str, page_id: str,
                        message: str = Form(""),
                        ref_pages: str = Form(""),
                        area: str = Form(""),
                        refs: list[UploadFile] = File(default=[]),
                        _: bool = Depends(require_auth)):
    _require_project(slug)
    msg = (message or "").strip()
    ref_page_ids = [x.strip() for x in (ref_pages or "").split(",") if x.strip()]
    ref_images = [await f.read() for f in (refs or []) if f is not None]
    if not msg and not ref_page_ids and not ref_images:
        raise HTTPException(status_code=400, detail="message required")
    # Optional selected region -> masked (surgical) edit. [x0,y0,x1,y1] in 0..1.
    box = None
    if area:
        try:
            b = json.loads(area)
            if isinstance(b, list) and len(b) == 4:
                box = [max(0.0, min(1.0, float(v))) for v in b]
                if box[2] - box[0] < 0.02 or box[3] - box[1] < 0.02:
                    box = None            # too small to mask meaningfully
        except Exception:  # noqa: BLE001 — a malformed box just means full-page
            box = None
    try:
        sess = page_chat.get_session(slug, page_id)
        res = sess.send(msg, ref_pages=ref_page_ids, ref_images=ref_images, box=box)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)[:300])
    # A failed turn (e.g. a referenced page doesn't exist) is a normal 200 with a
    # friendly reply the chat shows — not an HTTP error.
    if res.get("ok") and res.get("page_url"):
        res["page_url"] = _page_url(slug, page_id)
    return res


@app.post("/api/projects/{slug}/pages/{page_id}/chat/revert")
async def api_chat_revert(slug: str, page_id: str, _: bool = Depends(require_auth)):
    _require_project(slug)
    try:
        sess = page_chat.get_session(slug, page_id)
        ok = sess.revert()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")
    if not ok:
        raise HTTPException(status_code=409, detail="nothing to revert")
    return {"ok": True, "page_url": _page_url(slug, page_id)}


# --------------------------------------------------------------------------- #
# Job status, assets, PDF
# --------------------------------------------------------------------------- #
@app.get("/api/projects/{slug}/job")
def api_job(slug: str, _: bool = Depends(require_auth)):
    _require_project(slug)
    st = jobs.read_status(slug)
    if st.get("state") == "done" and st.get("group") == "generate":
        db.update_project(slug, status="Complete", progress=100)
    return st


@app.get("/api/projects/{slug}/assets/{kind}/{fname}")
def api_asset(slug: str, kind: str, fname: str, _: bool = Depends(require_auth)):
    _require_project(slug)
    if kind not in ("refs", "pages", "art", "previews") or "/" in fname or ".." in fname:
        raise HTTPException(status_code=400, detail="bad asset path")
    base = {"refs": pipeline_api.refs_dir, "pages": pipeline_api.pages_dir,
            "art": pipeline_api.art_dir,
            "previews": pipeline_api.previews_dir}[kind](slug)
    path = os.path.join(base, fname)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(path)


@app.get("/api/projects/{slug}/pdf")
def api_pdf(slug: str, _: bool = Depends(require_auth)):
    _require_project(slug)
    pdf = pipeline_api.find_pdf(slug)
    if not pdf:
        raise HTTPException(status_code=404, detail="no PDF yet — generate the book first")
    return FileResponse(pdf, media_type="application/pdf",
                        filename=os.path.basename(pdf))


# --------------------------------------------------------------------------- #
# Static UI: the Vite React SPA build (dist/). Real files under dist/ are served
# as-is; every other path falls back to index.html so client-side routes
# (/home, /login, /projects/..., …) survive hard refresh and deep links.
# Registered LAST so all /api/* routes above win; a stray /api/* path 404s here
# instead of being handed the SPA shell.
# --------------------------------------------------------------------------- #
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_SPA_INDEX = os.path.join(SPA_DIR, "index.html")


@app.get("/{full_path:path}")
async def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="not found")
    candidate = os.path.normpath(os.path.join(SPA_DIR, full_path))
    # Serve a real built asset when it exists, guarding against path traversal
    # that would escape dist/. Otherwise return the SPA shell.
    if full_path and candidate.startswith(SPA_DIR + os.sep) and os.path.isfile(candidate):
        return FileResponse(candidate)
    return FileResponse(_SPA_INDEX)
