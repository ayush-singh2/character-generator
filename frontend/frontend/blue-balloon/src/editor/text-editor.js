import React from 'react';
import ModuleBBTH from './book-theme.js';
import ModuleBBR from './render.js';
import { Icon as LucideIcon, LUCIDE_PATHS } from './icons.js';
/* BB artists — canvas text editing: inline editor + contextual formatting toolbar */

  const h = React.createElement;
  const { useRef, useEffect, useState } = React;

  /* Inline editor. Renders the element as an editable box using the very same
     type styles, so nothing shifts when editing starts. */
  function InlineText({ el, style, onCommit, onFormat }) {
    const ref = useRef(null);
    useEffect(() => {
      const n = ref.current; if (!n) return;
      n.textContent = el.text || "";
      n.focus();
      const r = document.createRange(); r.selectNodeContents(n);
      const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
    }, []);
    const commit = () => onCommit(ref.current ? ref.current.textContent : "");
    return h("div", { ref: ref, className: "txt-edit", contentEditable: true, spellCheck: true,
      suppressContentEditableWarning: true, style: style,
      "data-ph": "Type here…",
      onMouseDown: (e) => e.stopPropagation(),
      onBlur: commit,
      onKeyDown: (e) => {
        e.stopPropagation();
        const mod = e.metaKey || e.ctrlKey;
        if (mod && "biu".indexOf(e.key.toLowerCase()) >= 0) {
          e.preventDefault();
          onFormat({ b: "bold", i: "italic", u: "underline" }[e.key.toLowerCase()]);
          return;
        }
        if (e.key === "Escape") { e.preventDefault(); commit(); return; }
        if (e.key === "Enter" && el.kind !== "paragraph" && !e.shiftKey) { e.preventDefault(); commit(); }
      } });
  }

  /* Compact toolbar, only on screen while a text element is selected or edited.
     It shows what the element inherits from the book style, and writes a local
     override only for the control the user actually touches. */
  function TextToolbar({ el, rect, theme, page, onPatch }) {
    const BBR = ModuleBBR;
    const BBTH = ModuleBBTH;
    const Icon = LucideIcon;
    const [pop, setPop] = useState(null);
    const wrapRef = useRef(null);
    useEffect(() => {
      if (!pop) return;
      const onDoc = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setPop(null); };
      document.addEventListener("mousedown", onDoc, true);
      return () => document.removeEventListener("mousedown", onDoc, true);
    }, [pop]);

    const r = BBTH.resolveText(el, theme, page);
    const size = r.fontSize;
    const bold = el.bold == null ? r.fontWeight >= 600 : !!el.bold;
    const italic = el.italic == null ? !!r.italic : !!el.italic;
    const align = r.align;
    const step = size >= 24 ? 2 : 1;
    const setSize = (v) => onPatch({ size: Math.max(8, Math.min(96, Math.round(v * 10) / 10)) });
    const btn = (icon, on, label, onClick) => h("button", { key: label, className: "tt-b", "data-on": !!on,
      title: label, "aria-label": label,
      onMouseDown: (e) => e.preventDefault(), onClick: onClick }, h(Icon, { name: icon, size: 15 }));

    const w = 442, gap = 12;
    let left = rect.left + rect.width / 2 - w / 2;
    left = Math.max(12, Math.min(window.innerWidth - w - 12, left));
    const above = rect.top > 96;
    const top = above ? rect.top - 40 - gap : rect.bottom + gap;
    const swatches = BBTH.COLOR_ROLES.map((c) => ({ key: c.key, label: c.label, hex: theme.colors[c.key] }));

    return h("div", { className: "tt", ref: wrapRef, style: { left: left, top: top, width: w },
        onMouseDown: (e) => e.stopPropagation() },
      h("select", { className: "tt-sel", value: el.font || "", title: "Font", "aria-label": "Font",
          onMouseDown: (e) => e.stopPropagation(), onChange: (e) => onPatch({ font: e.target.value || null }) },
        h("option", { value: "" }, "Book · " + r.family),
        BBTH.FONTS.map((f) => h("option", { key: f, value: f }, f))),
      h("span", { className: "tt-sep" }),
      btn("bold", bold, "Bold", () => onPatch({ bold: !bold })),
      btn("italic", italic, "Italic", () => onPatch({ italic: !italic })),
      btn("underline", !!el.underline, "Underline", () => onPatch({ underline: !el.underline })),
      h("span", { className: "tt-sep" }),
      h("button", { className: "tt-b", title: "Decrease text size", "aria-label": "Decrease text size",
        onMouseDown: (e) => e.preventDefault(), onClick: () => setSize(size - step) }, "A\u2212"),
      h("span", { className: "tt-size", title: "Text size" }, Math.round(size)),
      h("button", { className: "tt-b", title: "Increase text size", "aria-label": "Increase text size",
        onMouseDown: (e) => e.preventDefault(), onClick: () => setSize(size + step) }, "A+"),
      h("span", { className: "tt-sep" }),
      h("span", { className: "tt-wrap" },
        h("button", { className: "tt-b", "data-on": pop === "color", title: "Text color", "aria-label": "Text color",
            onMouseDown: (e) => e.preventDefault(), onClick: () => setPop(pop === "color" ? null : "color") },
          h("span", { style: { width: 14, height: 14, borderRadius: 4, background: r.color, border: "1px solid rgba(20,40,80,.2)" } })),
        pop === "color" ? h("div", { className: "tt-pop" },
          h("div", { className: "tt-pop-k" }, "Book colors"),
          h("div", { className: "tt-cols" }, swatches.map((s) =>
            h("button", { key: s.key, className: "tt-col", "data-on": (el.color || "").toUpperCase() === String(s.hex).toUpperCase(),
              title: s.label + " · " + s.hex, style: { background: s.hex },
              onClick: () => { onPatch({ color: s.hex, effect: "none" }); setPop(null); } }))),
          h("button", { className: "tt-col-nm", style: { border: 0, background: "transparent", font: "inherit", cursor: "pointer", padding: 0, color: "var(--primary)" },
            onClick: () => { onPatch({ color: null }); setPop(null); } }, "Use the book color")) : null),
      h("select", { className: "tt-sel", style: { maxWidth: 66 }, value: el.lineHeight == null ? "" : String(el.lineHeight),
          title: "Line height", "aria-label": "Line height",
          onMouseDown: (e) => e.stopPropagation(),
          onChange: (e) => onPatch({ lineHeight: e.target.value === "" ? null : +e.target.value }) },
        h("option", { value: "" }, "↕ Book"),
        [1, 1.15, 1.3, 1.5, 1.7, 2].map((v) => h("option", { key: v, value: String(v) }, "↕ " + v.toFixed(2)))),
      h("span", { className: "tt-sep" }),
      btn("align-left", align === "left", "Align left", () => onPatch({ align: "left" })),
      btn("align-center", align === "center", "Align center", () => onPatch({ align: "center" })),
      btn("align-right", align === "right", "Align right", () => onPatch({ align: "right" })),
      BBTH.hasOverrides(el) ? h(React.Fragment, null,
        h("span", { className: "tt-sep" }),
        h("button", { className: "tt-b reset", title: "Drop this element’s own formatting and follow the book style",
          onMouseDown: (e) => e.preventDefault(), onClick: () => onPatch(BBTH.clearOverrides()) },
          h(Icon, { name: "rotate-ccw", size: 13 }), "Reset")) : null
    );
  }

  export default { InlineText, TextToolbar };

