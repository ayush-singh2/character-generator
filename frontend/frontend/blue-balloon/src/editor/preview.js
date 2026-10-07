import React from 'react';
import ModuleBBTH from './book-theme.js';
import ModuleBBR from './render.js';
import ModuleShadcnUiDesignSystem_6211ba from './ui.jsx';
/* Blue Balloon — Preview Book: a read-only reading mode laid over the editor.
   Reads the live document (pages, settings, book theme) — no second copy of the book.

   Performance shape (deliberate):
   · Spreads are keyed layers. A turn re-orders/reuses existing DOM — pages are never
     unmounted and remounted mid-animation, so no re-decode and no white frame.
   · Only three layers are mounted at a time (prev / current / next); the far neighbour
     is mounted after the turn ends, never during it.
   · A turn costs exactly two React updates (start, end). Nothing renders per frame:
     the motion is one composited transform on one leaf.
   · Page artwork for neighbouring spreads is downloaded and decoded during idle time.
   · Pages, leaves and thumbnails are memoized, so a parent (editor/AI) re-render or a
     page-counter change does not reconcile the book.
   · If a device still drops frames, the 3D leaf turn downgrades to a transform slide. */

  const h = React.createElement;
  const { useState, useEffect, useRef, useMemo, useCallback, memo } = React;
  const Button = ModuleShadcnUiDesignSystem_6211ba.Button;
  const BBR = ModuleBBR;
  const TURN = 620, OPEN = 700, SLIDE = 380;

  const I = {
    left: '<path d="m15 18-6-6 6-6"/>',
    right: '<path d="m9 18 6-6-6-6"/>',
    back: '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    expand: '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
    shrink: '<path d="M8 3v3a2 2 0 0 1-2 2H3"/><path d="M21 8h-3a2 2 0 0 1-2-2V3"/><path d="M3 16h3a2 2 0 0 1 2 2v3"/><path d="M16 21v-3a2 2 0 0 1 2-2h3"/>',
    share: '<path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><path d="m16 6-4-4-4 4"/><path d="M12 2v13"/>',
    refresh: '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/>'
  };
  const svg = (d, size) => h("svg", { width: size || 16, height: size || 16, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round",
    dangerouslySetInnerHTML: { __html: d } });
  const bgOf = (page, theme) => (ModuleBBTH ? ModuleBBTH.pageBg(page, theme) : (page && page.bg)) || "#fffdf7";
  const reduced = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const idle = (fn) => (window.requestIdleCallback ? window.requestIdleCallback(fn, { timeout: 400 }) : setTimeout(fn, 60));

  /* Artwork is fetched and decoded ahead of the turn, never during it. */
  const warmed = new Map();
  function warmPage(page) {
    if (!page || !page.els) return;
    page.els.forEach((el) => {
      if (!el.src || warmed.has(el.src)) return;
      const im = new Image();
      warmed.set(el.src, im);
      im.src = el.src;
      if (im.decode) im.decode().catch(() => {});
    });
  }

  /* One book page, drawn with the editor's own renderer at any scale. */
  const PageView = memo(function PageView({ page, ctx, scale }) {
    const dims = ctx.dims;
    const c = useMemo(() => Object.assign({}, ctx, { page: page }), [ctx, page]);
    const els = useMemo(() => (page.els || []).slice().sort((a, b) => (a.z || 1) - (b.z || 1)), [page]);
    return h("div", { className: "pv-page", style: { width: dims.w, height: dims.h, background: bgOf(page, ctx.theme), transform: "scale(" + scale + ")" } },
      els.map((el) => {
        const norm = Object.assign({}, el, { x: 0, y: 0, w: 100, h: el.h != null ? 100 : null });
        return h("div", { key: el.id, className: "el", style: { left: el.x + "%", top: el.y + "%",
          width: el.w + "%", height: el.h != null ? el.h + "%" : "auto", zIndex: el.z || 1 } }, BBR.renderEl(norm, c));
      }));
  });

  const MiniPage = memo(function MiniPage({ page, ctx, w, maxH }) {
    const dims = ctx.dims;
    const s = Math.min(w / dims.w, maxH / dims.h);
    return h("div", { style: { width: Math.round(dims.w * s), height: Math.round(dims.h * s), position: "relative", overflow: "hidden" } },
      h(PageView, { page: page, ctx: ctx, scale: s }));
  });

  /* A single leaf of the book. `side` is "l", "r" or "one"; the leaf marked
     data-sheet is the one that physically turns. */
  const Leaf = memo(function Leaf({ page, ctx, scale, side, sheet, state, label, blankBg, retryable, onRetry, onClose }) {
    const dims = ctx.dims;
    const st = { width: Math.round(dims.w * scale), height: Math.round(dims.h * scale) };
    if (!page) return h("div", { className: "pv-leaf pv-leaf--blank", "data-side": side, style: Object.assign({ background: blankBg }, st) },
      h("div", { className: "pv-leaf-in" }));
    return h("div", { className: "pv-leaf", "data-side": side, "data-sheet": sheet ? "true" : null, style: st },
      h("div", { className: "pv-leaf-in" },
        h(PageView, { page: page, ctx: ctx, scale: scale }),
        h("span", { className: "pv-gutter" }),
        state === "generating" ? h("div", { className: "pv-veil", role: "status" }, h("div", null,
          h("div", { className: "vic" }, h("span", { className: "spin" }, svg(I.refresh, 22))),
          h("div", { className: "vt" }, label),
          h("div", { className: "vs" }, "Generating illustration\u2026"))) : null,
        state === "error" ? h("div", { className: "pv-veil", role: "status" }, h("div", null,
          h("div", { className: "vt" }, "This page isn\u2019t ready yet."),
          h("div", { className: "vs" }, label + " didn\u2019t finish generating."),
          h("div", { className: "vb" },
            retryable ? h(Button, { size: "sm", onClick: () => onRetry(page.id) }, svg(I.refresh, 14), "Try Again") : null,
            h(Button, { size: "sm", variant: "outline", onClick: onClose }, "Back to Editor")))) : null));
  });

  const Thumb = memo(function Thumb({ idx, page, ctx, w, maxH, live, on, lb, onJump }) {
    return h("button", { className: "pv-thumb", "data-on": on, onClick: () => onJump(idx),
        style: { containIntrinsicSize: w + "px " + maxH + "px" },
        "aria-label": idx < 0 ? "Cover" : "Page " + (idx + 1), "aria-current": on ? "true" : null },
      live ? h(MiniPage, { page: page, ctx: ctx, w: w, maxH: maxH })
        : h("span", { className: "pv-thumb-ph", style: { width: w, height: maxH } }),
      h("span", { className: "n" }, lb));
  });

  function PreviewBook({ pages, settings, theme, dims, tasks, title, onClose, onShare, onRetry }) {
    const list = pages || [];
    const cover = list[0] && list[0].kind === "cover" ? list[0] : null;
    const reading = useMemo(() => (cover ? list.slice(1) : list.slice()), [list, cover]);
    const total = reading.length;
    const spreads = Math.floor(total / 2) + (total ? 1 : 0);   // [—,1] [2,3] [4,5] …

    // cur is the only source of truth: -1 on the closed cover, else an index into `reading`
    const [cur, setCur] = useState(-1);
    const [anim, setAnim] = useState(null);      // { from, to, dir, kind } — set once, cleared once
    const [win, setWin] = useState([-1, 0, 1]);  // spread positions kept mounted
    const [fs, setFs] = useState(false);
    const [box, setBox] = useState(null);
    const [short, setShort] = useState(() => window.innerHeight < 760);
    const [simple, setSimple] = useState(() => { try { return sessionStorage.getItem("bb_pv_simple") === "1"; } catch (e) { return false; } });
    const animRef = useRef(null), pendRef = useRef(0), curRef = useRef(-1);
    const safety = useRef(null), sampler = useRef(null), sampled = useRef(0);
    const fitRef = useRef(null), rootRef = useRef(null);
    curRef.current = cur;

    const ctx = useMemo(() => ({ dims: dims, theme: theme }), [dims.w, dims.h, theme]);
    const paper = bgOf(reading[0] || cover, theme);

    // one geometry for every screen: the book never resizes or shifts between turns
    const twoUp = !!box && box.w > 720 && box.w / (dims.w * 2 + 14) >= 0.34;
    const reserve = twoUp ? 96 : 118;
    const fitH = box ? Math.max(box.h - reserve, 150) : 0;
    const bookW = twoUp ? dims.w * 2 + 14 : dims.w;
    const scale = box ? Math.max(0.2, Math.min(Math.min(box.w / bookW, fitH / dims.h), 2)) : 0.5;
    const pageW = Math.round(dims.w * scale), pageH = Math.round(dims.h * scale);
    const boxW = twoUp ? pageW * 2 + 14 : pageW;

    const spreadOf = (i) => Math.floor((i + 1) / 2);
    const leavesOf = (s) => (s <= 0 ? [null, reading[0] || null] : [reading[2 * s - 1] || null, reading[2 * s] || null]);
    const posOf = (i) => (i < 0 ? -1 : twoUp ? spreadOf(i) : i);
    const curOfPos = (p) => (p < 0 ? -1 : twoUp ? (p === 0 ? 0 : 2 * p - 1) : p);
    const firstPos = cover ? -1 : 0;
    const lastPos = twoUp ? spreads - 1 : total - 1;
    const pos = posOf(cur);
    const onCover = cur < 0;
    const lastStop = pos >= lastPos && !onCover;
    const pagesAt = (p) => (p < 0 ? [null, cover] : twoUp ? leavesOf(p) : [null, reading[p]]);

    /* ---- navigation: one state update to start a turn, one to finish it ---- */
    function startSample() {
      if (simple || sampled.current > 2) return;
      const f = []; let last = performance.now(), on = true;
      const tick = (t) => { f.push(t - last); last = t; if (on) requestAnimationFrame(tick); };
      requestAnimationFrame(tick);
      sampler.current = { stop: () => { on = false; return f; } };
    }
    function endSample() {
      const s = sampler.current; sampler.current = null;
      if (!s) return;
      const f = s.stop().slice(3);
      if (f.length < 8) return;
      sampled.current++;
      // a third of the frames over ~26ms means this device can't hold the leaf turn
      if (f.filter((d) => d > 26).length / f.length > 0.33) {
        setSimple(true);
        try { sessionStorage.setItem("bb_pv_simple", "1"); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
      }
    }
    function endTurn() {
      if (!animRef.current) return;
      animRef.current = null;
      if (safety.current) { clearTimeout(safety.current); safety.current = null; }
      endSample();
      setAnim(null);
      const d = pendRef.current; pendRef.current = 0;
      if (d) requestAnimationFrame(() => go(d));
    }
    function move(from, to, d, animate) {
      const soft = animate && !reduced();
      const kind = !soft ? null : (from < 0 || to < 0) ? "cover" : (twoUp && !simple) ? "sheet" : "slide";
      if (kind) {
        const a = { from: from, to: to, dir: d, kind: kind };
        animRef.current = a;
        startSample();
        safety.current = setTimeout(endTurn, (kind === "cover" ? OPEN : kind === "sheet" ? TURN : SLIDE) + 320);
        setAnim(a);
      }
      setCur(curOfPos(to));
    }
    function go(d) {
      if (!total) return;
      if (animRef.current) { pendRef.current = d; return; }   // queue at most one
      const from = posOf(curRef.current);
      const to = Math.max(firstPos, Math.min(from + d, lastPos));
      if (to === from) return;
      move(from, to, d, true);
    }
    const jumpToPage = (i) => {
      const from = posOf(curRef.current);
      const to = i < 0 ? -1 : posOf(i);
      if (to === from) return;
      if (animRef.current) { if (Math.abs(to - from) === 1) pendRef.current = to > from ? 1 : -1; return; }
      move(from, to, to > from ? 1 : -1, Math.abs(to - from) === 1);   // far jumps land, they don't flip through
    };
    const onAnimEnd = (e) => { if (/^pv(Sheet|Slide)/.test(e.animationName)) endTurn(); };

    // mounted window: prev / current / next, refreshed only when nothing is animating
    useEffect(() => {
      if (anim) return;
      const want = [pos - 1, pos, pos + 1].filter((p) => p >= firstPos && p <= lastPos);
      setWin((w) => (w.length === want.length && w.every((v, i) => v === want[i]) ? w : want));
    }, [pos, anim, firstPos, lastPos, twoUp]);
    const mounted = useMemo(() => {
      const s = {}; const out = [];
      const push = (p) => { if (p >= firstPos && p <= lastPos && !s[p]) { s[p] = 1; out.push(p); } };
      win.forEach(push); push(pos);
      if (anim) { push(anim.from); push(anim.to); }
      return out.sort((a, b) => a - b);
    }, [win, pos, anim, firstPos, lastPos]);

    // decode neighbouring artwork while the reader is idle, so a turn never waits on an image
    useEffect(() => {
      const id = idle(() => {
        for (let p = pos - 2; p <= pos + 2; p++) {
          if (p < firstPos || p > lastPos) continue;
          pagesAt(p).forEach(warmPage);
        }
      });
      return () => { if (window.cancelIdleCallback && typeof id === "number") { try { window.cancelIdleCallback(id); } catch (e) { /* Optional browser capability or local cache is unavailable. */ } } };
    }, [pos, twoUp, reading, firstPos, lastPos]);

    useEffect(() => () => { if (safety.current) clearTimeout(safety.current); if (sampler.current) sampler.current.stop(); }, []);

    // fit the book to whatever space the reading area has (rAF-throttled, no-op when unchanged)
    useEffect(() => {
      const n = fitRef.current; if (!n) return;
      let raf = 0, lw = 0, lh = 0;
      const measure = () => {
        raf = 0;
        const w = n.clientWidth, hh = n.clientHeight;
        if (Math.abs(w - lw) < 2 && Math.abs(hh - lh) < 2) return;
        lw = w; lh = hh;
        setBox({ w: w, h: hh });
        setShort(window.innerHeight < 760);
      };
      const schedule = () => { if (!raf) raf = requestAnimationFrame(measure); };
      measure();
      let ro = null;
      if (window.ResizeObserver) { ro = new ResizeObserver(schedule); ro.observe(n); }
      else window.addEventListener("resize", schedule);
      return () => { if (raf) cancelAnimationFrame(raf); if (ro) ro.disconnect(); else window.removeEventListener("resize", schedule); };
    }, []);

    useEffect(() => {
      document.body.classList.add("previewing");
      const onFsChange = () => setFs(!!document.fullscreenElement);
      document.addEventListener("fullscreenchange", onFsChange);
      return () => {
        document.body.classList.remove("previewing");
        document.removeEventListener("fullscreenchange", onFsChange);
        if (document.fullscreenElement) { try { document.exitFullscreen(); } catch (e) { /* Optional browser capability or local cache is unavailable. */ } }
      };
    }, []);
    const toggleFs = () => {
      // `fs` also covers the fallback path, where the browser denies the Fullscreen API
      if (fs || document.fullscreenElement) {
        if (document.fullscreenElement) { try { document.exitFullscreen(); } catch (e) { /* Optional browser capability or local cache is unavailable. */ } }
        setFs(false);
        return;
      }
      const n = rootRef.current;
      if (n && n.requestFullscreen) { const p = n.requestFullscreen(); if (p && p.catch) p.catch(() => {}); }
      setFs(true);
    };

    useEffect(() => {
      const onKey = (e) => {
        const tag = (e.target.tagName || "").toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable) return;
        if (e.key === "ArrowRight" || e.key === "PageDown" || (e.key === " " && !e.shiftKey)) { e.preventDefault(); e.stopPropagation(); go(1); }
        else if (e.key === "ArrowLeft" || e.key === "PageUp" || (e.key === " " && e.shiftKey)) { e.preventDefault(); e.stopPropagation(); go(-1); }
        else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); if (fs || document.fullscreenElement) toggleFs(); else onClose(); }
      };
      window.addEventListener("keydown", onKey, true);
      return () => window.removeEventListener("keydown", onKey, true);
    }, [twoUp, fs, simple, lastPos]);

    /* ---- page state, kept as primitives so memoized leaves can bail out ---- */
    const taskMap = useMemo(() => {
      const m = {};
      (tasks || []).forEach((t) => { if (t.pageId) m[t.pageId] = t; });
      return m;
    }, [tasks]);
    const taskRef = useRef(taskMap); taskRef.current = taskMap;
    const closeRef = useRef(onClose); closeRef.current = onClose;
    const retryRef = useRef(onRetry); retryRef.current = onRetry;
    const doClose = useCallback(() => { if (closeRef.current) closeRef.current(); }, []);
    const doRetry = useCallback((pageId) => {
      const t = taskRef.current[pageId];
      if (t && retryRef.current) retryRef.current(t.id);
    }, []);
    const doJump = useCallback((i) => jumpToPage(i), [twoUp, simple, lastPos]);
    const stateOf = (p) => {
      if (!p) return null;
      const t = taskMap[p.id];
      if (t && t.status === "error") return "error";
      if (p.generating || (t && t.status === "running")) return "generating";
      return null;
    };
    const numOf = (p) => reading.indexOf(p) + 1;
    const leafProps = (p, side, sheet) => ({ page: p, ctx: ctx, scale: scale, side: side, sheet: sheet, blankBg: paper,
      state: stateOf(p), label: p ? "Page " + numOf(p) : "", retryable: !!(p && taskMap[p.id]), onRetry: doRetry, onClose: doClose });

    const busy = list.filter((p) => stateOf(p) === "generating").length;
    const leaves = onCover ? [null, cover] : pagesAt(pos);
    const shown = onCover ? 0 : twoUp ? Math.max(numOf(leaves[1]), numOf(leaves[0])) : cur + 1;
    const pct = total ? (shown / total) * 100 : 100;
    const indicator = onCover ? "Cover"
      : twoUp
        ? (leaves[0] && leaves[1] ? numOf(leaves[0]) + "\u2013" + numOf(leaves[1]) + " / " + total
          : (leaves[1] ? numOf(leaves[1]) : numOf(leaves[0])) + " / " + total)
        : (cur + 1) + " / " + total;
    const meta = total + (total === 1 ? " page" : " pages") + (settings && settings.style ? " \u00b7 " + settings.style : "");
    const isOn = (i) => (onCover ? i < 0 : i >= 0 && (twoUp ? leaves.indexOf(reading[i]) >= 0 : i === cur));
    const coverCap = h("div", { className: "pv-cover-cap" },
      h("div", { className: "t" }, title),
      busy ? h("div", { className: "s" }, busy + (busy === 1 ? " page" : " pages") + " still generating") : null,
      h(Button, { onClick: () => go(1), "aria-label": "Start reading", disabled: !total }, "Start Reading", svg(I.right, 15)));

    function layerCls(p) {
      let c = "pv-layer";
      if (anim) {
        if (anim.kind === "slide") {
          if (p === anim.from) c += " sl-out";
          if (p === anim.to) c += " sl-in";
          if (p === anim.from || p === anim.to) c += anim.dir > 0 ? " fwd" : " back";
        } else {
          if (anim.dir > 0 && p === anim.from) c += " turn-out top";
          if (anim.dir < 0 && p === anim.to) c += " turn-in top";
          if ((anim.dir > 0 && p === anim.to) || (anim.dir < 0 && p === anim.from)) c += " uncover";
          if (anim.kind === "cover") c += " slow";
        }
      }
      return c;
    }
    function renderLayer(p) {
      const isCover = p < 0;
      const pair = pagesAt(p);
      const on = p === pos || !!(anim && (p === anim.from || p === anim.to));
      return h("div", { key: (twoUp ? "s" : "p") + p, className: layerCls(p), "data-on": on ? "true" : "false",
          "data-closed": isCover ? "true" : null },
        twoUp ? (isCover
          ? h("div", { className: "pv-half", style: { width: pageW, height: pageH } }, coverCap)
          : h(Leaf, leafProps(pair[0], "l", false))) : null,
        twoUp ? h("span", { className: "pv-spine" }) : null,
        h(Leaf, leafProps(pair[1], twoUp ? "r" : "one", true)),
        h("span", { className: "pv-cast" }));
    }

    const thumbW = short ? 30 : 42, thumbH = short ? 40 : 56;
    const rail = useMemo(() => (cover ? [{ i: -1, page: cover, lb: "C" }] : [])
      .concat(reading.map((p, i) => ({ i: i, page: p, lb: i + 1 }))), [cover, reading]);

    return h("div", { className: "pv" + (fs ? " fs" : ""), ref: rootRef, role: "dialog", "aria-modal": "true", "aria-label": "Book preview" },
      h("div", { className: "pv-top" },
        h("div", { className: "pv-top-l" },
          h(Button, { variant: "ghost", size: "sm", onClick: onClose, "aria-label": "Exit preview", title: "Back to editor" },
            svg(I.back, 15), h("span", { className: "pv-lbl" }, "Back to editor"))),
        h("div", { className: "pv-title" },
          h("div", { className: "t" }, title),
          h("div", { className: "s" }, meta)),
        h("div", { className: "pv-top-r" },
          onShare ? h(Button, { variant: "outline", size: "sm", onClick: onShare, "aria-label": "Share book", title: "Share a read-only link" },
            svg(I.share, 15), h("span", { className: "pv-lbl" }, "Share")) : null,
          h(Button, { variant: "ghost", size: "icon", onClick: toggleFs, title: fs ? "Exit fullscreen" : "Fullscreen",
            "aria-label": fs ? "Exit fullscreen" : "Enter fullscreen" }, svg(fs ? I.shrink : I.expand, 16)))),
      h("div", { className: "pv-prog" }, h("span", { style: { width: pct + "%" } })),
      h("div", { className: "pv-stage" },
        h("div", { className: "pv-fit", ref: fitRef },
          h("div", { className: "pv-anim" },
            h("div", { className: "pv-book" + (twoUp ? " two" : ""), style: { width: boxW, height: pageH, "--pv-paper": paper },
                onAnimationEnd: onAnimEnd }, mounted.map(renderLayer)),
            onCover && !twoUp && !anim ? coverCap : null,
            lastStop ? h("div", { className: "pv-end" },
              h("div", { className: "et" }, "End of story"),
              h("div", { className: "eb" },
                h(Button, { variant: "outline", size: "sm", onClick: () => jumpToPage(-1) }, svg(I.refresh, 14), "Read Again"),
                h(Button, { variant: "outline", size: "sm", onClick: onClose }, "Back to Editor"),
                onShare ? h(Button, { variant: "ghost", size: "sm", onClick: onShare }, "Share Book") : null)) : null))),
      h("div", { className: "pv-bottom" },
        h("div", { className: "pv-nav" },
          h(Button, { variant: "outline", size: "sm", disabled: pos <= firstPos, onClick: () => go(-1), "aria-label": "Previous page" },
            svg(I.left, 15), h("span", { className: "pv-lbl" }, "Previous")),
          h("div", { className: "pv-ind", "aria-live": "polite" }, indicator),
          h(Button, { variant: "outline", size: "sm", disabled: pos >= lastPos, onClick: () => go(1), "aria-label": "Next page" },
            h("span", { className: "pv-lbl" }, "Next"), svg(I.right, 15))),
        total ? h("div", { className: "pv-thumbs", "aria-label": "Jump to a page" },
          rail.map((s) => h(Thumb, { key: s.i, idx: s.i, page: s.page, ctx: ctx, w: thumbW, maxH: thumbH,
            live: Math.abs(posOf(s.i) - pos) <= 8, on: isOn(s.i), lb: s.lb, onJump: doJump }))) : null)
    );
  }

  export default { PreviewBook, PageView, MiniPage };
