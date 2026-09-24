/* Workspace "Generated book" panel.
 *
 * The BB-artists Workspace ships an elaborate element-level canvas mock
 * (workspace.js). Rather than destabilise that, this file mounts its OWN React
 * root that delivers the three promised Workspace jobs against the real backend:
 *   1. watch the illustration job (layout -> generate -> correct -> compose -> book)
 *   2. browse the generated pages
 *   3. correct any page by a plain-language instruction (Author-Control §3)
 *   4. export the print-ready PDF (Author-Control §6)
 *
 * It's a floating launcher + modal, styled neutrally to sit with the design.
 */
(function () {
  if (!window.React || !window.ReactDOM || !window.BB) return;
  const e = React.createElement;
  const slug = BB.currentProject();
  if (!slug) return; // opened without a project — nothing to show

  const C = {
    ink: "#1c1917", sub: "#78716c", line: "#e7e5e4", card: "#ffffff",
    bg: "#faf9f7", primary: "#111827", primaryInk: "#ffffff", accent: "#6366f1"
  };
  const bust = (u) => u + (u.indexOf("?") >= 0 ? "&" : "?") + "v=" + Date.now();

  function Panel({ onClose }) {
    const [job, setJob] = React.useState(null);
    const [pages, setPages] = React.useState([]);
    const [active, setActive] = React.useState(null);      // page id being corrected
    const [instruction, setInstruction] = React.useState("");
    const [working, setWorking] = React.useState("");       // page id under edit
    const [imgv, setImgv] = React.useState({});             // page id -> cache-bust url
    const [err, setErr] = React.useState("");
    const [note, setNote] = React.useState("");             // per-page direction text
    const [reGen, setReGen] = React.useState(null);         // {pct} while re-illustrating

    const loadPages = React.useCallback(() => {
      BB.api.getPages(slug).then(setPages).catch(() => {});
    }, []);

    React.useEffect(() => {
      let alive = true;
      loadPages();
      const tick = () => {
        BB.api.getJob(slug).then((st) => {
          if (!alive) return;
          setJob(st);
          if (st.state === "running") setTimeout(tick, 2500);
          else loadPages();                                  // refresh when finished
        }).catch(() => {});
      };
      tick();
      return () => { alive = false; };
    }, [loadPages]);

    const running = job && job.state === "running";
    const stageLabel = ({
      layout: "Planning page layouts…", generate: "Illustrating pages…",
      correct: "Checking character consistency…", compose: "Placing the text…",
      book: "Assembling the PDF…"
    })[job && job.stage] || "Working…";

    const applyFix = async (pid) => {
      if (!instruction.trim() || working) return;
      setWorking(pid); setErr("");
      try {
        const res = await BB.api.correctPage(slug, pid, instruction.trim());
        setImgv((m) => Object.assign({}, m, { [pid]: res.url }));
        setInstruction("");
      } catch (ex) {
        setErr(ex.message || "Couldn't apply that change.");
      } finally { setWorking(""); }
    };

    const src = (p) => imgv[p.id] || bust(p.url);

    // load any saved direction when a page opens
    React.useEffect(() => {
      if (!active) return;
      setNote(""); setReGen(null);
      BB.api.getPageNote(slug, active).then((n) => setNote(n || "")).catch(() => {});
    }, [active]);

    // Re-illustrate ONE page from an authoritative direction (Author-Control §1).
    // Unlike a correction (a surgical edit), this redraws the page from scratch
    // using the note as the shot list, then re-runs the consistency loop.
    const reillustrate = async (pid) => {
      if (reGen || working) return;
      setErr(""); setReGen({ pct: 3 });
      try {
        await BB.api.setPageNote(slug, pid, note);        // stores note + starts job
        await BB.api.pollJob(slug, (st) => setReGen({ pct: st.pct || 3, stage: st.stage }));
        setImgv((m) => Object.assign({}, m, { [pid]: bust(pages.find((p) => p.id === pid).url) }));
        loadPages();
      } catch (ex) {
        setErr(ex.message || "Couldn't re-illustrate this page.");
      } finally { setReGen(null); }
    };

    // ---- detail (correct one page) ----
    const detail = active && pages.find((p) => p.id === active);

    return e("div", { style: S.scrim, onMouseDown: onClose },
      e("div", { style: S.modal, onMouseDown: (ev) => ev.stopPropagation() },
        e("div", { style: S.head },
          e("div", null,
            e("div", { style: S.title }, "Generated book"),
            e("div", { style: S.subtle }, running ? stageLabel
              : (pages.length ? pages.length + " page" + (pages.length === 1 ? "" : "s") + " ready"
                              : "No pages yet — start generation from the Characters step."))
          ),
          e("div", { style: { display: "flex", gap: 8 } },
            e("button", { style: S.ghostBtn, onClick: () => (window.location = BB.api.pdfUrl(slug)) }, "Export PDF"),
            e("button", { style: S.ghostBtn, onClick: onClose }, "Close")
          )
        ),

        running ? e("div", { style: S.progWrap },
          e("div", { style: S.track }, e("div", { style: Object.assign({}, S.fill, { width: (job.pct || 3) + "%" }) })),
          e("div", { style: S.subtle }, "This runs page by page and takes several minutes. You can leave this open.")
        ) : null,

        err ? e("div", { style: S.err }, err) : null,

        // ---- detail view: one page + correction box ----
        detail ? e("div", { style: S.detail },
          e("button", { style: S.linkBtn, onClick: () => setActive(null) }, "← All pages"),
          e("div", { style: { display: "flex", gap: 20, marginTop: 12, flexWrap: "wrap" } },
            e("div", { style: S.detailImgWrap },
              e("img", { src: src(detail), alt: "Page " + detail.id, style: S.detailImg }),
              working === detail.id ? e("div", { style: S.overlay }, "Applying your change…")
                : (reGen ? e("div", { style: S.overlay }, "Re-illustrating…") : null)
            ),
            e("div", { style: { flex: "1 1 300px", minWidth: 280 } },
              // 1) surgical correction
              e("div", { style: S.label }, "Correct this page"),
              e("div", { style: S.hint }, "Change one thing, keep the rest — e.g. “make the cat orange”, “add a red hat to Ella”, “add a jump rope in her hands”."),
              e("textarea", { style: S.textarea, value: instruction, placeholder: "Add a red hat to Ella…",
                onChange: (ev) => setInstruction(ev.target.value) }),
              e("button", { style: Object.assign({}, S.primaryBtn, (!instruction.trim() || working || reGen) ? S.disabled : null),
                disabled: !instruction.trim() || !!working || !!reGen, onClick: () => applyFix(detail.id) },
                working === detail.id ? "Applying…" : "Apply change"),

              // 2) authoritative direction → full re-illustration of this page
              e("div", { style: S.divider }),
              e("div", { style: S.label }, "Direct this page (shot list)"),
              e("div", { style: S.hint }, "Give this page its own direction and redraw it — e.g. “wide shot, Ella kneeling beside the crate, warm evening light, Biscuit visible in the background”. Used as the authoritative brief."),
              e("textarea", { style: S.textarea, value: note, placeholder: "wide shot, Ella kneeling beside the crate…",
                onChange: (ev) => setNote(ev.target.value) }),
              reGen ? e("div", { style: { margin: "8px 0" } },
                e("div", { style: S.track }, e("div", { style: Object.assign({}, S.fill, { width: (reGen.pct || 3) + "%" }) })),
                e("div", { style: S.subtle }, "Re-illustrating this page…")
              ) : null,
              e("button", { style: Object.assign({}, S.primaryBtn, (working || reGen) ? S.disabled : null),
                disabled: !!working || !!reGen, onClick: () => reillustrate(detail.id) },
                reGen ? "Re-illustrating…" : "Re-illustrate page")
            )
          )
        )
        // ---- gallery ----
        : e("div", { style: S.grid },
          pages.length === 0 && !running
            ? e("div", { style: S.empty }, "Nothing generated yet.")
            : pages.map((p) => e("div", { key: p.id, style: S.cardCell, onClick: () => setActive(p.id) },
                e("img", { src: src(p), alt: "Page " + p.id, style: S.thumb }),
                e("div", { style: S.cap }, "Page " + p.id)
              ))
        )
      )
    );
  }

  const S = {
    scrim: { position: "fixed", inset: 0, zIndex: 9000, background: "rgba(0,0,0,0.5)",
             display: "grid", placeItems: "center", padding: 24 },
    modal: { width: "min(1000px, 96vw)", maxHeight: "92vh", overflow: "auto", background: C.bg,
             border: "1px solid " + C.line, borderRadius: 16, boxShadow: "0 24px 60px rgba(0,0,0,0.3)" },
    head: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16,
            padding: "18px 20px", borderBottom: "1px solid " + C.line, position: "sticky", top: 0,
            background: C.bg, borderRadius: "16px 16px 0 0" },
    title: { fontSize: 18, fontWeight: 700, color: C.ink, letterSpacing: "-0.01em" },
    subtle: { fontSize: 13, color: C.sub, marginTop: 3 },
    ghostBtn: { fontSize: 13, fontWeight: 600, color: C.ink, background: C.card,
                border: "1px solid " + C.line, borderRadius: 9, padding: "8px 12px", cursor: "pointer" },
    progWrap: { padding: "16px 20px" },
    track: { height: 8, background: C.line, borderRadius: 99, overflow: "hidden" },
    fill: { height: "100%", background: C.accent, transition: "width 400ms ease" },
    err: { margin: "12px 20px 0", padding: "10px 12px", background: "#fef2f2", color: "#b91c1c",
           border: "1px solid #fecaca", borderRadius: 9, fontSize: 13 },
    grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 14, padding: 20 },
    cardCell: { cursor: "pointer", background: C.card, border: "1px solid " + C.line, borderRadius: 12,
                overflow: "hidden", transition: "transform 120ms ease" },
    thumb: { width: "100%", aspectRatio: "1 / 1", objectFit: "cover", display: "block", background: "#eee" },
    cap: { fontSize: 12, color: C.sub, padding: "8px 10px", fontWeight: 600 },
    empty: { gridColumn: "1 / -1", textAlign: "center", color: C.sub, padding: "40px 0", fontSize: 14 },
    detail: { padding: 20 },
    linkBtn: { background: "none", border: "none", color: C.accent, fontSize: 13, fontWeight: 600, cursor: "pointer", padding: 0 },
    detailImgWrap: { position: "relative", flex: "0 0 auto", width: "min(440px, 100%)" },
    detailImg: { width: "100%", borderRadius: 12, border: "1px solid " + C.line, display: "block", background: "#eee" },
    overlay: { position: "absolute", inset: 0, background: "rgba(0,0,0,0.55)", color: "#fff",
               display: "grid", placeItems: "center", borderRadius: 12, fontSize: 14, fontWeight: 600 },
    label: { fontSize: 14, fontWeight: 700, color: C.ink },
    hint: { fontSize: 12.5, color: C.sub, margin: "6px 0 10px", lineHeight: 1.5 },
    textarea: { width: "100%", minHeight: 90, resize: "vertical", padding: "10px 12px", fontSize: 14,
                border: "1px solid " + C.line, borderRadius: 10, fontFamily: "inherit", boxSizing: "border-box" },
    primaryBtn: { marginTop: 10, background: C.primary, color: C.primaryInk, border: "none",
                  borderRadius: 10, padding: "10px 16px", fontSize: 14, fontWeight: 600, cursor: "pointer" },
    disabled: { opacity: 0.5, cursor: "default" },
    divider: { height: 1, background: C.line, margin: "18px 0" },
    launch: { position: "fixed", right: 20, bottom: 20, zIndex: 8000, background: C.primary,
              color: C.primaryInk, border: "none", borderRadius: 999, padding: "12px 18px", fontSize: 14,
              fontWeight: 700, cursor: "pointer", boxShadow: "0 10px 24px rgba(0,0,0,0.25)" }
  };

  function Launcher() {
    const [open, setOpen] = React.useState(false);
    return e(React.Fragment, null,
      e("button", { style: S.launch, onClick: () => setOpen(true) }, "📖  Generated book"),
      open ? e(Panel, { onClose: () => setOpen(false) }) : null
    );
  }

  const mount = document.createElement("div");
  document.body.appendChild(mount);
  ReactDOM.createRoot(mount).render(e(Launcher));
})();
