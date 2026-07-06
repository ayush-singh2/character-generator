"""Client-facing Streamlit app — Character Generator.

Exposes ONE slice of the full book pipeline to clients: give a manuscript,
get every main character as two locked reference images —

    * close view  (portrait / head-and-shoulders)
    * full view   (full-body reference sheet)

It reuses the exact backend stages, nothing is reimplemented:
    extract  -> style.judge -> characters.mine_roster/draft_bible
             -> refs.portrait_prompt/full_body_prompt -> flux.generate

Run:  streamlit run client_app.py
"""

import concurrent.futures
import os
import tempfile
import time

import streamlit as st
from dotenv import load_dotenv

from pipeline import extract, flux, refs
from pipeline.characters import draft_bible, mine_roster
from pipeline.style import STYLE_CATALOG, judge

load_dotenv()

# On Streamlit Community Cloud there is no .env file — the API key is supplied
# via the app's Secrets. Copy those secrets into the environment so the backend
# pipeline modules (which read os.getenv) pick them up unchanged.
try:
    for _k, _v in st.secrets.items():
        os.environ.setdefault(_k, str(_v))
except Exception:
    pass  # no secrets configured (e.g. local run with .env) — that's fine

st.set_page_config(page_title="Character Generator", page_icon="🎭", layout="wide")


# ── password gate ───────────────────────────────────────────────────────────
def _require_password() -> None:
    """Block the app behind a shared password (set APP_PASSWORD in Secrets).

    If APP_PASSWORD is not configured, the app stays open (so a fresh deploy
    isn't locked out before the secret is added). Once set, users must enter it
    before anything else renders — protecting your API credits on a public URL.
    """
    expected = os.getenv("APP_PASSWORD")
    if not expected:
        return  # no password configured — open
    if st.session_state.get("_authed"):
        return
    st.title("🔒 Character Generator")
    st.caption("This app is password-protected. Enter the password to continue.")
    pw = st.text_input("Password", type="password")
    if pw:
        if pw == expected:
            st.session_state["_authed"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


_require_password()


# ── helpers ────────────────────────────────────────────────────────────────
def build_doc_from_text(text: str, title: str, author: str) -> dict:
    """Wrap pasted prose in the same doc shape extract.py produces."""
    return {
        "source_pdf": None,
        "title": title or "Untitled",
        "author": author or "Unknown",
        "num_pages": 1,
        "num_stories": None,
        "pages": [{"page_no": 1, "text": text, "chapter_no": None, "chapter_title": None}],
    }


def build_doc_from_pdf(uploaded, title: str, author: str) -> dict:
    """Persist the upload to a temp file and run the real PDF extractor."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded.getbuffer())
        path = tmp.name
    try:
        # apply_meta=False: use the uploaded PDF's real title/author, not the
        # manuscript/meta.json override used by the fixed CLI pipeline.
        doc = extract.extract(path, apply_meta=False)
    finally:
        os.unlink(path)
    if title:
        doc["title"] = title
    if author:
        doc["author"] = author
    return doc


def ss(key, default=None):
    return st.session_state.setdefault(key, default)


def generate_view(prompt: str, attempts: int = 3) -> bytes:
    """Generate one image, retrying transient failures.

    flux.generate already retries dropped connections / 429 / 5xx, but Flux
    also *intermittently* returns a 200 with no image ("No image returned"),
    which hits some views (often the tight close-ups) and not others. Retrying
    a couple of times makes those views self-heal. Moderation is deterministic,
    so we do NOT retry it — retrying would just waste time and money.
    """
    last = None
    for i in range(1, attempts + 1):
        try:
            return flux.generate(prompt)
        except flux.ModerationError:
            raise
        except Exception as e:  # noqa: BLE001 — transient; retry then surface
            last = e
            print(f"[generate_view] attempt {i}/{attempts} failed: {e}", flush=True)
            if i < attempts:
                time.sleep(2 * i)  # 2s, 4s backoff
    raise last


def generate_close(prompt: str, reference: bytes | None, attempts: int = 3) -> bytes:
    """Generate the close-up. If a full-body reference is given, edit from it so
    the face/outfit match the turnaround; otherwise fall back to text-to-image."""
    last = None
    for i in range(1, attempts + 1):
        try:
            if reference:
                return flux.edit(prompt, [reference])
            return flux.generate(prompt)
        except flux.ModerationError:
            raise
        except Exception as e:  # noqa: BLE001 — transient; retry then surface
            last = e
            print(f"[generate_close] attempt {i}/{attempts} failed: {e}", flush=True)
            if i < attempts:
                time.sleep(2 * i)
    raise last


# ── sidebar / settings ─────────────────────────────────────────────────────
st.title("🎭 Character Generator")
st.caption(
    "Upload a manuscript. We extract every main character and generate a "
    "**close view** (portrait) and **full view** (full-body sheet) for each."
)

with st.sidebar:
    st.header("Settings")
    max_chars = st.slider("Max characters to design", 1, 10, 5)
    concurrency = st.slider(
        "Parallel image requests", 1, 8, 4,
        help="How many images to generate at once. Higher = faster, but may hit API rate limits.",
    )
    style_mode = st.radio(
        "Art style",
        ["Auto-detect from manuscript", "Choose manually"],
        help="Auto-detect asks the LLM to pick the best-fitting style family.",
    )
    manual_style = None
    if style_mode == "Choose manually":
        key = st.selectbox("Style family", list(STYLE_CATALOG))
        manual_style = STYLE_CATALOG[key]

    if not os.getenv("OPENROUTER_API_KEY"):
        st.error("OPENROUTER_API_KEY is not set in .env")


# ── step 1: manuscript input ───────────────────────────────────────────────
st.subheader("1 · Provide the manuscript")
tab_pdf, tab_text = st.tabs(["Upload PDF", "Paste text"])
with tab_pdf:
    pdf_file = st.file_uploader("Manuscript PDF", type=["pdf"])
with tab_text:
    text_input = st.text_area("Paste the full manuscript", height=220)

col_t, col_a = st.columns(2)
title = col_t.text_input("Title (optional override)")
author = col_a.text_input("Author (optional override)")

if st.button("🔍 Analyze manuscript", type="primary", use_container_width=True):
    if not pdf_file and not text_input.strip():
        st.warning("Upload a PDF or paste some text first.")
    else:
        st.subheader("📋 Processing — live activity")
        t0 = time.time()
        timer = st.empty()  # running clock, refreshed at every stage

        def tick(msg: str) -> None:
            timer.info(f"⏱️ {time.time() - t0:0.1f}s elapsed  ·  {msg}")

        with st.status("Processing manuscript…", expanded=True) as status:
          try:
            # 1 · read the manuscript ------------------------------------------
            t = time.time()
            tick("reading manuscript…")
            st.write("📖 **Reading manuscript** — extracting text…")
            doc = (
                build_doc_from_pdf(pdf_file, title, author)
                if pdf_file
                else build_doc_from_text(text_input, title, author)
            )
            words = sum(len(p.get("text", "").split()) for p in doc["pages"])
            st.session_state["doc"] = doc
            st.write(
                f"✓ Extracted **{doc['title']}** by *{doc['author']}* — "
                f"{doc['num_pages']} page(s), ~{words:,} words  ·  {time.time() - t:0.1f}s"
            )

            # 2 · choose the art style -----------------------------------------
            t = time.time()
            tick("choosing art style…")
            if manual_style:
                st.write("🎨 **Art style** — using your manually chosen style family…")
                style_prompt = manual_style
                style_result = {"chosen": "(manual)", "style_prompt": manual_style}
            else:
                st.write("🎨 **Choosing art style** — LLM reading the prose to pick a style…")
                style_result = judge(doc)
                style_prompt = style_result.get("style_prompt", "")
            st.session_state["style_prompt"] = style_prompt
            st.session_state["style_result"] = style_result
            st.write(
                f"✓ Style locked: **{style_result.get('chosen', '?')}**"
                + (f" (runner-up: {style_result.get('runner_up')})" if style_result.get("runner_up") else "")
                + f"  ·  {time.time() - t:0.1f}s"
            )
            if style_result.get("reasoning"):
                st.caption(f"_Why:_ {style_result['reasoning']}")
            st.caption(style_prompt[:400] + ("…" if len(style_prompt) > 400 else ""))
            # Transparency: show exactly what prose the LLM saw + its full output,
            # so a wrong/hallucinated style is easy to spot (it is not hardcoded).
            with st.expander("Style analysis — prose sent to the LLM & full decision"):
                prose = "\n\n".join(p.get("text", "")[:600] for p in doc["pages"][:6])
                st.markdown("**Prose actually sent to the style judge:**")
                st.text(prose[:2000] or "(no text extracted — the LLM had only the title to go on!)")
                st.markdown("**Full style decision (JSON):**")
                st.json(style_result)

            # 3 · mine the character roster ------------------------------------
            t = time.time()
            tick("mining character roster (LLM reading every page)…")
            st.write("🕵️ **Mining character roster** — LLM scanning every page for characters…")
            roster = mine_roster(doc)
            chars = roster["characters"]
            st.session_state["roster"] = chars
            st.write(f"✓ Found **{len(chars)}** characters  ·  {time.time() - t:0.1f}s")
            for c in chars:
                st.write(
                    f"· `[{c.get('weight', '?'):>3}]` **{c['name']}** "
                    f"({c.get('tier', '?')}) — {c.get('role', '')}"
                )
            with st.expander("Roster JSON — raw extracted data"):
                st.json(roster)

            # 4 · draft the visual bible ---------------------------------------
            t = time.time()
            tick(f"drafting visual bible for top {max_chars} characters (LLM)…")
            st.write(
                f"📓 **Drafting visual bible** — designing the top {max_chars} "
                "characters' appearance & properties…"
            )
            bible = draft_bible(roster, doc, limit=max_chars)
            bchars = bible["characters"]
            st.session_state["bible"] = bchars
            st.write(f"✓ Designed **{len(bchars)}** characters  ·  {time.time() - t:0.1f}s")
            for c in bchars:
                st.markdown(
                    f"**{c['name']}** — {c.get('age_appearance', '')} {c.get('gender', '')} · "
                    f"Hair: {c.get('hair', '')} · Eyes: {c.get('eyes', '')} · "
                    f"Outfit: {c.get('default_outfit', {}).get('description', '')[:80]}"
                )
                with st.expander(f"{c['name']} — full JSON properties"):
                    st.json(c)

            st.session_state.pop("images", None)  # reset any prior renders
            total = time.time() - t0
            status.update(
                label=f"✅ Analysis complete in {total:0.1f}s",
                state="complete",
                expanded=True,
            )
            timer.success(
                f"⏱️ Manuscript processed & {len(bchars)} characters designed in {total:0.1f}s"
            )
          except Exception as e:  # noqa: BLE001 — surface any failure to the client
            status.update(
                label=f"❌ Processing failed after {time.time() - t0:0.1f}s",
                state="error",
                expanded=True,
            )
            timer.error(
                f"Processing failed: {e}\n\n"
                "This is usually a temporary network or API hiccup — "
                "click **Analyze manuscript** again to retry."
            )
            st.stop()


# ── step 2: review characters ──────────────────────────────────────────────
if "bible" in st.session_state:
    doc = st.session_state["doc"]
    st.success(f"**{doc['title']}** — found {len(st.session_state['roster'])} characters")
    st.caption(f"Art style: {st.session_state['style_prompt'][:160]}…")

    st.subheader("2 · Choose which characters to generate")
    # Dedupe: the LLM occasionally lists the same character twice, which would
    # otherwise queue duplicate generations for that character.
    names = list(dict.fromkeys(c["name"] for c in st.session_state["bible"]))
    chosen = st.multiselect("Characters", names, default=names)

    with st.expander("View character bible (LLM-designed details)"):
        for c in st.session_state["bible"]:
            st.markdown(
                f"**{c['name']}** — {c.get('age_appearance','')} {c.get('gender','')}  \n"
                f"Hair: {c.get('hair','')} · Eyes: {c.get('eyes','')}  \n"
                f"Outfit: {c.get('default_outfit',{}).get('description','')}"
            )

    # ── step 3: generate images (parallel + live view) ─────────────────────
    if st.button("🎨 Generate character images", type="primary", use_container_width=True):
        images = ss("images", {})
        style_prompt = st.session_state["style_prompt"]
        bible_by_name = {c["name"]: c for c in st.session_state["bible"]}

        # Dedupe selected names so no character is queued (and billed) twice.
        chosen_unique = list(dict.fromkeys(chosen))

        # Two images per chosen character: a full-body turnaround and a close-up.
        VIEWS = {"portrait": "Close view — face / bust", "full_body": "Full view — front / side / back"}

        st.subheader("3 · Generating — live")
        n_tasks = len(chosen_unique) * len(VIEWS)

        # ── overview timer: at-a-glance status for the whole batch ──────────
        PER_IMAGE_S = 25  # rough per-image time; refined live from throughput
        est_total = (n_tasks / concurrency) * PER_IMAGE_S

        def fmt(secs: float) -> str:
            secs = max(0, int(secs))
            return f"{secs // 60}m {secs % 60:02d}s" if secs >= 60 else f"{secs}s"

        overview = st.container()
        with overview:
            oc1, oc2, oc3, oc4 = st.columns(4)
            m_done = oc1.empty()
            m_elapsed = oc2.empty()
            m_left = oc3.empty()
            m_eta = oc4.empty()
        m_done.metric("Images", f"0 / {n_tasks}")
        m_elapsed.metric("Elapsed", "0s")
        m_left.metric("Est. remaining", f"~{fmt(est_total)}")
        m_eta.metric("Est. total", f"~{fmt(est_total)}")

        progress = st.progress(0.0, text=f"Starting {n_tasks} images at {concurrency}× parallel…")
        # Live grid lives inside a placeholder we wipe once done, so it does NOT
        # duplicate the persistent download gallery rendered below.
        live_area = st.empty()
        cells = {}
        with live_area.container():
            for name in chosen_unique:
                st.markdown(f"### {name}")
                cols = st.columns(len(VIEWS))
                for col, (kind, label) in zip(cols, VIEWS.items()):
                    ph = col.empty()
                    ph.info(f"⏳ {label} — queued…")
                    cells[(name, kind)] = ph

        done = 0
        gen_t0 = time.time()

        def _tick(label: str) -> None:
            elapsed = time.time() - gen_t0
            remaining = (n_tasks - done) * (elapsed / done) if done else n_tasks / concurrency * PER_IMAGE_S
            m_done.metric("Images", f"{done} / {n_tasks}")
            m_elapsed.metric("Elapsed", fmt(elapsed))
            m_left.metric("Est. remaining", f"~{fmt(remaining)}")
            m_eta.metric("Est. total", f"~{fmt(elapsed + remaining)}")
            progress.progress(
                done / n_tasks,
                text=f"{done} / {n_tasks} images  ·  {fmt(elapsed)} elapsed  ·  ~{fmt(remaining)} left  ·  {label}",
            )

        # ── Phase A: full-body turnarounds (parallel) ───────────────────────
        # These come first so each close-up can be generated FROM its own
        # turnaround, keeping the two views the same character.
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = {
                ex.submit(generate_view, refs.full_body_prompt(bible_by_name[name], style_prompt)): name
                for name in chosen_unique
            }
            for fut in concurrent.futures.as_completed(futs):
                name = futs[fut]
                ph = cells[(name, "full_body")]
                try:
                    img = fut.result()
                    images.setdefault(name, {})["full_body"] = img
                    ph.image(img, caption=VIEWS["full_body"], use_container_width=True)
                except flux.ModerationError:
                    ph.warning(f"{VIEWS['full_body']}: prompt was moderated — skipped.")
                except Exception as e:  # noqa: BLE001 — surface any API error to the client
                    ph.error(f"{VIEWS['full_body']}: failed — {e}")
                done += 1
                _tick("full-body turnarounds")

        # ── Phase B: close-ups, edited FROM each full-body reference ─────────
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = {
                ex.submit(
                    generate_close,
                    refs.close_up_edit_prompt(bible_by_name[name], style_prompt)
                    if images.get(name, {}).get("full_body")
                    else refs.portrait_prompt(bible_by_name[name], style_prompt),
                    images.get(name, {}).get("full_body"),
                ): name
                for name in chosen_unique
            }
            for fut in concurrent.futures.as_completed(futs):
                name = futs[fut]
                ph = cells[(name, "portrait")]
                try:
                    img = fut.result()
                    images.setdefault(name, {})["portrait"] = img
                    ph.image(img, caption=VIEWS["portrait"], use_container_width=True)
                except flux.ModerationError:
                    ph.warning(f"{VIEWS['portrait']}: prompt was moderated — skipped.")
                except Exception as e:  # noqa: BLE001 — surface any API error to the client
                    ph.error(f"{VIEWS['portrait']}: failed — {e}")
                done += 1
                _tick("close-ups")

        total = time.time() - gen_t0
        m_elapsed.metric("Elapsed", fmt(total))
        m_left.metric("Est. remaining", "0s")
        m_eta.metric("Total", fmt(total))
        progress.progress(1.0, text=f"Done — {n_tasks} images in {fmt(total)}")
        live_area.empty()  # clear the transient live grid; gallery renders below
        st.success(f"⏱️ Generated {n_tasks} images in {fmt(total)}.")
        st.session_state["images"] = images


# ── results ────────────────────────────────────────────────────────────────
if st.session_state.get("images"):
    st.subheader("4 · Generated characters — download")
    for name, imgs in st.session_state["images"].items():
        st.markdown(f"### {name}")
        c1, c2 = st.columns(2)
        if "portrait" in imgs:
            c1.image(imgs["portrait"], caption="Close view — face / bust", use_container_width=True)
            c1.download_button(
                "⬇ Download close view", imgs["portrait"],
                file_name=f"{refs.slug(name)}_portrait.png", mime="image/png",
                key=f"dl_p_{name}",
            )
        else:
            c1.info("Close view not available.")
        if "full_body" in imgs:
            c2.image(imgs["full_body"], caption="Full view — front / side / back turnaround", use_container_width=True)
            c2.download_button(
                "⬇ Download full view", imgs["full_body"],
                file_name=f"{refs.slug(name)}_full_body.png", mime="image/png",
                key=f"dl_b_{name}",
            )
        else:
            c2.info("Full view not available.")

# redeploy: refresh cached modules
