import { TEAM_CANDIDATES, DEFAULT_CAST, INNER_CONTENT } from '../data/sample-book';
import { aiService } from '../services/ai';
import { storage as localStorage } from '../services/storage';
import React from 'react';
import ModuleBBSS from './story-settings.js';
import ModuleBBTH from './book-theme.js';
import ModuleBBR from './render.js';
import ModuleBBTXT from './text-editor.js';
import ModuleBBPG from './pages-panel.js';
import ModuleBBSTY from './book-style.js';
import ModuleBBSCN from './scene-builder.js';
import ModuleBBAI from './assistant.js';
import ModuleBBPV from './preview.js';
import ModuleBBMS from './manuscript.js';
import ModuleBBCV from './cover.js';
import ModuleShadcnUiDesignSystem_6211ba from './ui.jsx';
import { Icon as LucideIcon, LUCIDE_PATHS } from './icons.js';
import BBWS from './characters.js';
import { readImage } from '../services/storage';
import { backendEnabled, saveDraft } from '../services/projects';
import { runGeneration, waitForJob, assetUrl } from '../services/generation';
import { uploadManuscript, pdfHref, correctPage, chatPage, revertPageChat, listPages } from '../services/book';
import { ExportDialog, ShareDialog } from '../components/ExportDialogs.jsx';
import { useCanvasScale } from '../hooks/useCanvasScale.js';
/* BB artists — Storybook workspace editor */

  const DS = ModuleShadcnUiDesignSystem_6211ba;
  const { Button, AlertDialog, Dialog, DialogHeader, DialogTitle, DialogDescription, DialogFooter, Checkbox } = DS;
  const LIcon = LucideIcon;
  const BBR = ModuleBBR, BBTXT = ModuleBBTXT, BBPG = ModuleBBPG;
  const BBTH = ModuleBBTH, BBSTY = ModuleBBSTY, BBSCN = ModuleBBSCN, BBAI = ModuleBBAI, BBPV = ModuleBBPV;
  const BBMS = ModuleBBMS, BBCV = ModuleBBCV;
  const h = React.createElement;
  const { useState, useRef, useEffect, useLayoutEffect } = React;

  // ---- option lists (shared with the New Project setup) ----
  const BBSS = ModuleBBSS;
  const FONTS = ["Geist", "Geist Mono", "Lora", "Inter", "Merriweather", "Playfair Display"];
  const ROLES = ["Heading", "Subheading", "Body Text", "Caption", "Quote"];

  const TEAM_COLORS = ["#6366f1", "#0e7490", "#b45309", "#be185d", "#15803d", "#7c3aed", "#0891b2", "#c2410c"];
  const initials = (n) => n.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();

  const FONT_STACKS = {
    "Geist": "'Geist', system-ui, sans-serif",
    "Geist Mono": "'Geist Mono', ui-monospace, monospace",
    "Inter": "'Inter', system-ui, sans-serif",
    "Lora": "'Lora', Georgia, serif",
    "Merriweather": "'Merriweather', Georgia, serif",
    "Playfair Display": "'Playfair Display', Georgia, serif"
  };

  // ---- tiny inline-svg helper ----
  function Svg(inner, size) {
    return h("svg", { width: size || 16, height: size || 16, viewBox: "0 0 24 24", fill: "none",
      stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round",
      dangerouslySetInnerHTML: { __html: inner } });
  }
  const PATHS = {
    copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    front: '<path d="M12 10V3"/><path d="m8 6 4-4 4 4"/><path d="M4 21h16"/>',
    back: '<path d="M12 14v7"/><path d="m8 11 4 4 4-4"/><path d="M4 3h16"/>',
    trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    swap: '<path d="M21 7 17 3v3h-8"/><path d="M3 7h8"/><path d="m3 17 4 4v-3h8"/><path d="M21 17h-8"/>',
    upload: '<path d="M12 15V3"/><path d="m7 8 5-5 5 5"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
    sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4"/><path d="m6 6 2 2M16 16l2 2M18 6l-2 2M8 16l-2 2"/>',
    edit: '<path d="M12 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-6"/><path d="M17.6 3.4a2.1 2.1 0 0 1 3 3L12.2 14.8l-4.2 1.2 1.2-4.2z"/>',
    send: '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7z"/>',
    move: '<path d="M5 9l-3 3 3 3"/><path d="M9 5l3-3 3 3"/><path d="M15 19l-3 3-3-3"/><path d="M19 9l3 3-3 3"/><path d="M2 12h20"/><path d="M12 2v20"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    chevL: '<path d="m15 18-6-6 6-6"/>',
    undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 5 5v0a5 5 0 0 1-5 5H8"/>',
    redo: '<path d="m15 14 5-5-5-5"/><path d="M20 9H9a5 5 0 0 0-5 5v0a5 5 0 0 0 5 5h7"/>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.5-3.5a2 2 0 0 0-2.8 0L6 21"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    book: '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
    refresh: '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/>'
  };

  function chip(kind) {
    const base = { className: "ctx-chip" };
    if (kind === "replace") return h("span", { ...base, style: { background: "var(--primary)" } }, Svg(PATHS.swap, 14));
    if (kind === "upload") return h("span", { ...base, style: { background: "var(--bb-accent-2)" } }, Svg(PATHS.upload, 14));
    if (kind === "color") return h("span", { ...base, style: { background: "conic-gradient(from 0deg,#ef4444,#f59e0b,#22c55e,#3b82f6,#a855f7,#ef4444)" } });
    if (kind === "metallic") return h("span", { ...base, style: { background: "linear-gradient(135deg,#f5f5f5,#9aa0a6 45%,#e8eaed 60%,#6b7177)" } });
    if (kind === "glass") return h("span", { ...base, style: { background: "rgba(96,165,250,0.35)", border: "1px solid rgba(255,255,255,0.6)" } });
    if (kind === "emboss") return h("span", { ...base, style: { background: "radial-gradient(circle at 35% 30%,#fde68a,#d97706)" } });
    if (kind === "transparent") return h("span", { ...base, style: { background: "repeating-conic-gradient(#cbd5e1 0% 25%, #fff 0% 50%) 50% / 11px 11px" } });
    return h("span", base);
  }

  // ---- character roster (kept in the document so add / remove / undo all work) ----
  const TINTS = ["#6366f1", "#0e7490", "#b45309", "#be185d", "#15803d", "#7c3aed"];

  const CHAR_ORDER = "bb_char_order_v4";
  function loadRoster() {
    let order = null, map = {};
    try { order = JSON.parse(localStorage.getItem(CHAR_ORDER) || "null"); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
    try { map = JSON.parse(localStorage.getItem(BBWS.STORE) || "{}"); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
    if (!order || !order.length) return DEFAULT_CAST.slice();
    const known = {}; DEFAULT_CAST.forEach((c) => { known[c.id] = c; });
    const out = order.map((id, i) => {
      const s = map[id] || {}, k = known[id];
      if (!s.name && !k) return null;
      return { id: id, name: s.name || k.name, role: s.role || (k && k.role) || "Supporting character",
        color: (k && k.color) || TINTS[i % TINTS.length],
        scenes: (s.scenes && s.scenes.length) || (k && k.scenes) || 0 };
    }).filter(Boolean);
    return out.length ? out : DEFAULT_CAST.slice();
  }
  function saveRoster(list) {
    try {
      localStorage.setItem(CHAR_ORDER, JSON.stringify(list.map((c) => c.id)));
      const map = JSON.parse(localStorage.getItem(BBWS.STORE) || "{}");
      list.forEach((c) => { map[c.id] = Object.assign({ mode: null, design: null, variants: [], scenes: [] }, map[c.id], { id: c.id, name: c.name, role: c.role }); });
      localStorage.setItem(BBWS.STORE, JSON.stringify(map));
    } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
  }
  function charsOnPage(els, roster) {
    const t = (els || []).map((e) => e.text || "").join(" ").toLowerCase();
    return (roster || []).filter((c) => c.name && t.indexOf(c.name.toLowerCase()) >= 0).map((c) => c.id);
  }

  let UID = 1;
  const uid = () => "el" + (UID++);
  const newTag = (k) => k + "#" + (40 + Math.floor(Math.random() * 60));
  function el(kind, label, x, y, w, extra) {
    return Object.assign({ id: uid(), kind, label, x, y, w, h: null, opacity: 100, rotation: 0,
      color: null, effect: "none", z: 1, tag: newTag(kind) }, extra || {});
  }
  const HERO_GRADS = [
    "linear-gradient(165deg,#7c3aed,#9f1239 70%,#3a1420)",
    "linear-gradient(165deg,#1d4ed8,#0891b2 60%,#fbbf24)",
    "linear-gradient(165deg,#065f46,#14532d 70%,#052015)",
    "linear-gradient(165deg,#1e1b4b,#312e81 70%,#0a0f24)"
  ];


  function innerCountFor(settings) {
    const n = parseInt(String((settings && settings.length) || "32").replace(/[^0-9]/g, ""), 10) || 32;
    return Math.max(2, Math.min(6, Math.round(n / 8)));
  }

  /* Pages carry theme ROLES, not literal colors, so editing the book style in the
     editor re-styles every page without regenerating anything. */
  function buildPages(settings, roster, manuscript) {
    settings = settings || {};
    const pageNums = settings.pageNums !== false;
    const pages = [];
    pages.push({ id: "pg0", name: "Cover", kind: "cover", bgRole: "cover", layout: "title",
      els: [
        el("frame", "Border", 4, 3, 92, { h: 94, z: 0 }),
        el("emblem", "Logo", 39, 8, 22, { z: 3 }),
        el("title", "Title", 8, 30, 84, { text: settings.name || "The Lantern Boy", z: 3 }),
        el("subtitle", "Subtitle", 8, 45, 84, { text: "A bedtime story", z: 3 }),
        el("image", "Illustration", 16, 53, 68, { h: 32, art: 0, z: 2 }),
        el("subtitle", "Author", 8, 90, 84, { text: settings.author || "Made with Blue Balloon", size: 13, z: 3 })
      ] });
    // the manuscript is the source: one page per chapter when it exists
    const chapters = manuscript && BBMS ? BBMS.chaptersOf(manuscript) : [];
    const inner = chapters.length
      ? chapters.map((c, i) => ({ hd: c.title, img: i % 4, tx: BBMS.blocks(c.html).join(" ") }))
      : INNER_CONTENT.slice(0, innerCountFor(settings));
    inner.forEach(function (p, i) {
      const els = [
        el("heading", "Heading", 10, 10, 80, { text: p.hd, z: 2 }),
        el("image", "Illustration", 13, 19, 74, { h: 38, art: p.img, z: 1 }),
        el("paragraph", "Body text", 12, 62, 76, { text: p.tx, z: 2 })
      ];
      if (pageNums) els.unshift(el("pageno", "Page number", 8, 6, 18, { text: String(i + 1).padStart(2, "0"), z: 2 }));
      pages.push({ id: "pg" + (i + 1), name: "Page " + (i + 1), kind: "page", bgRole: "background",
        layout: "imagetext", els: els, chars: charsOnPage(els, roster) });
    });
    return pages;
  }

  /* Map the backend pipeline's page records onto the editor's page model. The
     pipeline renders the illustration (`art_url`, text-free) separately from the
     words (`text` + a `text_area` placement hint), so we show the ART as a
     full-bleed background and lay the text on top as a REAL text element. That
     makes the words movable/editable by clicking — and the client exporter
     (which renders `els`) composites them back over the art. Falls back to the
     baked page image when a book predates the split. Page 0 is the cover. */
  function TEXT_Y(area) { return area === "top" ? 6 : area === "center" ? 42 : 72; }
  function buildBackendPages(apiPages) {
    return (apiPages || []).map(function (p, i) {
      const cover = i === 0;
      const bg = p.art_url || p.url;
      const els = [el("image", "Illustration", 0, 0, 100, { h: 100, src: bg, z: 0 })];
      // The pipeline's art is text-free, so lay the words on top as a movable,
      // editable element: the cover gets a styled title, body pages a paragraph.
      const words = (p.text || "").trim();
      if (words) {
        const area = (p.text_area || (cover ? "top" : "bottom")).toLowerCase();
        els.push(el(cover ? "title" : "paragraph", cover ? "Title" : "Body text",
          8, TEXT_Y(area), 84,
          { text: words, z: 2, h: cover ? 30 : 24, align: "center", whiteSpace: "pre-wrap" }));
      }
      return {
        id: "pg" + p.id, name: cover ? "Cover" : "Page " + i,
        kind: cover ? "cover" : "page", bgRole: cover ? "cover" : "background",
        layout: cover ? "image" : "imagetext", backendId: p.id, chars: [], els: els
      };
    });
  }

  // ---- page helpers ----
  const pad2 = (n) => String(n).padStart(2, "0");
  function renumber(pages) {
    let n = 0;
    return pages.map((pg) => {
      if (pg.kind === "cover") return pg;
      n++;
      const els = pg.els.map((e) => e.kind === "pageno" ? Object.assign({}, e, { text: pad2(n) }) : e);
      return Object.assign({}, pg, { name: pg.customName ? pg.name : "Page " + n, els: els });
    });
  }
  const newPageId = () => "pg" + Date.now().toString(36) + Math.floor(Math.random() * 900 + 100);
  function blankPage(settings) {
    const els = settings.pageNums !== false ? [el("pageno", "Page number", 8, 6, 18, { text: "00", z: 2 })] : [];
    return { id: newPageId(), name: "Page", kind: "page", bgRole: "background", layout: "imagetext", els: els, chars: [] };
  }
  function clonePage(pg) {
    return Object.assign({}, pg, { id: newPageId(), kind: pg.kind === "cover" ? "page" : pg.kind,
      customName: !!pg.customName, name: pg.customName ? pg.name + " copy" : pg.name, review: null,
      els: pg.els.map((e) => Object.assign({}, e, { id: uid(), tag: newTag(e.kind) })) });
  }

  const renderEl = BBR.renderEl;

  function rowsFor(kind) {
    const noun = kind === "emblem" ? "logo" : "image";
    if (kind === "emblem" || kind === "image") return [
      { id: "replace", label: "Replace " + noun, chip: "replace", act: "replace" },
      { id: "upload", label: "Upload " + noun, chip: "upload", act: "upload" },
      { id: "color", label: "Change color", chip: "color", act: "color" },
      { id: "metallic", label: "Metallic", chip: "metallic", act: "effect", eff: "metallic" },
      { id: "glass", label: "Glass", chip: "glass", act: "effect", eff: "glass" },
      { id: "emboss", label: "Emboss", chip: "emboss", act: "effect", eff: "emboss" },
      { id: "transparent", label: "Transparent", chip: "transparent", act: "effect", eff: "transparent" }
    ];
    if (kind === "shape" || kind === "frame") return [
      { id: "color", label: kind === "frame" ? "Border color" : "Fill color", chip: "color", act: "color" },
      { id: "transparent", label: "Transparent", chip: "transparent", act: "effect", eff: "transparent" }
    ];
    return [
      { id: "color", label: "Change color", chip: "color", act: "color" },
      { id: "emboss", label: "Emboss", chip: "emboss", act: "effect", eff: "emboss" },
      { id: "metallic", label: "Gold foil", chip: "metallic", act: "effect", eff: "metallic" },
      { id: "transparent", label: "Transparent", chip: "transparent", act: "effect", eff: "transparent" }
    ];
  }
  const MULTI_ROWS = [
    { id: "color", label: "Change color", chip: "color", act: "color" },
    { id: "metallic", label: "Metallic", chip: "metallic", act: "effect", eff: "metallic" },
    { id: "glass", label: "Glass", chip: "glass", act: "effect", eff: "glass" },
    { id: "emboss", label: "Emboss", chip: "emboss", act: "effect", eff: "emboss" },
    { id: "transparent", label: "Transparent", chip: "transparent", act: "effect", eff: "transparent" }
  ];

  function PropsDock(props) {
    const { els, onAction, onPatch, onClose } = props;
    const primary = els[0];
    const multi = els.length > 1;
    const rows = multi ? MULTI_ROWS : rowsFor(primary.kind);
    const item = (r) => h("button", { key: r.id, className: "ctx-item", onClick: () => onAction(r) },
      chip(r.chip), h("span", null, r.label),
      r.act === "effect" && primary.effect === r.eff ? h("span", { style: { marginLeft: "auto", opacity: 0.7 } }, h(LIcon, { name: "check", size: 14 })) : null
    );
    const action = (id, label, path, danger) => h("button", { key: id, className: "ctx-item" + (danger ? " danger" : ""), onClick: () => onAction({ act: id }) },
      h("span", { className: "ctx-ic" }, Svg(path, 16)), h("span", null, label));
    const KIND_NAME = { image: "Image", emblem: "Logo", shape: "Shape", frame: "Frame" };
    const kindName = multi ? null : (BBR.isText(primary) ? "Text" : (KIND_NAME[primary.kind] || "Element"));
    return h("div", { className: "rdock props-dock", style: { right: props.rightOffset || 0 }, onMouseDown: (e) => e.stopPropagation() },
      h("div", { className: "ctx-head" },
        h("div", { style: { minWidth: 0 } },
          h("span", { className: "lbl" }, multi ? els.length + " elements" : primary.label),
          multi ? null : h("span", { className: "tag", style: { marginLeft: 8 } }, kindName)
        ),
        h("button", { className: "ctx-close", title: "Close", onClick: onClose }, Svg(PATHS.x, 14))
      ),
      multi ? h("div", { className: "ctx-note" }, "Changes apply to all selected") : null,
      !multi && BBR.isText(primary) ? action("text", "Edit text", BBR.P.pencil) : null,
      !multi && !BBR.isText(primary) ? h("div", { className: "ctx-note" }, "Drag to move \u00b7 pull a corner to resize") : null,
      rows.map(item),
      !multi && primary.kind === "shape" ? h("div", { className: "ctx-slider" },
        h("div", { className: "row" }, h("span", { className: "nm" }, "Corner radius"), h("span", { className: "vl" }, (primary.radius || 0) + "px")),
        h("input", { type: "range", min: 0, max: 60, value: primary.radius || 0, onChange: (e) => onPatch({ radius: +e.target.value }) })) : null,
      h("div", { className: "ctx-sep" }),
      h("div", { className: "ctx-slider" },
        h("div", { className: "row" }, h("span", { className: "nm" }, "Opacity"), h("span", { className: "vl" }, primary.opacity + "%")),
        h("input", { type: "range", min: 0, max: 100, value: primary.opacity, onChange: (e) => onPatch({ opacity: +e.target.value }) })
      ),
      h("div", { className: "ctx-slider" },
        h("div", { className: "row" }, h("span", { className: "nm" }, "Rotation"), h("span", { className: "vl" }, (primary.rotation || 0) + "°")),
        h("input", { type: "range", min: -180, max: 180, value: primary.rotation || 0, onChange: (e) => onPatch({ rotation: +e.target.value }) })
      ),
      h("div", { className: "ctx-sep" }),
      action("dup", "Duplicate", PATHS.copy),
      action("front", "Bring to front", PATHS.front),
      action("back", "Send to back", PATHS.back),
      action("del", multi ? "Delete all" : "Delete", PATHS.trash, true)
    );
  }

  const Thumb = BBR.Thumb;

  function ShortcutsDialog({ onClose }) {
    const rows = [["Undo", ["\u2318", "Z"]], ["Redo", ["\u21e7", "\u2318", "Z"]],
      ["Duplicate selection, or page", ["\u2318", "D"]], ["Delete selected element", ["Delete"]],
      ["Edit any text", ["Double-click"]], ["Bold / italic / underline", ["\u2318", "B / I / U"]],
      ["Finish editing", ["Esc"]]];
    return h(Dialog, { open: true, onOpenChange: onClose },
      h(DialogHeader, null, h(DialogTitle, null, "Keyboard shortcuts"),
        h(DialogDescription, null, "These work anywhere in the editor.")),
      h("div", { className: "ks" }, rows.map((r) => h("div", { className: "ks-row", key: r[0] },
        h("span", null, r[0]),
        h("span", { className: "ks-k" }, r[1].map((k, i) => h("kbd", { key: i }, k)))))),
      h(DialogFooter, null, h(Button, { onClick: onClose }, "Done")));
  }

  function parseJSON(text) {
    if (!text) return null;
    try { return JSON.parse(text); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
    const a = text.indexOf("{"), b = text.lastIndexOf("}");
    if (a >= 0 && b > a) { try { return JSON.parse(text.slice(a, b + 1)); } catch (e) { /* Optional browser capability or local cache is unavailable. */ } }
    return null;
  }

  function pageDims(settings) {
    const sz = (settings && settings.size) || "A4";
    const land = /horizon/i.test((settings && settings.orientation) || "");
    if (/square/i.test(sz)) return { w: 560, h: 560 };
    let w = 470, h = 630;
    if (/a5/i.test(sz)) { w = 458; h = 648; }
    else if (/a3/i.test(sz)) { w = 478; h = 620; }
    else if (/letter/i.test(sz)) { w = 486; h = 628; }
    return land ? { w: h, h: w } : { w: w, h: h };
  }
  // Pipeline pages are baked images with their OWN aspect ratio (usually square,
  // 1024×1024) which rarely matches the A4 default. Forcing a square image into
  // a portrait A4 canvas with object-fit:cover cropped the sides — clipping the
  // text baked near the edges. When we know the real image aspect, size the
  // canvas to it (longest side = BASE) so the whole page shows, uncropped.
  function aspectDims(aspect) {
    const BASE = 660;
    if (!aspect || !isFinite(aspect) || aspect <= 0) return { w: BASE, h: BASE };
    return aspect >= 1
      ? { w: BASE, h: Math.round(BASE / aspect) }
      : { w: Math.round(BASE * aspect), h: BASE };
  }
  // ---- default settings (loaded from draft) ----
  function loadSettings() {
    let d = {};
    try { d = JSON.parse(localStorage.getItem("bb_draft") || "{}"); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
    let title = "The Lantern Boy";
    try {
      const cur = localStorage.getItem("bb_current");
      const list = JSON.parse(localStorage.getItem("bb_projects") || "[]");
      const found = list.find((p) => p.id === cur);
      if (found) title = found.title;
    } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
    return {
      fresh: !!d.fresh,
      author: d.author || "",
      name: d.name || title,
      manuscript: d.manuscript || "",
      style: BBSS.normalizeStyle(d.style),
      length: d.length || "32 pages",
      size: d.size || "A4",
      orientation: d.orientation || "Vertical",
      pageNums: d.pageNums !== false,
      fonts: (d.fonts && d.fonts.length) ? d.fonts : [
        { family: "Geist", role: "Heading", size: 32 },
        { family: "Lora", role: "Subheading", size: 20 },
        { family: "Lora", role: "Body Text", size: 14 }
      ],
      palette: (d.palette && d.palette.length) ? d.palette : ["#4a1512", "#d4a83a", "#7C2D12", "#F3E5C8"],
      aesthetic: d.aesthetic || "",
      team: d.team || [],
      theme: d.theme || null
    };
  }

  // Collaboration / access metadata and the book theme — these fields do NOT
  // affect page generation, so changing them must never mark the book as
  // out-of-date or trigger a regeneration. Book style is applied live instead.
  const NON_DESIGN_KEYS = ["team", "name", "theme"];
  function designOnly(s) {
    const c = Object.assign({}, s);
    NON_DESIGN_KEYS.forEach((k) => delete c[k]);
    return c;
  }

  // small control primitives for the settings panel
  function field(label, control) {
    return h("div", { className: "setrow" }, h("div", { className: "k" }, label), control);
  }
  // ---- document load / autosave ----
  function docKey() { let cur = ""; try { cur = localStorage.getItem("bb_current") || ""; } catch (e) { /* Optional browser capability or local cache is unavailable. */ } return "bb_ws_doc_" + (cur || "default"); }
  function bumpUid(pages) {
    let mx = 0;
    pages.forEach((p) => (p.els || []).forEach((e) => { const n = parseInt(String(e.id).replace(/\D/g, ""), 10); if (n > mx) mx = n; }));
    if (mx >= UID) UID = mx + 1;
  }
  function loadDoc() {
    const settings = loadSettings();
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(docKey()) || "null"); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
    if (saved && saved.pages && saved.pages.length) {
      bumpUid(saved.pages);
      const st = Object.assign({}, settings, saved.settings || {});
      st.theme = BBTH.ensureTheme(st);
      const pages = BBTH.migratePages(saved.pages);
      return { pages: pages, settings: st,
        chars: Array.isArray(saved.chars) ? saved.chars : loadRoster(),
        manuscript: saved.manuscript || BBMS.derive(pages, st) };
    }
    const roster = settings.fresh ? [] : loadRoster();
    const fresh = Object.assign({}, settings, { theme: BBTH.ensureTheme(settings) });
    const pages = settings.fresh ? [buildPages(fresh, [])[0], blankPage(fresh)] : buildPages(fresh, roster);
    if (settings.fresh) { fresh.fresh = false; }
    return { pages: pages, settings: fresh, chars: roster, manuscript: BBMS.derive(pages, fresh) };
  }
  function saveDoc(doc) {
    try {
      localStorage.setItem(docKey(), JSON.stringify(doc));
      const list = JSON.parse(localStorage.getItem("bb_projects") || "[]");
      const id = localStorage.getItem("bb_current") || "default";
      const item = { id, title: doc.settings.name, style: doc.settings.style, updatedAt: new Date().toISOString() };
      localStorage.setItem("bb_projects", JSON.stringify(list.some(p => p.id === id) ? list.map(p => p.id === id ? item : p) : [item, ...list]));
      return true;
    } catch { return false; }
  }

  function SettingsPanel(props) {
    const { pending, setP, team, setTeam, onName, theme, onOpenStyle } = props;
    const [teamPicker, setTeamPicker] = useState(false);
    const manRef = useRef(null);
    const set = (k, v) => setP((s) => Object.assign({}, s, { [k]: v }));
    const addTeam = (n) => { setTeam((t) => t.concat([n])); setTeamPicker(false); };
    const removeTeam = (n) => setTeam((t) => t.filter((x) => x !== n));

    const avail = TEAM_CANDIDATES.filter((c) => !team.includes(c.name));

    return h("div", { className: "panel-body" },
      field("Project name", h("input", { className: "set-input", value: pending.name,
        onChange: (e) => { set("name", e.target.value); onName(e.target.value); } })),
      field("Manuscript",
        h("div", { className: "set-file" },
          h("span", { className: "fn" }, pending.manuscript || "Not uploaded"),
          h("button", { className: "set-link", onClick: () => manRef.current.click() }, "Replace"),
          h("input", { type: "file", ref: manRef, accept: backendEnabled ? ".txt,.docx,.doc,.md" : ".txt", style: { display: "none" },
            onChange: async (e) => { const f = e.target.files[0]; e.target.value = ""; if (!f) return;
              // Backend: hand the raw file to the pipeline (docx/txt) — it parses,
              // copyedits and builds character refs server-side.
              if (backendEnabled) { set("manuscript", f.name); props.onImport(null, f); return; }
              if (f.size > 1024 * 1024) { alert("Choose a text file under 1 MB."); return; }
              const text = await f.text(); props.onImport(text); set("manuscript", f.name); } })
        )),
      // Page setup — same controls as the New Project page
      h("div", { className: "setrow" },
        h("div", { className: "k", style: { marginBottom: 10 } }, "Page setup"),
        h("div", { className: "subrow" },
          h("p", { className: "subhead" }, "Page size"),
          h(BBSS.OrientationToggle, { value: pending.orientation, onChange: (v) => set("orientation", v) })),
        h(BBSS.SizeGrid, { value: pending.size, orientation: pending.orientation, onChange: (v) => set("size", v) }),
        h("div", { className: "divider" }),
        h("div", { className: "subrow" }, h("p", { className: "subhead" }, "Book length")),
        h(BBSS.LengthPicker, { value: pending.length, onChange: (v) => set("length", v) }),
        h("div", { className: "divider" }),
        h("label", { className: "checkrow", htmlFor: "ws-pagenums" },
          h(Checkbox, { id: "ws-pagenums", checked: pending.pageNums !== false, onChange: (e) => set("pageNums", e.target.checked) }),
          h("div", null,
            h("div", { className: "ct" }, "Include page numbers"),
            h("div", { className: "cs" }, "Add page numbers to the bottom of each storybook page.")))),
      h("div", { className: "setrow" },
        h("div", { className: "k", style: { marginBottom: 10 } }, "Illustration style"),
        h(BBSS.StyleGrid, { value: pending.style, onChange: (v) => set("style", v) })),
      h("div", { className: "setrow" },
        h("div", { className: "k", style: { marginBottom: 9 } }, "Book style"),
        h("div", { className: "bs-card bs-style" },
          h("div", { style: { minWidth: 0, flex: 1 } },
            h("div", { className: "bs-style-nm" }, theme.typography.heading.fontFamily + " / " + theme.typography.body.fontFamily),
            h("div", { className: "bs-style-s" }, "Fonts, colors and page layouts")),
          h("div", { style: { display: "flex", gap: 4, flex: "0 0 auto" } }, BBTH.paletteOf(theme).map((c, i) =>
            h("span", { key: i, className: "bs-dot", style: { background: c, width: 18, height: 18 } })))),
        h("button", { className: "bs-link", onClick: onOpenStyle }, "Edit in Book style",
          h(LIcon, { name: "chevron-right", size: 13 }))),
      field("Desired aesthetic", h("textarea", { className: "set-textarea", rows: 3, value: pending.aesthetic,
        placeholder: "Describe the mood, palette and feel…", onChange: (e) => set("aesthetic", e.target.value) })),
      h("div", { className: "setrow" },
        h("div", { className: "k" }, "Teammates (demo)"),
        team.length ? h("div", { className: "set-team" }, team.map((n, i) =>
          h("div", { className: "set-ava-row", key: n },
            h("div", { className: "set-ava", style: { background: TEAM_COLORS[i % TEAM_COLORS.length] } }, initials(n)),
            h("span", { className: "tn" }, n),
            h("button", { className: "set-x", title: "Remove", onClick: () => removeTeam(n) }, Svg(PATHS.x, 12)))))
          : h("div", { className: "set-empty" }, "No teammates yet. This local list does not grant access."),
        h("button", { className: "set-add", onClick: () => setTeamPicker((v) => !v), disabled: !avail.length },
          Svg(PATHS.plus, 13), avail.length ? "Add teammate" : "All added"),
        teamPicker ? h("div", { className: "team-pop" }, avail.map((c) =>
          h("button", { key: c.name, className: "team-pop-row", onClick: () => addTeam(c.name) },
            h("div", { className: "set-ava sm", style: { background: TEAM_COLORS[(team.length) % TEAM_COLORS.length] } }, initials(c.name)),
            h("div", null, h("div", { className: "tn" }, c.name), h("div", { className: "tr" }, c.role)),
            h("span", { className: "ctx-ic", style: { marginLeft: "auto" } }, Svg(PATHS.plus, 14))))) : null)
    );
  }

  function Workspace() {
    // ---- history-backed document state: { pages, settings, chars } ----
    const initDoc = React.useMemo(loadDoc, []);
    const initSettings = initDoc.settings;
    const [hist, setHist] = useState(() => ({ stack: [initDoc], idx: 0 }));
    const doc = hist.stack[hist.idx];
    const pages = doc.pages;
    const settings = doc.settings;
    const chars = doc.chars || [];
    const ms = doc.manuscript || BBMS.derive(pages, settings);
    const theme = settings.theme || BBTH.ensureTheme(settings);
    const canUndo = hist.idx > 0;
    const canRedo = hist.idx < hist.stack.length - 1;

    const [current, setCurrent] = useState(0);
    // Measured width/height of the pipeline's baked page images; drives the
    // canvas aspect so backend pages aren't cropped into the A4 default.
    const [imgAspect, setImgAspect] = useState(null);
    const [rail, setRail] = useState(() => {const mode = new URLSearchParams(location.search).get("mode"); return ["pages","manuscript","cover","characters","style","setting"].includes(mode) ? mode : "pages";});
    const [panelOpen, setPanelOpen] = useState(() => window.innerWidth > 767);
    const [editMode, setEditMode] = useState(false);
    const [selIds, setSelIds] = useState([]);
    const [marquee, setMarquee] = useState(null);
    const [aiOpen, setAiOpen] = useState(false);
    const [preview, setPreview] = useState(false);
    const [pvWait, setPvWait] = useState(false);
    const [callout, setCallout] = useState(false);
    const [exportOpen, setExportOpen] = useState(false);
    const [uploadError, setUploadError] = useState("");
    const [shareOpen, setShareOpen] = useState(false);
    const [aiWidth, setAiWidth] = useState(430);
    const [chats, setChats] = useState({});
    const [chatInput, setChatInput] = useState("");
    const [chatBusy, setChatBusy] = useState(false);
    const [activity, setActivity] = useState(null);
    const ai = BBSCN.useAiTasks();
    const [editingId, setEditingId] = useState(null);
    const [tbRect, setTbRect] = useState(null);
    const [titleEdit, setTitleEdit] = useState(null);
    const [nameEdit, setNameEdit] = useState(null);
    const [charDlg, setCharDlg] = useState(null);
    const [charRemove, setCharRemove] = useState(null);
    const [pageDelete, setPageDelete] = useState(null);
    const [sceneFilter, setSceneFilter] = useState(null);
    const [shortcuts, setShortcuts] = useState(false);
    const [insertMenu, setInsertMenu] = useState(null);
    const [saveState, setSaveState] = useState("");
    const [msSection, setMsSection] = useState(null);
    // "Select area": drag a rectangle on the page, then ask the assistant about just that part
    const [areaMode, setAreaMode] = useState(false);
    const [area, setArea] = useState(null);           // { x, y, w, h } in page %, ids: elements inside
    const areaRef = useRef(null); areaRef.current = area;
    const mode = rail === "manuscript" ? "manuscript" : (rail === "cover" ? "cover" : "pages");
    const coverIdx = pages.findIndex((p) => p.kind === "cover");

    // settings editing buffer (not applied until "Regenerate all")
    const [pending, setPending] = useState(settings);
    const [regenerating, setRegenerating] = useState(false);
    // backend generation progress banner ({stage, pct}) — null when idle/local
    const [genProgress, setGenProgress] = useState(null);
    const [genError, setGenError] = useState("");
    // Teammate access is collaboration metadata, kept OUT of the page-design
    // history so assigning/changing access never marks pages dirty or regenerates.
    const [team, setTeam] = useState(() => initSettings.team || []);
    // Compare only design-relevant fields — teammate access changes are applied
    // live and never require regenerating the pages.
    const settingsDirty = JSON.stringify(designOnly(pending)) !== JSON.stringify(designOnly(settings));

    // ---- character designs (shared with Characters / Design-with-AI pages) ----
    const [charData, setCharData] = useState(BBWS.loadCharData);
    // applied snapshot persists across the Design-with-AI round trip / refresh
    const REGEN_FLAG = "bb_ws_regen";
    const [charsApplied, setCharsApplied] = useState(() => {
      let flag = false, applied = null;
      try { flag = localStorage.getItem(REGEN_FLAG) === "1"; applied = localStorage.getItem(BBWS.APPLIED); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
      const cur = JSON.stringify(BBWS.loadCharData());
      if (flag && applied != null) return applied;   // a change is pending → keep the stale baseline so it reads as dirty
      try { localStorage.setItem(BBWS.APPLIED, cur); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
      return cur;
    });
    const charsDirty = JSON.stringify(charData) !== charsApplied;
    const dirty = settingsDirty || charsDirty;
    const charUploadTarget = useRef(null);
    const totalPages = BBWS.totalBookPages(settings);

    function writeChars(next) {
      setCharData(next); BBWS.saveCharData(next);
      try { localStorage.setItem(REGEN_FLAG, "1"); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
    }
    function setCharSource(charId, variantId, source) {
      writeChars(Object.assign({}, charData, { [charId]: (function () {
        const c = Object.assign({ mode: "constant", design: null, variants: [] }, charData[charId]);
        if (variantId) c.variants = (c.variants || []).map((v) => v.id === variantId ? Object.assign({}, v, { source }) : v);
        else c.design = source;
        return c;
      })() }));
    }
    function setCharRanges(charId, variantId, ranges) {
      writeChars(Object.assign({}, charData, { [charId]: (function () {
        const c = Object.assign({ mode: "variants", design: null, variants: [] }, charData[charId]);
        c.variants = (c.variants || []).map((v) => v.id === variantId ? Object.assign({}, v, { ranges }) : v);
        return c;
      })() }));
    }
    function onCharUpload(charId, variantId) { charUploadTarget.current = { charId, variantId }; charFileRef.current.click(); }
    async function onCharUploadFile(e) {
      const file = e.target.files[0], target = charUploadTarget.current;
      if (!file || !target) return;
      e.target.value = "";
      try { const preview = await readImage(file); setCharSource(target.charId, target.variantId, {type: "upload", name: file.name, preview}); }
      catch(error) {setUploadError(error.message);}
    }

    function onCharAI(charId, variantId) {
      BBWS.saveCharData(charData);
      try { localStorage.setItem(REGEN_FLAG, "1"); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
      const p = new URLSearchParams({ char: charId, return: "workspace" });
      if (variantId) p.set("variant", variantId);
      location.href = "/character-design?" + p.toString();
    }

    const colorRef = useRef(null);
    const fileRef = useRef(null);
    const charFileRef = useRef(null);
    const pendingRef = useRef(null);
    const pageRef = useRef(null);
    const dragRef = useRef(null);
    const resizeRef = useRef(null);
    const selRef = useRef([]); selRef.current = selIds;
    const curRef = useRef(0); curRef.current = current;
    const chatBodyRef = useRef(null);

    const title = settings.name;
    // Backend-backed books: size the canvas to the real image (measured on load)
    // so the baked page shows at its true aspect and nothing gets clipped.
    const dims = imgAspect ? aspectDims(imgAspect) : pageDims(settings);
    const pageScale = useCanvasScale(dims);
    const renderCtx = { dims: dims, theme: theme };
    const page = pages[Math.min(current, pages.length - 1)];
    const pageCtx = Object.assign({}, renderCtx, { page: page });
    const selEls = page.els.filter((e) => selIds.includes(e.id));
    const styleSelEl = selEls.length === 1 && BBR.isText(selEls[0]) ? selEls[0] : null;
    const pageTask = ai.tasks.find((t) => t.pageId === page.id);
    const reviewPages = pages.filter((p) => p.review);
    const reviewInfo = reviewPages.length ? { count: reviewPages.length, name: reviewPages[0].review } : null;
    const tbId = editingId || (selIds.length === 1 && BBR.isText(page.els.find((e) => e.id === selIds[0])) ? selIds[0] : null);
    const tbEl = tbId ? page.els.find((e) => e.id === tbId) : null;

    // keep pending in sync when applied settings change (undo/redo/regenerate)
    useEffect(() => { setPending(settings); }, [settings]);
    // clamp current page when page count changes
    useEffect(() => { if (current > pages.length - 1) setCurrent(pages.length - 1); }, [pages.length]);
    // the Cover designer always works on the cover page
    useEffect(() => { if (mode === "cover" && coverIdx >= 0 && current !== coverIdx) setCurrent(coverIdx); }, [mode, coverIdx, current]);
    // autosave — every edit persists, quietly
    const firstRun = useRef(true);
    useEffect(() => {
      if (firstRun.current) { firstRun.current = false; }
      setSaveState("saving");
      const t = setTimeout(() => { setSaveState(saveDoc(doc) ? "saved" : "error"); }, 450);
      const flush = () => saveDoc(doc);
      window.addEventListener("pagehide", flush);
      return () => { clearTimeout(t); saveDoc(doc); window.removeEventListener("pagehide", flush); };
    }, [doc]);
    // keep the formatting toolbar pinned to the live element box
    useLayoutEffect(() => {
      if (!tbId) { setTbRect(null); return; }
      const measure = () => { const n = document.querySelector('.page .el[data-id="' + tbId + '"]'); if (n) setTbRect(n.getBoundingClientRect()); };
      measure();
      const stage = document.querySelector(".stage");
      window.addEventListener("resize", measure);
      if (stage) stage.addEventListener("scroll", measure);
      return () => { window.removeEventListener("resize", measure); if (stage) stage.removeEventListener("scroll", measure); };
    }, [tbId, doc, current, panelOpen, aiOpen, aiWidth, dirty]);
    // the ring cursor gets out of the way while typing
    useEffect(() => { document.body.classList.toggle("text-editing", !!editingId); }, [editingId]);
    // keep the shared character list in step with the document, undo included
    useEffect(() => { saveRoster(chars); }, [chars]);

    // On open, pull this project's EXISTING backend pages (a book already produced
    // by the pipeline) into the canvas so the author can correct them via chat
    // WITHOUT re-running generation. Runs once; skips if the doc already holds
    // backend pages, so local overlays/edits made afterwards are preserved.
    useEffect(() => {
      if (!backendEnabled) return;
      let slug = "";
      try { slug = localStorage.getItem("bb_current") || ""; } catch (e) { return; }
      if (!slug) return;
      let alive = true;
      listPages(slug).then((ps) => {
        if (!alive || !ps || !ps.length) return;
        const apiPages = ps.map((p) => Object.assign({}, p, { url: assetUrl(p.url) }));
        // Measure a content page (not the cover) to drive the canvas aspect, so
        // the baked square art isn't cropped into A4 and clipping the text.
        const probe = apiPages[apiPages.length > 1 ? 1 : 0];
        if (probe && probe.url) {
          const im = new Image();
          im.onload = () => { if (alive && im.naturalWidth && im.naturalHeight) setImgAspect(im.naturalWidth / im.naturalHeight); };
          im.src = probe.url;
        }
        commitDoc((cur) => cur.pages.some((pg) => pg.backendId)
          ? cur
          : Object.assign({}, cur, { pages: buildBackendPages(apiPages) }));
      }).catch(() => { /* no backend pages / offline — keep the local doc */ });
      return () => { alive = false; };
    }, []);

    // ---- history ops ----
    function commitDoc(producer) {
      setHist((H) => {
        const cur = H.stack[H.idx];
        const next = producer(cur);
        if (!next || next === cur) return H;
        let stack = H.stack.slice(0, H.idx + 1);
        stack.push(next);
        if (stack.length > 80) stack = stack.slice(stack.length - 80);
        return { stack: stack, idx: stack.length - 1 };
      });
    }
    function liveDoc(producer) {
      setHist((H) => {
        const cur = H.stack[H.idx];
        const next = producer(cur);
        if (!next) return H;
        const stack = H.stack.slice();
        stack[H.idx] = next;
        return { stack: stack, idx: H.idx };
      });
    }
    const undo = () => setHist((H) => H.idx > 0 ? { stack: H.stack, idx: H.idx - 1 } : H);
    const redo = () => setHist((H) => H.idx < H.stack.length - 1 ? { stack: H.stack, idx: H.idx + 1 } : H);

    // commit/live a change to the current page's elements
    function pagesWith(cur, fn) {
      return Object.assign({}, cur, { pages: cur.pages.map((pg, i) => i !== curRef.current ? pg : Object.assign({}, pg, { els: fn(pg.els.slice()) })) });
    }
    function patchEls(ids, patch, live) {
      const op = (cur) => pagesWith(cur, (els) => els.map((e) => ids.includes(e.id) ? Object.assign({}, e, patch) : e));
      (live ? liveDoc : commitDoc)(op);
    }
    function mutate(fn) { commitDoc((cur) => pagesWith(cur, fn)); }

    // ---- page management — every action lands in history, so undo restores it ----
    const withPages = (cur, list) => Object.assign({}, cur, { pages: renumber(list) });
    function addPage(kind) {
      if (kind === "dup") return duplicatePage(curRef.current);
      const at = pages.length;
      commitDoc((cur) => withPages(cur, cur.pages.concat([blankPage(cur.settings)])));
      setSelIds([]); setEditingId(null); setSceneFilter(null); setCurrent(at);
    }
    function duplicatePage(i) {
      commitDoc((cur) => { const list = cur.pages.slice(); list.splice(i + 1, 0, clonePage(cur.pages[i])); return withPages(cur, list); });
      setSelIds([]); setEditingId(null); setSceneFilter(null); setCurrent(i + 1);
    }
    function deletePage(i) {
      if (pages.length <= 1) return;
      commitDoc((cur) => withPages(cur, cur.pages.filter((_, j) => j !== i)));
      setSelIds([]); setEditingId(null);
      setCurrent((c) => Math.min(c > i ? c - 1 : c, pages.length - 2));
    }
    function movePage(from, insertAt) {
      const to = insertAt > from ? insertAt - 1 : insertAt;
      if (to === from) return;
      commitDoc((cur) => { const list = cur.pages.slice(); const it = list.splice(from, 1)[0]; list.splice(to, 0, it); return withPages(cur, list); });
      setCurrent((c) => c === from ? to : (c > from && c <= to ? c - 1 : (c >= to && c < from ? c + 1 : c)));
    }
    function renamePage(i, name) {
      commitDoc((cur) => withPages(cur, cur.pages.map((pg, j) => j === i ? Object.assign({}, pg, { name: name, customName: true }) : pg)));
    }
    function clearReview(i) {
      commitDoc((cur) => Object.assign({}, cur, { pages: cur.pages.map((pg, j) => (i == null || j === i) ? Object.assign({}, pg, { review: null }) : pg) }));
    }

    // ---- characters — manage the cast at any point, without regenerating ----
    const writeRoster = (cur, list) => Object.assign({}, cur, { chars: list });
    function addChar(data) {
      const id = "c" + Date.now().toString(36);
      commitDoc((cur) => writeRoster(cur, (cur.chars || []).concat([{ id: id, name: data.name, role: data.role,
        color: TINTS[(cur.chars || []).length % TINTS.length], scenes: 0, ref: data.ref || null }])));
      // a brand new character never invalidates pages that were already made
      if (data.ref && data.ref.preview) {
        const next = Object.assign({}, charData, { [id]: { mode: "constant", variants: [],
          design: { type: "upload", name: data.ref.name, preview: data.ref.preview } } });
        setCharData(next); BBWS.saveCharData(next);
        if (!charsDirty) {
          const js = JSON.stringify(next);
          try { localStorage.setItem(BBWS.APPLIED, js); localStorage.removeItem(REGEN_FLAG); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
          setCharsApplied(js);
        }
      }
      setCharDlg(null);
    }
    function editChar(id, data) {
      commitDoc((cur) => writeRoster(cur, (cur.chars || []).map((c) => c.id === id
        ? Object.assign({}, c, { name: data.name, role: data.role, ref: data.ref || null }) : c)));
      if (data.ref && data.ref.preview && (!charData[id] || !charData[id].design || charData[id].design.preview !== data.ref.preview))
        setCharSource(id, null, { type: "upload", name: data.ref.name, preview: data.ref.preview });
      setCharDlg(null);
    }
    function duplicateChar(c) {
      const id = c.id + "-copy" + Math.floor(Math.random() * 900 + 100);
      commitDoc((cur) => {
        const list = (cur.chars || []).slice();
        const at = list.findIndex((x) => x.id === c.id);
        list.splice(at + 1, 0, Object.assign({}, c, { id: id, name: c.name + " copy", scenes: 0 }));
        return writeRoster(cur, list);
      });
    }
    // Removing a character never deletes story content — pages that mention them
    // are flagged for review instead.
    function removeChar(c) {
      commitDoc((cur) => Object.assign({}, writeRoster(cur, (cur.chars || []).filter((x) => x.id !== c.id)), {
        pages: cur.pages.map((pg) => (pg.chars || []).indexOf(c.id) >= 0
          ? Object.assign({}, pg, { review: c.name, chars: (pg.chars || []).filter((x) => x !== c.id) })
          : pg) }));
      if (sceneFilter && sceneFilter.id === c.id) setSceneFilter(null);
      setCharRemove(null);
    }
    function removeCopy(c) {
      const mentions = pages.filter((p) => (p.chars || []).indexOf(c.id) >= 0).length;
      const n = c.scenes || mentions;
      const unit = c.scenes ? "scenes" : "pages";
      if (!n) return "This will remove " + c.name + " from your character list.";
      return c.name + " appears in " + n + " " + unit + ". Removing this character may affect their appearances in those "
        + unit + " — the content stays, and affected pages are flagged for review.";
    }

    // ---- text ----
    // page text and the manuscript stay in step: a linked chapter mirrors its page
    function withPageEls(cur, idx, els) {
      const pg = Object.assign({}, cur.pages[idx], { els: els, chars: charsOnPage(els, cur.chars) });
      return Object.assign({}, cur, { pages: cur.pages.map((p, i) => i === idx ? pg : p),
        manuscript: BBMS.syncFromPage(cur.manuscript || BBMS.derive(cur.pages, cur.settings), pg) });
    }
    function startTextEdit(id) { setSelIds([id]); setEditingId(id); }
    function commitTextEdit(id, text) {
      setEditingId(null);
      commitDoc((cur) => {
        const pg = cur.pages[curRef.current];
        const before = pg.els.find((e) => e.id === id);
        if (!before || (before.text || "") === text) return cur;
        return withPageEls(cur, curRef.current, pg.els.map((e) => e.id === id ? Object.assign({}, e, { text: text }) : e));
      });
    }

    // ---- manuscript ----
    const msOf = (cur) => cur.manuscript || BBMS.derive(cur.pages, cur.settings);
    function setSection(id, patch) {
      commitDoc((cur) => {
        const m = msOf(cur);
        const sec = m.sections.find((s) => s.id === id); if (!sec) return cur;
        const next = Object.assign({}, sec, patch);
        if (next.title === sec.title && next.html === sec.html) return cur;
        const out = Object.assign({}, cur, { manuscript: Object.assign({}, m, { sections: m.sections.map((s) => s.id === id ? next : s) }) });
        if (next.pageId) out.pages = cur.pages.map((pg) => {
          if (pg.id !== next.pageId) return pg;
          const s = BBMS.syncPage(pg, next);
          return Object.assign({}, s, { chars: charsOnPage(s.els, cur.chars) });
        });
        return out;
      });
    }
    function addChapter(title) {
      const id = "ch" + Date.now().toString(36);
      commitDoc((cur) => {
        const m = msOf(cur), list = m.sections.slice();
        let at = -1; list.forEach((s, i) => { if (s.kind === "chapter") at = i; });
        if (at < 0) at = list.findIndex((s) => s.kind === "toc");
        list.splice(at + 1, 0, { id: id, kind: "chapter", title: title, html: "<p></p>", pageId: null });
        return Object.assign({}, cur, { manuscript: Object.assign({}, m, { sections: list }) });
      });
      setMsSection(id);
    }
    function removeSection(id) {
      commitDoc((cur) => { const m = msOf(cur); return Object.assign({}, cur, { manuscript: Object.assign({}, m, { sections: m.sections.filter((s) => s.id !== id) }) }); });
      if (msSection === id) setMsSection(null);
    }

    // ---- cover ----
    function coverEdit(fn, live) { (live ? liveDoc : commitDoc)((cur) => pagesWith(cur, fn)); }
    function addCoverEl(kind, extra) {
      const top = Math.max.apply(null, [1].concat(page.els.map((e) => e.z || 1))) + 1;
      const made = kind === "image" ? el("image", extra.label || "Image", 20, 20, 60, Object.assign({ h: 34, art: Math.floor(Math.random() * 4), z: top }, extra))
        : kind === "shape" ? el("shape", extra.label || "Rectangle", 30, 40, 40, Object.assign({ h: 18, z: top }, extra))
        : el(kind, extra.label || "Text", 10, 60, 80, Object.assign({ z: top }, extra));
      mutate((els) => els.concat([made]));
      setSelIds([made.id]);
    }
    function setCoverBg(color) {
      commitDoc((cur) => Object.assign({}, cur, { pages: cur.pages.map((pg) => pg.kind === "cover" ? Object.assign({}, pg, { bg: color || null }) : pg) }));
    }
    function setAuthor(v, live) {
      (live ? liveDoc : commitDoc)((cur) => cur.settings.author === v ? cur : Object.assign({}, cur, { settings: Object.assign({}, cur.settings, { author: v }) }));
    }
    function useBookTitle() {
      const t = page.els.find((e) => e.label === "Title" && BBR.isText(e));
      if (t) patchEls([t.id], { text: settings.name });
    }
    function addCoverPage() {
      commitDoc((cur) => withPages(cur, [buildPages(cur.settings, cur.chars)[0]].concat(cur.pages)));
      setCurrent(0);
    }
    // switching modes never carries selection or edit state across
    function go(id) {
      const url = new URL(location.href); url.searchParams.set("mode", id); history.replaceState(null, "", url);
      if (id !== rail) {
        setSelIds([]); setEditingId(null);
        if (id === "manuscript" || id === "cover") { setEditMode(false); if (id === "cover" && coverIdx >= 0) setCurrent(coverIdx); }
      }
      if (id !== "manuscript" && id !== "cover") setPanelOpen(true);
      setRail(id);
    }
    function toggleFormat(elObj, k) {
      const m = BBR.kindOf(elObj);
      const on = elObj[k] == null ? (k === "bold" ? m.fw >= 600 : (k === "italic" ? !!m.italic : false)) : !!elObj[k];
      patchEls([elObj.id], { [k]: !on });
    }
    function insertEl(kind) {
      const made = kind === "image"
        ? el("image", "Illustration", 13, 22, 74, { h: 38, art: Math.floor(Math.random() * 4), z: 2 })
        : kind === "heading"
          ? el("heading", "Heading", 10, 10, 80, { text: "New heading", z: 3 })
          : el("paragraph", "Body text", 12, 62, 76, { text: "New text.", z: 3 });
      mutate((els) => els.concat([made]));
      setEditMode(true); setSelIds([made.id]);
      if (kind !== "image") setTimeout(() => setEditingId(made.id), 20);
    }
    function commitTitle() {
      const v = (titleEdit || "").trim();
      setTitleEdit(null);
      if (!v || v === settings.name) return;
      commitDoc((cur) => Object.assign({}, cur, { settings: Object.assign({}, cur.settings, { name: v }) }));
      setPending((p) => Object.assign({}, p, { name: v }));
      try {
        const id = localStorage.getItem("bb_current");
        const list = JSON.parse(localStorage.getItem("bb_projects") || "[]");
        localStorage.setItem("bb_projects", JSON.stringify(list.map((p) => p.id === id ? Object.assign({}, p, { title: v }) : p)));
        const d = JSON.parse(localStorage.getItem("bb_draft") || "{}"); d.name = v;
        localStorage.setItem("bb_draft", JSON.stringify(d));
      } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
    }
    function commitPageName() {
      const v = (nameEdit || "").trim();
      setNameEdit(null);
      if (v && v !== page.name) renamePage(current, v);
    }

    // ---- book style: one theme object, applied live to every page ----
    function setTheme(next) {
      commitDoc((cur) => Object.assign({}, cur, { settings: Object.assign({}, cur.settings, { theme: next }) }));
      BBTH.saveDraftTheme(next);
    }
    // push a selected element's own formatting into its theme role
    function promoteToTheme(elObj) {
      setTheme(BBTH.promote(elObj, theme, page));
      patchEls([elObj.id], BBTH.clearOverrides());
    }
    // recolor one page: only the elements that were following that theme role
    function applyPageColor(role, hex) {
      const want = String(theme.colors[role] || "").toUpperCase();
      const ids = page.els.filter((e) => BBR.isText(e) && !e.color
        && String(BBTH.colorOf(e, theme, page)).toUpperCase() === want).map((e) => e.id);
      if (ids.length) patchEls(ids, { color: hex });
    }
    function applyPageLayout(i, id) {
      commitDoc((cur) => Object.assign({}, cur, { pages: cur.pages.map((pg, j) => j === i ? BBSTY.applyLayout(pg, id) : pg) }));
    }
    function applyLayoutToSimilar(id) {
      const kind = page.kind;
      commitDoc((cur) => Object.assign({}, cur, { pages: cur.pages.map((pg) => pg.kind === kind ? BBSTY.applyLayout(pg, id) : pg) }));
    }

    // ---- AI scene generation: runs as a task, so editing never blocks ----
    function setGenerating(pageId, on) {
      liveDoc((cur) => Object.assign({}, cur, { pages: cur.pages.map((p) => p.id === pageId ? Object.assign({}, p, { generating: !!on }) : p) }));
    }
    function sceneCharsFor(prompt) {
      return BBSCN.charsInPrompt(prompt, chars).map((c) => {
        const d = charData[c.id];
        return Object.assign({}, c, { thumb: (d && d.design && d.design.preview) || null });
      });
    }
    async function generateScene(prompt) {
      
      const recent = pages.slice(Math.max(0, curRef.current - 2), curRef.current + 1)
        .map((p) => p.els.filter((e) => BBR.isText(e)).map((e) => e.text).join(" ")).join("\n");
      const cast = chars.map((c) => c.name + " (" + c.role + ")").join(", ");
      const q = 'You are writing one page of a children\u2019s storybook called "' + settings.name + '". '
        + 'Characters: ' + (cast || "none listed") + '.\nRecent pages:\n' + recent
        + '\n\nThe author asks: "' + prompt + '"\n\nReply with ONLY a JSON object '
        + '{"heading":"<a 3-5 word scene title>","text":"<2-3 sentences of storybook prose>"}.';
      try {
        const out = await aiService.complete(q);
        const j = parseJSON(out);
        if (!j || !j.text) throw new Error("bad-json");
        return { hd: j.heading || "A new scene", tx: j.text };
      } catch (e) {
        const err = new Error("scene-failed");
        err.bbMessage = "The assistant couldn\u2019t finish this scene. Nothing on the page was changed.";
        throw err;
      }
    }
    function applyScene(pageId, res) {
      commitDoc((cur) => {
        const idx = cur.pages.findIndex((p) => p.id === pageId);
        if (idx < 0) return cur;
        const pg = cur.pages[idx];
        const els = pg.els.filter((e) => e.kind === "pageno").concat([
          el("heading", "Heading", 10, 10, 80, { text: res.hd, z: 2 }),
          el("image", "Illustration", 13, 19, 74, { h: 38, art: Math.floor(Math.random() * 4), z: 1 }),
          el("paragraph", "Body text", 12, 62, 76, { text: res.tx, z: 2 })
        ]);
        const next = Object.assign({}, pg, { els: els, layout: "imagetext", generating: false,
          chars: charsOnPage(els, cur.chars) });
        return Object.assign({}, cur, { pages: cur.pages.map((p, j) => j === idx ? next : p) });
      });
    }
    function startScene(prompt) {
      let targetId = page.id, targetIndex = curRef.current, name = page.name, created = false;
      if (!BBPG.isBlank(page)) {
        const pg = blankPage(settings);
        pg.generating = true;
        commitDoc((cur) => withPages(cur, cur.pages.concat([pg])));
        targetId = pg.id; targetIndex = pages.length; created = true;
        name = "Page " + (pages.filter((p) => p.kind !== "cover").length + 1);
      } else setGenerating(page.id, true);
      setCurrent(targetIndex); setSelIds([]); setEditingId(null); setAiOpen(true);
      ai.start({ kind: "scene", pageId: targetId, pageName: name, prompt: prompt, created: created,
        chars: sceneCharsFor(prompt), run: () => generateScene(prompt),
        onDone: (res) => applyScene(targetId, res) });
      // the conversation follows the user onto the page being built
      if (targetId !== page.id) pushMsg(targetId, { role: "user", text: prompt });
      pushMsg(targetId, { role: "ai", text: "Building a scene on " + name + ". Keep editing while I work \u2014 I\u2019ll say when it\u2019s ready." });
    }
    function sceneKeep(t) { ai.dismiss(t.id); }
    function sceneEdit(t) {
      ai.dismiss(t.id);
      const hd = page.els.find((e) => e.kind === "heading") || page.els.find((e) => BBR.isText(e));
      if (hd) { setEditMode(true); startTextEdit(hd.id); }
    }
    function sceneRegen(t) {
      setGenerating(t.pageId, true);
      ai.regenerate(t.id, () => generateScene(t.prompt + " \u2014 a different take"));
    }
    function sceneUsePrev(t) { if (t.previous) applyScene(t.pageId, t.previous); ai.dismiss(t.id); }
    function sceneCancel(t) {
      ai.cancel(t.id);
      setGenerating(t.pageId, false);
      if (t.created) {
        const i = pages.findIndex((p) => p.id === t.pageId);
        if (i >= 0 && pages.length > 1) deletePage(i);
      }
    }
    function sceneAdjust(t) {
      ai.dismiss(t.id); setGenerating(t.pageId, false);
      setChatInput(t.prompt); setAiOpen(true);
    }

    // ---- settings apply / revert ----
    function revertSettings() {
      setPending(settings);
      try {
        const applied = JSON.parse(charsApplied || "{}");
        setCharData(applied); BBWS.saveCharData(applied);
        localStorage.removeItem(REGEN_FLAG);
      } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
    }
    function finishRegen(nextChars) {
      try { localStorage.setItem(BBWS.APPLIED, nextChars); localStorage.removeItem(REGEN_FLAG); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
      setCharsApplied(nextChars);
      setSelIds([]);
      setEditMode(false);
      setRegenerating(false);
    }
    function regenerateAll() {
      const next = pending;
      const nextChars = JSON.stringify(charData);
      setRegenerating(true);
      // With the backend enabled, run the REAL pipeline: persist the applied
      // settings as the project draft (best-effort), kick a generate job, poll
      // it, then swap in the composed page PNGs. Local sample generation is kept
      // verbatim as the fallback below.
      if (backendEnabled) {
        let slug = "";
        try { slug = localStorage.getItem("bb_current") || ""; } catch (e) { /* storage unavailable */ }
        if (slug) saveDraft(slug, next).catch(() => {});
        setGenError(""); setGenProgress({ stage: "starting", pct: 0 });
        runGeneration(slug, { onProgress: (st) => setGenProgress({ stage: st.stage, pct: st.pct }) })
          .then((apiPages) => {
            setGenProgress(null);
            if (apiPages && apiPages.length) {
              commitDoc((cur) => Object.assign({}, cur, { settings: next, pages: buildBackendPages(apiPages) }));
            } else {
              // no pages came back — keep the local layout so the author isn't stranded
              commitDoc((cur) => { const pg = buildPages(next, cur.chars, cur.manuscript);
                return Object.assign({}, cur, { settings: next, pages: pg, manuscript: BBMS.relink(cur.manuscript, pg) }); });
            }
            finishRegen(nextChars);
          })
          .catch((e) => {
            setGenProgress(null);
            setGenError(e.bbMessage || e.message || "Generation failed. Nothing was changed.");
            setRegenerating(false);
          });
        return;
      }
      setTimeout(() => {
        commitDoc((cur) => { const pg = buildPages(next, cur.chars, cur.manuscript);
          return Object.assign({}, cur, { settings: next, pages: pg, manuscript: BBMS.relink(cur.manuscript, pg) }); });
        finishRegen(nextChars);
      }, 850);
    }

    // edit-mode cursor + global drag/marquee + resize listeners
    useEffect(() => {
      document.body.classList.toggle("editing", editMode);
      const ring = document.getElementById("ring");
      if (!editMode) { setSelIds([]); document.body.classList.remove("over-stage"); }
      const onMoveRing = (e) => { if (ring) ring.style.transform = "translate(" + e.clientX + "px," + e.clientY + "px)"; };
      const onMove = (e) => {
        if (resizeRef.current) {
          const w = Math.max(340, Math.min(720, window.innerWidth - e.clientX));
          setAiWidth(w);
          return;
        }
        const d = dragRef.current; if (!d) return;
        if (d.type === "resize") {
          d.moved = true;
          const dx = (e.clientX - d.sx) / d.rect.width * 100;
          const dy = (e.clientY - d.sy) / d.rect.height * 100;
          const o = d.orig;
          let x = o.x, y = o.y, w = o.w, hh = o.h;
          if (d.corner.indexOf("e") >= 0) w = o.w + dx;
          if (d.corner.indexOf("w") >= 0) { w = o.w - dx; x = o.x + dx; }
          if (o.h != null) {
            if (d.corner.indexOf("s") >= 0) hh = o.h + dy;
            if (d.corner.indexOf("n") >= 0) { hh = o.h - dy; y = o.y + dy; }
            if (e.shiftKey || d.lockAspect) { // keep the original proportions
              const ratio = o.w / o.h;
              const fromW = Math.abs(w - o.w) >= Math.abs(hh - o.h) * ratio;
              if (fromW) hh = w / ratio; else w = hh * ratio;
              if (d.corner.indexOf("w") >= 0) x = o.x + o.w - w;
              if (d.corner.indexOf("n") >= 0) y = o.y + o.h - hh;
            }
          }
          if (w < 4) { if (d.corner.indexOf("w") >= 0) x = o.x + o.w - 4; w = 4; }
          if (hh != null && hh < 3) { if (d.corner.indexOf("n") >= 0) y = o.y + o.h - 3; hh = 3; }
          const patch = { x: x, y: y, w: w }; if (o.h != null) patch.h = hh;
          const apply = (cur) => Object.assign({}, cur, { pages: cur.pages.map((pg, i) => i !== curRef.current ? pg : Object.assign({}, pg, {
            els: pg.els.map((el) => el.id === d.id ? Object.assign({}, el, patch) : el) })) });
          if (!d.committed) { d.committed = true; commitDoc(apply); } else liveDoc(apply);
          return;
        }
        if (d.type === "area") {
          const r = d.rect;
          const px = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
          const x1 = px((d.sx - r.left) / r.width * 100, 0, 100), y1 = px((d.sy - r.top) / r.height * 100, 0, 100);
          const x2 = px((e.clientX - r.left) / r.width * 100, 0, 100), y2 = px((e.clientY - r.top) / r.height * 100, 0, 100);
          const box = { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1), drawing: true };
          d.box = box;
          setArea(box);
          return;
        }
        if (d.type === "drag") {
          if (Math.abs(e.clientX - d.sx) > 2 || Math.abs(e.clientY - d.sy) > 2) d.moved = true;
          const dx = (e.clientX - d.sx) / d.rect.width * 100;
          const dy = (e.clientY - d.sy) / d.rect.height * 100;
          const apply = (cur) => Object.assign({}, cur, { pages: cur.pages.map((pg, i) => i !== curRef.current ? pg : Object.assign({}, pg, {
            els: pg.els.map((el) => d.ids.includes(el.id) ? Object.assign({}, el, { x: d.orig[el.id].x + dx, y: d.orig[el.id].y + dy }) : el)
          })) });
          if (d.moved && !d.committed) { d.committed = true; commitDoc(apply); }
          else if (d.committed) liveDoc(apply);
        } else if (d.type === "marquee") {
          const r = { left: Math.min(d.sx, e.clientX), top: Math.min(d.sy, e.clientY), right: Math.max(d.sx, e.clientX), bottom: Math.max(d.sy, e.clientY) };
          setMarquee({ x: r.left, y: r.top, w: r.right - r.left, h: r.bottom - r.top });
          const hit = [];
          document.querySelectorAll(".page .el").forEach((node) => {
            const b = node.getBoundingClientRect();
            if (b.left < r.right && b.right > r.left && b.top < r.bottom && b.bottom > r.top) hit.push(node.getAttribute("data-id"));
          });
          setSelIds(hit);
        }
      };
      const onUp = () => {
        const d = dragRef.current;
        if (d && d.type === "area") {
          const b = d.box;
          if (b && b.w > 2 && b.h > 2) {
            const ids = [];
            document.querySelectorAll(".page .el").forEach((node) => {
              const el = node, pr = pageRef.current.getBoundingClientRect(), er = el.getBoundingClientRect();
              const ex = (er.left - pr.left) / pr.width * 100, ey = (er.top - pr.top) / pr.height * 100;
              const ew = er.width / pr.width * 100, eh = er.height / pr.height * 100;
              if (ex < b.x + b.w && ex + ew > b.x && ey < b.y + b.h && ey + eh > b.y) ids.push(node.getAttribute("data-id"));
            });
            setArea({ x: b.x, y: b.y, w: b.w, h: b.h, ids: ids, pageId: pageRef.current.getAttribute("data-page") });
            setSelIds([]); setAreaMode(false); setAiOpen(true);
          } else setArea(null);
        }
        dragRef.current = null; resizeRef.current = null; document.body.classList.remove("resizing"); setMarquee(null); };
      window.addEventListener("mousemove", onMoveRing);
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
      return () => {
        window.removeEventListener("mousemove", onMoveRing);
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };
    }, [editMode]);

    // keyboard: undo/redo, duplicate and delete for whatever is selected
    const kb = useRef({});
    kb.current = {
      dupEls: () => { if (!dirty) onAction({ act: "dup" }); },
      delEls: () => { if (dirty) return; const ids = selRef.current; mutate((els) => els.filter((x) => ids.indexOf(x.id) < 0)); setSelIds([]); },
      dupPage: () => { if (!dirty) duplicatePage(curRef.current); },
      escape: () => { setSelIds([]); setInsertMenu(null); setAreaMode(false); if (areaRef.current && !chatBusy) setArea(null); }
    };
    useEffect(() => {
      const onKey = (e) => {
        const tag = (e.target.tagName || "").toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable) return;
        if (document.body.classList.contains("previewing")) return;
        const mod = e.metaKey || e.ctrlKey;
        if (mod && e.key.toLowerCase() === "z") { e.preventDefault(); if (e.shiftKey) redo(); else undo(); }
        else if (mod && e.key.toLowerCase() === "y") { e.preventDefault(); redo(); }
        else if (mod && e.key.toLowerCase() === "d") { e.preventDefault(); if (selRef.current.length) kb.current.dupEls(); else kb.current.dupPage(); }
        else if ((e.key === "Delete" || e.key === "Backspace") && selRef.current.length) { e.preventDefault(); kb.current.delEls(); }
        else if (e.key === "Escape") kb.current.escape();
      };
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, []);

    useEffect(() => { if (chatBodyRef.current) chatBodyRef.current.scrollTop = chatBodyRef.current.scrollHeight; }, [chats, current, aiOpen, chatBusy]);

    function startDrag(e, elObj) {
      e.stopPropagation();
      const ids = selRef.current.includes(elObj.id) ? selRef.current.slice() : [elObj.id];
      if (!selRef.current.includes(elObj.id)) setSelIds(ids);
      const rect = pageRef.current.getBoundingClientRect();
      const orig = {};
      page.els.forEach((x) => { if (ids.includes(x.id)) orig[x.id] = { x: x.x, y: x.y }; });
      dragRef.current = { type: "drag", ids, sx: e.clientX, sy: e.clientY, rect, orig, moved: false, committed: false };
    }
    function startResize(e, elObj, corner) {
      e.stopPropagation(); e.preventDefault();
      const rect = pageRef.current.getBoundingClientRect();
      dragRef.current = { type: "resize", id: elObj.id, corner: corner, sx: e.clientX, sy: e.clientY, rect: rect,
        orig: { x: elObj.x, y: elObj.y, w: elObj.w, h: elObj.h }, lockAspect: elObj.kind === "emblem", committed: false };
    }
    function startArea(e) {
      e.preventDefault(); e.stopPropagation();
      setSelIds([]); setEditingId(null);
      dragRef.current = { type: "area", sx: e.clientX, sy: e.clientY, rect: pageRef.current.getBoundingClientRect(), box: null };
    }
    function toggleAreaMode() {
      if (areaMode) { setAreaMode(false); return; }
      setArea(null); setSelIds([]); setEditingId(null); setAreaMode(true);
    }
    function clearArea() { setArea(null); setAreaMode(false); }
    // click selects any element; double-click opens the editor that fits its type
    function onElDoubleClick(ev, e) {
      if (dirty || areaMode) return;
      ev.stopPropagation();
      if (BBR.isText(e)) startTextEdit(e.id);
      else setSelIds([e.id]);
    }
    function startMarquee(e) {
      if (e.target.closest(".el")) return;
      setSelIds([]);
      dragRef.current = { type: "marquee", sx: e.clientX, sy: e.clientY };
    }

    function onAction(r) {
      const ids = selRef.current; const primary = page.els.find((e) => e.id === ids[0]); if (!primary) return;
      if (r.act === "text") { startTextEdit(primary.id); return; }
      if (r.act === "effect") { patchEls(ids, { effect: primary.effect === r.eff ? "none" : r.eff }); return; }
      if (r.act === "color") { pendingRef.current = { ids }; colorRef.current.value = "#d4a83a"; colorRef.current.click(); return; }
      if (r.act === "replace" || r.act === "upload") { pendingRef.current = { ids: [primary.id] }; fileRef.current.click(); return; }
      if (r.act === "dup") {
        const clones = selEls.map((s) => Object.assign({}, s, { id: uid(), x: s.x + 4, y: s.y + 4, z: (s.z || 1) + 1, tag: newTag(s.kind) }));
        mutate((els) => els.concat(clones));
        setSelIds(clones.map((c) => c.id)); return;
      }
      if (r.act === "front") { const mx = Math.max.apply(null, page.els.map((e) => e.z || 1)); patchEls(ids, { z: mx + 1 }); return; }
      if (r.act === "back") { const mn = Math.min.apply(null, page.els.map((e) => e.z || 1)); patchEls(ids, { z: mn - 1 }); return; }
      if (r.act === "del") { mutate((els) => els.filter((e) => !ids.includes(e.id))); setSelIds([]); return; }
    }
    function onColor(e) { if (pendingRef.current) patchEls(pendingRef.current.ids, { color: e.target.value, effect: "none" }); }
    async function onFile(e) { const f = e.target.files[0]; if (!f || !pendingRef.current) return; const ids = [...pendingRef.current.ids]; e.target.value = ""; try { const src = await readImage(f); patchEls(ids, { src, effect: "none" }); } catch(error) {setUploadError(error.message);} }

    // ---- AI chat ----
    function applyActions(actions) {
      if (!actions || !actions.length) return;
      commitDoc((cur) => pagesWith(cur, (els0) => {
        let els = els0;
        actions.forEach((a) => {
          if (a.op === "delete") { els = els.filter((e) => e.id !== a.id); return; }
          if (a.op === "duplicate") { const s = els.find((e) => e.id === a.id); if (s) els.push(Object.assign({}, s, { id: uid(), x: s.x + 4, y: s.y + 4, tag: newTag(s.kind) })); return; }
          els = els.map((e) => {
            if (e.id !== a.id) return e;
            const p = {};
            if (a.op === "setText") p.text = a.text;
            if (a.op === "setColor") { p.color = a.color; p.effect = "none"; }
            if (a.op === "setOpacity") p.opacity = Math.max(0, Math.min(100, +a.value));
            if (a.op === "setRotation") p.rotation = +a.value;
            if (a.op === "setEffect") p.effect = a.effect;
            if (a.op === "move") { if (a.x != null) p.x = +a.x; if (a.y != null) p.y = +a.y; }
            return Object.assign({}, e, p);
          });
        });
        return els;
      }));
    }
    function pushMsg(pid, m) { setChats((c) => Object.assign({}, c, { [pid]: (c[pid] || []).concat([m]) })); }

    // Dropped/attached image attachments → real Files to upload as visual
    // references. The composer keeps an object URL for image chips; fetch it back
    // into a blob. Non-image attachments can't guide an i2i edit, so skip them.
    async function refBlobsFrom(files) {
      const out = [];
      for (const f of (files || [])) {
        if (f.kind !== "image" || !f.url) continue;
        try {
          const b = await (await fetch(f.url)).blob();
          out.push(new File([b], f.name || "reference.png", { type: b.type || "image/png" }));
        } catch (e) { /* unreadable attachment — skip it */ }
      }
      return out;
    }

    // Translate page references the author types ("…like on page 11") into the
    // backend file ids the server fetches. The viewer numbers pages by their
    // POSITION in reading order (see numOf in preview.js), but a pipeline book
    // can have gaps in its file ids — text-only pages are never illustrated — so
    // the 11th page the author SEES is not necessarily page_11.png. We resolve
    // against the same positional scheme the viewer shows (the Nth non-cover
    // page), so the server receives the id of the page the author actually meant.
    // Mirrors the server's own page-ref regex (page/pg/p + optional #, or cover).
    function resolveRefPages(text) {
      const nonCover = pages.filter((p) => p.kind !== "cover");
      const ids = [];
      const re = /\b(?:page|pg|p)\s*#?\s*(\d+)\b/gi;
      let m;
      while ((m = re.exec(text || ""))) {
        const pg = nonCover[parseInt(m[1], 10) - 1];
        if (pg && pg.backendId != null) ids.push(String(pg.backendId));
      }
      if (/\bcover\b/i.test(text || "")) {
        const cov = pages.find((p) => p.kind === "cover");
        if (cov && cov.backendId != null) ids.push(String(cov.backendId));
      }
      // De-dupe and never let a page reference itself.
      return [...new Set(ids)].filter((id) => id !== String(page.backendId));
    }

    // Per-page server correction via the human-in-the-loop CHAT endpoint. A
    // backend-generated page is a single illustration, so the author's message
    // (plus any referenced page — named "page 5" in the text, or a dropped image)
    // runs one i2i edit and swaps the returned image in place. Identity locks are
    // applied server-side so a fix can't drift the characters.
    async function serverCorrectPage(pid, instruction, files, sel) {
      // A dragged-in page thumbnail arrives as an attachment carrying `pageRef`
      // (its backend id) — send those as page references; everything else is an
      // uploaded file reference.
      const pageRefIds = (files || []).filter((f) => f.pageRef != null).map((f) => String(f.pageRef));
      const refBlobs = await refBlobsFrom((files || []).filter((f) => f.pageRef == null));
      if (!instruction && !refBlobs.length && !pageRefIds.length) { pushMsg(pid, { role: "ai", text: "Tell me what to change on this page." }); return; }
      const slug = localStorage.getItem("bb_current") || "default";
      const refIds = [...new Set(resolveRefPages(instruction).concat(pageRefIds))].filter((id) => id !== String(page.backendId));
      // A selected region (percent box) → a normalised [x0,y0,x1,y1] box so the
      // server does a masked edit that leaves everything outside it untouched.
      const area = sel ? [sel.x / 100, sel.y / 100, (sel.x + sel.w) / 100, (sel.y + sel.h) / 100] : null;
      setChatBusy(true);
      try {
        const res = await chatPage(slug, page.backendId, instruction, refIds, refBlobs, area);
        if (res && res.ok === false) {                       // e.g. a referenced page doesn't exist
          pushMsg(pid, { role: "ai", text: res.reply || "I couldn't apply that." });
          return;
        }
        const url = res && res.page_url ? assetUrl(res.page_url) : null;
        if (url) {
          commitDoc((cur) => Object.assign({}, cur, { pages: cur.pages.map((pg) =>
            pg.id === pid ? Object.assign({}, pg, { els: pg.els.map((e) =>
              e.kind === "image" ? Object.assign({}, e, { src: url }) : e) }) : pg) }));
          // Offer a one-click Undo (plus the typed "undo"), so a surprising result
          // is never a dead end — revert restores the exact previous version.
          pushMsg(pid, { role: "ai",
            text: res.reply || ((area ? "Updated the selected area on " : "Updated the illustration on ") + page.name + "."),
            actions: [{ id: "revert", label: "Undo this change" }] });
        } else {
          pushMsg(pid, { role: "ai", text: "The server didn’t return an updated image. Nothing was changed." });
        }
      } catch (e) {
        pushMsg(pid, { role: "ai", text: e && e.bbMessage ? e.bbMessage : "That correction failed on the server. Nothing was changed." });
      } finally {
        setChatBusy(false);
      }
    }

    // Undo the last server-side correction for this page and swap the image back.
    async function serverRevert(pid) {
      const slug = localStorage.getItem("bb_current") || "default";
      setChatBusy(true);
      try {
        const res = await revertPageChat(slug, page.backendId);
        const url = res && res.page_url ? assetUrl(res.page_url) : null;
        if (url) {
          commitDoc((cur) => Object.assign({}, cur, { pages: cur.pages.map((pg) =>
            pg.id === pid ? Object.assign({}, pg, { els: pg.els.map((e) =>
              e.kind === "image" ? Object.assign({}, e, { src: url }) : e) }) : pg) }));
          pushMsg(pid, { role: "ai", text: "Reverted the last change on " + page.name + "." });
        } else {
          pushMsg(pid, { role: "ai", text: "Nothing to revert on " + page.name + "." });
        }
      } catch (e) {
        pushMsg(pid, { role: "ai", text: "Nothing to revert on " + page.name + "." });
      } finally {
        setChatBusy(false);
      }
    }

    async function sendChat(payload) {
      const msg = (payload && payload.text != null ? payload.text : chatInput).trim();
      const files = (payload && payload.files) || [];
      if ((!msg && !files.length) || chatBusy) return;
      const pid = page.id;
      const sel = areaRef.current && areaRef.current.pageId === pid ? areaRef.current : null;
      setChatInput("");
      pushMsg(pid, { role: "user", text: msg, files: files, area: !!sel });
      // Backend page (single illustration) → correct on the server via the chat
      // endpoint. "undo"/"revert" reverts the last server change for this page.
      if (backendEnabled && page.backendId) {
        // Treat a short, undo-dominant message as a revert — NOT as a new edit.
        // Covers "undo", "revert", "undo that/this/it/last change", "go back",
        // "put it back". Anything longer is a real instruction. This matters
        // because the old strict match sent near-misses through as a destructive
        // edit, wiping the version the author was trying to get back to.
        if (!files.length && /^\s*(please\s+)?(undo|revert|go\s+back|put\s+it\s+back)(\s+(that|this|it|again|the\s+last(\s+change)?|last(\s+change)?|change))?\s*[.!]?\s*$/i.test(msg)) { await serverRevert(pid); return; }
        await serverCorrectPage(pid, msg, files, sel); return;
      }
      const img = files.find((f) => f.kind === "image" && f.url) || null;
      const intent = sel ? "chat" : BBAI.classify(msg);
      if (intent === "scene" && !dirty) { startScene(msg); return; }
      if (intent === "rewrite") { rewritePage(pid, msg); return; }
      setChatBusy(true);
      // with a selected area, the assistant only sees (and may only change) what is inside it
      const scope = sel ? page.els.filter((e) => sel.ids.indexOf(e.id) >= 0) : page.els;
      const elsInfo = scope.map((e) => ({ id: e.id, kind: e.kind, label: e.label, text: e.text || null, color: e.color, opacity: e.opacity, rotation: e.rotation, effect: e.effect, x: Math.round(e.x), y: Math.round(e.y), w: Math.round(e.w), h: e.h != null ? Math.round(e.h) : null }));
      const prompt =
        'You are an assistant editing ONE page ("' + page.name + '") of a children\'s storybook in a design tool. ' +
        (sel ? ('The user selected a rectangular area of the page: x ' + Math.round(sel.x) + '%, y ' + Math.round(sel.y) + '%, width ' + Math.round(sel.w) + '%, height ' + Math.round(sel.h) + '%. Only change elements inside it. ') : '') +
        'These are the ' + (sel ? 'elements inside the selected area' : 'page elements') + ' as JSON:\n' + JSON.stringify(elsInfo) + '\n\n' +
        (files.length ? ('The user attached: ' + files.map(function (f) { return f.name + " (" + f.kind + ")"; }).join(", ") + '. Treat them as context for this request' + (img ? '; the image can be used as the illustration on this page' : '') + '.\n\n') : '') +
        'User request: "' + (msg || (img ? "Use this image on the page" : "")) + '"\n\n' +
        'Reply with ONLY a JSON object, no markdown, of the form {"reply":"<one short friendly sentence>","actions":[...]}. ' +
        'Allowed actions (use only existing ids): ' +
        '{"op":"setText","id","text"}, {"op":"setColor","id","color":"#hex"}, {"op":"setOpacity","id","value":0-100}, ' +
        '{"op":"setRotation","id","value":-180..180}, {"op":"setEffect","id","effect":"none|metallic|glass|emboss|transparent"}, ' +
        '{"op":"move","id","x":0-90,"y":0-90}, {"op":"delete","id"}, {"op":"duplicate","id"}. ' +
        'Coordinates x,y are percentages of the page. If nothing applies, use an empty actions array.';
      try {
        if (!aiService || !aiService.complete) throw new Error("no-ai");
        const out = await aiService.complete(prompt);
        const j = parseJSON(out);
        // if an image was attached, drop it onto the page's illustration element
        if (img) {
          const pool = sel ? scope : page.els;
          const target = pool.find((e) => e.kind === "image") || pool.find((e) => e.kind === "emblem");
          if (target) patchEls([target.id], { src: img.url, effect: "none" });
        }
        if (j) { applyActions((j.actions || []).filter((a) => !sel || sel.ids.indexOf(a.id) >= 0)); setChats((c) => Object.assign({}, c, { [pid]: (c[pid] || []).concat([{ role: "ai", text: j.reply || "Done." }]) })); }
        else setChats((c) => Object.assign({}, c, { [pid]: (c[pid] || []).concat([{ role: "ai", text: out || "Sorry, I couldn't parse that." }]) }));
      } catch (err) {
        if (img) {
          const pool = sel ? scope : page.els;
          const target = pool.find((e) => e.kind === "image") || pool.find((e) => e.kind === "emblem");
          if (target) patchEls([target.id], { src: img.url, effect: "none" });
        }
        setChats((c) => Object.assign({}, c, { [pid]: (c[pid] || []).concat([{ role: "ai", text: img ? ("Placed \u201c" + img.name + "\u201d onto " + page.name + ".") : ("The AI assistant isn't reachable in this preview, but here it would update " + (sel ? "the selected area of " : "") + "\u201c" + page.name + "\u201d for you.") }]) }));
      }
      setChatBusy(false);
      // the area was for this one request; the editor goes back to normal
      if (sel) { setArea((a) => a === sel ? null : a); setAreaMode(false); }
    }
    // rewriting copy comes back as a suggestion the user can apply, insert or reroll
    async function rewritePage(pid, msg) {
      setChatBusy(true);
      const target = page.els.find((e) => e.kind === "paragraph") || page.els.find((e) => BBR.isText(e));
      const cur = (target && target.text) || "";
      let suggestion;
      try {
        if (!aiService || !aiService.complete) throw new Error("no-ai");
        const out = await aiService.complete('Rewrite this page of a children\u2019s storybook. Request: "' + msg
          + '"\n\nCurrent text:\n' + cur + '\n\nReply with ONLY the rewritten text, 2\u20133 sentences, no quotes.');
        suggestion = (out || "").trim().replace(/^["\u201c]|["\u201d]$/g, "");
        if (!suggestion) throw new Error("empty");
      } catch (e) {
        pushMsg(pid, {role: "ai", text: "AI rewriting is not connected. Your original text is unchanged."}); setChatBusy(false); return;
      }
      pushMsg(pid, { role: "ai", text: suggestion, suggest: suggestion, prompt: msg,
        targetId: target ? target.id : null,
        actions: [{ id: "apply", label: "Apply to page", primary: true }, { id: "insert", label: "Insert below" },
          { id: "another", label: "Try another version" }] });
      setChatBusy(false);
    }
    function setElText(id, text) {
      commitDoc((cur) => withPageEls(cur, curRef.current, cur.pages[curRef.current].els.map((e) => e.id === id ? Object.assign({}, e, { text: text }) : e)));
    }
    function onChatAct(i, act) {
      const pid = page.id;
      const m = (chats[pid] || [])[i]; if (!m) return;
      if (act === "revert") { serverRevert(pid); return; }   // one-click Undo on an edit
      if (act === "apply" && m.suggest) {
        const t = m.targetId ? page.els.find((e) => e.id === m.targetId) : null;
        if (t) { setElText(t.id, m.suggest); pushMsg(pid, { role: "ai", text: "Applied to " + page.name + ". Undo puts the old words back." }); }
        else pushMsg(pid, { role: "ai", text: "There is no story text on this page yet \u2014 use Insert below instead." });
        return;
      }
      if (act === "insert" && m.suggest) {
        const made = el("paragraph", "Body text", 12, 76, 76, { text: m.suggest, z: 3 });
        mutate((els) => els.concat([made]));
        setSelIds([made.id]);
        return;
      }
      if (act === "another") { rewritePage(pid, (m.prompt || "") + " \u2014 a different version"); return; }
      if (act === "scene") { startScene(m.prompt || "Generate a scene for this page"); return; }
      if (act === "edit") { setChatInput(m.prompt || ""); return; }
    }

    // ----- middle panel -----
    let panelHead, panelSub, panelBody;
    if (rail === "pages") {
      panelHead = "Pages"; panelSub = pages.length + (pages.length === 1 ? " page" : " pages");
      panelBody = h(BBPG.PagesPanel, {
        pages: pages, current: current, ctx: renderCtx, locked: dirty, filter: sceneFilter, review: reviewInfo,
        note: dirty ? (charsDirty && !settingsDirty ? "Pages are out of date — a character design changed." : "Pages are out of date with story settings.") : null,
        onSelect: (i) => { if (window.innerWidth < 768) setPanelOpen(false); setCurrent(i); setSelIds([]); setEditingId(null); },
        onNew: addPage, onDup: duplicatePage, onDelete: (i) => setPageDelete(i),
        onRename: renamePage, onMove: movePage,
        onReviewed: (i) => clearReview(i), onReviewedAll: () => clearReview(null),
        onClearFilter: () => setSceneFilter(null)
      });
    } else if (rail === "characters") {
      panelHead = "Characters";
      panelSub = !chars.length ? "None yet" : (chars.length === 1 ? "1 character" : chars.length + " in this story");
      panelBody = h(BBWS.CharactersPanel, {
        chars: chars, charData: charData, total: totalPages,
        onUpload: onCharUpload, onAI: onCharAI, onRanges: setCharRanges,
        onAdd: () => setCharDlg({}), onEdit: (c) => setCharDlg({ char: c }),
        onDuplicate: duplicateChar, onRemove: (c) => setCharRemove(c),
        onScenes: (c) => { setSceneFilter({ id: c.id, name: c.name }); setRail("pages"); setPanelOpen(true); }
      });
    } else if (rail === "style") {
      panelHead = "Book style"; panelSub = "Fonts, colors and layouts";
      panelBody = h(BBSTY.BookStylePanel, { theme: theme, settings: settings, page: page, pages: pages,
        selEl: styleSelEl, onTheme: setTheme, onPromote: promoteToTheme, onPageColor: applyPageColor,
        onElColor: (hex) => { if (styleSelEl) patchEls([styleSelEl.id], { color: hex, effect: "none" }); },
        onClearEl: () => { if (styleSelEl) patchEls([styleSelEl.id], BBTH.clearOverrides()); },
        onLayout: (id) => applyPageLayout(current, id), onLayoutAll: applyLayoutToSimilar,
        onOpenSettings: () => setRail("setting") });
    } else {
      panelHead = "Story settings"; panelSub = dirty ? "Unapplied changes" : "Affects every page";
      panelBody = h(SettingsPanel, { pending: pending, setP: setPending, title: title, team: team, setTeam: setTeam,
        onImport: (text, file) => {
          if (backendEnabled && file) {
            let slug = ""; try { slug = localStorage.getItem("bb_current") || ""; } catch (e) { /* storage unavailable */ }
            setGenError(""); setGenProgress({ stage: "uploading manuscript", pct: 0 });
            // The manuscript endpoint starts the parse/copyedit/refs job (it
            // stops at character approval — it does NOT generate the book). Poll
            // that job to completion; the author then designs/approves
            // characters and hits "Regenerate all" to build the pages.
            uploadManuscript(slug, file)
              .then(() => waitForJob(slug, { onProgress: (st) => setGenProgress({ stage: st.stage, pct: st.pct }) }))
              .then(() => { setGenProgress(null); })
              .catch((e) => { setGenProgress(null); setGenError(e.bbMessage || e.message || "Manuscript upload failed."); });
            return;
          }
          const id = ms.sections.find(s => s.kind === "chapter")?.id; if(id) setSection(id,{html: BBMS.toHtml(text)});
        }, theme: theme, onOpenStyle: () => setRail("style"),
        onName: (v) => liveDoc((cur) => Object.assign({}, cur, { settings: Object.assign({}, cur.settings, { name: v }) })) });
    }

    const railBtn = (id, icon, label) => h("button", { className: "rail-btn", "data-active": rail === id, title: label, "aria-label": label, onClick: () => go(id) }, h(LIcon, { name: icon, size: 20 }));
    const msSec = mode === "manuscript" ? (ms.sections.find((s) => s.id === msSection) || ms.sections.find((s) => s.kind === "chapter") || ms.sections[0]) : null;
    // settings-changed overlay — shared by the Pages stage and the Cover designer
    const regenOverlay = dirty ? h("div", { className: "regen-overlay" },
      h("div", { className: "regen-card" },
        h("div", { className: "regen-ic" }, regenerating ? h("span", { className: "spin" }, Svg(PATHS.refresh, 22)) : h(LIcon, { name: "circle-alert", size: 22 })),
        h("div", { className: "regen-t" }, regenerating ? "Regenerating all pages…" : (charsDirty && !settingsDirty ? "A character has been changed" : "Settings have been changed")),
        h("div", { className: "regen-s" }, regenerating
          ? (genProgress
              ? "Generating on the server — " + (genProgress.stage || "working") + (genProgress.pct ? " (" + genProgress.pct + "%)" : "…")
              : "Applying the new story settings to every page.")
          : genError
          ? genError
          : (charsDirty && !settingsDirty
              ? "The character was updated. Every page must be regenerated so the new look appears across the book."
              : "It will require regeneration of all the pages to get the new settings applied.")),
        regenerating ? null : h("div", { className: "regen-btns" },
          h(Button, { variant: "outline", onClick: revertSettings }, "Revert changes"),
          h(Button, { onClick: regenerateAll }, Svg(PATHS.refresh, 15), "Regenerate all"))
      )) : null;

    const chatThread = chats[page.id] || [];
    // ---- Preview Book: read-only reading mode over the live document ----
    const generatingCount = pages.filter((p) => p.generating
      || ai.tasks.some((t) => t.pageId === p.id && t.status === "running")).length;
    function openPreview() {
      if (saveState === "saving") { setPvWait(true); return; }  // autosave settles first
      setPreview(true);
    }
    useEffect(() => { if (pvWait && saveState !== "saving") { setPvWait(false); setPreview(true); } }, [saveState, pvWait]);
    // the assistant introduces itself once per session, a beat after the editor settles
    function hideCallout() { setCallout(false); try { sessionStorage.setItem("bb_ai_callout", "1"); } catch (e) { /* Optional browser capability or local cache is unavailable. */ } }
    function openAi() { hideCallout(); setAiOpen(true); }
    useEffect(() => {
      let seen = false; try { seen = sessionStorage.getItem("bb_ai_callout") === "1"; } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
      if (seen) return;
      const t = setTimeout(() => setCallout(true), 1000);
      return () => clearTimeout(t);
    }, []);
    useEffect(() => {
      if (!callout) return;
      const t = setTimeout(hideCallout, 12000);
      return () => clearTimeout(t);
    }, [callout]);
    useEffect(() => { if (aiOpen && callout) hideCallout(); }, [aiOpen]);
    const propsVisible = mode === "pages" && selEls.length > 0 && !dirty && !areaMode;
    const dockRight = (propsVisible ? 270 : 0) + (aiOpen ? aiWidth : 0);
    const aiWorking = !!(pageTask && pageTask.status === "running") || chatBusy;
    const taskHandlers = pageTask ? {
      onCancel: () => sceneCancel(pageTask), onKeep: () => sceneKeep(pageTask), onEdit: () => sceneEdit(pageTask),
      onRegenerate: () => sceneRegen(pageTask), onUseVersion: () => ai.dismiss(pageTask.id),
      onKeepPrevious: () => sceneUsePrev(pageTask), onRetry: () => ai.retry(pageTask.id), onAdjust: () => sceneAdjust(pageTask) } : null;
    const CORNERS = ["nw", "ne", "sw", "se"];

    return h("main", { className: "ws", "aria-label": "Storybook workspace", style: { paddingRight: dockRight } },
      // rail
      h("nav", { className: "rail", "aria-label": "Workspace" },
        h("button", { className: "logo", title: "Home", "aria-label": "Go to Home", onClick: () => location.href = "/home" }, "BB"),
        railBtn("manuscript", "file-pen", "Manuscript"),
        railBtn("cover", "book-image", "Cover"),
        railBtn("pages", "file-text", "Pages"),
        h("div", { className: "rail-sep" }),
        railBtn("characters", "users", "Characters"),
        railBtn("style", "palette", "Book style"),
        railBtn("setting", "settings", "Story settings"),
        h("div", { className: "spacer" }),
        h("button", { className: "rail-btn", title: "Share read-only link", onClick: () => setShareOpen(true) }, h(LIcon, { name: "share-2", size: 19 })),
        h("button", { className: "rail-btn", title: "Export book", onClick: () => setExportOpen(true) }, h(LIcon, { name: "download", size: 19 }))
      ),
      panelOpen && mode === "pages" ? h("button", {className: "panel-backdrop", "aria-label": "Close navigation panel", onClick: () => setPanelOpen(false)}) : null,
      // middle panel (collapsible) — Pages-side tools only
      mode === "pages" && panelOpen ? h("div", { className: "panel" },
        h("div", { className: "panel-head" },
          h("div", { className: "panel-head-row" },
            h("div", null, h("div", { className: "t" }, panelHead), h("div", { className: "s" }, panelSub)),
            h("button", { className: "panel-collapse", title: "Minimize panel", onClick: () => setPanelOpen(false) }, Svg(PATHS.chevL, 18))
          )
        ),
        panelBody
      ) : null,
      // canvas
      h("div", { className: "canvas-col" },
        h("div", { className: "topbar" },
          h("div", { className: "crumb" },
            mode === "pages" && !panelOpen ? h("button", { className: "backbtn", title: "Show panel", onClick: () => setPanelOpen(true) }, h(LIcon, { name: "panel-left", size: 16 })) : null,
            titleEdit != null
              ? h("input", { className: "title-input", value: titleEdit, autoFocus: true, "aria-label": "Book title",
                  onChange: (e) => setTitleEdit(e.target.value), onBlur: commitTitle,
                  onKeyDown: (e) => { e.stopPropagation(); if (e.key === "Enter") commitTitle(); if (e.key === "Escape") setTitleEdit(null); } })
              : h("b", { title: "Double-click to rename", onDoubleClick: () => setTitleEdit(title) }, title),
            h("span", null, "/"),
            mode === "manuscript" ? h("span", { className: "pgname", style: { cursor: "default" } }, "Manuscript" + (msSec ? " \u00b7 " + msSec.title : ""))
            : mode === "cover" ? h("span", { className: "pgname", style: { cursor: "default" } }, "Cover")
            : nameEdit != null
              ? h("input", { className: "title-input", style: { minWidth: 110, fontWeight: 400 }, value: nameEdit, autoFocus: true, "aria-label": "Page name",
                  onChange: (e) => setNameEdit(e.target.value), onBlur: commitPageName,
                  onKeyDown: (e) => { e.stopPropagation(); if (e.key === "Enter") commitPageName(); if (e.key === "Escape") setNameEdit(null); } })
              : h("span", { className: "pgname", title: "Double-click to rename", onDoubleClick: () => setNameEdit(page.name) }, page.name),
            mode === "pages" && page.review ? h("button", { className: "review-pill", title: "Mark as reviewed", onClick: () => clearReview(current) },
              h(LIcon, { name: "flag", size: 11 }), "Needs review") : null,
            areaMode ? h("span", { className: "edit-hint", style: { marginLeft: 6 } }, h(LIcon, { name: "square-mouse-pointer", size: 14 }), "Drag over the part of the page you want to change")
            : editMode ? h("span", { className: "edit-hint", style: { marginLeft: 6 } }, Svg(PATHS.move, 14), "Drag to move · double-click text to edit") : null
          ),
          h("div", { className: "right" },
            saveState ? h("span", { className: "save-chip", "aria-live": "polite" },
              saveState === "saving" ? "Saving…" : saveState === "error" ? h("span", {className: "local-save-error"}, "Save failed") : h(React.Fragment, null, h(LIcon, { name: "check", size: 13 }), "Saved locally")) : null,
            ai.tasks.length ? h(BBSCN.StatusPill, { tasks: ai.tasks,
              onClick: (e) => { const r = e.currentTarget.getBoundingClientRect(); setActivity({ x: r.right, y: r.bottom + 8 }); } }) : null,
            // universal undo / redo
            h("div", { className: "undo-group" },
              h("button", { className: "icon-btn", title: "Undo", "aria-label": "Undo", disabled: !canUndo, onClick: undo }, Svg(PATHS.undo, 16)),
              h("button", { className: "icon-btn", title: "Redo", "aria-label": "Redo", disabled: !canRedo, onClick: redo }, Svg(PATHS.redo, 16))
            ),
            h("div", { className: "tb-sep" }),
            h(Button, { variant: "outline", size: "sm", className: "pv-open", title: "Preview your storybook",
              "aria-label": "Preview book", disabled: pvWait, onClick: openPreview },
              Svg(PATHS.book, 16), "Preview Book",
              generatingCount ? h("span", { className: "pv-open-badge", title: generatingCount + " pages still generating" }, generatingCount) : null),
            h("div", { className: "tb-sep" }),
            editMode ? h("button", { className: "icon-btn", title: "Insert element", "aria-label": "Insert element", disabled: dirty,
              onClick: (e) => { const r = e.currentTarget.getBoundingClientRect(); setInsertMenu({ x: r.right, y: r.bottom + 7 }); } }, Svg(PATHS.plus, 16)) : null,
            mode === "pages" ? h(Button, { variant: editMode ? "default" : "outline", size: "icon", title: editMode ? "Done editing" : "Edit", "aria-label": editMode ? "Done editing" : "Edit", disabled: dirty, onClick: () => setEditMode((v) => !v) },
              editMode ? h(LIcon, { name: "check", size: 16 }) : Svg(PATHS.edit, 17)) : null
          )
        ),
        mode === "manuscript" ? h(BBMS.ManuscriptMode, { ms: ms, sectionId: msSec && msSec.id, onSelect: setMsSection, onSection: setSection,
          onAdd: addChapter, onRemove: removeSection, settings: settings }) :
        mode === "cover" ? h(BBCV.CoverMode, { page: coverIdx >= 0 && current === coverIdx ? page : null, dims: dims, theme: theme, settings: settings,
          selIds: selIds, setSelIds: setSelIds, patch: patchEls, edit: coverEdit, addEl: addCoverEl,
          onUpload: (id) => { pendingRef.current = { ids: [id] }; fileRef.current.click(); },
          onAI: (id) => { setSelIds([id]); setChatInput("Generate a cover illustration for \u201c" + settings.name + "\u201d: "); openAi(); },
          onBg: setCoverBg, onAuthor: setAuthor, onUseTitle: useBookTitle, onAddCover: addCoverPage,
          locked: dirty, overlay: regenOverlay, aiOpen: aiOpen }) :
        h("div", { className: "stage" + (editMode ? " editing" : "") + (dirty ? " locked" : "") + (areaMode ? " area-mode" : ""),
            onMouseEnter: () => editMode && !dirty && document.body.classList.add("over-stage"),
            onMouseLeave: () => document.body.classList.remove("over-stage"),
            onMouseDown: (e) => { if (!dirty && !e.target.closest(".page") && !e.target.closest(".area-box")) setSelIds([]); },
            onMouseMove: (e) => { const r = document.getElementById("ring"); if (editMode && r && !dragRef.current) r.classList.toggle("armed", !!e.target.closest(".el")); } },
          h("div", { className: "page" + (dirty ? " stale" : "")
              + (aiWorking && !dirty ? " ai-working" : "")
              + (pageTask && pageTask.status === "done" ? " revealed" : ""), ref: pageRef, "data-page": page.id,
            style: { width: dims.w, height: dims.h, "--page-scale": pageScale, background: BBTH.pageBg(page, theme) },
            onMouseDown: (e) => {
              if (dirty) return;
              if (areaMode) { startArea(e); return; }
              if (editMode) startMarquee(e); else if (!e.target.closest(".el")) setSelIds([]);
            } },
            BBPG.isBlank(page) && !dirty ? h("div", { className: "blank-hint" },
              h("div", { className: "blank-t" }, "Blank page"),
              h("div", { className: "blank-s" }, "Add text, artwork, or another element to begin."),
              h("div", { className: "blank-adds" },
                h("button", { className: "blank-add", onClick: () => insertEl("heading") }, "Heading"),
                h("button", { className: "blank-add", onClick: () => insertEl("paragraph") }, "Text"),
                h("button", { className: "blank-add", onClick: () => insertEl("image") }, "Illustration"))) : null,
            page.els.slice().sort((a, b) => (a.z || 1) - (b.z || 1)).map((e) => {
              const norm = Object.assign({}, e, { x: 0, y: 0, w: 100, h: e.h != null ? 100 : null });
              const txt = BBR.isText(e);
              const editing = editingId === e.id;
              const on = selIds.includes(e.id);
              const handles = on && selIds.length === 1 && !editing && !areaMode;
              return h("div", { key: e.id, "data-id": e.id, "data-text": txt ? "true" : null, "data-kind": e.kind,
                className: "el" + (on ? " selected" : ""),
                style: { left: e.x + "%", top: e.y + "%", width: e.w + "%", height: e.h != null ? e.h + "%" : "auto", zIndex: editing ? 99 : (e.z || 1) },
                onMouseDown: (ev) => { if (!dirty && !editing && !areaMode) startDrag(ev, e); },
                onDoubleClick: (ev) => onElDoubleClick(ev, e) },
                h("div", { style: { width: "100%", height: "100%" } },
                  editing
                    ? h(BBTXT.InlineText, { el: norm, style: BBR.textStyle(norm, pageCtx),
                        onCommit: (t) => commitTextEdit(e.id, t), onFormat: (k) => toggleFormat(e, k) })
                    : renderEl(norm, pageCtx)),
                handles ? (e.h != null
                  ? CORNERS.map((c) => h("span", { key: c, className: "rz rz-" + c, title: "Resize (hold Shift to keep proportions)", onMouseDown: (ev) => startResize(ev, e, c) }))
                  : ["w", "e"].map((c) => h("span", { key: c, className: "rz rz-" + c, title: "Resize width", onMouseDown: (ev) => startResize(ev, e, c) }))) : null);
            }),
            // selected area — the part of the page the assistant is asked about
            area && (area.drawing || area.pageId === page.id) ? h("div", { className: "area-box" + (chatBusy && !area.drawing ? " working" : ""),
                style: { left: area.x + "%", top: area.y + "%", width: area.w + "%", height: area.h + "%" } },
              area.drawing ? null : h("span", { className: "area-tag" }, chatBusy ? "Assistant is working here" : "Selected area"),
              area.drawing || chatBusy ? null : h("button", { className: "area-x", title: "Clear selected area", "aria-label": "Clear selected area",
                onMouseDown: (ev) => ev.stopPropagation(), onClick: clearArea }, Svg(PATHS.x, 11))) : null,
            aiWorking && !dirty ? h("div", { className: "ai-chip" }, h("span", { className: "dotpulse" }), "Assistant is working on this page") : null
          ),
          // settings-changed overlay
          regenOverlay
        )
      ),
      // properties dock
      propsVisible ? h(PropsDock, { els: selEls, rightOffset: aiOpen ? aiWidth : 0, onAction, onPatch: (p) => patchEls(selRef.current, p), onClose: () => setSelIds([]) }) : null,
      // AI assistant dock (resizable) — chat, voice, attachments, task list
      aiOpen ? h(BBAI.AiDock, { width: aiWidth, page: page, thread: chatThread, busy: chatBusy,
        tasks: ai.tasks, input: chatInput, onInput: setChatInput, bodyRef: chatBodyRef,
        task: mode === "pages" ? pageTask : null, taskHandlers: taskHandlers,
        area: area && !area.drawing && area.pageId === page.id ? area : null, onClearArea: clearArea,
        areaMode: areaMode, canArea: mode === "pages" && !dirty, onToggleArea: toggleAreaMode,
        onSend: sendChat, onAct: onChatAct, onClose: () => setAiOpen(false),
        onResizeStart: (e) => { e.preventDefault(); resizeRef.current = true; document.body.classList.add("resizing"); },
        onGoto: (t) => { const i = pages.findIndex((p) => p.id === t.pageId); if (i >= 0) { setCurrent(i); ai.background(t.id, false); } },
        onRetry: (id) => ai.retry(id) }) : null,
      // contextual text formatting — on screen only while a text element is live
      mode === "pages" && tbEl && tbRect && !dirty && !areaMode ? h(BBTXT.TextToolbar, { el: tbEl, rect: tbRect, theme: theme, page: page,
        onPatch: (p) => patchEls([tbEl.id], p) }) : null,
      activity ? h(BBSCN.ActivityPopover, { x: activity.x, y: activity.y, tasks: ai.tasks,
        onClose: () => setActivity(null),
        onGoto: (t) => { const i = pages.findIndex((p) => p.id === t.pageId); if (i >= 0) { setCurrent(i); ai.background(t.id, false); } },
        onRetry: (id) => ai.retry(id), onDismiss: (id) => ai.dismiss(id) }) : null,
      insertMenu ? h(BBR.Menu, { x: insertMenu.x, y: insertMenu.y, align: "end", onClose: () => setInsertMenu(null), items: [
        { label: "Heading", icon: "heading", onSelect: () => insertEl("heading") },
        { label: "Text", icon: "type", onSelect: () => insertEl("paragraph") },
        { label: "Illustration", icon: "image", onSelect: () => insertEl("image") }
      ] }) : null,
      charDlg ? h(BBWS.CharacterDialog, { char: charDlg.char, onClose: () => setCharDlg(null),
        onSave: (d) => charDlg.char ? editChar(charDlg.char.id, d) : addChar(d) }) : null,
      charRemove ? h(AlertDialog, { open: true, onOpenChange: () => setCharRemove(null),
        title: "Remove " + charRemove.name + "?", description: removeCopy(charRemove),
        cancelText: "Cancel", actionText: "Remove character", destructive: true,
        onAction: () => removeChar(charRemove) }) : null,
      pageDelete != null ? h(AlertDialog, { open: true, onOpenChange: () => setPageDelete(null),
        title: "Delete this page?",
        description: "“" + pages[pageDelete].name + "” will be removed from your storybook. Undo brings it straight back.",
        cancelText: "Cancel", actionText: "Delete page", destructive: true,
        onAction: () => { deletePage(pageDelete); setPageDelete(null); } }) : null,
      shortcuts ? h(ShortcutsDialog, { onClose: () => setShortcuts(false) }) : null,
      // marquee + hidden inputs
      marquee ? h("div", { className: "marquee", style: { left: marquee.x, top: marquee.y, width: marquee.w, height: marquee.h } }) : null,
      h("input", { type: "color", ref: colorRef, style: { display: "none" }, onChange: onColor }),
      h("input", { type: "file", ref: fileRef, accept: "image/*", style: { display: "none" }, onChange: onFile }),
      h("input", { type: "file", ref: charFileRef, accept: "image/*", style: { display: "none" }, onChange: onCharUploadFile }),
      uploadError ? h(Dialog, {open: true, label: "Image upload failed", onOpenChange: () => setUploadError("")}, h(DialogHeader,null,h(DialogTitle,null,"Image upload failed"),h(DialogDescription,null,uploadError)),h(DialogFooter,null,h(Button,{onClick: () => setUploadError("")},"Got it"))) : null,
      // export / share dialogs
      exportOpen ? h(ExportDialog, { pages, dims, theme, settings: Object.assign({}, settings, { palette: BBTH.paletteOf(theme) }),
        pageCount: pages.length,
        serverPdfHref: backendEnabled ? pdfHref((function () { try { return localStorage.getItem("bb_current") || ""; } catch (e) { return ""; } })()) : null,
        onClose: () => setExportOpen(false) }) : null,
      // Backend progress / error banner for flows that run outside the "Regenerate
      // all" overlay (manuscript upload -> parse job). Guarded so the local demo
      // never shows it.
      (!dirty && (genProgress || genError)) ? h("div", { className: "gen-banner", role: "status" },
        genError
          ? h("span", null, h(LIcon, { name: "circle-alert", size: 15 }), " ", genError,
              h("button", { className: "set-link", style: { marginLeft: 8 }, onClick: () => setGenError("") }, "Dismiss"))
          : h("span", null, h("span", { className: "spin" }, Svg(PATHS.refresh, 15)), " Server: ",
              (genProgress.stage || "working"), (genProgress.pct ? " (" + genProgress.pct + "%)" : "…"))) : null,
      shareOpen ? h(ShareDialog, { onExport: () => {setShareOpen(false); setExportOpen(true);}, settings: settings, onClose: () => setShareOpen(false) }) : null,
      preview ? h(BBPV.PreviewBook, { pages: pages, settings: settings, theme: theme, dims: dims, tasks: ai.tasks,
        title: title, onClose: () => setPreview(false), onShare: () => setShareOpen(true),
        onRetry: (id) => ai.retry(id) }) : null,
      // floating assistant — the one way into the existing chat dock (the manuscript has its own writing assistant)
      mode !== "manuscript" ? h("div", { className: "ai-fab-wrap", style: { "--dock": dockRight + "px" } },
        callout && !aiOpen && !dirty ? h("div", { className: "ai-callout", role: "button", tabIndex: 0,
          onClick: openAi, onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openAi(); } } },
          h("span", null, "I\u2019m here to help you"),
          h("button", { className: "ai-callout-x", "aria-label": "Dismiss", title: "Dismiss",
            onClick: (e) => { e.stopPropagation(); hideCallout(); } }, Svg(PATHS.x, 12))) : null,
        h("button", { className: "ai-fab", "data-on": aiOpen, "aria-label": aiOpen ? "Close AI assistant" : "Open AI assistant",
          title: "Ask Blue Balloon", disabled: dirty, onClick: () => { if (aiOpen) setAiOpen(false); else openAi(); } },
          BBAI.botSvg(28))
      ) : null
    );
  }

  export default Workspace;
