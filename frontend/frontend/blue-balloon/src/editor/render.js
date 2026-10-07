import React from 'react';
import ModuleBBTH from './book-theme.js';
import { Icon as LucideIcon, LUCIDE_PATHS } from './icons.js';
/* BB artists — workspace shared bits: page-element rendering, thumbnails, fixed menu */

  const h = React.createElement;
  const { useState, useRef, useEffect, useLayoutEffect } = React;

  Object.assign(LUCIDE_PATHS, {
    "bold": '<path d="M6 12h9a4 4 0 0 1 0 8H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h7a4 4 0 0 1 0 8"/>',
    "italic": '<line x1="19" x2="10" y1="4" y2="4"/><line x1="14" x2="5" y1="20" y2="20"/><line x1="15" x2="9" y1="4" y2="20"/>',
    "underline": '<path d="M6 4v6a6 6 0 0 0 12 0V4"/><line x1="4" x2="20" y1="20" y2="20"/>',
    "align-left": '<line x1="21" x2="3" y1="6" y2="6"/><line x1="15" x2="3" y1="12" y2="12"/><line x1="17" x2="3" y1="18" y2="18"/>',
    "align-center": '<line x1="21" x2="3" y1="6" y2="6"/><line x1="17" x2="7" y1="12" y2="12"/><line x1="19" x2="5" y1="18" y2="18"/>',
    "align-right": '<line x1="21" x2="3" y1="6" y2="6"/><line x1="21" x2="9" y1="12" y2="12"/><line x1="21" x2="7" y1="18" y2="18"/>',
    "keyboard": '<path d="M10 8h.01"/><path d="M12 12h.01"/><path d="M14 8h.01"/><path d="M16 12h.01"/><path d="M18 8h.01"/><path d="M6 8h.01"/><path d="M7 16h10"/><path d="M8 12h.01"/><rect width="20" height="16" x="2" y="4" rx="2"/>',
    "type": '<polyline points="4 7 4 4 20 4 20 7"/><line x1="9" x2="15" y1="20" y2="20"/><line x1="12" x2="12" y1="4" y2="20"/>',
    "heading": '<path d="M6 12h12"/><path d="M6 20V4"/><path d="M18 20V4"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "arrow-up-to-line": '<path d="M5 3h14"/><path d="m18 13-6-6-6 6"/><path d="M12 7v14"/>',
    "arrow-down-to-line": '<path d="M12 17V3"/><path d="m6 11 6 6 6-6"/><path d="M19 21H5"/>',
    "file-plus": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M12 11v6"/><path d="M9 14h6"/>',
    "flag": '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" x2="4" y1="22" y2="15"/>'
  });

  function Svg(inner, size) {
    return h("svg", { width: size || 16, height: size || 16, viewBox: "0 0 24 24", fill: "none",
      stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round",
      dangerouslySetInnerHTML: { __html: inner } });
  }

  const P = {
    copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    front: '<path d="M12 10V3"/><path d="m8 6 4-4 4 4"/><path d="M4 21h16"/>',
    back: '<path d="M12 14v7"/><path d="m8 11 4 4 4-4"/><path d="M4 3h16"/>',
    trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    swap: '<path d="M21 7 17 3v3h-8"/><path d="M3 7h8"/><path d="m3 17 4 4v-3h8"/><path d="M21 17h-8"/>',
    upload: '<path d="M12 15V3"/><path d="m7 8 5-5 5 5"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
    sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4"/><path d="m6 6 2 2M16 16l2 2M18 6l-2 2M8 16l-2 2"/>',
    send: '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7z"/>',
    move: '<path d="M5 9l-3 3 3 3"/><path d="M9 5l3-3 3 3"/><path d="M15 19l-3 3-3-3"/><path d="M19 9l3 3-3 3"/><path d="M2 12h20"/><path d="M12 2v20"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    chevL: '<path d="m15 18-6-6 6-6"/>',
    undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 5 5v0a5 5 0 0 1-5 5H8"/>',
    redo: '<path d="m15 14 5-5-5-5"/><path d="M20 9H9a5 5 0 0 0-5 5v0a5 5 0 0 0 5 5h7"/>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.5-3.5a2 2 0 0 0-2.8 0L6 21"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    refresh: '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/>',
    pencil: '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
    dots: '<circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/><circle cx="5" cy="12" r="1.4"/>'
  };

  // typographic defaults per text kind (size/weight/family/leading/alignment)
  const KIND = {
    title: { fs: 38, fw: 700, ff: "Georgia, 'Times New Roman', serif", ls: "-0.01em", lh: 1.05, ta: "center" },
    subtitle: { fs: 17, fw: 400, ff: "Georgia, serif", ls: "0.04em", lh: 1.3, ta: "center", italic: true },
    heading: { fs: 22, fw: 700, ff: "Georgia, serif", ls: "-0.01em", lh: 1.1, ta: "left" },
    paragraph: { fs: 13.5, fw: 400, ff: "Georgia, serif", ls: "0", lh: 1.7, ta: "left" },
    pageno: { fs: 13, fw: 600, ff: "Georgia, serif", ls: "0.12em", lh: 1, ta: "left" }
  };
  const TEXT_KINDS = ["title", "subtitle", "heading", "paragraph", "pageno"];
  const isText = (el) => !!el && TEXT_KINDS.indexOf(el.kind) >= 0;
  const kindOf = (el) => KIND[el.kind] || KIND.paragraph;
  const sizeOf = (el, theme, pg) => el.size != null ? el.size
    : (theme && ModuleBBTH ? ModuleBBTH.resolveText(el, theme, pg).fontSize : kindOf(el).fs);

  function styleFor(el) {
    const s = { left: el.x + "%", top: el.y + "%", width: el.w + "%",
      opacity: (el.effect === "transparent" ? Math.min(el.opacity, 35) : el.opacity) / 100,
      transform: "rotate(" + (el.rotation || 0) + "deg)", zIndex: el.z || 1 };
    if (el.h != null) s.height = el.h + "%";
    return s;
  }

  function textStyle(el, ctx) {
    const m = kindOf(el);
    const theme = ctx && ctx.theme;
    const r = theme && ModuleBBTH ? ModuleBBTH.resolveText(el, theme, ctx.page) : null;
    const st = Object.assign(styleFor(el), r ? {
      fontFamily: r.fontFamily, fontSize: r.fontSize + "px", fontWeight: r.fontWeight,
      letterSpacing: r.letterSpacing, lineHeight: r.lineHeight, textAlign: r.align, color: r.color,
      fontStyle: r.italic ? "italic" : "normal",
      textDecoration: el.underline ? "underline" : "none", textWrap: "pretty"
    } : {
      fontFamily: (ctx && ctx.font) || m.ff, fontSize: sizeOf(el) + "px",
      fontWeight: el.bold == null ? m.fw : (el.bold ? 700 : 400),
      letterSpacing: m.ls, lineHeight: el.lineHeight || m.lh, textAlign: el.align || m.ta,
      color: el.color || "#333", fontStyle: (el.italic == null ? !!m.italic : !!el.italic) ? "italic" : "normal",
      textDecoration: el.underline ? "underline" : "none", textWrap: "pretty" });
    if (el.effect === "emboss") st.textShadow = "0 1px 0 rgba(255,255,255,.55), 0 -1px 1px rgba(0,0,0,.4)";
    if (el.effect === "metallic") { st.backgroundImage = "linear-gradient(135deg,#fff7df,#c9a24a 45%,#fff1c2 60%,#8a6516)"; st.WebkitBackgroundClip = "text"; st.backgroundClip = "text"; st.WebkitTextFillColor = "transparent"; st.color = "transparent"; }
    if (el.effect === "glass") st.color = "rgba(120,120,120,0.55)";
    // Preserve authored line breaks (e.g. a title page's "…\nWritten by …").
    if (el.whiteSpace) st.whiteSpace = el.whiteSpace;
    return st;
  }

  function renderEl(el, ctx) {
    const base = styleFor(el);
    const theme = ctx && ctx.theme;
    const TH = ModuleBBTH;
    const accent = theme && theme.colors ? theme.colors.accent : "#D4A83A";
    if (el.kind === "frame") {
      return h("div", { style: Object.assign({}, base, { border: "2px solid " + (el.color || accent),
        borderRadius: "4px", boxShadow: "inset 0 0 0 4px color-mix(in oklab," + accent + " 20%, transparent)" }) });
    }
    if (el.kind === "emblem") {
      let bg = el.color || (TH ? "radial-gradient(circle at 35% 28%," + TH.mix(accent, "#FFFFFF", 0.55) + "," + accent + " 55%," + TH.mix(accent, "#000000", 0.45) + ")"
        : "radial-gradient(circle at 35% 28%, #f7e3a1, #d4a83a 55%, #8a6516)");
      const st = Object.assign({}, base, { aspectRatio: "1 / 1", borderRadius: "50%", display: "grid",
        placeItems: "center", color: "#5b3a10", boxShadow: "0 4px 12px rgba(0,0,0,0.3)" });
      if (el.effect === "metallic") bg = "linear-gradient(135deg,#f5f5f5,#9aa0a6 42%,#e8eaed 60%,#6b7177)";
      if (el.effect === "glass") { bg = "rgba(255,255,255,0.16)"; st.backdropFilter = "blur(4px)"; st.border = "1px solid rgba(255,255,255,0.6)"; st.color = "rgba(255,255,255,0.85)"; }
      if (el.effect === "emboss") st.boxShadow = "inset 0 2px 4px rgba(255,255,255,.6), inset 0 -3px 6px rgba(0,0,0,.35), 0 3px 8px rgba(0,0,0,.3)";
      st.background = bg;
      return h("div", { style: st }, el.src ? h("img", { src: el.src, alt: el.label || "Book illustration", style: { width: "100%", height: "100%", objectFit: "cover", borderRadius: "50%" } }) : Svg(P.sparkle, 24));
    }
    if (el.kind === "shape") {
      return h("div", { style: Object.assign({}, base, { background: el.color || accent,
        borderRadius: el.shape === "circle" ? "50%" : (el.radius || 0) + "px" }) });
    }
    if (el.kind === "image") {
      const st = Object.assign({}, base, { borderRadius: "5px", overflow: "hidden",
        background: el.grad || (theme && TH ? TH.artGrad(theme, el.art || 0) : "linear-gradient(160deg,#94a3b8,#475569)"),
        boxShadow: "0 6px 16px rgba(0,0,0,0.18)" });
      if (el.effect === "glass") { st.filter = "saturate(0.7) brightness(1.1)"; st.opacity = (el.opacity / 100) * 0.8; }
      if (el.effect === "metallic") st.filter = "grayscale(0.5) contrast(1.1)";
      if (el.effect === "emboss") st.boxShadow = "0 6px 16px rgba(0,0,0,0.18), inset 0 2px 6px rgba(255,255,255,.3), inset 0 -4px 10px rgba(0,0,0,.3)";
      return h("div", { style: st }, el.src ? h("img", { src: el.src, style: { width: "100%", height: "100%", objectFit: "cover" } }) : null);
    }
    return h("div", { style: textStyle(el, ctx) }, el.text || "");
  }

  function Thumb(page, ctx) {
    const dims = (ctx && ctx.dims) || { w: 470, h: 630 };
    const maxW = 232, maxH = 150;
    const scale = Math.min(maxW / dims.w, maxH / dims.h);
    const c = Object.assign({}, ctx, { page: page });
    const bg = ModuleBBTH ? ModuleBBTH.pageBg(page, c.theme) : page.bg;
    return h("div", { style: { width: dims.w * scale, height: dims.h * scale, position: "relative" } },
      h("div", { style: { width: dims.w, height: dims.h, transform: "scale(" + scale + ")", transformOrigin: "top left",
          position: "absolute", borderRadius: 6, overflow: "hidden", background: bg, pointerEvents: "none" } },
        page.els.slice().sort((a, b) => (a.z || 1) - (b.z || 1)).map((e) => {
          const norm = Object.assign({}, e, { x: 0, y: 0, w: 100, h: e.h != null ? 100 : null });
          return h("div", { key: e.id, className: "el", style: { left: e.x + "%", top: e.y + "%",
            width: e.w + "%", height: e.h != null ? e.h + "%" : "auto", zIndex: e.z || 1, pointerEvents: "none" } },
            renderEl(norm, c));
        })
      )
    );
  }

  /* Fixed-position menu — used for page •••, character ••• and right-click.
     items: {label, icon, onSelect, destructive, disabled} | {separator} | {note} */
  function Menu({ x, y, items, onClose, align }) {
    const ref = useRef(null);
    const [pos, setPos] = useState(null);
    useLayoutEffect(() => {
      const n = ref.current; if (!n) return;
      const r = n.getBoundingClientRect();
      let left = align === "end" ? x - r.width : x, top = y;
      if (left + r.width > window.innerWidth - 8) left = window.innerWidth - r.width - 8;
      if (left < 8) left = 8;
      if (top + r.height > window.innerHeight - 8) top = Math.max(8, y - r.height - 26);
      setPos({ left: left, top: top });
    }, []);
    useEffect(() => {
      const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose(); };
      const onKey = (e) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } };
      document.addEventListener("mousedown", onDoc, true);
      window.addEventListener("keydown", onKey, true);
      return () => { document.removeEventListener("mousedown", onDoc, true); window.removeEventListener("keydown", onKey, true); };
    }, [onClose]);
    return h("div", { className: "bb-menu", ref: ref, role: "menu",
        style: { left: (pos ? pos.left : x), top: (pos ? pos.top : y), visibility: pos ? "visible" : "hidden" },
        onContextMenu: (e) => e.preventDefault() },
      items.filter(Boolean).map((it, i) => it.separator
        ? h("div", { key: i, className: "bb-menu-sep" })
        : it.note
          ? h("div", { key: i, className: "bb-menu-note" }, it.note)
          : h("button", { key: i, className: "bb-menu-item" + (it.destructive ? " danger" : ""), role: "menuitem",
              disabled: !!it.disabled, onClick: () => { onClose(); it.onSelect && it.onSelect(); } },
              h("span", { className: "bb-menu-ic" }, it.icon ? h(LucideIcon, { name: it.icon, size: 14 }) : null),
              h("span", null, it.label))));
  }

  export default { Svg, P, KIND, TEXT_KINDS, isText, kindOf, sizeOf, styleFor, textStyle, renderEl, Thumb, Menu };
