import React from 'react';
import ModuleBBColorPicker from './color-picker.js';
import ModuleBBSS from './story-settings.js';
import ModuleBBTH from './book-theme.js';
import ModuleBBSTY from './book-style.js';
import ModuleShadcnUiDesignSystem_6211ba from './ui.jsx';
import { Icon as LucideIcon, LUCIDE_PATHS } from './icons.js';
/* Blue Balloon — Book style panel: the book's fonts, colors and page layouts,
   read from the same bookTheme the New Storybook setup created. Global edits live
   in the theme; a selected element keeps its own formatting. ModuleBBSTY */

  const h = React.createElement;
  const { useState, useEffect } = React;
  const Icon = LucideIcon;
  const BBTH = ModuleBBTH;
  const BBSS = ModuleBBSS;
  const DS = ModuleShadcnUiDesignSystem_6211ba;
  const { Button } = DS;

  Object.assign(LUCIDE_PATHS, {
    "palette": '<path d="M12 22a1 1 0 0 1 0-20 10 9 0 0 1 10 9 5 5 0 0 1-5 5h-2.25a1.75 1.75 0 0 0-1.4 2.8l.3.4a1.75 1.75 0 0 1-1.4 2.8z"/><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "line-height": '<path d="M3 5h18"/><path d="M3 19h18"/><path d="M8 10h8"/><path d="M8 14h8"/>',
    "droplet": '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>',
    "rotate-ccw": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    "layout": '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/>',
    "wand": '<path d="m3 21 9-9"/><path d="M15 4V2"/><path d="M15 16v-2"/><path d="M8 9h2"/><path d="M20 9h2"/><path d="M17.8 11.8 19 13"/><path d="M17.8 6.2 19 5"/><path d="m12.2 6.2 1.2-1.2"/>'
  });

  /* ---- page layouts: positions only, so applying one never rewrites the story ---- */
  const LAYOUTS = [
    { id: "title", name: "Title page",
      pv: [[16, 14, 68, 8, "h"], [26, 28, 48, 4, "t"], [14, 40, 72, 42, "i"]],
      place: { frame: [4, 3, 92, 94], emblem: [39, 7, 22, null], title: [8, 26, 84, null, { align: "center" }],
        heading: [8, 26, 84, null, { align: "center" }], subtitle: [14, 42, 72, null, { align: "center" }],
        image: [14, 52, 72, 32], paragraph: [14, 87, 72, null, { align: "center" }], pageno: [8, 6, 18, null] } },
    { id: "chapter", name: "Chapter",
      pv: [[20, 30, 60, 8, "h"], [30, 44, 40, 4, "t"], [26, 56, 48, 26, "i"]],
      place: { title: [10, 28, 80, null, { align: "center" }], heading: [12, 32, 76, null, { align: "center" }],
        subtitle: [18, 46, 64, null, { align: "center" }], image: [26, 56, 48, 24],
        paragraph: [14, 84, 72, null, { align: "center" }], pageno: [8, 6, 18, null] } },
    { id: "text", name: "Text page",
      pv: [[12, 12, 54, 7, "h"], [12, 26, 76, 4, "t"], [12, 35, 76, 4, "t"], [12, 44, 66, 4, "t"], [12, 53, 72, 4, "t"], [24, 70, 52, 18, "i"]],
      place: { title: [10, 10, 80, null], heading: [10, 12, 80, null], subtitle: [10, 20, 80, null],
        paragraph: [10, 25, 80, null], image: [22, 74, 56, 18], pageno: [8, 6, 18, null] } },
    { id: "imagetext", name: "Image + text",
      pv: [[12, 10, 50, 7, "h"], [12, 22, 76, 38, "i"], [12, 66, 76, 4, "t"], [12, 75, 68, 4, "t"], [12, 84, 58, 4, "t"]],
      place: { title: [10, 8, 80, null], heading: [10, 10, 80, null], subtitle: [10, 16, 80, null],
        image: [13, 19, 74, 38], paragraph: [12, 62, 76, null], pageno: [8, 6, 18, null] } },
    { id: "full", name: "Full art",
      pv: [[0, 0, 100, 100, "i"], [12, 64, 60, 7, "h"], [12, 80, 70, 4, "t"]],
      place: { image: [0, 0, 100, 100, { z: 1 }], title: [8, 56, 84, null, { z: 4, colorRole: "secondary" }],
        heading: [8, 64, 84, null, { z: 4, colorRole: "secondary" }],
        subtitle: [8, 71, 84, null, { z: 4, colorRole: "secondary" }],
        paragraph: [8, 79, 84, null, { z: 4, colorRole: "secondary" }],
        pageno: [8, 6, 18, null, { z: 4, colorRole: "secondary" }] } },
    { id: "minimal", name: "Minimal",
      pv: [[14, 26, 52, 7, "h"], [14, 42, 44, 4, "t"], [34, 64, 34, 22, "i"]],
      place: { title: [12, 24, 76, null], heading: [12, 26, 76, null], subtitle: [12, 34, 76, null],
        paragraph: [12, 40, 64, null], image: [32, 64, 36, 20], pageno: [8, 6, 18, null] } }
  ];
  const layoutOf = (pg) => pg && pg.layout ? pg.layout : (pg && pg.kind === "cover" ? "title" : "imagetext");

  /* Reposition the page's existing elements into the chosen layout. */
  function applyLayout(pg, id) {
    const L = LAYOUTS.find((l) => l.id === id) || LAYOUTS[3];
    const seen = {};
    const els = (pg.els || []).map((e) => {
      const spec = L.place[e.kind];
      if (!spec) return e;
      const n = seen[e.kind] = (seen[e.kind] || 0) + 1;
      const step = (spec[3] != null ? spec[3] : 9) + 4;
      const next = Object.assign({}, e, { x: spec[0], y: spec[1] + (n - 1) * step, w: spec[2] });
      if (spec[3] != null) next.h = spec[3]; else if (e.kind !== "image" && e.kind !== "frame") next.h = null;
      if (spec[4]) Object.assign(next, spec[4]);
      else if (e.kind === "heading" || e.kind === "paragraph") { if (!e.align) next.align = null; }
      return next;
    });
    return Object.assign({}, pg, { layout: id, els: els });
  }

  function LayoutPreview({ layout }) {
    return h("div", { className: "bs-laypv" }, layout.pv.map((b, i) =>
      h("span", { key: i, className: b[4], style: { left: b[0] + "%", top: b[1] + "%", width: b[2] + "%", height: b[3] + "%" } })));
  }

  function Stepper({ value, min, max, step, fmt, onChange }) {
    const dec = () => onChange(Math.max(min, Math.round((value - step) * 100) / 100));
    const inc = () => onChange(Math.min(max, Math.round((value + step) * 100) / 100));
    return h("div", { className: "bs-step" },
      h("button", { type: "button", onClick: dec, disabled: value <= min, "aria-label": "Decrease" }, "\u2212"),
      h("span", { className: "v" }, fmt ? fmt(value) : value),
      h("button", { type: "button", onClick: inc, disabled: value >= max, "aria-label": "Increase" }, "+"));
  }
  const field = (label, ctl) => h("div", { className: "bs-f" }, h("span", { className: "bs-f-l" }, label), ctl);
  const select = (value, opts, onChange) => h("select", { className: "bs-sel", value: value, onChange: (e) => onChange(e.target.value) },
    opts.map((o) => h("option", { key: String(o.v != null ? o.v : o), value: o.v != null ? o.v : o }, o.label || o)));

  /* ---- typography ---- */
  function TypeSection({ theme, onTheme, selEl, onPromote, onClearEl }) {
    const [open, setOpen] = useState(null);
    const setRole = (key, patch) => onTheme(Object.assign({}, theme, { typography: Object.assign({}, theme.typography,
      { [key]: Object.assign({}, theme.typography[key], patch) }) }));
    return h("div", null, BBTH.TYPE_ROLES.map((r) => {
      const t = theme.typography[r.key];
      const isOpen = open === r.key;
      const pvSize = Math.max(13, Math.min(r.key === "heading" ? 23 : 17, t.fontSize));
      return h("div", { className: "bs-row", key: r.key, "data-open": isOpen },
        h("button", { className: "bs-row-h", onClick: () => setOpen(isOpen ? null : r.key) },
          h("div", { className: "bs-row-top" },
            h("span", { className: "bs-role" }, r.label),
            h("span", { className: "bs-chev" }, h(Icon, { name: "chevron-down", size: 14 }))),
          h("div", { className: "bs-prev", style: { fontFamily: BBTH.FONT_STACKS[t.fontFamily] || t.fontFamily,
            fontSize: pvSize, fontWeight: t.fontWeight, fontStyle: t.italic ? "italic" : "normal",
            letterSpacing: (t.letterSpacing || 0) + "em" } }, r.sample),
          h("div", { className: "bs-font" }, t.fontFamily + " \u00b7 " + t.fontSize + " \u00b7 " + BBTH.weightLabel(t.fontWeight))),
        isOpen ? h("div", { className: "bs-ctl" },
          field("Font", select(t.fontFamily, BBTH.FONTS, (v) => setRole(r.key, { fontFamily: v }))),
          field("Size", h(Stepper, { value: t.fontSize, min: 8, max: 96, step: 1, onChange: (v) => setRole(r.key, { fontSize: v }) })),
          field("Weight", select(t.fontWeight, BBTH.WEIGHTS.map((w) => ({ v: w.v, label: w.label })), (v) => setRole(r.key, { fontWeight: +v }))),
          field("Line height", h(Stepper, { value: t.lineHeight, min: 0.9, max: 2.4, step: 0.05, fmt: (v) => v.toFixed(2), onChange: (v) => setRole(r.key, { lineHeight: v }) })),
          field("Letter spacing", h(Stepper, { value: t.letterSpacing || 0, min: -0.05, max: 0.2, step: 0.01, fmt: (v) => (v > 0 ? "+" : "") + v.toFixed(2) + "em", onChange: (v) => setRole(r.key, { letterSpacing: v }) })),
          r.key !== "body" ? field("Style", h("div", { className: "bs-step" },
            h("button", { type: "button", onClick: () => setRole(r.key, { italic: false }), style: { flex: 1, width: "auto", fontWeight: t.italic ? 400 : 600 } }, "Regular"),
            h("button", { type: "button", onClick: () => setRole(r.key, { italic: true }), style: { flex: 1, width: "auto", fontStyle: "italic", fontWeight: t.italic ? 600 : 400 } }, "Italic"))) : null,
          selEl && BBTH.resolveText(selEl, theme).role === r.key && BBTH.hasOverrides(selEl)
            ? h("button", { className: "bs-promote", onClick: () => onPromote(selEl, r.key) },
                h(Icon, { name: "wand", size: 13 }), "Use selected element for all " + r.label.toLowerCase() + "s")
            : null
        ) : null);
    }));
  }

  /* ---- colors ---- */
  function ColorSection({ theme, onTheme, selEl, onElColor, onPageColor, pageName }) {
    const [editing, setEditing] = useState(null);   // role key
    const [draft, setDraft] = useState("");
    const [scope, setScope] = useState("book");
    const [picker, setPicker] = useState(false);
    useEffect(() => { if (!selEl && scope === "element") setScope("book"); }, [selEl]);
    const openRole = (key) => {
      if (editing === key) { setEditing(null); return; }
      setEditing(key); setDraft(theme.colors[key]); setScope(selEl ? "element" : "book"); setPicker(false);
    };
    const save = () => {
      const hex = BBTH.isHex(draft) ? BBTH.norm(draft) : theme.colors[editing];
      if (scope === "element" && selEl) onElColor(hex);
      else if (scope === "page") onPageColor(editing, hex);
      else onTheme(Object.assign({}, theme, { colors: Object.assign({}, theme.colors, { [editing]: hex }) }));
      setEditing(null);
    };
    const radio = (id, label, sub, disabled) => h("button", { key: id, className: "bs-radio", "data-on": scope === id,
      disabled: !!disabled, onClick: () => setScope(id) }, h("i"), h("span", null, label,
      sub ? h("span", { style: { color: "var(--muted-foreground)" } }, " \u00b7 " + sub) : null));
    const label = editing ? (BBTH.COLOR_ROLES.find((c) => c.key === editing) || {}).label : "";
    return h("div", null,
      h("div", { className: "bs-sw-list" }, BBTH.COLOR_ROLES.map((c) => {
        const hex = theme.colors[c.key];
        return h("button", { className: "bs-swr", key: c.key, "data-active": editing === c.key, onClick: () => openRole(c.key),
          title: c.label + " \u00b7 " + hex },
          h("span", { className: "bs-dot", style: { background: hex } }),
          h("span", { className: "col" },
            h("span", { className: "nm" }, c.label),
            h("span", { className: "rl" }, BBTH.nameColor(hex) + " \u00b7 " + c.hint)),
          h("span", { className: "hx" }, hex));
      })),
      editing ? h("div", { className: "bs-edit" },
        h("div", { className: "bs-edit-h" },
          h("span", null, "Edit " + label.toLowerCase() + " color"),
          h("button", { className: "set-x", title: "Cancel", onClick: () => setEditing(null) }, h(Icon, { name: "x", size: 13 }))),
        h("div", { className: "bs-edit-row" },
          h("span", { className: "bs-chip", style: { background: BBTH.isHex(draft) ? draft : theme.colors[editing] } }),
          h("input", { className: "bs-hex", value: draft, spellCheck: false, "aria-label": "Hex value",
            onChange: (e) => setDraft(e.target.value),
            onKeyDown: (e) => { e.stopPropagation(); if (e.key === "Enter") save(); } }),
          h("button", { className: "set-link", onClick: () => setPicker(true) }, "Pick\u2026")),
        h("div", { className: "bs-scope" },
          h("div", { className: "bs-scope-k" }, "Apply to"),
          radio("element", "This element only", selEl ? selEl.label : "nothing selected", !selEl),
          radio("page", "Current page", pageName),
          radio("book", "Entire book theme")),
        h("div", { className: "bs-edit-foot" },
          h(Button, { variant: "outline", size: "sm", onClick: () => setEditing(null) }, "Cancel"),
          h(Button, { size: "sm", onClick: save }, "Save")),
        picker ? h(ModuleBBColorPicker, { open: true, initial: BBTH.isHex(draft) ? draft : theme.colors[editing],
          title: "Edit " + label.toLowerCase() + " color", onClose: () => setPicker(false),
          onPick: (hex) => { setDraft(hex.toUpperCase()); setPicker(false); } }) : null
      ) : null);
  }

  /* ---- panel ---- */
  function BookStylePanel(props) {
    const { theme, settings, page, pages, selEl, onTheme, onElColor, onPageColor, onPromote, onClearEl,
      onLayout, onLayoutAll, onOpenSettings } = props;
    const style = (BBSS.STYLES.find((s) => s.name === settings.style) || BBSS.STYLES[0]);
    const cur = layoutOf(page);
    const similar = pages.filter((p) => p.id !== page.id && p.kind === page.kind).length;
    const sec = (k, note, body) => h("div", { className: "bs-sec" },
      h("div", { className: "bs-k" }, k, note ? h("span", { className: "n" }, note) : null), body);

    return h("div", { className: "panel-body bs-body" },
      selEl ? h("div", { className: "bs-selected" },
        h("span", { className: "ic" }, h(Icon, { name: "square-mouse-pointer", size: 15 })),
        h("div", { style: { minWidth: 0 } },
          h("div", { className: "t" }, selEl.label + " selected"),
          h("div", { className: "s" }, BBTH.hasOverrides(selEl)
            ? "This element has its own formatting, so it ignores parts of the book style."
            : "It follows the book style below. Format it on the canvas to override just this element."),
          BBTH.hasOverrides(selEl) ? h("button", { className: "bs-link", onClick: onClearEl },
            h(Icon, { name: "rotate-ccw", size: 12 }), "Reset to book style") : null)) : null,

      sec("Book style", null, h("div", null,
        h("div", { className: "bs-card bs-style" },
          h("div", { className: "bs-scene" }, h(BBSS.StyleScene, { s: style })),
          h("div", { style: { minWidth: 0, flex: 1 } },
            h("div", { className: "bs-style-nm" }, style.name),
            h("div", { className: "bs-style-s" }, settings.size + " \u00b7 " + (settings.orientation === "Horizontal" ? "Landscape" : "Portrait") + " \u00b7 " + settings.length))),
        h("button", { className: "bs-link", onClick: onOpenSettings },
          "Illustration style and page setup", h(Icon, { name: "chevron-right", size: 13 })))),

      sec("Typography", "From setup", h(TypeSection, { theme, onTheme, selEl, onPromote, onClearEl })),

      sec("Colors", "Book palette", h(ColorSection, { theme, onTheme, selEl, onElColor, onPageColor, pageName: page.name })),

      sec("Page style", page.name, h("div", null,
        h("div", { className: "bs-lay" }, LAYOUTS.map((l) =>
          h("button", { className: "bs-laycard", key: l.id, "data-active": cur === l.id, title: l.name,
            onClick: () => onLayout(l.id) },
            h(LayoutPreview, { layout: l }),
            h("span", { className: "bs-layname" }, l.name)))),
        h("div", { className: "bs-applyrow" },
          h(Button, { variant: "outline", size: "sm", disabled: !similar, onClick: () => onLayoutAll(cur) },
            h(Icon, { name: "layers", size: 13 }), similar ? "Apply to " + similar + " similar page" + (similar === 1 ? "" : "s") : "No similar pages")),
        h("div", { className: "bs-note" }, "Layouts move what is already on the page \u2014 your words and artwork are kept."))),

      h("div", { className: "bs-note", style: { padding: "2px 1px 8px" } },
        "Fonts and colors here apply to the whole book. Selected text keeps any formatting you gave it from the canvas toolbar.")
    );
  }

  export default { BookStylePanel, LAYOUTS, applyLayout, layoutOf };

