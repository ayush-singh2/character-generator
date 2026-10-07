import React from 'react';
import ModuleBBSS from './story-settings.js';
import { Icon as LucideIcon, LUCIDE_PATHS } from './icons.js';
/* Blue Balloon — story setup data + controls shared by New Project and the workspace
   Story settings panel. Exposes ModuleBBSS. Styles live in bb-story-settings.css. */

  const e = React.createElement;
  const { useState, useEffect } = React;
  const Icon = LucideIcon;

  const PAGE_SIZES = [
    { name: "A3", w: 297, h: 420, label: "297 × 420 mm" },
    { name: "A4", w: 210, h: 297, label: "210 × 297 mm" },
    { name: "A5", w: 148, h: 210, label: "148 × 210 mm" },
    { name: "Letter", w: 216, h: 279, label: "8.5 × 11 in" },
    { name: "Square", w: 210, h: 210, label: "210 × 210 mm" }
  ];
  /* Swap `img` for a real sample illustration per style when available; the CSS scene is a placeholder. */
  const STYLES = [
    { name: "Storybook Illustration", desc: "Warm, hand-drawn picture-book feel", cls: "story", pal: { sky: "#f6d9b0", sun: "#f3b85e", hill: "#7a9a4a", hill2: "#4f7a3a", tree: "#3e6b3a", trunk: "#6b4a2e", fox: "#d4703f" } },
    { name: "Watercolor", desc: "Soft washes and bleeding edges", cls: "watercolor", pal: { sky: "#dce9f3", sun: "#f7d9a0", hill: "#9cc0a6", hill2: "#6f9c84", tree: "#5c8a6a", trunk: "#8a6a50", fox: "#e29a70" } },
    { name: "Flat", desc: "Clean simplified shapes, no shading", cls: "flat", pal: { sky: "#8fc3e6", sun: "#ffd166", hill: "#6fbf73", hill2: "#3f9a5a", tree: "#2f7a4a", trunk: "#5a3e2b", fox: "#ef8354" } },
    { name: "Vector", desc: "Crisp geometric shapes with bold outlines", cls: "vector", pal: { sky: "#f2f6fb", sun: "#f4c06a", hill: "#5b8fd6", hill2: "#3e6fb0", tree: "#3e8f8a", trunk: "#2a2622", fox: "#2f5fa8" } },
    { name: "Digital Painting", desc: "Rich light, depth and atmosphere", cls: "paint", pal: { sky: "linear-gradient(180deg,#2b2a5e,#b25a6a 70%,#f2a35e)", sun: "#ffe4a8", hill: "#3a2d4a", hill2: "#221a33", tree: "#1b1526", trunk: "#1b1526", fox: "#e0764a" } },
    { name: "Line Art", desc: "Ink outlines on white, no color", cls: "line", pal: { sky: "#fff", sun: "#fff", hill: "#fff", hill2: "#fff", tree: "#fff", trunk: "#fff", fox: "#fff" } },
    { name: "3D Render", desc: "Dimensional, glossy characters and scenes", cls: "render", pal: { sky: "#cfe0f5", sun: "#ffd98a", hill: "#8dc78f", hill2: "#5fa86a", tree: "#4d9a5e", trunk: "#7a5a3e", fox: "#f08a5d" } }
  ];
  const LENGTHS = ["16 pages", "24 pages", "32 pages", "48 pages", "64 pages"];
  const LENGTH_HINT = { "16 pages": "Short read", "24 pages": "Bedtime story", "32 pages": "Classic picture book", "48 pages": "Longer tale", "64 pages": "Chapter-style" };

  function StyleScene({ s }) {
    if (s.img) return e("img", { className: "scene", src: s.img, alt: s.name + " sample", style: { objectFit: "cover", width: "100%" } });
    const st = {}; Object.keys(s.pal).forEach((k) => st["--" + k] = s.pal[k]); st.background = s.pal.sky;
    return e("div", { className: "scene " + s.cls, style: st, "aria-hidden": true },
      e("span", { className: "sun" }), e("span", { className: "hill" }), e("span", { className: "hill b" }),
      e("span", { className: "tree" }), e("span", { className: "fox" }));
  }
  function SizePreview({ sz, landscape }) {
    const w = landscape ? sz.h : sz.w, h = landscape ? sz.w : sz.h; const k = 48 / Math.max(w, h);
    return e("i", { style: { width: Math.round(w * k), height: Math.round(h * k) } });
  }
  const landLabel = (sz) => sz.label.replace(/^([\d.]+) × ([\d.]+)/, "$2 × $1");

  function OrientationToggle({ value, onChange }) {
    const landscape = value === "Horizontal";
    return e("div", { className: "oseg", role: "group", "aria-label": "Orientation" },
      e("button", { type: "button", "data-active": !landscape, title: "Portrait", "aria-label": "Portrait", onClick: () => onChange("Vertical") }, e("i", { style: { width: 11, height: 15 } })),
      e("button", { type: "button", "data-active": landscape, title: "Landscape", "aria-label": "Landscape", onClick: () => onChange("Horizontal") }, e("i", { style: { width: 15, height: 11 } })));
  }
  function SizeGrid({ value, orientation, onChange }) {
    const landscape = orientation === "Horizontal";
    return e("div", { className: "sizes" }, PAGE_SIZES.map((sz) =>
      e("button", { type: "button", key: sz.name, className: "size", "data-active": value === sz.name, "aria-pressed": value === sz.name, onClick: () => onChange(sz.name) },
        e("div", { className: "pv" }, e(SizePreview, { sz: sz, landscape: landscape })),
        e("div", { className: "nm" }, sz.name),
        e("div", { className: "dm" }, landscape ? landLabel(sz) : sz.label))));
  }
  function LengthGrid({ value, onChange }) {
    return e("div", { className: "lengths" }, LENGTHS.map((l) =>
      e("button", { type: "button", key: l, className: "len", "data-active": value === l, "aria-pressed": value === l, onClick: () => onChange(l) },
        l, e("small", null, LENGTH_HINT[l]))));
  }
  /* Book length: preset dropdown + custom count. Books bind in two-sided sheets,
     so any custom value snaps to the nearest even number. */
  const MIN_PAGES = 8, MAX_PAGES = 200;
  const pagesOf = (v) => { const n = parseInt(String(v == null ? "" : v).replace(/[^0-9]/g, ""), 10); return n > 0 ? n : 32; };
  const evenPages = (n) => Math.max(MIN_PAGES, Math.min(MAX_PAGES, Math.round((Number(n) || 32) / 2) * 2));
  const lengthLabel = (n) => n + " pages";
  function LengthPicker({ value, onChange }) {
    const n = pagesOf(value);
    const isPreset = LENGTHS.indexOf(lengthLabel(n)) >= 0;
    const [custom, setCustom] = useState(!isPreset);
    const [draft, setDraft] = useState(String(n));
    const commit = (raw) => { const v = evenPages(raw); setDraft(String(v)); onChange(lengthLabel(v)); };
    useEffect(() => {
      const p = pagesOf(value);
      setDraft(String(p));
      if (LENGTHS.indexOf(lengthLabel(p)) < 0) setCustom(true);
      if (p % 2 !== 0) onChange(lengthLabel(evenPages(p)));
    }, [value]);
    const onSelect = (ev) => {
      const v = ev.target.value;
      if (v === "__custom") { setCustom(true); commit(pagesOf(draft)); return; }
      setCustom(false); onChange(v);
    };
    return e("div", { className: "lenpick" },
      e("div", { className: "lenrow" },
        e("select", { className: "len-select", "aria-label": "Book length", value: custom ? "__custom" : lengthLabel(n), onChange: onSelect },
          LENGTHS.map((l) => e("option", { key: l, value: l }, l + " \u00b7 " + LENGTH_HINT[l])),
          e("option", { value: "__custom" }, "Custom length\u2026")),
        custom ? e("div", { className: "lenstep" },
          e("button", { type: "button", "aria-label": "Two pages fewer", disabled: n <= MIN_PAGES, onClick: () => commit(evenPages(pagesOf(draft)) - 2) }, "\u2212"),
          e("input", { type: "number", min: MIN_PAGES, max: MAX_PAGES, step: 2, value: draft, "aria-label": "Page count",
            onChange: (ev) => setDraft(ev.target.value),
            onBlur: () => commit(draft),
            onKeyDown: (ev) => { if (ev.key === "Enter") { ev.preventDefault(); commit(draft); if (ev.target.blur) ev.target.blur(); } } }),
          e("span", { className: "lenunit" }, "pages"),
          e("button", { type: "button", "aria-label": "Two pages more", disabled: n >= MAX_PAGES, onClick: () => commit(evenPages(pagesOf(draft)) + 2) }, "+")) : null),
      e("p", { className: "lenhint" }, custom
        ? "Even counts only \u2014 " + n + " pages is " + (n / 2) + " printed sheets. Odd numbers round to the nearest even."
        : (LENGTH_HINT[lengthLabel(n)] || "")));
  }
  function StyleGrid({ value, onChange }) {
    return e("div", { className: "stylegrid" }, STYLES.map((s) =>
      e("button", { type: "button", key: s.name, className: "scard", "data-active": value === s.name, "aria-pressed": value === s.name, title: s.desc, onClick: () => onChange(s.name) },
        e(StyleScene, { s: s }),
        e("div", { className: "sc-body" },
          e("div", null, e("p", { className: "sc-name" }, s.name), e("p", { className: "sc-desc" }, s.desc)),
          e("span", { className: "sc-check" }, e(Icon, { name: "check", size: 12 }))))));
  }
  function Swatches({ palette, onEdit, onRemove, onAdd }) {
    return e("div", { className: "swatches" },
      palette.map((hex, i) => e("span", { className: "swatch", key: i, onClick: () => onEdit(i, hex), title: "Edit color" },
        e("span", { className: "dot", style: { background: hex } }), hex,
        e("span", { className: "rm", title: "Remove", onClick: (ev) => { ev.stopPropagation(); onRemove(i); } }, e(Icon, { name: "x", size: 12 })))),
      e("button", { type: "button", className: "add-swatch", onClick: onAdd }, e(Icon, { name: "plus", size: 13 }), "Add color"));
  }
  const STYLE_NAMES = STYLES.map((s) => s.name);
  /* older drafts stored a combined "Flat Vector" style */
  function normalizeStyle(v) {
    if (v && STYLE_NAMES.indexOf(v) >= 0) return v;
    if (v && /flat/i.test(v)) return "Flat";
    if (v && /vector/i.test(v)) return "Vector";
    return STYLE_NAMES[0];
  }

  export default { PAGE_SIZES, STYLES, STYLE_NAMES, LENGTHS, LENGTH_HINT, StyleScene, SizePreview,
    OrientationToggle, SizeGrid, LengthGrid, LengthPicker, StyleGrid, Swatches, normalizeStyle, landLabel,
    pagesOf, evenPages, lengthLabel, MIN_PAGES, MAX_PAGES };

