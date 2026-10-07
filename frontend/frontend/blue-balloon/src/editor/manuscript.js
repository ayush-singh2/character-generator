import DOMPurify from 'dompurify';
import { aiService } from '../services/ai';
import React from 'react';
import ModuleBBR from './render.js';
import ModuleBBSCN from './scene-builder.js';
import ModuleBBAI from './assistant.js';
import ModuleBBMS from './manuscript.js';
import ModuleShadcnUiDesignSystem_6211ba from './ui.jsx';
import { Icon as LucideIcon, LUCIDE_PATHS } from './icons.js';
/* Blue Balloon — Manuscript editor mode. ModuleBBMS
   The manuscript lives on the document (doc.manuscript) next to pages; chapters
   that came from pages stay linked (pageId) so edits flow both ways. */

  const h = React.createElement;
  const { useState, useRef, useEffect, useLayoutEffect } = React;
  const Icon = LucideIcon;
  const DS = ModuleShadcnUiDesignSystem_6211ba;
  const { Button } = DS;

  Object.assign(LUCIDE_PATHS, {
    "file-pen": '<path d="M12.5 22H18a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v9.5"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M13.378 15.626a1 1 0 1 0-3.004-3.004l-5.01 5.012a2 2 0 0 0-.506.854l-.837 2.87a.5.5 0 0 0 .62.62l2.87-.837a2 2 0 0 0 .854-.506z"/>',
    "book-image": '<path d="m20 13.7-2.1-2.1a2 2 0 0 0-2.8 0L9.7 17"/><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"/><circle cx="10" cy="8" r="2"/>',
    "list": '<line x1="8" x2="21" y1="6" y2="6"/><line x1="8" x2="21" y1="12" y2="12"/><line x1="8" x2="21" y1="18" y2="18"/><line x1="3" x2="3.01" y1="6" y2="6"/><line x1="3" x2="3.01" y1="12" y2="12"/><line x1="3" x2="3.01" y1="18" y2="18"/>',
    "list-ordered": '<line x1="10" x2="21" y1="6" y2="6"/><line x1="10" x2="21" y1="12" y2="12"/><line x1="10" x2="21" y1="18" y2="18"/><path d="M4 6h1v4"/><path d="M4 10h2"/><path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/>',
    "text-quote": '<path d="M17 6H3"/><path d="M21 12H8"/><path d="M21 18H8"/><path d="M3 12v6"/>',
    "sparkles": '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/>',
    "panel-right": '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M15 3v18"/>',
    "wand": '<path d="M15 4V2"/><path d="M15 16v-2"/><path d="M8 9h2"/><path d="M20 9h2"/><path d="M17.8 11.8 19 13"/><path d="M15 9h.01"/><path d="M17.8 6.2 19 5"/><path d="m3 21 9-9"/><path d="M12.2 6.2 11 5"/>',
    "undo-2": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11"/>',
    "redo-2": '<path d="m15 14 5-5-5-5"/><path d="M20 9H9.5A5.5 5.5 0 0 0 4 14.5A5.5 5.5 0 0 0 9.5 20H13"/>',
    "menu": '<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>',
    "loader": '<path d="M12 2v4"/><path d="m16.2 7.8 2.9-2.9"/><path d="M18 12h4"/><path d="m16.2 16.2 2.9 2.9"/><path d="M12 18v4"/><path d="m4.9 19.1 2.9-2.9"/><path d="M2 12h4"/><path d="m4.9 4.9 2.9 2.9"/>'
  });

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  function plain(html) { const d = document.createElement("div"); d.innerHTML = html || ""; return (d.textContent || "").replace(/\s+/g, " ").trim(); }
  function blocks(html) {
    const d = document.createElement("div"); d.innerHTML = html || "";
    const out = []; d.querySelectorAll("p,h1,h2,h3,li,blockquote").forEach((n) => { const t = (n.textContent || "").trim(); if (t) out.push(t); });
    return out.length ? out : (plain(html) ? [plain(html)] : []);
  }
  const words = (html) => { const t = plain(html); return t ? t.split(/\s+/).length : 0; };
  const toHtml = (text) => String(text || "").split(/\n{2,}|\n/).map((p) => p.trim()).filter(Boolean).map((p) => "<p>" + esc(p) + "</p>").join("");

  /* ---- derive the manuscript from what the book already has ---- */
  function derive(pages, settings) {
    const cover = (pages || []).find((p) => p.kind === "cover");
    const byLabel = (l) => { const e = cover && cover.els.find((x) => x.label === l); return e ? (e.text || "") : ""; };
    const author = (settings && settings.author) || byLabel("Author") || "";
    const inner = (pages || []).filter((p) => p.kind !== "cover");
    const chapters = inner.map((pg, i) => {
      const hd = pg.els.find((e) => e.kind === "heading");
      const paras = pg.els.filter((e) => e.kind === "paragraph" && (e.text || "").trim());
      return { id: "ch-" + pg.id, kind: "chapter", pageId: pg.id,
        title: (hd && hd.text) || "Chapter " + (i + 1),
        html: paras.map((p) => "<p>" + esc(p.text) + "</p>").join("") || "<p></p>" };
    });
    return { sections: [
      { id: "ms-title", kind: "front", fixed: "title", title: "Title Page",
        html: "<h1>" + esc((settings && settings.name) || "Untitled") + "</h1>" + (byLabel("Subtitle") ? "<p>" + esc(byLabel("Subtitle")) + "</p>" : "") + (author ? "<p>" + esc(author) + "</p>" : "") },
      { id: "ms-copyright", kind: "front", fixed: "copyright", title: "Copyright",
        html: "<p>Copyright \u00a9 " + new Date().getFullYear() + (author ? " " + esc(author) : "") + ". All rights reserved.</p><p>No part of this book may be reproduced in any form without written permission from the author.</p>" },
      { id: "ms-toc", kind: "toc", fixed: "toc", title: "Table of Contents", html: "" }
    ].concat(chapters, [
      { id: "ms-ack", kind: "back", title: "Acknowledgements", html: "" },
      { id: "ms-about", kind: "back", title: "About the Author", html: "" }
    ]) };
  }
  /* page → manuscript: a linked chapter mirrors its page's heading + story text */
  function syncFromPage(ms, pg) {
    if (!ms || !pg || pg.kind === "cover") return ms;
    const i = ms.sections.findIndex((s) => s.pageId === pg.id);
    if (i < 0) return ms;
    const hd = pg.els.find((e) => e.kind === "heading");
    const paras = pg.els.filter((e) => e.kind === "paragraph" && (e.text || "").trim());
    const sec = ms.sections[i];
    const next = Object.assign({}, sec, { title: (hd && hd.text) || sec.title,
      html: paras.length ? paras.map((p) => "<p>" + esc(p.text) + "</p>").join("") : sec.html });
    if (next.title === sec.title && next.html === sec.html) return ms;
    return Object.assign({}, ms, { sections: ms.sections.map((s, j) => j === i ? next : s) });
  }
  /* manuscript → page: heading follows the chapter title, story text follows the body */
  function syncPage(pg, sec) {
    let hdDone = false, pDone = false;
    const text = blocks(sec.html).join(" ");
    const els = pg.els.map((e) => {
      if (e.kind === "heading" && !hdDone) { hdDone = true; return Object.assign({}, e, { text: sec.title }); }
      if (e.kind === "paragraph" && !pDone) { pDone = true; return Object.assign({}, e, { text: text }); }
      return e;
    });
    return Object.assign({}, pg, { els: els });
  }
  /* after pages are rebuilt from the manuscript, chapters point at the new pages */
  function relink(ms, pages) {
    if (!ms) return ms;
    const inner = (pages || []).filter((p) => p.kind !== "cover");
    let k = 0;
    return Object.assign({}, ms, { sections: ms.sections.map((s) => s.kind !== "chapter" ? s
      : Object.assign({}, s, { pageId: inner[k] ? inner[k++].id : null })) });
  }
  const chaptersOf = (ms) => ms.sections.filter((s) => s.kind === "chapter");

  const qs = (c) => { try { return document.queryCommandState(c); } catch (e) { return false; } };
  const BLOCKS = [["p", "Paragraph"], ["h2", "Heading"], ["h3", "Subheading"], ["blockquote", "Quote"]];
  const ACTIONS = [
    { id: "rewrite", label: "Rewrite", icon: "wand" },
    { id: "clarity", label: "Improve clarity", icon: "eye" },
    { id: "shorten", label: "Shorten", icon: "minus" },
    { id: "expand", label: "Expand", icon: "plus" },
    { id: "tone", label: "Change tone", icon: "type" },
    { id: "grammar", label: "Fix grammar", icon: "check" },
    { id: "continue", label: "Continue writing", icon: "pencil" }
  ];
  const TONES = ["Warmer", "Playful", "Calmer", "Simpler", "More formal"];
  const INSTR = {
    rewrite: "Rewrite this passage, keeping its meaning and roughly its length.",
    clarity: "Improve the clarity and flow of this passage without changing what happens.",
    shorten: "Shorten this passage by about a third, keeping the voice.",
    expand: "Expand this passage with a little more sensory detail, keeping the voice.",
    grammar: "Fix grammar, spelling and punctuation only. Change nothing else.",
    continue: "Continue writing from where this passage ends. Write two or three new sentences only."
  };
  function fallback(action, t) {
    const BBSCN = ModuleBBSCN;
    const sents = t.match(/[^.!?]+[.!?]+["\u201d']?\s*/g) || [t];
    if (action === "shorten") return sents.slice(0, Math.max(1, Math.ceil(sents.length * 0.6))).join("").trim();
    if (action === "grammar") return t.replace(/\s+/g, " ").replace(/\s+([,.!?;:])/g, "$1").replace(/(^|[.!?]\s+)([a-z])/g, (m, a, b) => a + b.toUpperCase()).trim();
    const canned = BBSCN ? BBSCN.cannedScene(t, sents.length).tx : "";
    if (action === "continue") return canned;
    if (action === "expand") return t.trim() + " " + canned;
    return canned || t;
  }

  /* ===== section navigation ===== */
  function Nav({ ms, sectionId, open, onSelect, onAdd, onRename, onRemove }) {
    const [adding, setAdding] = useState(false);
    const [title, setTitle] = useState("");
    const [renaming, setRenaming] = useState(null);
    const [menu, setMenu] = useState(null);
    const chapters = chaptersOf(ms);
    const commitAdd = () => { const t = title.trim(); setAdding(false); setTitle(""); onAdd(t || "Chapter " + (chapters.length + 1)); };
    const item = (s, n) => renaming && renaming.id === s.id
      ? h("input", { key: s.id, className: "ms-rename", autoFocus: true, value: renaming.v,
          onChange: (e) => setRenaming({ id: s.id, v: e.target.value }),
          onBlur: () => { const v = renaming.v.trim(); if (v && v !== s.title) onRename(s.id, v); setRenaming(null); },
          onKeyDown: (e) => { e.stopPropagation(); if (e.key === "Enter") e.target.blur(); if (e.key === "Escape") setRenaming(null); } })
      : h("div", { key: s.id, className: "ms-item", role: "button", tabIndex: 0, "data-active": s.id === sectionId,
          onClick: () => onSelect(s.id), onKeyDown: (e) => { if (e.key === "Enter") onSelect(s.id); },
          onDoubleClick: () => { if (!s.fixed) setRenaming({ id: s.id, v: s.title }); } },
          n != null ? h("span", { className: "n" }, n) : h(Icon, { name: s.kind === "toc" ? "list" : "file-text", size: 14, style: { color: "var(--muted-foreground)", flex: "0 0 auto" } }),
          h("span", { className: "t" }, s.title),
          s.fixed ? null : h("button", { className: "more", title: "Section options", "data-open": !!(menu && menu.s.id === s.id),
            onClick: (e) => { e.stopPropagation(); const r = e.currentTarget.getBoundingClientRect(); setMenu({ x: r.right, y: r.bottom + 4, s: s }); } },
            h(Icon, { name: "ellipsis", size: 14 })));
    return h("div", { className: "ms-nav", "data-open": open },
      h("div", { className: "panel-head" }, h("div", { className: "t" }, "Manuscript"),
        h("div", { className: "s" }, chapters.length + (chapters.length === 1 ? " chapter" : " chapters") + " \u00b7 " + ms.sections.reduce((a, s) => a + words(s.html), 0) + " words")),
      h("div", { className: "ms-nav-body" },
        h("div", { className: "ms-grp" }, "Front matter"),
        ms.sections.filter((s) => s.kind === "front" || s.kind === "toc").map((s) => item(s)),
        h("div", { className: "ms-grp" }, "Chapters"),
        chapters.map((s, i) => item(s, i + 1)),
        adding ? h("div", { className: "ms-addform" },
            h("input", { autoFocus: true, placeholder: "Chapter title", value: title, onChange: (e) => setTitle(e.target.value),
              onKeyDown: (e) => { e.stopPropagation(); if (e.key === "Enter") commitAdd(); if (e.key === "Escape") { setAdding(false); setTitle(""); } } }),
            h(Button, { size: "sm", onClick: commitAdd }, "Add"))
          : h("button", { className: "ms-add", onClick: () => setAdding(true) }, h(Icon, { name: "plus", size: 13 }), "Add chapter"),
        h("div", { className: "ms-grp" }, "Back matter"),
        ms.sections.filter((s) => s.kind === "back").map((s) => item(s))),
      menu ? h(ModuleBBR.Menu, { x: menu.x, y: menu.y, align: "end", onClose: () => setMenu(null), items: [
        { label: "Rename", icon: "pencil", onSelect: () => setRenaming({ id: menu.s.id, v: menu.s.title }) },
        { separator: true },
        { label: menu.s.kind === "chapter" ? "Delete chapter" : "Delete section", icon: "trash", destructive: true,
          disabled: menu.s.kind === "chapter" && chapters.length <= 1, onSelect: () => onRemove(menu.s.id) },
        menu.s.pageId ? { note: "This chapter is linked to a page. Deleting it leaves the page in place." } : null
      ] }) : null);
  }

  /* ===== the mode ===== */
  function ManuscriptMode(props) {
    const { ms, sectionId, onSelect, onSection, onAdd, onRemove, settings } = props;
    const secs = ms.sections;
    const sec = secs.find((s) => s.id === sectionId) || secs.find((s) => s.kind === "chapter") || secs[0];
    const readOnly = sec.kind === "toc";
    const [navOpen, setNavOpen] = useState(false);
    const [aiOpen, setAiOpen] = useState(false);
    const [fmt, setFmt] = useState({});
    const [titleEdit, setTitleEdit] = useState(null);
    const [selText, setSelText] = useState("");
    const [busy, setBusy] = useState(false);
    const [sugg, setSugg] = useState(null);
    const [tone, setTone] = useState(TONES[0]);
    const edRef = useRef(null);
    const selRef = useRef(null);
    const timer = useRef(null);
    const secRef = useRef(sec); secRef.current = sec;

    // track the caret: formatting state for the toolbar, selection for the assistant
    useEffect(() => {
      const on = () => {
        const n = edRef.current, s = document.getSelection();
        if (!n || !s || !s.rangeCount || !n.contains(s.anchorNode)) return;
        const t = s.toString();
        if (t.trim()) { selRef.current = s.getRangeAt(0).cloneRange(); setSelText(t); } else { selRef.current = null; setSelText(""); }
        let block = ""; try { block = String(document.queryCommandValue("formatBlock") || "").toLowerCase(); } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
        setFmt({ b: qs("bold"), i: qs("italic"), u: qs("underline"), ul: qs("insertUnorderedList"), ol: qs("insertOrderedList"),
          al: qs("justifyLeft"), ac: qs("justifyCenter"), ar: qs("justifyRight"), block: BLOCKS.some((b) => b[0] === block) ? block : "p" });
      };
      document.addEventListener("selectionchange", on);
      return () => document.removeEventListener("selectionchange", on);
    }, []);
    useEffect(() => { setSugg(null); setSelText(""); selRef.current = null; setTitleEdit(null); }, [sec.id]);
    // external changes (undo, page edits) land in the editor when it is not being typed in
    useLayoutEffect(() => {
      const n = edRef.current; if (!n || readOnly) return;
      const html = DOMPurify.sanitize(sec.html || "");
      if (n.innerHTML !== html && document.activeElement !== n) n.innerHTML = html;
    }, [sec.id, sec.html, readOnly]);

    function flush() {
      clearTimeout(timer.current); timer.current = null;
      const n = edRef.current, s = secRef.current;
      if (n && s.kind !== "toc" && n.innerHTML !== (s.html || "")) onSection(s.id, { html: DOMPurify.sanitize(n.innerHTML) });
    }
    function onInput() {
      const n = edRef.current; if (n) n.setAttribute("data-empty", plain(n.innerHTML) ? "false" : "true");
      clearTimeout(timer.current); timer.current = setTimeout(flush, 600);
    }
    useEffect(() => () => flush(), []);
    function exec(cmd, val) {
      const n = edRef.current; if (!n || readOnly) return;
      n.focus(); document.execCommand(cmd, false, val || null); onInput();
    }
    function link() {
      const url = window.prompt("Link address", "https://");
      if (url && /^https?:\/\//i.test(url)) exec("createLink", url);
    }
    const commitTitle = () => { const v = (titleEdit || "").trim(); setTitleEdit(null); if (v && v !== sec.title) onSection(sec.id, { title: v }); };

    // ---- assistant: suggestions only, nothing lands until accepted ----
    async function run(action) {
      const whole = plain(sec.html);
      const target = selText.trim() || whole;
      if (!target && action !== "continue") return;
      setBusy(true); setSugg(null);
      const inst = action === "tone" ? "Rewrite this passage in a " + tone.toLowerCase() + " tone." : INSTR[action];
      let text, offline = false;
      try {
        if (!aiService || !aiService.complete) throw new Error("no-ai");
        const out = await aiService.complete('You are helping an author edit the manuscript of a children\u2019s book called "' + (settings.name || "Untitled") + '" (section: ' + sec.title + '). ' + inst + ' Reply with ONLY the resulting text \u2014 no preamble, no quotes.\n\n' + (target || whole));
        text = (out || "").trim().replace(/^["\u201c]|["\u201d]$/g, "");
        if (!text) throw new Error("empty");
      } catch (e) { text = fallback(action, target || whole); offline = true; }
      setSugg({ action: action, label: action === "tone" ? "Change tone \u00b7 " + tone : ACTIONS.find((a) => a.id === action).label, text: text, sel: !!selText.trim(), offline: offline });
      setBusy(false);
    }
    function accept() {
      const n = edRef.current; if (!n || !sugg) return;
      n.focus();
      if (sugg.action === "continue") n.innerHTML += toHtml(sugg.text);
      else if (sugg.sel && selRef.current) {
        try { const s = document.getSelection(); s.removeAllRanges(); s.addRange(selRef.current); document.execCommand("insertText", false, sugg.text); }
        catch (e) { n.innerHTML = toHtml(sugg.text); }
      } else n.innerHTML = toHtml(sugg.text);
      setSugg(null); selRef.current = null; setSelText("");
      flush();
    }

    const tb = (name, title, on, fn) => h("button", { className: "tt-b", title: title, "aria-label": title, "data-on": !!on, disabled: readOnly,
      onMouseDown: (e) => { e.preventDefault(); fn(); } }, h(Icon, { name: name, size: 15 }));
    const sep = () => h("span", { className: "tt-sep" });
    const chapters = chaptersOf(ms);
    const chapterNo = sec.kind === "chapter" ? chapters.indexOf(sec) + 1 : null;

    return h("div", { className: "mode ms" },
      h(Nav, { ms: ms, sectionId: sec.id, open: navOpen, onSelect: (id) => { flush(); onSelect(id); setNavOpen(false); },
        onAdd: (t) => { flush(); onAdd(t); }, onRename: (id, t) => onSection(id, { title: t }), onRemove: onRemove }),
      h("div", { className: "ms-main" },
        h("div", { className: "ms-tb" },
          h("button", { className: "tt-b ms-drawer-btn", title: "Sections", onClick: () => setNavOpen((v) => !v) }, h(Icon, { name: "menu", size: 16 })),
          h("div", { className: "ms-tb-scroll" },
          tb("undo-2", "Undo", false, () => exec("undo")), tb("redo-2", "Redo", false, () => exec("redo")), sep(),
          h("select", { className: "ms-block", "aria-label": "Text style", value: fmt.block || "p", disabled: readOnly,
            onMouseDown: (e) => e.stopPropagation(), onChange: (e) => exec("formatBlock", "<" + e.target.value + ">") },
            BLOCKS.map((b) => h("option", { key: b[0], value: b[0] }, b[1]))), sep(),
          tb("bold", "Bold", fmt.b, () => exec("bold")), tb("italic", "Italic", fmt.i, () => exec("italic")), tb("underline", "Underline", fmt.u, () => exec("underline")), sep(),
          tb("align-left", "Align left", fmt.al, () => exec("justifyLeft")), tb("align-center", "Align center", fmt.ac, () => exec("justifyCenter")), tb("align-right", "Align right", fmt.ar, () => exec("justifyRight")), sep(),
          tb("list", "Bulleted list", fmt.ul, () => exec("insertUnorderedList")), tb("list-ordered", "Numbered list", fmt.ol, () => exec("insertOrderedList")),
          tb("text-quote", "Quote", fmt.block === "blockquote", () => exec("formatBlock", fmt.block === "blockquote" ? "<p>" : "<blockquote>")), sep(),
          tb("link", "Add link", false, link)),
          h("button", { className: "tt-b ms-ai-toggle", "data-on": aiOpen, title: "Writing assistant",
            onClick: () => setAiOpen((v) => !v) }, ModuleBBAI.botSvg(16), "Assistant")),
        h("div", { className: "ms-scroll", onMouseDown: (e) => { if (e.target === e.currentTarget && edRef.current) edRef.current.focus(); } },
          h("div", { className: "ms-sheet" },
            sec.fixed ? h("div", { className: "ms-title", style: { cursor: "default" } }, sec.title)
              : h("input", { className: "ms-title", "aria-label": "Section title", placeholder: "Untitled chapter",
                  value: titleEdit != null ? titleEdit : sec.title,
                  onChange: (e) => setTitleEdit(e.target.value), onBlur: commitTitle,
                  onKeyDown: (e) => { e.stopPropagation(); if (e.key === "Enter") e.target.blur(); if (e.key === "Escape") setTitleEdit(null); } }),
            h("div", { className: "ms-meta" },
              chapterNo ? h("span", null, "Chapter " + chapterNo) : h("span", null, sec.kind === "back" ? "Back matter" : "Front matter"),
              readOnly ? null : h(React.Fragment, null, h("span", null, "\u00b7"), h("span", null, words(sec.html) + " words")),
              sec.pageId ? h(React.Fragment, null, h("span", null, "\u00b7"), h("span", { title: "Edits here update the story text on the linked page" }, "Linked to a page")) : null),
            readOnly
              ? h("div", { className: "ms-toc" },
                  chapters.map((c, i) => h("button", { key: c.id, className: "ms-toc-row", onClick: () => onSelect(c.id) },
                    h("span", { className: "tt" }, c.title), h("span", { className: "dots" }), h("span", { className: "pg" }, i + 1))),
                  h("div", { className: "ms-toc-note" }, "Builds itself from your chapters. Rename or reorder chapters in the list on the left."))
              : h("div", { key: sec.id, className: "ms-editor", ref: edRef, contentEditable: true, suppressContentEditableWarning: true,
                  spellCheck: true, "data-placeholder": sec.kind === "chapter" ? "Start writing\u2026" : "Add text for this section\u2026",
                  "data-empty": plain(sec.html) ? "false" : "true", style: { position: "relative" },
                  onInput: onInput, onBlur: flush,
                  onKeyDown: (e) => { e.stopPropagation(); if (e.key === "Tab") { e.preventDefault(); exec(e.shiftKey ? "outdent" : "indent"); } } }))),
      ),
      h("div", { className: "ms-ai", "data-open": aiOpen },
        h("div", { className: "ms-ai-h" },
          h("span", { className: "ic" }, ModuleBBAI.botSvg(18)),
          h("div", { style: { flex: 1 } }, h("div", { className: "t" }, "Writing assistant"), h("div", { className: "s" }, "Suggestions only \u2014 you decide what stays")),
          h("button", { className: "panel-collapse", title: "Hide", onClick: () => setAiOpen(false) }, h(Icon, { name: "x", size: 15 }))),
        h("div", { className: "ms-ai-body" },
          readOnly ? h("div", { className: "cv-empty" }, "The table of contents is generated for you. Open a chapter to work with the assistant.")
          : h(React.Fragment, null,
            selText.trim() ? h("div", { className: "ms-sel" }, h("b", null, "Selected: "), selText.trim())
              : h("div", { className: "ms-sel" }, "Select some text to work on just that passage. With nothing selected, actions apply to the whole section."),
            ACTIONS.map((a) => h("button", { key: a.id, className: "ms-act", disabled: busy, onClick: () => run(a.id) },
              h("span", { className: "ic" }, h(Icon, { name: a.icon, size: 14 })), a.label,
              a.id === "tone" ? h("select", { value: tone, onClick: (e) => e.stopPropagation(), onChange: (e) => { e.stopPropagation(); setTone(e.target.value); } },
                TONES.map((t) => h("option", { key: t }, t))) : null)),
            busy ? h("div", { className: "ms-busy" }, h("span", { className: "spin" }, h(Icon, { name: "loader", size: 15 })), "Working on it\u2026") : null,
            sugg ? h("div", { className: "ms-sugg" },
              h("div", { className: "ms-sugg-k" }, h("span", null, sugg.label), sugg.offline ? h("span", { title: "The assistant isn\u2019t reachable in this preview, so this is a sample." }, "Sample") : null),
              h("div", { className: "ms-sugg-t" }, sugg.text),
              h("div", { className: "ms-sugg-b" },
                h(Button, { size: "sm", onClick: accept }, h(Icon, { name: "check", size: 14 }), sugg.action === "continue" ? "Add to section" : (sugg.sel ? "Replace selection" : "Replace section")),
                h(Button, { size: "sm", variant: "outline", onClick: () => setSugg(null) }, "Reject"),
                h(Button, { size: "sm", variant: "ghost", onClick: () => run(sugg.action) }, "Try again"))) : null,
            h("div", { className: "ms-hint" }, "Accepted changes go into the manuscript like any other edit, so Undo always brings the previous words back."))))
    );
  }

  export default { derive, syncFromPage, syncPage, relink, plain, blocks, words, esc, toHtml, chaptersOf, ManuscriptMode };
