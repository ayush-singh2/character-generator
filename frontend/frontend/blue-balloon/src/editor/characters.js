import { storage as localStorage } from '../services/storage';
import React from 'react';
import ModuleBBR from './render.js';
import ModuleShadcnUiDesignSystem_6211ba from './ui.jsx';
import { Icon as LucideIcon, LUCIDE_PATHS } from './icons.js';
/* BB artists — Workspace side panels: Characters editor, Export & Share dialogs */

  const h = React.createElement;
  const { useState, useRef, useEffect } = React;
  const Icon = LucideIcon;
  const DS = ModuleShadcnUiDesignSystem_6211ba;
  const { Button, Input, Select, Dialog, DialogHeader, DialogTitle, DialogDescription, DialogFooter } = DS;
  const ROLES = ["Protagonist", "Companion", "Parent", "Mentor", "Narrator", "Villain", "Supporting character", "Other"];

  // ---- extra glyphs ----
  Object.assign(LUCIDE_PATHS, {
    "layers": '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"/><path d="M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"/><path d="M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17"/>',
    "image": '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
    "pencil": '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
    "book-open": '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
    "minus": '<path d="M5 12h14"/>',
    "upload": '<path d="M12 3v12"/><path d="m7 8 5-5 5 5"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "copy": '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "share-2": '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" x2="15.42" y1="13.51" y2="17.49"/><line x1="15.41" x2="8.59" y1="6.51" y2="10.49"/>',
    "refresh-cw": '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/>',
    "file-down": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M12 18v-6"/><path d="m9 15 3 3 3-3"/>',
    "eye": '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>'
  });

  const STORE = "bb_characters";
  const APPLIED = "bb_characters_applied";
  const VAR_COLORS = ["#6366f1", "#0e7490", "#b45309", "#be185d", "#15803d", "#7c3aed"];

  // sensible defaults so the workspace always has something to show
  const DEFAULT_CHARS = {
    ram:   { mode: "constant", design: { type: "ai", versions: 3, changes: ["Weathered indigo cloak", "Calmer expression"] }, variants: [] },
    shyam: { mode: "variants", design: null, variants: [
      { id: "v1", name: "Everyday", source: { type: "ai", versions: 2, changes: ["Green tunic, rolled sleeves"] }, ranges: [[1, 14]] },
      { id: "v2", name: "Festival", source: { type: "upload", name: "shyam-festival.png" }, ranges: [[15, 32]] }
    ] },
    gita:  { mode: "constant", design: { type: "upload", name: "gita-reference.png" }, variants: [] },
    sita:  { mode: "constant", design: { type: "ai", versions: 2, changes: ["Star-dotted midnight shawl"] }, variants: [] }
  };

  function loadCharData() {
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(STORE) || "{}"); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
    const out = {};
    const ids = Object.keys(DEFAULT_CHARS).concat(Object.keys(saved).filter((k) => !(k in DEFAULT_CHARS)));
    ids.forEach((id) => {
      const d = DEFAULT_CHARS[id] || { mode: "constant", design: null, variants: [] };
      const s = saved[id];
      const meaningful = s && (s.design || (s.variants && s.variants.some((v) => v && v.source)));
      out[id] = meaningful ? s : d;
    });
    // make sure variant objects are complete
    Object.values(out).forEach((c) => { c.variants = (c.variants || []).map((v, i) => Object.assign({ id: "v" + (i + 1), name: "Variant " + (i + 1), source: null, ranges: [] }, v)); });
    return out;
  }
  function saveCharData(d) { try { localStorage.setItem(STORE, JSON.stringify(d)); } catch (e) { /* Optional browser capability or local cache is unavailable. */ } }

  function totalBookPages(settings) {
    const n = parseInt(String((settings && settings.length) || "32").replace(/[^0-9]/g, ""), 10);
    return n && n > 0 ? n : 32;
  }

  // ---- tiny svg helper ----
  function Svg(inner, size) {
    return h("svg", { width: size || 16, height: size || 16, viewBox: "0 0 24 24", fill: "none",
      stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round",
      dangerouslySetInnerHTML: { __html: inner } });
  }

  const fmtRange = ([a, b]) => a === b ? "" + a : a + "\u2013" + b;

  // ===== compact page-range editor =====
  function RangeEditor({ ranges, total, onChange }) {
    const [adding, setAdding] = useState(false);
    const [from, setFrom] = useState("");
    const [to, setTo] = useState("");
    const fromRef = useRef(null);
    const start = () => { setAdding(true); setFrom(""); setTo(""); setTimeout(() => fromRef.current && fromRef.current.focus(), 0); };
    const a = parseInt(from, 10), b = parseInt(to || from, 10);
    const valid = from !== "" && a >= 1 && a <= total && b >= a && b <= total;
    const commit = () => { if (!valid) return; onChange([...ranges, [a, b]].sort((x, y) => x[0] - y[0])); setAdding(false); setFrom(""); setTo(""); };
    const remove = (i) => onChange(ranges.filter((_, j) => j !== i));
    return h("div", { className: "cp-ranges" },
      h("div", { className: "cp-ranges-l" }, h(Icon, { name: "book-open", size: 11 }), "Appears on pages"),
      h("div", { className: "cp-rchips" },
        ranges.map((r, i) => h("span", { className: "cp-rchip", key: i }, fmtRange(r),
          h("span", { className: "rm", title: "Remove", onClick: () => remove(i) }, Svg('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>', 10)))),
        adding
          ? h("span", { className: "cp-raddform" },
              h("input", { ref: fromRef, type: "number", min: 1, max: total, placeholder: "1", value: from,
                onChange: (ev) => setFrom(ev.target.value),
                onKeyDown: (ev) => { if (ev.key === "Enter") commit(); if (ev.key === "Escape") setAdding(false); } }),
              h("span", { className: "dash" }, "\u2013"),
              h("input", { type: "number", min: 1, max: total, placeholder: "" + total, value: to,
                onChange: (ev) => setTo(ev.target.value),
                onKeyDown: (ev) => { if (ev.key === "Enter") commit(); if (ev.key === "Escape") setAdding(false); } }),
              h("button", { className: "ok", disabled: !valid, onClick: commit, title: "Add" }, h(Icon, { name: "check", size: 13 }))
            )
          : h("button", { className: "cp-raddbtn", onClick: start }, h(Icon, { name: "plus", size: 11 }), "Add")
      )
    );
  }

  // ===== change menu (upload here / design with AI) =====
  function ChangeButton({ label, onUpload, onAI }) {
    const [open, setOpen] = useState(false);
    const [flip, setFlip] = useState(false);
    const ref = useRef(null);
    useEffect(() => {
      if (!open) return;
      const btn = ref.current && ref.current.querySelector(".cp-change");
      if (btn) {
        const r = btn.getBoundingClientRect();
        const spaceBelow = window.innerHeight - r.bottom;
        setFlip(spaceBelow < 150);
      }
      const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
      document.addEventListener("mousedown", close);
      return () => document.removeEventListener("mousedown", close);
    }, [open]);
    return h("div", { className: "cp-change-wrap", ref: ref },
      h("button", { className: "cp-change", "data-open": open, onClick: () => setOpen((v) => !v) },
        Svg('<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>', 12),
        label || "Change", h(Icon, { name: "chevron-down", size: 13, style: { opacity: 0.6 } })),
      open ? h("div", { className: "cp-menu", "data-flip": flip },
        h("button", { className: "cp-menu-row", onClick: () => { setOpen(false); onUpload(); } },
          h("span", { className: "cp-menu-ic up" }, h(Icon, { name: "upload", size: 14 })),
          h("div", null, h("div", { className: "cp-menu-t" }, "Upload image"), h("div", { className: "cp-menu-s" }, "Replace it here"))),
        h("button", { className: "cp-menu-row", onClick: () => { setOpen(false); onAI(); } },
          h("span", { className: "cp-menu-ic ai" }, h(Icon, { name: "pencil", size: 14 })),
          h("div", null, h("div", { className: "cp-menu-t" }, "Design with AI"), h("div", { className: "cp-menu-s" }, "Open the AI studio")))
      ) : null
    );
  }

  function Thumb({ source, color, name }) {
    const ai = source && source.type === "ai";
    const img = source && source.preview;
    return h("div", { className: "cp-thumb", style: { background: img ? "#000" : color } },
      img ? h("img", { src: img, alt: name })
        : h("div", { className: "cp-thumb-ph" }, ai ? h(Icon, { name: "image", size: 18 }) : (name ? name[0] : h(Icon, { name: "image", size: 16 }))),
      source ? h("span", { className: "cp-thumb-bdg" }, h(Icon, { name: "image", size: 9 }), ai ? "AI" : "Upload") : null
    );
  }

  // ===== Characters panel =====
  // the compact card shows who the character is; design, variants and page ranges
  // live in an expandable detail (from the ••• menu) so nothing is lost
  function previewOf(c, st) {
    if (st.design && st.design.preview) return st.design.preview;
    const v = (st.variants || []).find((x) => x.source && x.source.preview);
    if (v) return v.source.preview;
    return (c.ref && c.ref.preview) || null;
  }
  function CharacterDetail({ c, st, total, onUpload, onAI, onRanges }) {
    const isVar = st.mode === "variants" && st.variants && st.variants.length;
    return isVar
      ? h("div", { className: "cp-body" },
          st.variants.map((v, i) => h("div", { className: "cp-var", key: v.id },
            h("div", { className: "cp-var-h" },
              h("span", { className: "cp-vchip", style: { background: VAR_COLORS[i % VAR_COLORS.length] } }),
              h("span", { className: "cp-vname" }, v.name)),
            h("div", { className: "cp-var-body" },
              h(Thumb, { source: v.source, color: VAR_COLORS[i % VAR_COLORS.length], name: c.name }),
              h("div", { className: "cp-var-right" },
                h(RangeEditor, { ranges: v.ranges || [], total, onChange: (rs) => onRanges(c.id, v.id, rs) }),
                h(ChangeButton, { onUpload: () => onUpload(c.id, v.id), onAI: () => onAI(c.id, v.id) }))))))
      : h("div", { className: "cp-body" },
          h("div", { className: "cp-design" },
            h(Thumb, { source: st.design, color: c.color, name: c.name }),
            h("div", { className: "cp-design-right" },
              h("div", { className: "cp-design-meta" }, st.design
                ? (st.design.type === "ai" ? "AI-designed" : (st.design.name || "Uploaded design"))
                : "No design yet"),
              h(ChangeButton, { onUpload: () => onUpload(c.id, null), onAI: () => onAI(c.id, null) }))));
  }

  function CharactersPanel({ chars, charData, total, sceneCount, onUpload, onAI, onRanges, onAdd, onEdit, onDuplicate, onRemove, onScenes }) {
    const [menu, setMenu] = useState(null);   // { x, y, char }
    const [open, setOpen] = useState(null);   // id of the card whose design detail is expanded
    const itemsFor = (c) => [
      { label: "Edit character", icon: "pencil", onSelect: () => onEdit(c) },
      { label: open === c.id ? "Hide design & pages" : "Design & pages", icon: "image", onSelect: () => setOpen(open === c.id ? null : c.id) },
      { label: "View scenes", icon: "book-open", onSelect: () => onScenes(c) },
      { label: "Duplicate character", icon: "copy", onSelect: () => onDuplicate(c) },
      { separator: true },
      { label: "Remove character", icon: "trash", destructive: true, onSelect: () => onRemove(c) }
    ];
    if (!chars.length) return h("div", { className: "panel-body" },
      h("div", { className: "cp-empty" },
        h("div", { className: "cp-empty-t" }, "No characters yet"),
        h("div", { className: "cp-empty-s" }, "Add the people, creatures or personalities that appear in your story."),
        h(Button, { onClick: onAdd }, h(Icon, { name: "plus", size: 15 }), "Add character")));
    return h("div", { className: "panel-body" },
      h("div", { className: "cp-hint" }, "Add, edit or remove characters at any point."),
      h("div", { className: "cp-list" },
        chars.map((c) => {
          const st = charData[c.id] || { mode: "constant", design: null, variants: [] };
          const img = previewOf(c, st);
          const menuOpen = !!(menu && menu.char && menu.char.id === c.id);
          return h("div", { className: "cpc", key: c.id, "data-menu": menuOpen, "data-open": open === c.id },
            h("div", { className: "cpc-row", onDoubleClick: () => onEdit(c) },
              h("div", { className: "cpc-av", style: { background: img ? "#000" : c.color } },
                img ? h("img", { src: img, alt: c.name }) : h("span", null, c.name[0])),
              h("div", { className: "cpc-txt" },
                h("div", { className: "cpc-nm", title: c.name }, c.name),
                h("div", { className: "cpc-rl", title: c.role }, c.role)),
              h("div", { className: "cpc-acts" },
                h("button", { className: "cpc-edit", title: "Edit character", "aria-label": "Edit " + c.name,
                  onClick: (e) => { e.stopPropagation(); onEdit(c); } }, h(Icon, { name: "pencil", size: 14 })),
                h("button", { className: "cpc-more", title: "More", "aria-label": "Options for " + c.name, "data-open": menuOpen,
                  onClick: (e) => { e.stopPropagation(); const r = e.currentTarget.getBoundingClientRect(); setMenu({ x: r.right, y: r.bottom + 5, char: c }); } },
                  h(Icon, { name: "ellipsis", size: 15 })))),
            open === c.id ? h("div", { className: "cpc-detail" },
              h(CharacterDetail, { c, st, total, onUpload, onAI, onRanges })) : null
          );
        })
      ),
      h("button", { className: "set-add", style: { marginTop: 12 }, onClick: onAdd }, h(Icon, { name: "plus", size: 13 }), "Add character"),
      menu ? h(ModuleBBR.Menu, { x: menu.x, y: menu.y, align: "end", items: itemsFor(menu.char), onClose: () => setMenu(null) }) : null
    );
  }

  // ===== Add / edit character =====
  function CharacterDialog({ char, onSave, onClose }) {
    const editing = !!(char && char.id);
    const [name, setName] = useState((char && char.name) || "");
    const [role, setRole] = useState((char && char.role) || "Supporting character");
    const [ref_, setRef] = useState((char && char.ref) || null);
    const fileRef = useRef(null);
    const ok = !!name.trim();
    const save = () => { if (ok) onSave({ name: name.trim(), role: role, ref: ref_ }); };
    const pick = (e) => {
      const f = e.target.files[0]; if (!f) return;
      const r = new FileReader();
      r.onload = () => setRef({ name: f.name, preview: r.result });
      r.readAsDataURL(f); e.target.value = "";
    };
    return h(Dialog, { open: true, onOpenChange: onClose },
      h(DialogHeader, null,
        h(DialogTitle, null, editing ? "Edit character" : "Add character"),
        h(DialogDescription, null, editing
          ? "Details update everywhere this character is listed. Pages you have already made stay exactly as they are."
          : "The new character becomes available for any page or scene. Your book is not regenerated.")),
      h("div", { className: "ch-form" },
        h("label", { className: "ch-f" }, h("span", { className: "ch-lab" }, "Name"),
          h(Input, { value: name, autoFocus: true, placeholder: "e.g. Ram",
            onChange: (e) => setName(e.target.value),
            onKeyDown: (e) => { if (e.key === "Enter") save(); } })),
        h("label", { className: "ch-f" }, h("span", { className: "ch-lab" }, "Role"),
          h(Select, { value: role, onChange: (e) => setRole(e.target.value), options: ROLES })),
        h("div", { className: "ch-f" },
          h("span", { className: "ch-lab" }, "Reference", h("span", { className: "ch-opt" }, "Optional")),
          h("div", { className: "ch-ref" },
            h("div", { className: "ch-ref-th" }, ref_ && ref_.preview
              ? h("img", { src: ref_.preview, alt: name })
              : h(Icon, { name: "image", size: 17 })),
            h("div", { style: { flex: 1, minWidth: 0 } },
              h("div", { className: "ch-ref-s" }, ref_ ? (ref_.name || "Reference added") : "An image helps keep the look consistent.")),
            h(Button, { variant: "outline", size: "sm", onClick: () => fileRef.current.click() }, ref_ ? "Replace" : "Upload"),
            ref_ ? h("button", { className: "set-x", title: "Remove reference", onClick: () => setRef(null) }, h(Icon, { name: "x", size: 13 })) : null,
            h("input", { type: "file", ref: fileRef, accept: "image/*", style: { display: "none" }, onChange: pick })))),
      h(DialogFooter, null,
        h(Button, { variant: "outline", onClick: onClose }, "Cancel"),
        h(Button, { disabled: !ok, onClick: save }, editing ? "Save character" : "Add character"))
    );
  }


export default { loadCharData, saveCharData, totalBookPages, CharactersPanel, CharacterDialog, ROLES, STORE, APPLIED };
