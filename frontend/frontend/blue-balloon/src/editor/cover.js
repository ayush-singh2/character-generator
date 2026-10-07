import React from 'react';
import ModuleBBTH from './book-theme.js';
import ModuleBBR from './render.js';
import ModuleBBCV from './cover.js';
import ModuleShadcnUiDesignSystem_6211ba from './ui.jsx';
import { Icon as LucideIcon, LUCIDE_PATHS } from './icons.js';
/* Blue Balloon — Cover designer mode. ModuleBBCV
   Edits the book's cover page directly (the same page Pages and Preview show),
   so nothing is duplicated: title, author, image, background and layers all
   live on that one page record. */

  const h = React.createElement;
  const { useState, useRef, useEffect } = React;
  const Icon = LucideIcon;
  const DS = ModuleShadcnUiDesignSystem_6211ba;
  const { Button } = DS;
  const BBR = ModuleBBR, BBTH = ModuleBBTH;

  Object.assign(LUCIDE_PATHS, {
    "square": '<rect width="18" height="18" x="3" y="3" rx="2"/>',
    "circle": '<circle cx="12" cy="12" r="10"/>',
    "paint-bucket": '<path d="m19 11-8-8-8.6 8.6a2 2 0 0 0 0 2.8l5.2 5.2c.8.8 2 .8 2.8 0L19 11Z"/><path d="m5 2 5 5"/><path d="M2 13h15"/><path d="M22 20a2 2 0 1 1-4 0c0-1.6 1.7-2.4 2-4 .3 1.6 2 2.4 2 4Z"/>',
    "zoom-in": '<circle cx="11" cy="11" r="8"/><line x1="21" x2="16.65" y1="21" y2="16.65"/><line x1="11" x2="11" y1="8" y2="14"/><line x1="8" x2="14" y1="11" y2="11"/>',
    "zoom-out": '<circle cx="11" cy="11" r="8"/><line x1="21" x2="16.65" y1="21" y2="16.65"/><line x1="8" x2="14" y1="11" y2="11"/>',
    "chevron-up": '<path d="m18 15-6-6-6 6"/>',
    "sliders-horizontal": '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/><line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/><line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/><line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="16" x2="16" y1="18" y2="18"/>',
    "shapes": '<path d="M8.3 10a.7.7 0 0 1-.626-1.079L11.4 3a.7.7 0 0 1 1.198-.043L16.3 8.9a.7.7 0 0 1-.572 1.1Z"/><rect x="3" y="14" width="7" height="7" rx="1"/><circle cx="17.5" cy="17.5" r="3.5"/>'
  });

  const ICON_OF = { title: "heading", subtitle: "type", heading: "heading", paragraph: "type", pageno: "type", image: "image", emblem: "sparkles", frame: "square", shape: "shapes" };
  const round1 = (n) => Math.round(n * 10) / 10;
  const ZOOMS = [0.25, 0.33, 0.5, 0.67, 0.8, 1, 1.25, 1.5, 2];

  function num(label, value, onChange, opts) {
    return h("label", { className: "cv-num" }, h("span", null, label),
      h("input", { className: "set-num", type: "number", value: value == null ? "" : value, step: (opts && opts.step) || 1,
        min: opts && opts.min, max: opts && opts.max, placeholder: opts && opts.placeholder,
        onChange: (e) => { const v = e.target.value; onChange(v === "" ? null : +v); } }));
  }
  const field = (k, ctl, extra) => h("div", { className: "cv-f" }, h("div", { className: "k" }, k, extra || null), ctl);
  function colorRow(value, onChange, onClear) {
    return h("div", { className: "cv-colorrow" },
      h("span", { className: "cv-sw", style: { background: value } }, h("input", { type: "color", value: value, onChange: (e) => onChange(e.target.value) })),
      h("span", { className: "hex" }, String(value).toUpperCase()),
      onClear ? h("button", { className: "cv-link", style: { marginLeft: "auto" }, onClick: onClear }, "Book style") : null);
  }

  function CoverMode(props) {
    const { page, dims, theme, selIds, setSelIds, patch, edit, addEl, onUpload, onAI, onBg, settings, onAuthor, onUseTitle, locked, overlay, onAddCover, aiOpen } = props;
    const [zoom, setZoom] = useState(null);       // null = fit
    const [fit, setFit] = useState(1);
    const [toolsOpen, setToolsOpen] = useState(() => window.innerWidth > 900);
    const [propsOpen, setPropsOpen] = useState(true);
    const [shapeMenu, setShapeMenu] = useState(null);
    const stageRef = useRef(null);
    const dragRef = useRef(null);
    const selRef = useRef(selIds); selRef.current = selIds;
    // the assistant dock takes the right edge: the properties panel steps aside until asked for
    useEffect(() => { if (aiOpen) setPropsOpen(false); }, [aiOpen]);

    useEffect(() => {
      const calc = () => { const n = stageRef.current; if (!n) return;
        setFit(Math.max(0.15, Math.min(1.5, Math.min((n.clientWidth - 80) / dims.w, (n.clientHeight - 80) / dims.h)))); };
      calc();
      const ro = new ResizeObserver(calc);
      if (stageRef.current) ro.observe(stageRef.current);
      return () => ro.disconnect();
    }, [dims.w, dims.h, toolsOpen, propsOpen]);
    const scale = zoom || fit;

    // drag to move, corner handle to resize — first movement lands in history, the rest is live
    useEffect(() => {
      const mv = (e) => {
        const d = dragRef.current; if (!d) return;
        if (!d.moved && Math.abs(e.clientX - d.sx) < 2 && Math.abs(e.clientY - d.sy) < 2) return;
        const live = d.moved; d.moved = true;
        const dx = (e.clientX - d.sx) / (dims.w * d.scale) * 100, dy = (e.clientY - d.sy) / (dims.h * d.scale) * 100;
        edit((els) => els.map((el) => {
          const o = d.orig[el.id]; if (!o) return el;
          if (d.type === "drag") return Object.assign({}, el, { x: round1(o.x + dx), y: round1(o.y + dy) });
          return Object.assign({}, el, { w: round1(Math.max(4, o.w + dx)), h: o.h != null ? round1(Math.max(3, o.h + dy)) : null });
        }), live);
      };
      const up = () => { dragRef.current = null; };
      window.addEventListener("mousemove", mv); window.addEventListener("mouseup", up);
      return () => { window.removeEventListener("mousemove", mv); window.removeEventListener("mouseup", up); };
    }, [dims.w, dims.h]);

    if (!page) return h("div", { className: "mode" }, h("div", { className: "cv-stage cv-none", style: { placeContent: "center" } },
      h("div", null, h("div", { style: { fontWeight: 600, marginBottom: 6 } }, "This book has no cover page"),
        h("div", { className: "cv-empty" }, "Add one to start designing. It appears first in Pages and in Preview Book."),
        h(Button, { style: { marginTop: 14 }, onClick: onAddCover }, h(Icon, { name: "plus", size: 15 }), "Add cover page"))));

    const ctx = { dims: dims, theme: theme, page: page };
    const sorted = page.els.slice().sort((a, b) => (a.z || 1) - (b.z || 1));
    const sel = page.els.filter((e) => selIds.includes(e.id));
    const one = sel.length === 1 ? sel[0] : null;
    const byLabel = (l) => page.els.find((e) => e.label === l && BBR.isText(e));
    const titleEl = byLabel("Title"), subEl = byLabel("Subtitle"), authEl = byLabel("Author");
    const start = (ev, e, type) => {
      if (locked) return;
      ev.stopPropagation(); ev.preventDefault();
      const ids = type === "resize" ? [e.id] : (selRef.current.includes(e.id) ? selRef.current : [e.id]);
      if (!selRef.current.includes(e.id)) setSelIds([e.id]);
      const orig = {}; page.els.forEach((x) => { if (ids.includes(x.id)) orig[x.id] = { x: x.x, y: x.y, w: x.w, h: x.h }; });
      dragRef.current = { type: type, ids: ids, sx: ev.clientX, sy: ev.clientY, scale: scale, orig: orig, moved: false };
    };
    function reorder(id, dir) {
      edit((els) => {
        const list = els.slice().sort((a, b) => (a.z || 1) - (b.z || 1));
        const i = list.findIndex((e) => e.id === id), j = i + dir;
        if (i < 0 || j < 0 || j >= list.length) return els;
        const t = list[i]; list[i] = list[j]; list[j] = t;
        const z = {}; list.forEach((e, k) => { z[e.id] = k + 1; });
        return els.map((e) => Object.assign({}, e, { z: z[e.id] }));
      });
    }
    const zoomStep = (dir) => { const cur = scale; const next = dir > 0 ? ZOOMS.find((z) => z > cur + 0.01) : ZOOMS.slice().reverse().find((z) => z < cur - 0.01); if (next) setZoom(next); };
    const del = (ids) => { edit((els) => els.filter((e) => !ids.includes(e.id))); setSelIds([]); };
    const P = (p, live) => patch(one ? [one.id] : selIds, p, live);

    // ---- properties ----
    let propsHead, propsSub, propsBody;
    const position = (el) => field("Position and size", h("div", { className: "cv-grid2" },
      num("X", round1(el.x), (v) => P({ x: v || 0 })), num("Y", round1(el.y), (v) => P({ y: v || 0 })),
      num("W", round1(el.w), (v) => P({ w: Math.max(4, v || 4) })),
      el.h != null ? num("H", round1(el.h), (v) => P({ h: Math.max(3, v || 3) })) : null));
    const opacity = (el) => field("Opacity", h("input", { className: "cv-range", type: "range", min: 0, max: 100, value: el.opacity,
      onChange: (e) => P({ opacity: +e.target.value }, true), onMouseUp: (e) => P({ opacity: +e.target.value }) }), h("span", null, el.opacity + "%"));
    const layerBtns = (el) => h("div", { className: "cv-grid2" },
      h(Button, { variant: "outline", size: "sm", onClick: () => patch([el.id], { z: Math.max.apply(null, page.els.map((e) => e.z || 1)) + 1 }) }, "To front"),
      h(Button, { variant: "outline", size: "sm", onClick: () => patch([el.id], { z: Math.min.apply(null, page.els.map((e) => e.z || 1)) - 1 }) }, "To back"));
    const removeBtn = (ids, label) => h(Button, { variant: "outline", size: "sm", className: "cv-danger", onClick: () => del(ids) }, h(Icon, { name: "trash", size: 14 }), label || "Remove");

    if (!one && sel.length > 1) {
      propsHead = sel.length + " elements"; propsSub = "Changes apply to all selected";
      propsBody = [opacity(sel[0]), removeBtn(selIds, "Remove all")];
    } else if (one && BBR.isText(one)) {
      const r = BBTH.resolveText(one, theme, page);
      propsHead = one.label; propsSub = "Text";
      propsBody = [
        field("Text", h("textarea", { className: "set-textarea", rows: 3, value: one.text || "",
          onChange: (e) => P({ text: e.target.value }, true), onBlur: (e) => P({ text: e.target.value }) })),
        field("Font", h("select", { className: "set-select", value: one.font || "", onChange: (e) => P({ font: e.target.value || null }) },
          [h("option", { key: "", value: "" }, "Book style (" + (r.family || "default") + ")")].concat(BBTH.FONTS.map((f) => h("option", { key: f, value: f }, f))))),
        h("div", { className: "cv-grid2" },
          field("Size", num("px", one.size != null ? one.size : r.fontSize, (v) => P({ size: v }), { min: 6, max: 160 })),
          field("Color", colorRow(r.color, (c) => P({ color: c, effect: "none" }), one.color ? () => P({ color: null }) : null))),
        field("Style", h("div", { className: "cv-tog" },
          h("button", { "data-on": r.fontWeight >= 600, title: "Bold", onClick: () => P({ bold: !(r.fontWeight >= 600) }) }, h(Icon, { name: "bold", size: 14 })),
          h("button", { "data-on": !!r.italic, title: "Italic", onClick: () => P({ italic: !r.italic }) }, h(Icon, { name: "italic", size: 14 })),
          h("button", { "data-on": !!one.underline, title: "Underline", onClick: () => P({ underline: !one.underline }) }, h(Icon, { name: "underline", size: 14 })))),
        field("Alignment", h("div", { className: "cv-tog" }, [["left", "align-left"], ["center", "align-center"], ["right", "align-right"]].map((a) =>
          h("button", { key: a[0], "data-on": r.align === a[0], title: "Align " + a[0], onClick: () => P({ align: a[0] }) }, h(Icon, { name: a[1], size: 14 }))))),
        position(one), opacity(one), layerBtns(one),
        one.label === "Title" && settings.name && one.text !== settings.name ? field("Book title", h(Button, { variant: "outline", size: "sm", onClick: onUseTitle }, "Use \u201c" + settings.name + "\u201d")) : null,
        BBTH.hasOverrides(one) ? h("button", { className: "cv-link", style: { alignSelf: "flex-start" }, onClick: () => P(BBTH.clearOverrides()) }, "Reset to book style") : null,
        removeBtn([one.id])
      ];
    } else if (one && (one.kind === "image" || one.kind === "emblem")) {
      propsHead = one.label; propsSub = one.kind === "emblem" ? "Logo" : "Image";
      propsBody = [
        field(one.kind === "emblem" ? "Logo" : "Image", h("div", { className: "cv-grid2" },
          h(Button, { variant: "outline", size: "sm", onClick: () => onUpload(one.id) }, h(Icon, { name: "upload", size: 14 }), "Upload"),
          h(Button, { variant: "outline", size: "sm", onClick: () => onAI(one.id) }, h(Icon, { name: "sparkles", size: 14 }), "Generate")),
          one.src ? h("button", { className: "cv-link", onClick: () => P({ src: null }) }, "Clear image") : null),
        one.kind === "emblem" ? field("Color", colorRow(one.color || theme.colors.accent, (c) => P({ color: c, effect: "none" }), one.color ? () => P({ color: null }) : null)) : null,
        position(one), opacity(one), layerBtns(one), removeBtn([one.id])
      ];
    } else if (one) {
      const isShape = one.kind === "shape";
      propsHead = one.label; propsSub = isShape ? "Shape" : "Frame";
      propsBody = [
        isShape ? field("Shape", h("div", { className: "cv-tog" },
          h("button", { "data-on": one.shape !== "circle", onClick: () => P({ shape: "rect", label: "Rectangle" }) }, "Rectangle"),
          h("button", { "data-on": one.shape === "circle", onClick: () => P({ shape: "circle", label: "Circle" }) }, "Circle"))) : null,
        field("Color", colorRow(one.color || theme.colors.accent, (c) => P({ color: c }), one.color ? () => P({ color: null }) : null)),
        isShape && one.shape !== "circle" ? field("Corner radius", num("px", one.radius || 0, (v) => P({ radius: Math.max(0, v || 0) }), { min: 0, max: 200 })) : null,
        position(one), opacity(one), layerBtns(one), removeBtn([one.id])
      ];
    } else {
      const bgNow = page.bg || null;
      const textField = (label, el, kind) => field(label, el
        ? h("input", { className: "set-input", value: el.text || "", placeholder: label,
            onChange: (e) => { patch([el.id], { text: e.target.value }, true); if (label === "Author") onAuthor(e.target.value, true); },
            onBlur: (e) => { patch([el.id], { text: e.target.value }); if (label === "Author") onAuthor(e.target.value); } })
        : h(Button, { variant: "outline", size: "sm", onClick: () => addEl(kind, { label: label, text: label === "Author" ? (settings.author || "Author name") : (label === "Title" ? settings.name : "Subtitle") }) }, h(Icon, { name: "plus", size: 13 }), "Add " + label.toLowerCase()),
        el && label === "Title" && settings.name && el.text !== settings.name ? h("button", { className: "cv-link", onClick: onUseTitle }, "Use book title") : null);
      propsHead = "Cover"; propsSub = "Click any element to edit it";
      propsBody = [
        textField("Title", titleEl, "title"), textField("Subtitle", subEl, "subtitle"), textField("Author", authEl, "subtitle"),
        field("Background", h("div", { className: "cv-swatches" },
          h("button", { className: "cv-sw", "data-on": !bgNow, title: "Book style", onClick: () => onBg(null), style: { background: BBTH.pageBg(Object.assign({}, page, { bg: null }), theme) } }),
          BBTH.paletteOf(theme).map((c) => h("button", { key: c, className: "cv-sw", "data-on": bgNow && String(bgNow).toUpperCase() === String(c).toUpperCase(), title: BBTH.nameColor(c), style: { background: c }, onClick: () => onBg(c) })),
          h("span", { className: "cv-sw custom", title: "Custom color" }, h(Icon, { name: "plus", size: 14 }),
            h("input", { type: "color", value: bgNow && BBTH.isHex(bgNow) ? bgNow : theme.colors.primary, onChange: (e) => onBg(e.target.value) }))),
          bgNow ? h("button", { className: "cv-link", onClick: () => onBg(null) }, "Book style") : null),
        h("div", { className: "cv-empty" }, "Title and author are shared with the manuscript\u2019s title page. Everything here shows up in Pages and Preview Book straight away.")
      ];
    }

    const tool = (icon, label, fn, disabled) => h("button", { className: "cv-tool", onClick: fn, disabled: !!disabled || locked }, h("span", { className: "ic" }, h(Icon, { name: icon, size: 15 })), label);
    const handleSize = 12 / scale;

    return h("div", { className: "mode cv" },
      toolsOpen ? h("div", { className: "cv-tools" },
        h("div", { className: "cv-props-h" },
          h("div", { style: { flex: 1 } }, h("div", { className: "t" }, "Tools")),
          h("button", { className: "panel-collapse", title: "Hide tools", onClick: () => setToolsOpen(false) }, h(Icon, { name: "panel-left", size: 15 }))),
        h("div", { className: "cv-sec" },
          h("div", { className: "cv-sec-k" }, "Add"),
          tool("type", "Text", () => { addEl("subtitle", { label: "Text", text: "New text" }); setPropsOpen(true); }),
          tool("image", "Image", () => { addEl("image", { label: "Image" }); setPropsOpen(true); }),
          tool("shapes", "Shape", (e) => { const r = e.currentTarget.getBoundingClientRect(); setShapeMenu({ x: r.right + 6, y: r.top }); }),
          tool("paint-bucket", "Background", () => { setSelIds([]); setPropsOpen(true); })),
        h("div", { className: "cv-sec", style: { paddingBottom: 0 } }, h("div", { className: "cv-sec-k" }, "Layers")),
        h("div", { className: "cv-layers" }, sorted.slice().reverse().map((e, i) =>
          h("div", { key: e.id, className: "cv-layer", "data-active": selIds.includes(e.id), role: "button", tabIndex: 0,
              onClick: () => { setSelIds([e.id]); setPropsOpen(true); } },
            h("span", { className: "ic" }, h(Icon, { name: ICON_OF[e.kind] || "square", size: 13 })),
            h("span", { className: "lb" }, e.label + (BBR.isText(e) && e.text ? " \u00b7 " + e.text : "")),
            h("span", { className: "ord" },
              h("button", { className: "cv-ord", title: "Move up", disabled: i === 0, onClick: (ev) => { ev.stopPropagation(); reorder(e.id, 1); } }, h(Icon, { name: "chevron-up", size: 13 })),
              h("button", { className: "cv-ord", title: "Move down", disabled: i === sorted.length - 1, onClick: (ev) => { ev.stopPropagation(); reorder(e.id, -1); } }, h(Icon, { name: "chevron-down", size: 13 })))))),
      ) : null,
      h("div", { className: "cv-stage" + (locked ? " locked" : ""), ref: stageRef, onMouseDown: (e) => { if (e.target === e.currentTarget) setSelIds([]); } },
        !toolsOpen ? h("button", { className: "icon-btn cv-drawer-btn l", title: "Show tools", onClick: () => setToolsOpen(true) }, h(Icon, { name: "panel-left", size: 15 })) : null,
        !propsOpen ? h("button", { className: "icon-btn cv-drawer-btn r", title: "Show properties", onClick: () => setPropsOpen(true) }, h(Icon, { name: "sliders-horizontal", size: 15 })) : null,
        h("div", { style: { width: dims.w * scale, height: dims.h * scale, flex: "0 0 auto", position: "relative" } },
          h("div", { className: "cv-page" + (locked ? " stale" : ""), style: { width: dims.w, height: dims.h, transform: "scale(" + scale + ")", transformOrigin: "top left", background: BBTH.pageBg(page, theme) },
              onMouseDown: (e) => { if (e.target === e.currentTarget) setSelIds([]); } },
            sorted.map((e) => {
              const norm = Object.assign({}, e, { x: 0, y: 0, w: 100, h: e.h != null ? 100 : null });
              const on = selIds.includes(e.id);
              return h("div", { key: e.id, className: "cv-el" + (on ? " selected" : ""), "data-id": e.id,
                  style: { left: e.x + "%", top: e.y + "%", width: e.w + "%", height: e.h != null ? e.h + "%" : "auto", zIndex: e.z || 1 },
                  onMouseDown: (ev) => start(ev, e, "drag") },
                h("div", { style: { width: "100%", height: "100%" } }, BBR.renderEl(norm, ctx)),
                on && selIds.length === 1 ? h("div", { className: "cv-handle", title: "Resize", style: { width: handleSize, height: handleSize, borderWidth: Math.max(1, 1.5 / scale) },
                  onMouseDown: (ev) => start(ev, e, "resize") }) : null);
            }))),
        h("div", { className: "cv-zoom" },
          h("button", { className: "zb", title: "Zoom out", onClick: () => zoomStep(-1) }, h(Icon, { name: "zoom-out", size: 15 })),
          h("span", { className: "pct" }, Math.round(scale * 100) + "%"),
          h("button", { className: "zb", title: "Zoom in", onClick: () => zoomStep(1) }, h(Icon, { name: "zoom-in", size: 15 })),
          h("button", { className: "zb fit", title: "Fit to screen", "data-on": !zoom, onClick: () => setZoom(null) }, "Fit")),
        overlay || null),
      propsOpen ? h("div", { className: "cv-props" },
        h("div", { className: "cv-props-h" },
          h("div", { style: { flex: 1, minWidth: 0 } }, h("div", { className: "t" }, propsHead), h("div", { className: "s" }, propsSub)),
          one || sel.length ? h("button", { className: "panel-collapse", title: "Deselect", onClick: () => setSelIds([]) }, h(Icon, { name: "x", size: 15 })) : null,
          h("button", { className: "panel-collapse", style: { marginLeft: 0 }, title: "Hide properties", onClick: () => setPropsOpen(false) }, h(Icon, { name: "panel-right", size: 15 }))),
        h("div", { className: "cv-props-b" }, propsBody)) : null,
      shapeMenu ? h(BBR.Menu, { x: shapeMenu.x, y: shapeMenu.y, onClose: () => setShapeMenu(null), items: [
        { label: "Rectangle", icon: "square", onSelect: () => addEl("shape", { label: "Rectangle", shape: "rect" }) },
        { label: "Circle", icon: "circle", onSelect: () => addEl("shape", { label: "Circle", shape: "circle" }) }
      ] }) : null
    );
  }

  export default { CoverMode };
