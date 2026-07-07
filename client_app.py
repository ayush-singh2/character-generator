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
from io import BytesIO

import streamlit as st
from dotenv import load_dotenv
from PIL import Image

from pipeline import extract, flux, refs, storybook
from pipeline.characters import draft_bible, mine_roster
from pipeline.llm import chat_json_image
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
def build_doc_from_docx(uploaded, title: str, author: str) -> dict:
    """Parse an 'Illustration Notes' .docx manuscript into the analysis doc shape.

    Uses the real picture-book parser, so page directives, spot/spread layout,
    the character bible and the illustrator note all come through. The story
    text (art-direction stripped) feeds style + character mining exactly as the
    CLI pipeline does; the extra structure is stashed for later generation.
    """
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(uploaded.getbuffer())
        path = tmp.name
    sb = storybook.parse(path)                 # rich picture-book units
    doc = storybook.as_manuscript_doc(sb)      # {title, author, pages:[...]}
    doc["title"] = title or sb.get("title") or "Untitled"
    doc["author"] = author or sb.get("author") or "Unknown"
    doc["num_pages"] = len(doc["pages"])
    doc["source_docx"] = path
    # carry the picture-book extras through for the generation phase
    doc["storybook"] = sb
    doc["characters_hint"] = sb.get("characters", [])
    doc["illustrator_note"] = sb.get("illustrator_note", "")
    # surface any photos embedded in the manuscript so the user can see them and
    # crop one subject per character for exact-likeness references
    try:
        import zipfile
        z = zipfile.ZipFile(path)
        doc["reference_images_bytes"] = [
            z.read(n) for n in sorted(z.namelist())
            if "media/" in n and n.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ]
    except Exception:  # noqa: BLE001
        doc["reference_images_bytes"] = []
    return doc


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


def crop_front_figure(img_bytes: bytes, frac: float = 0.4) -> bytes:
    """Crop the left `frac` of a turnaround sheet — the front-facing figure.

    The full-body reference is a front/side/back sheet; feeding all three to the
    close-up edit confuses the model (it may add a companion or mix poses).
    Cropping to just the leftmost (front) figure gives it one clean subject.
    """
    try:
        im = Image.open(BytesIO(img_bytes)).convert("RGB")
        w, h = im.size
        cropped = im.crop((0, 0, max(1, int(w * frac)), h))
        buf = BytesIO()
        cropped.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:  # noqa: BLE001 — fall back to the full sheet
        print(f"[crop_front_figure] failed, using full image: {e}", flush=True)
        return img_bytes


def crop_face(img_bytes: bytes) -> bytes:
    """Derive a head/bust close view by cropping the top of the full-body.

    Guarantees a close view even when the close-up API call fails or is
    moderated — the full-body almost always succeeded, so we crop its head.
    Works for both a single centred figure and a 3-view turnaround (the top
    band holds the head/heads either way).
    """
    try:
        im = Image.open(BytesIO(img_bytes)).convert("RGB")
        w, h = im.size
        bust = im.crop((0, 0, w, max(1, int(h * 0.5))))   # top half = head/shoulders
        buf = BytesIO()
        bust.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:  # noqa: BLE001
        print(f"[crop_face] failed: {e}", flush=True)
        return img_bytes


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


def describe_reference(image_bytes: bytes, name: str) -> str:
    """Vision-caption a reference photo into concrete, literal attributes.

    Conditioning Flux on the photo alone loses details (a strong style prompt
    overrides the hat, glasses, outfit colours). Feeding these exact attributes
    back into the text prompt is what makes "every detail match" actually work.
    """
    sysd = (
        "You are a precise visual describer helping an illustrator copy a real "
        f"subject exactly. Describe ONLY the single main subject ({name}); ignore "
        f"any background people or animals unless {name} itself is that animal.")
    userd = (
        "Describe the subject literally for exact reproduction: species/type, "
        "headwear, eyewear, hairstyle + length + colour (or fur/coat colour + "
        "markings), facial features, skin tone, approximate age, body build, top "
        "(colour), bottom (colour), footwear, accessories. Be explicit about "
        'COLOURS. Return JSON {"description":"..."} as one dense sentence.')
    try:
        return chat_json_image(sysd, userd, image_bytes, mime="image/png").get(
            "description", "")
    except Exception as e:  # noqa: BLE001
        print(f"[describe_reference] {name}: {e}", flush=True)
        return ""


def _exact_likeness(prompt: str, name: str, caption: str = "") -> str:
    """Wrap a prompt so Flux reproduces the subject in the reference photo exactly."""
    detail = (f" {name} looks EXACTLY like this — reproduce every detail: {caption}."
              if caption else "")
    return (
        f"The attached image is a REAL reference photo of {name}. Reproduce {name} "
        "EXACTLY as they appear — same headwear, eyewear, hairstyle and hair length "
        "(ponytail, braids, bun, long, short, bald), facial features and expression, "
        "skin tone, body build, age, and the same clothing and accessories with the "
        f"same COLOURS.{detail} Do NOT invent a different-looking subject or change "
        "the outfit. Only re-render them in this illustration style: " + prompt
    )


def generate_view_ref(prompt: str, references: list[bytes], attempts: int = 3) -> bytes:
    """Generate a view conditioned on reference photo(s) for exact likeness."""
    last = None
    for i in range(1, attempts + 1):
        try:
            return flux.edit(prompt, references)
        except flux.ModerationError:
            raise
        except Exception as e:  # noqa: BLE001 — transient; retry then surface
            last = e
            print(f"[generate_view_ref] attempt {i}/{attempts} failed: {e}", flush=True)
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
    max_chars = st.slider("Max characters to design", 1, 12, 7)
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
tab_docx, tab_pdf, tab_text = st.tabs(
    ["Upload manuscript (.docx)", "Upload PDF", "Paste text"])
with tab_docx:
    docx_file = st.file_uploader(
        "Illustration-Notes .docx", type=["docx"],
        help="The writer's manuscript with Page directives and Illustration: notes.")
    if docx_file:
        st.caption("✓ Page layout, spot/spread structure, character bible and "
                   "illustrator note are parsed automatically.")
with tab_pdf:
    pdf_file = st.file_uploader("Manuscript PDF", type=["pdf"])
with tab_text:
    text_input = st.text_area("Paste the full manuscript", height=220)

col_t, col_a = st.columns(2)
title = col_t.text_input("Title (optional override)")
author = col_a.text_input("Author (optional override)")

if st.button("🔍 Analyze manuscript", type="primary", use_container_width=True):
    if not docx_file and not pdf_file and not text_input.strip():
        st.warning("Upload a .docx or PDF, or paste some text first.")
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
            if docx_file:
                doc = build_doc_from_docx(docx_file, title, author)
            elif pdf_file:
                doc = build_doc_from_pdf(pdf_file, title, author)
            else:
                doc = build_doc_from_text(text_input, title, author)
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
                top_styles = [{"key": "manual", "label": "Your chosen style",
                               "why": "", "style_prompt": manual_style}]
                style_result = {"chosen": "(manual)", "style_prompt": manual_style,
                                "top_styles": top_styles}
            else:
                st.write("🎨 **Recommending styles** — LLM reading the prose to rank the best 3…")
                style_result = judge(doc)
                top_styles = style_result.get("top_styles", [])
                style_prompt = top_styles[0]["style_prompt"] if top_styles else style_result.get("style_prompt", "")
                st.session_state["auto_style_prompt"] = style_prompt
            st.session_state["style_prompt"] = style_prompt
            st.session_state["style_result"] = style_result
            st.session_state["top_styles"] = top_styles
            st.write(f"✓ Recommended **{len(top_styles)}** style(s)  ·  {time.time() - t:0.1f}s")
            for si, sty in enumerate(top_styles, 1):
                st.markdown(f"**{si}. {sty['label']}**" + (f" — {sty['why']}" if sty.get("why") else ""))
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
    if style_mode == "Choose manually" and manual_style:
        st.caption("Art style: your manually chosen family (sidebar).")
    else:
        _labels = [s["label"] for s in st.session_state.get("top_styles", [])]
        if _labels:
            st.caption("Recommended styles: " + " · ".join(_labels))

    st.subheader("2 · Choose which characters to generate")
    # Dedupe: the LLM occasionally lists the same character twice.
    _seen: set = set()
    uniq_chars = []
    for c in st.session_state["bible"]:
        if c["name"] not in _seen:
            _seen.add(c["name"])
            uniq_chars.append(c)

    st.caption(
        "**Main** and **supporting** characters are pre-selected. "
        "**Minor / background** roles are optional — uncheck any to save cost."
    )
    b1, b2, b3 = st.columns(3)
    if b1.button("Select all", use_container_width=True):
        for c in uniq_chars:
            st.session_state[f"pick_{c['name']}"] = True
    if b2.button("Only main + supporting", use_container_width=True):
        for c in uniq_chars:
            st.session_state[f"pick_{c['name']}"] = (c.get("tier", "").lower() != "minor")
    if b3.button("Clear all", use_container_width=True):
        for c in uniq_chars:
            st.session_state[f"pick_{c['name']}"] = False

    _tier_icon = {"main": "⭐", "supporting": "🔹", "minor": "▫️"}
    chosen = []
    cols = st.columns(2)
    for i, c in enumerate(uniq_chars):
        tier = (c.get("tier") or "").lower()
        kind = c.get("kind", "")
        species = c.get("species", "")
        default = tier != "minor"  # smart default: skip minor/background
        bits = [tier or "?"]
        if kind == "representative":
            bits.append("stand-in")
        if species and species != "human":
            bits.append(species)
        label = f"{_tier_icon.get(tier, '•')} {c['name']}  ·  {' · '.join(bits)}"
        if cols[i % 2].checkbox(label, value=default, key=f"pick_{c['name']}"):
            chosen.append(c["name"])

    n_sel = len(chosen)
    st.caption(f"**{n_sel}** selected → **{n_sel * 2}** images (~${n_sel * 2 * 0.07:.2f}).")

    # ── per-character reference photos (exact likeness) ──────────────────────
    with st.expander("📎 Reference photo per character — for EXACT likeness", expanded=False):
        st.caption(
            "Upload a clear photo of a character (a real person or pet) and the "
            "generated art will match it exactly — hairstyle, face, build, "
            "clothing. Best with a clean photo of just that one subject."
        )
        doc0 = st.session_state.get("doc", {})
        embedded = doc0.get("reference_images_bytes") or []
        if embedded:
            st.caption(f"ℹ️ {len(embedded)} photo(s) were embedded in the manuscript — "
                       "shown below. Crop to one subject and upload per character for "
                       "the sharpest match.")
            st.image(embedded, width=110)
        rcols = st.columns(2)
        for i, name in enumerate(chosen):
            up = rcols[i % 2].file_uploader(
                f"📷 {name}", type=["png", "jpg", "jpeg", "webp"],
                key=f"ref_{name}")
            if up is not None:
                rcols[i % 2].image(up, width=90, caption=f"{name} reference")
    st.session_state["_chosen_names"] = chosen

    with st.expander("View character bible (LLM-designed details)"):
        for c in st.session_state["bible"]:
            st.markdown(
                f"**{c['name']}** — {c.get('age_appearance','')} {c.get('gender','')}  \n"
                f"Hair: {c.get('hair','')} · Eyes: {c.get('eyes','')}  \n"
                f"Outfit: {c.get('default_outfit',{}).get('description','')}"
            )

    # ── step 3: generate images (parallel + live view) ─────────────────────
    def run_generation(style_prompt: str, chosen_unique: list[str]) -> None:
        # Fresh set each run so a style change fully replaces the images.
        images: dict = {}
        bible_by_name = {c["name"]: c for c in st.session_state["bible"]}

        # Per-character reference photos → condition generation for EXACT likeness.
        char_refs: dict = {}
        for name in chosen_unique:
            up = st.session_state.get(f"ref_{name}")
            if up is not None:
                try:                       # normalise any upload to PNG bytes
                    img = Image.open(BytesIO(up.getvalue())).convert("RGB")
                    b = BytesIO(); img.save(b, format="PNG")
                    char_refs[name] = b.getvalue()
                except Exception:  # noqa: BLE001
                    pass
        # Vision-caption each reference once so the exact attributes land in the prompt.
        char_caption: dict = {}
        if char_refs:
            with st.spinner("Reading reference photos…"):
                for name, b in char_refs.items():
                    char_caption[name] = describe_reference(b, name)
            st.caption("📷 Exact-likeness references in use for: " + ", ".join(char_refs))

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
        def _fullbody_task(name):
            if name in char_refs:          # exact-likeness: caption + condition on photo
                lean = (f"full-body children's book character illustration of {name} "
                        f"standing in a neutral pose, plain background. {style_prompt}")
                return generate_view_ref(
                    _exact_likeness(lean, name, char_caption.get(name, "")),
                    [char_refs[name]])
            return generate_view(refs.full_body_prompt(bible_by_name[name], style_prompt))

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = {ex.submit(_fullbody_task, name): name for name in chosen_unique}
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
        def _closeup_gen(name):
            has_fb = bool(images.get(name, {}).get("full_body"))
            fb_crop = crop_front_figure(images[name]["full_body"]) if has_fb else None
            if name in char_refs:
                # Exact likeness: condition on the real photo FIRST, plus the
                # matching full-body so the two views stay the same character.
                lean = (f"head-and-shoulders close-up portrait of {name}, facing "
                        f"forward, plain background. {style_prompt}")
                ref_list = [char_refs[name]] + ([fb_crop] if fb_crop else [])
                return generate_view_ref(
                    _exact_likeness(lean, name, char_caption.get(name, "")), ref_list)
            if has_fb:
                return generate_close(
                    refs.close_up_edit_prompt(bible_by_name[name], style_prompt), fb_crop)
            return generate_close(
                refs.portrait_prompt(bible_by_name[name], style_prompt), None)

        def _closeup_task(name):
            """Always return a close view — if the API call fails or is moderated,
            crop the head from the full-body (which almost always succeeded) so the
            client never sees 'Close view not available'."""
            try:
                return _closeup_gen(name), False
            except Exception as e:  # noqa: BLE001 — moderation or API error
                fb = images.get(name, {}).get("full_body")
                if fb:
                    print(f"[closeup] {name}: {str(e)[:80]} — cropping face from full-body",
                          flush=True)
                    return crop_face(fb), True
                raise

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = {ex.submit(_closeup_task, name): name for name in chosen_unique}
            for fut in concurrent.futures.as_completed(futs):
                name = futs[fut]
                ph = cells[(name, "portrait")]
                try:
                    img, fallback = fut.result()
                    images.setdefault(name, {})["portrait"] = img
                    cap = VIEWS["portrait"] + (" (from full-body)" if fallback else "")
                    ph.image(img, caption=cap, use_container_width=True)
                except Exception as e:  # noqa: BLE001 — no full-body either
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
        st.session_state["gen_style"] = style_prompt  # remember the tone we rendered

    # ── step 3: pick a style (preview main char in the top 3) → generate all ─
    chosen_unique = list(dict.fromkeys(chosen))
    bible_by_name = {c["name"]: c for c in st.session_state["bible"]}
    # Manual mode stays live from the current sidebar selection; auto mode uses
    # the top-3 recommended at analysis time.
    if style_mode == "Choose manually" and manual_style:
        top_styles = [{"key": "manual", "label": "Your chosen style",
                       "why": "", "style_prompt": manual_style}]
    else:
        top_styles = st.session_state.get("top_styles", [])
    # Main character (highest-ranked) represents each style in the preview.
    main_name = uniq_chars[0]["name"] if uniq_chars else (chosen_unique[0] if chosen_unique else None)

    st.subheader("3 · Pick a style")
    if not top_styles or not main_name:
        st.info("Analyze a manuscript first to get style recommendations.")
    else:
        st.caption(
            f"Preview shows the main character **{main_name}** in each recommended style. "
            "Pick one to generate **all selected characters (both views)** in that style."
        )
        if st.button("🎨 Generate style previews", type="primary", use_container_width=True):
            st.session_state["show_style_previews"] = True

        if st.session_state.get("show_style_previews"):
            # Render the main character full-length in each style — parallel, cached.
            pkey = tuple(s["style_prompt"] for s in top_styles) + (main_name,)
            if st.session_state.get("style_previews_key") != pkey:
                with st.spinner(f"Rendering {main_name} in {len(top_styles)} style(s)…"):
                    def _prev(sty):
                        try:
                            return generate_view(
                                refs.full_body_prompt(bible_by_name[main_name], sty["style_prompt"])
                            )
                        except Exception as e:  # noqa: BLE001
                            print(f"[style preview] {sty.get('key')} failed: {e}", flush=True)
                            return None
                    with concurrent.futures.ThreadPoolExecutor(max_workers=min(3, len(top_styles))) as ex:
                        st.session_state["style_previews"] = list(ex.map(_prev, top_styles))
                st.session_state["style_previews_key"] = pkey

            previews = st.session_state.get("style_previews", [])
            cols = st.columns(len(top_styles))
            for i, sty in enumerate(top_styles):
                with cols[i]:
                    st.markdown(f"**{i + 1}. {sty['label']}**")
                    if sty.get("why"):
                        st.caption(sty["why"])
                    img = previews[i] if i < len(previews) else None
                    if img:
                        st.image(img, use_container_width=True)
                    else:
                        st.error("Preview failed.")
                    if st.button("✅ Generate all in this style", key=f"applysty_{i}",
                                 use_container_width=True):
                        st.session_state["show_style_previews"] = False
                        st.session_state.pop("style_previews", None)
                        st.session_state.pop("style_previews_key", None)
                        run_generation(sty["style_prompt"], chosen_unique)


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
