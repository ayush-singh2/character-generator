import React from 'react';
import ModuleBBR from './render.js';
import { Icon as LucideIcon, LUCIDE_PATHS } from './icons.js';
/* BB artists — workspace Pages sidebar: add / duplicate / rename / delete / drag-reorder */

  const h = React.createElement;
  const { useState, useRef, useEffect } = React;

  const isBlank = (pg) => !(pg.els || []).some((e) => e.kind !== "pageno");

  function PagesPanel(props) {
    const BBR = ModuleBBR;
    const Icon = LucideIcon;
    const { pages, current, ctx, locked, note, filter, review, onSelect, onNew, onDup, onDelete,
      onRename, onMove, onReviewed, onReviewedAll, onClearFilter } = props;
    const [menu, setMenu] = useState(null);         // { x, y, i }
    const [renaming, setRenaming] = useState(null); // { i, value }
    const [drag, setDrag] = useState(null);
    const [dropAt, setDropAt] = useState(null);
    const renameRef = useRef(null);

    useEffect(() => { if (renaming && renameRef.current) { renameRef.current.focus(); renameRef.current.select(); } }, [renaming && renaming.i]);

    const visible = pages.map((p, i) => ({ p: p, i: i }))
      .filter((x) => !filter || (x.p.chars || []).indexOf(filter.id) >= 0);

    const startRename = (i) => setRenaming({ i: i, value: pages[i].name });
    const commitRename = () => {
      if (!renaming) return;
      const v = (renaming.value || "").trim();
      if (v && v !== pages[renaming.i].name) onRename(renaming.i, v);
      setRenaming(null);
    };

    const itemsFor = (i) => {
      const pg = pages[i];
      const last = pages.length <= 1;
      return [
        { label: "Duplicate page", icon: "copy", onSelect: () => onDup(i) },
        { label: "Rename page", icon: "pencil", onSelect: () => startRename(i) },
        { separator: true },
        { label: "Move to beginning", icon: "arrow-up-to-line", disabled: i === 0, onSelect: () => onMove(i, 0) },
        { label: "Move to end", icon: "arrow-down-to-line", disabled: i === pages.length - 1, onSelect: () => onMove(i, pages.length) },
        pg.review ? { separator: true } : null,
        pg.review ? { label: "Mark as reviewed", icon: "check", onSelect: () => onReviewed(i) } : null,
        { separator: true },
        { label: "Delete page", icon: "trash", destructive: !last, disabled: last, onSelect: last ? null : () => onDelete(i) },
        last ? { note: "Your storybook must contain at least one page." } : null
      ];
    };

    const openMenu = (e, i) => {
      e.preventDefault(); e.stopPropagation();
      setMenu({ x: e.clientX, y: e.clientY + 6, i: i });
    };

    const card = (pg, i) => h("div", { className: "pc-wrap", key: pg.id, "data-dragging": drag === i,
      draggable: !locked && !filter && !renaming,
      onDragStart: (e) => { setDrag(i); try {
          e.dataTransfer.effectAllowed = "copyMove";
          e.dataTransfer.setData("text/plain", String(i));   // reorder within the panel
          // Also advertise the page as a chat reference: dropping the thumbnail
          // on the AI composer attaches it (by backend id) so "use this page" works.
          const im = (pg.els || []).find((x) => x.kind === "image");
          e.dataTransfer.setData("application/x-bb-page", JSON.stringify({
            id: pg.backendId != null ? String(pg.backendId) : null,
            name: pg.name, url: im ? im.src : null }));
        } catch (err) { /* Optional browser capability or local cache is unavailable. */ } },
      onDragEnd: () => { setDrag(null); setDropAt(null); },
      onDragOver: (e) => { if (drag == null) return; e.preventDefault();
        const r = e.currentTarget.getBoundingClientRect();
        setDropAt(e.clientY < r.top + r.height / 2 ? i : i + 1); },
      onDrop: (e) => { e.preventDefault(); if (drag != null && dropAt != null && dropAt !== drag && dropAt !== drag + 1) onMove(drag, dropAt); setDrag(null); setDropAt(null); } },
      dropAt === i ? h("div", { className: "pc-drop" }) : null,
      dropAt === pages.length && i === pages.length - 1 ? h("div", { className: "pc-drop bottom" }) : null,
      h("div", { className: "pagecard" + (locked ? " stale" : ""), "data-active": i === current, role: "button", tabIndex: 0, "aria-label": pg.name, "aria-pressed": i === current, onKeyDown: (e) => {if(e.target !== e.currentTarget) return; if(e.key === "Enter" || e.key === " ") {e.preventDefault(); onSelect(i);}},
          onClick: () => onSelect(i), onContextMenu: locked ? null : (e) => openMenu(e, i) },
        h("div", { className: "thumb-wrap" },
          BBR.Thumb(pg, ctx),
          isBlank(pg) ? h("span", { className: "pc-blank" }, "Blank page") : null),
        pg.generating
          ? h("span", { className: "pc-badge gen", title: "The assistant is building this scene" }, h(Icon, { name: "loader", size: 9, className: "spin" }), "Generating")
          : pg.review ? h("span", { className: "pc-badge", title: "Flagged for review — " + pg.review }, h(Icon, { name: "flag", size: 9 }), "Review") : null,
        locked ? null : h("button", { className: "pc-more", draggable: false, title: "Page options",
          "aria-label": "Page options for " + pg.name, "data-open": !!(menu && menu.i === i),
          onMouseDown: (e) => e.stopPropagation(), onClick: (e) => openMenu(e, i) }, h(Icon, { name: "ellipsis", size: 15 })),
        h("div", { className: "pc-foot" },
          renaming && renaming.i === i
            ? h("input", { ref: renameRef, className: "pc-rename", value: renaming.value,
                onClick: (e) => e.stopPropagation(),
                onChange: (e) => setRenaming({ i: i, value: e.target.value }),
                onBlur: commitRename,
                onKeyDown: (e) => { e.stopPropagation(); if (e.key === "Enter") commitRename(); if (e.key === "Escape") setRenaming(null); } })
            : h("span", { className: "pc-name", title: "Double-click to rename",
                onDoubleClick: (e) => { e.stopPropagation(); if (!locked) startRename(i); } }, pg.name),
          h("span", { className: "pc-idx" }, String(i + 1).padStart(2, "0")))
      ));

    return h("div", { className: "panel-body" },
      h("button", { className: "ms-add", disabled: locked, onClick: onNew }, h(Icon, { name: "plus", size: 14 }), "Add page"),
      note ? h("div", { className: "panel-note" }, note) : null,
      review && review.count ? h("div", { className: "panel-note warn" },
        h(Icon, { name: "flag", size: 13 }),
        h("span", null, review.count + (review.count === 1 ? " page needs" : " pages need") + " review after removing " + review.name),
        h("button", { className: "nlink", onClick: onReviewedAll }, "Mark all reviewed")) : null,
      filter ? h("div", { className: "pg-filter" },
        h(Icon, { name: "user", size: 13 }),
        h("span", null, h("span", { className: "n" }, filter.name), " \u00b7 ", visible.length, visible.length === 1 ? " page" : " pages"),
        h("button", { className: "backbtn x", style: { width: 26, height: 26, marginLeft: "auto" }, title: "Clear filter", onClick: onClearFilter },
          h(Icon, { name: "x", size: 13 }))) : null,
      filter && !visible.length
        ? h("div", { className: "cp-empty" },
            h("div", { className: "cp-empty-t" }, "No pages mention " + filter.name),
            h("div", { className: "cp-empty-s" }, "Add them to a page, or clear the filter to see the whole book."))
        : visible.map((x) => card(x.p, x.i)),
      menu ? h(BBR.Menu, { x: menu.x, y: menu.y, items: itemsFor(menu.i), onClose: () => setMenu(null) }) : null
    );
  }

  export default { PagesPanel, isBlank };
