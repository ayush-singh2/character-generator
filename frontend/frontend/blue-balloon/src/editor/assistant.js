import React from 'react';
import ModuleBBSCN from './scene-builder.js';
import ModuleBBAI from './assistant.js';
import { Icon as LucideIcon, LUCIDE_PATHS } from './icons.js';
/* Blue Balloon — AI assistant dock: storybook chat with voice input, attachments
   and actionable replies. Presentational only; the workspace owns the thread and
   the tasks. ModuleBBAI */

  const h = React.createElement;
  const { useState, useRef, useEffect } = React;
  const Icon = LucideIcon;
  const BBSCN = ModuleBBSCN;

  Object.assign(LUCIDE_PATHS, {
    "mic": '<path d="M12 19v3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><rect x="9" y="2" width="6" height="13" rx="3"/>',
    "paperclip": '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
    "square": '<rect width="12" height="12" x="6" y="6" rx="2"/>'
  });

  const MAX_BYTES = 10 * 1024 * 1024;
  const KINDS = [
    { kind: "image", label: "IMG", ext: ["png", "jpg", "jpeg", "webp"], mime: /^image\/(png|jpe?g|webp)$/i },
    { kind: "pdf", label: "PDF", ext: ["pdf"], mime: /pdf/i },
    { kind: "doc", label: "DOCX", ext: ["docx", "doc"], mime: /word|officedocument/i },
    { kind: "txt", label: "TXT", ext: ["txt"], mime: /^text\/plain$/i }
  ];
  const ACCEPT = ".png,.jpg,.jpeg,.webp,.pdf,.docx,.txt,image/png,image/jpeg,image/webp,application/pdf,text/plain";
  const FORMATS = "PNG, JPG, WEBP, PDF, DOCX or TXT \u00b7 up to 10 MB";
  function kindOf(file) {
    const ext = (file.name || "").split(".").pop().toLowerCase();
    const hit = KINDS.find((k) => k.mime.test(file.type || "") || k.ext.indexOf(ext) >= 0);
    return hit || null;
  }
  const fmtSize = (b) => b < 1024 ? b + " B" : b < 1048576 ? Math.round(b / 1024) + " KB" : (b / 1048576).toFixed(1) + " MB";

  function classify(text) {
    const s = (text || "").toLowerCase();
    if (/\b(scene|illustrat|draw|picture|artwork|next page|regenerate|generate)\b/.test(s)) return "scene";
    if (/\b(rewrite|re-write|shorten|expand|reword|tone|warmer|dialogue|copy|revise|text)\b/.test(s)) return "rewrite";
    return "chat";
  }

  const SUGGESTIONS = [
    "Generate a scene",
    "Rewrite this page warmer",
    "Shorten the text",
    "Suggest dialogue",
    "Illustration direction",
    "What happens next?"
  ];

  /* ---- voice input: real speech recognition when the browser has it ---- */
  function useMic(onTranscript) {
    const [state, setState] = useState("idle");
    const [secs, setSecs] = useState(0);
    const rec = useRef(null), timer = useRef(null), text = useRef(""), t0 = useRef(0);
    const FALLBACK = "Make this scene feel more magical and add Ram near the lantern.";
    const clear = () => { if (timer.current) clearInterval(timer.current); timer.current = null; };
    useEffect(() => () => { clear(); if (rec.current) { try { rec.current.abort(); } catch (e) { /* Optional browser capability or local cache is unavailable. */ } } }, []);
    function start() {
      if (timer.current) return;
      text.current = ""; setSecs(0); setState("recording");
      t0.current = Date.now();
      timer.current = setInterval(() => setSecs(Math.floor((Date.now() - t0.current) / 1000)), 400);
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) return;
      try {
        const r = new SR();
        r.continuous = true; r.interimResults = true; r.lang = "en-US";
        r.onresult = (ev) => { let s = ""; for (let i = 0; i < ev.results.length; i++) s += ev.results[i][0].transcript; text.current = s; };
        r.onerror = () => {};
        r.start();
        rec.current = r;
      } catch (e) { rec.current = null; }
    }
    function finish() {
      clear();
      if (rec.current) { try { rec.current.stop(); } catch (e) { /* Optional browser capability or local cache is unavailable. */ } }
      setState("processing");
      setTimeout(() => {
        const t = (text.current || "").trim();
        rec.current = null;
        setState("idle");
        onTranscript(t || FALLBACK);
      }, 950);
    }
    function cancel() {
      clear();
      if (rec.current) { try { rec.current.abort(); } catch (e) { /* Optional browser capability or local cache is unavailable. */ } }
      rec.current = null; setState("idle");
    }
    return { state: state, secs: secs, start: start, finish: finish, cancel: cancel };
  }

  const mmss = (s) => Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");

  function AttachChip({ file, onRemove }) {
    return h("div", { className: "ai-att" },
      file.kind === "image" && file.url
        ? h("img", { src: file.url, alt: "" })
        : h("span", { className: "ai-att-ic" }, file.label),
      h("div", { style: { minWidth: 0 } },
        h("div", { className: "ai-att-nm", title: file.name }, file.name),
        h("div", { className: "ai-att-sz" }, file.pageRef != null ? "Reference" : fmtSize(file.size))),
      onRemove ? h("button", { className: "ai-att-x", title: "Remove", "aria-label": "Remove " + file.name, onClick: onRemove },
        h(Icon, { name: "x", size: 12 })) : null);
  }

  function Composer({ value, onValue, onSend, busy, placeholder, areaOn, canArea, onArea }) {
    const [files, setFiles] = useState([]);
    const [err, setErr] = useState(null);
    const [focus, setFocus] = useState(false);
    const [drag, setDrag] = useState(false);
    const inputRef = useRef(null);
    const taRef = useRef(null);
    const mic = useMic((t) => {
      onValue(value ? value.replace(/\s*$/, " ") + t : t);
      setTimeout(() => { if (taRef.current) taRef.current.focus(); }, 0);
    });

    useEffect(() => {
      const n = taRef.current; if (!n) return;
      n.style.height = "auto";
      n.style.height = Math.min(124, n.scrollHeight) + "px";
    }, [value]);

    function add(list) {
      const next = [], bad = [];
      Array.from(list || []).forEach((f) => {
        const k = kindOf(f);
        if (!k) { bad.push({ why: "type", name: f.name }); return; }
        if (f.size > MAX_BYTES) { bad.push({ why: "size", name: f.name }); return; }
        next.push({ id: "f" + Date.now().toString(36) + next.length, name: f.name, size: f.size,
          kind: k.kind, label: k.label, url: k.kind === "image" ? URL.createObjectURL(f) : null });
      });
      if (bad.length) {
        const b = bad[0];
        setErr(b.why === "type"
          ? { t: "File type not supported.", s: "\u201c" + b.name + "\u201d can\u2019t be read. Accepted: " + FORMATS + "." }
          : { t: "This file is too large.", s: "\u201c" + b.name + "\u201d is over 10 MB. Please choose a smaller file." });
      } else setErr(null);
      if (next.length) setFiles((f) => f.concat(next));
    }
    // A page thumbnail dragged from the pages panel → attach it as a reference
    // (by backend id) instead of a file upload. Shows the page's art as the chip.
    function addPageRef(p) {
      setErr(null);
      setFiles((f) => p && p.id && !f.some((x) => x.pageRef === String(p.id))
        ? f.concat([{ id: "pg" + p.id, name: p.name || ("Page " + p.id), size: 0,
            kind: "image", label: "Page", url: p.url || null, pageRef: String(p.id) }])
        : f);
    }
    const remove = (id) => setFiles((f) => f.filter((x) => x.id !== id));
    const canSend = !busy && (!!(value || "").trim() || files.length > 0) && mic.state === "idle";
    function send() {
      if (!canSend) return;
      onSend({ text: (value || "").trim(), files: files });
      setFiles([]); setErr(null);
    }

    return h("div", { className: "ai-comp" },
      h("div", { className: "ai-box", "data-focus": focus, "data-drag": drag,
          onDragOver: (e) => { e.preventDefault(); setDrag(true); },
          onDragLeave: () => setDrag(false),
          onDrop: (e) => { e.preventDefault(); setDrag(false);
            const raw = (() => { try { return e.dataTransfer.getData("application/x-bb-page"); } catch (_) { return ""; } })();
            if (raw) { try { const p = JSON.parse(raw); if (p && p.id) { addPageRef(p); return; } } catch (_) { /* fall through to files */ } }
            add(e.dataTransfer.files); } },
        err ? h("div", { className: "ai-err" },
          h(Icon, { name: "circle-alert", size: 13, style: { flex: "0 0 auto", marginTop: 1 } }),
          h("div", null, h("b", null, err.t), " ", err.s),
          h("button", { className: "ai-att-x", title: "Dismiss", onClick: () => setErr(null) }, h(Icon, { name: "x", size: 11 }))) : null,
        files.length ? h("div", { className: "ai-atts" }, files.map((f) =>
          h(AttachChip, { key: f.id, file: f, onRemove: () => remove(f.id) }))) : null,
        mic.state !== "idle"
          ? h("div", { className: "ai-rec" },
              mic.state === "recording"
                ? h(React.Fragment, null,
                    h("span", { className: "lbl" }, "Listening\u2026"),
                    h("span", { className: "ai-wave" }, Array.from({ length: 16 }).map((_, i) =>
                      h("i", { key: i, style: { animationDelay: (i * 70) + "ms" } }))),
                    h("span", { className: "dur" }, mmss(mic.secs)),
                    h("button", { className: "ai-recbtn", onClick: mic.finish }, "Stop"),
                    h("button", { className: "ai-recbtn", onClick: mic.cancel }, "Cancel"))
                : h(React.Fragment, null,
                    h("span", { className: "spin", style: { color: "var(--destructive)", display: "grid" } }, h(Icon, { name: "loader", size: 14, className: "spin" })),
                    h("span", { className: "lbl" }, "Writing down what you said\u2026")))
          : h("textarea", { ref: taRef, rows: 1, placeholder: placeholder, value: value,
              onFocus: () => setFocus(true), onBlur: () => setFocus(false),
              onChange: (e) => onValue(e.target.value),
              onPaste: (e) => { const f = e.clipboardData && e.clipboardData.files; if (f && f.length) { e.preventDefault(); add(f); } },
              onKeyDown: (e) => { e.stopPropagation(); if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } } }),
        h("div", { className: "ai-tools" },
          h("button", { className: "ai-tool", title: "Attach an image, PDF or document", "aria-label": "Attach a file",
            onClick: () => inputRef.current.click() }, h(Icon, { name: "plus", size: 17 })),
          h("button", { className: "ai-tool", "data-on": mic.state !== "idle", title: mic.state === "idle" ? "Speak your request" : "Recording",
            "aria-label": "Voice input", onClick: () => mic.state === "recording" ? mic.finish() : (mic.state === "idle" ? mic.start() : null) },
            h(Icon, { name: "mic", size: 16 })),
          onArea ? h("button", { className: "ai-tool lbl", "data-active": !!areaOn, disabled: !canArea && !areaOn,
            title: areaOn ? "Cancel area selection" : "Pick a part of the page to change",
            "aria-label": "Select area", "aria-pressed": !!areaOn, onClick: onArea },
            h(Icon, { name: "square-mouse-pointer", size: 15 }), areaOn ? "Cancel" : "Select area") : null,
          h("button", { className: "ai-send", disabled: !canSend, onClick: send },
            "Send", h(Icon, { name: "send", size: 13 })))),
      h("div", { className: "ai-hint" }, h(Icon, { name: "paperclip", size: 11 }), FORMATS),
      h("input", { type: "file", ref: inputRef, accept: ACCEPT, multiple: true, style: { display: "none" },
        onChange: (e) => { add(e.target.files); e.target.value = ""; } }));
  }

  function TaskStrip({ tasks, onGoto, onRetry }) {
    const live = tasks.filter((t) => t.status !== "done" || t.background);
    if (!live.length) return null;
    return h("div", { className: "ai-tasks" },
      h("div", { className: "ai-tasks-k" }, "AI activity"),
      live.map((t) => h("div", { className: "ai-task", key: t.id },
        h("span", { className: "st" }, t.status === "running" ? h("span", { className: "dotpulse" })
          : t.status === "error" ? h(Icon, { name: "circle-alert", size: 13, style: { color: "var(--destructive)" } })
          : h(Icon, { name: "check", size: 13, style: { color: "#16a34a" } })),
        h("div", { className: "txt" },
          h("div", { className: "tt" }, t.pageName),
          h("div", { className: "ts" }, BBSCN.statusLine(t))),
        t.status === "error"
          ? h("button", { className: "go", onClick: () => onRetry(t.id) }, "Try again")
          : h("button", { className: "go", onClick: () => onGoto(t) }, t.status === "done" ? "Open" : "View"))));
  }

  /* Friendly assistant mark — a rounded speech-bubble face. Used on the floating
     assistant button and this dock's header, so both read as the same helper. */
  const BOT = '<path d="M12 2.9V5"/><circle cx="12" cy="2.1" r="1"/><rect x="4" y="5" width="16" height="11" rx="3.6"/>'
    + '<path d="M4 9.4a2.2 2.2 0 0 0 0 4.4"/><path d="M20 9.4a2.2 2.2 0 0 1 0 4.4"/>'
    + '<path d="M8.3 11.3c.55-.85 1.55-.85 2.1 0"/><path d="M13.6 11.3c.55-.85 1.55-.85 2.1 0"/>'
    + '<path d="M10.2 13.5c.9.85 2.7.85 3.6 0"/><path d="M9.4 16 8 20.1l4.3-4.1"/>';
  const botSvg = (size) => h("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round",
    dangerouslySetInnerHTML: { __html: BOT } });

  function AiDock(props) {
    const { width, page, thread, busy, tasks, input, onInput, onSend, onAct, onClose,
      onResizeStart, onGoto, onRetry, bodyRef, task, taskHandlers, area, onClearArea,
      areaMode, canArea, onToggleArea } = props;
    const running = tasks.filter((t) => t.status === "running").length;
    const areaCount = area && area.ids ? area.ids.length : 0;
    return h("div", { className: "rdock chat-dock", style: { right: 0, width: width } },
      h("div", { className: "chat-resize", title: "Drag to resize", onMouseDown: onResizeStart }),
      h("div", { className: "chat-head" },
        h("div", { className: "ic" }, botSvg(19)),
        h("div", { style: { minWidth: 0 } },
          h("div", { className: "t" }, "Storybook assistant"),
          h("div", { className: "s" }, running ? "Working on " + running + " thing" + (running === 1 ? "" : "s") : "Editing " + page.name)),
        h("button", { className: "backbtn x", title: "Close", onClick: onClose }, h(Icon, { name: "x", size: 15 }))),
      h("div", { className: "chat-body", ref: bodyRef },
        h("div", { className: "bubble ai" },
          "Tell me what this page needs \u2014 a new scene, different words, a note on the illustration. You can speak it, or attach a reference, manuscript or notes."),
        thread.map((m, i) => h("div", { key: i, className: "bubble " + (m.role === "user" ? "user" : m.role === "think" ? "think" : "ai") },
          m.files && m.files.length ? h("div", { className: "ai-atts" }, m.files.map((f) =>
            h(AttachChip, { key: f.id, file: f }))) : null,
          m.area ? h("div", { className: "ai-area-tag" }, h(Icon, { name: "square-mouse-pointer", size: 11 }), "Selected area") : null,
          m.text ? h("div", null, m.text) : null,
          m.actions && m.actions.length ? h("div", { className: "ai-acts" }, m.actions.map((a) =>
            h("button", { key: a.id, className: "ai-act" + (a.primary ? " primary" : ""), onClick: () => onAct(i, a.id) }, a.label))) : null)),
        task && !task.background ? h(BBSCN.TaskCard, Object.assign({ task: task, chars: task.chars }, taskHandlers || {})) : null,
        busy ? h("div", { className: "bubble ai tk", "data-state": "running" },
          h("div", { className: "tk-h" }, h("span", { className: "dotpulse", style: { margin: "0 6px" } }),
            h("div", null, h("div", { className: "tk-t" }, "Working on " + page.name + "\u2026"),
              h("div", { className: "tk-s" }, area ? "Applying your change to the selected area" : "Reading the page and applying your change")))) : null),
      thread.length === 0 && !area ? h("div", { className: "chat-sugg" }, SUGGESTIONS.map((s) =>
        h("button", { key: s, className: "chat-chip", onClick: () => onSend({ text: s, files: [] }) }, s))) : null,
      h(TaskStrip, { tasks: tasks, onGoto: onGoto, onRetry: onRetry }),
      area ? h("div", { className: "ai-area" },
        h("span", { className: "ai-area-ic" }, h(Icon, { name: "square-mouse-pointer", size: 14 })),
        h("div", { style: { minWidth: 0, flex: 1 } },
          h("div", { className: "ai-area-t" }, "Selected area on " + page.name),
          h("div", { className: "ai-area-s" }, areaCount ? areaCount + " element" + (areaCount === 1 ? "" : "s") + " inside \u00b7 describe the change below" : "No elements inside \u00b7 describe what to add here")),
        h("button", { className: "ai-att-x", title: "Clear selected area", "aria-label": "Clear selected area", onClick: onClearArea }, h(Icon, { name: "x", size: 12 }))) : null,
      areaMode ? h("div", { className: "ai-area draw" },
        h("span", { className: "ai-area-ic" }, h(Icon, { name: "square-mouse-pointer", size: 14 })),
        h("div", { style: { minWidth: 0, flex: 1 } },
          h("div", { className: "ai-area-t" }, "Pick an area"),
          h("div", { className: "ai-area-s" }, "Drag over the part of " + page.name + " you want to change")),
        h("button", { className: "ai-att-x", title: "Cancel area selection", "aria-label": "Cancel area selection", onClick: onToggleArea }, h(Icon, { name: "x", size: 12 }))) : null,
      h(Composer, { value: input, onValue: onInput, onSend: onSend, busy: busy,
        areaOn: areaMode, canArea: canArea, onArea: onToggleArea,
        placeholder: area ? "What should change in this area?" : "Ask Blue Balloon to change this scene\u2026" }));
  }

  export default { AiDock, Composer, classify, kindOf, fmtSize, BOT, botSvg, SUGGESTIONS, ACCEPT, FORMATS, MAX_BYTES };
