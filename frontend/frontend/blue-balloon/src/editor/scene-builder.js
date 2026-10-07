import React from 'react';
import ModuleBBTH from './book-theme.js';
import ModuleBBSCN from './scene-builder.js';
import { Icon as LucideIcon, LUCIDE_PATHS } from './icons.js';
/* Blue Balloon — AI scene building: task engine, canvas progress, activity list.
   Generation runs as a task so the user can keep editing, and every stage says
   what is happening. ModuleBBSCN */

  const h = React.createElement;
  const { useState, useRef, useEffect } = React;
  const Icon = LucideIcon;
  const BBTH = ModuleBBTH;

  Object.assign(LUCIDE_PATHS, {
    "sparkles": '<path d="M11.02 2.6a1 1 0 0 1 1.96 0l1.2 4.42a2 2 0 0 0 1.4 1.4l4.42 1.2a1 1 0 0 1 0 1.96l-4.42 1.2a2 2 0 0 0-1.4 1.4l-1.2 4.42a1 1 0 0 1-1.96 0l-1.2-4.42a2 2 0 0 0-1.4-1.4l-4.42-1.2a1 1 0 0 1 0-1.96l4.42-1.2a2 2 0 0 0 1.4-1.4z"/><path d="M19 15v4"/><path d="M21 17h-4"/>',
    "square-mouse-pointer": '<path d="M12.034 12.681a.498.498 0 0 1 .647-.647l9 3.5a.5.5 0 0 1-.033.943l-3.444 1.068a1 1 0 0 0-.66.66l-1.07 3.443a.5.5 0 0 1-.943.033z"/><path d="M5 3a2 2 0 0 0-2 2"/><path d="M19 3a2 2 0 0 1 2 2"/><path d="M5 21a2 2 0 0 1-2-2"/><path d="M9 3h1"/><path d="M9 21h2"/><path d="M14 3h1"/><path d="M3 9v1"/><path d="M21 9v2"/><path d="M3 14v1"/>'
  });

  const SCENE_STAGES = [
    { id: "read", label: "Reading the story" },
    { id: "cast", label: "Finding the right characters" },
    { id: "compose", label: "Building the composition" },
    { id: "visual", label: "Creating the illustration" },
    { id: "final", label: "Finishing the page" }
  ];
  const MICRO = [
    "Reading what happens next\u2026",
    "Finding the right moment in the story\u2026",
    "Setting the scene\u2026",
    "Bringing the characters together\u2026",
    "Choosing details from the story\u2026",
    "Making the scene feel connected to the previous page\u2026",
    "Checking character references\u2026",
    "Putting the final touches on the scene\u2026"
  ];

  /* ---- fallback story content, used when the assistant isn't reachable ---- */
  const SCENES = [
    { hd: "The Moonlit Forest", tx: "Ram stepped between the tall trees with the lantern held high. The path glowed a soft amber, and somewhere in the dark a small voice was already calling his name." },
    { hd: "The Lantern on the Water", tx: "They set the lantern on the river and watched it go. It drifted like a slow, warm moon, carrying everything they had not said downstream into the night." },
    { hd: "The Hidden Gate", tx: "Behind the willow stood a gate nobody remembered building. Ram pressed his palm against the cold iron and felt it hum, like a bell that had been sleeping for years." },
    { hd: "Voices in the Reeds", tx: "The reeds leaned in to listen. Shyam crouched low and whispered a question, and the whole riverbank whispered it back to him, word for patient word." },
    { hd: "The Long Way Home", tx: "Morning found them tired and laughing. The lantern had gone cool, swinging between them while the first birds practised their early, careless songs." },
    { hd: "First Light on the Hill", tx: "They climbed until the valley opened underneath them. The lantern was hardly needed now \u2014 the whole sky had turned the colour of warm honey." }
  ];
  function cannedScene(prompt, seed) {
    let n = Math.abs(seed || 0);
    for (let i = 0; i < (prompt || "").length; i++) n += prompt.charCodeAt(i);
    return SCENES[n % SCENES.length];
  }
  function sceneLine(prompt) {
    const p = (prompt || "").trim().replace(/\s+/g, " ");
    if (!p) return "A new moment in the story";
    return p.length > 82 ? p.slice(0, 80) + "\u2026" : p;
  }
  function charsInPrompt(prompt, chars) {
    const t = (prompt || "").toLowerCase();
    const named = (chars || []).filter((c) => c.name && t.indexOf(c.name.toLowerCase()) >= 0);
    return named.length ? named : (chars || []).slice(0, 2);
  }

  /* ---- task engine ---- */
  function useAiTasks() {
    const [tasks, setTasks] = useState([]);
    const timers = useRef({});
    const patch = (id, p) => setTasks((ts) => ts.map((t) => t.id === id ? Object.assign({}, t, typeof p === "function" ? p(t) : p) : t));
    const stop = (id) => { const T = timers.current[id]; if (!T) return; clearInterval(T.stage); clearInterval(T.micro); delete timers.current[id]; };
    useEffect(() => () => Object.keys(timers.current).forEach(stop), []);

    function launch(id, spec, startedAt) {
      const n = (spec.stages || SCENE_STAGES).length;
      timers.current[id] = {
        stage: setInterval(() => patch(id, (t) => (t.status === "running" && t.stage < n - 1) ? { stage: t.stage + 1 } : {}), 1250),
        micro: setInterval(() => patch(id, (t) => ({ micro: (t.micro + 1) % MICRO.length })), 2700)
      };
      Promise.resolve().then(spec.run).then((result) => {
        const wait = Math.max(0, 4200 - (Date.now() - startedAt));
        setTimeout(() => {
          stop(id);
          patch(id, { status: "done", stage: n, result: result, finishedAt: Date.now() });
          if (spec.onDone) spec.onDone(result, id);
        }, wait);
      }).catch((err) => {
        const wait = Math.max(0, 2200 - (Date.now() - startedAt));
        setTimeout(() => {
          stop(id);
          patch(id, { status: "error", errorText: (err && err.bbMessage) || "The assistant couldn\u2019t finish the illustration." });
        }, wait);
      });
    }

    function start(spec) {
      const id = "task" + Date.now().toString(36) + Math.floor(Math.random() * 900);
      const started = Date.now();
      setTasks((ts) => ts.concat([Object.assign({ id: id, kind: "scene", stage: 0, micro: 0, status: "running",
        background: false, version: 1, spec: spec }, spec, { spec: spec })]));
      launch(id, spec, started);
      return id;
    }
    function retry(id) {
      const t = tasks.find((x) => x.id === id); if (!t) return;
      patch(id, { status: "running", stage: 0, micro: 0, errorText: null, background: false });
      launch(id, t.spec, Date.now());
    }
    function regenerate(id, run) {
      const t = tasks.find((x) => x.id === id); if (!t) return;
      const spec = Object.assign({}, t.spec, run ? { run: run } : {});
      patch(id, { status: "running", stage: 0, micro: 0, background: false, version: (t.version || 1) + 1,
        previous: t.result, spec: spec });
      launch(id, spec, Date.now());
    }
    const cancel = (id) => { stop(id); setTasks((ts) => ts.filter((t) => t.id !== id)); };
    const dismiss = cancel;
    const background = (id, on) => patch(id, { background: on !== false });
    return { tasks, start, retry, regenerate, cancel, dismiss, background, patch };
  }

  const statusLine = (t) => t.status === "error" ? "Couldn\u2019t finish"
    : t.status === "done" ? "Ready"
    : (SCENE_STAGES[Math.min(t.stage, SCENE_STAGES.length - 1)] || {}).label || "Working\u2026";

  function StageList({ stage, status }) {
    return h("div", { className: "sb-stages" }, SCENE_STAGES.map((s, i) => {
      const state = status === "done" || i < stage ? "done" : (i === stage ? "active" : "todo");
      return h("div", { className: "sb-stage", key: s.id, "data-state": state },
        h("span", { className: "ic" }, state === "done"
          ? h(Icon, { name: "check", size: 13, style: { color: "#16a34a" } })
          : state === "active" ? h("span", { className: "dotpulse" }) : h("span", { className: "ring" })),
        h("span", null, s.label));
    }));
  }

  function Skeleton({ dims, stage, status }) {
    const k = 0.62;
    const blocks = [
      { cls: "i", x: 8, y: 12, w: 84, h: 44, from: 2 },
      { cls: "h", x: 8, y: 62, w: 52, h: 4.5, from: 1 },
      { cls: "t", x: 8, y: 71, w: 84, h: 2.8, from: 3 },
      { cls: "t", x: 8, y: 77, w: 78, h: 2.8, from: 3 },
      { cls: "t", x: 8, y: 83, w: 62, h: 2.8, from: 4 }
    ];
    return h("div", { className: "sb-skel", style: { width: dims.w * k, height: dims.h * k } },
      blocks.map((b, i) => h("div", { key: i, className: "sb-blk", "data-in": status !== "error" && stage >= b.from,
        style: { left: b.x + "%", top: b.y + "%", width: b.w + "%", height: b.h + "%" } })));
  }

  function CharChips({ chars }) {
    if (!chars || !chars.length) return null;
    return h("div", { className: "sb-chiprow" }, chars.map((c) =>
      h("span", { className: "sb-char", key: c.id },
        h("i", { style: { background: c.color || "#5B8FD6" } }, c.thumb ? h("img", { src: c.thumb, alt: "" }) : (c.name || "?")[0]),
        c.name)));
  }

  /* ---- canvas overlay while a scene is being built ---- */
  function SceneBuilder(props) {
    const { task, dims, chars, onBackground, onCancel, onKeep, onEdit, onRegenerate,
      onUseVersion, onKeepPrevious, onRetry, onAdjust } = props;
    if (!task || task.background) return null;

    if (task.status === "done") {
      const isVer = (task.version || 1) > 1;
      return h("div", { className: "sb-bar" },
        h("div", { className: "sb-bar-row" },
          h("span", { className: "sb-ok" }, h(Icon, { name: "check", size: 16 })),
          h("div", { className: "sb-bar-txt" },
            h("div", { className: "sb-bar-t" }, isVer ? "Version " + task.version + " is ready" : "Scene ready"),
            h("div", { className: "sb-bar-s" }, isVer
              ? "Version " + (task.version - 1) + " is kept until you choose."
              : "Your scene has been added to " + task.pageName + ".")),
          h("div", { className: "sb-bar-acts" }, isVer
            ? [h("button", { key: "u", className: "sb-btn primary", onClick: onUseVersion }, "Use this version"),
               h("button", { key: "p", className: "sb-btn", onClick: onKeepPrevious }, "Keep previous"),
               h("button", { key: "r", className: "sb-btn", onClick: onRegenerate }, h(Icon, { name: "refresh-cw", size: 13 }), "Again")]
            : [h("button", { key: "k", className: "sb-btn primary", onClick: onKeep }, "Keep scene"),
               h("button", { key: "e", className: "sb-btn", onClick: onEdit }, "Edit"),
               h("button", { key: "r", className: "sb-btn", onClick: onRegenerate }, h(Icon, { name: "refresh-cw", size: 13 }), "Regenerate")])));
    }

    const failed = task.status === "error";
    return h("div", { className: "sb-wrap" },
      h("div", { className: "sb" },
        h(Skeleton, { dims: dims, stage: task.stage, status: task.status }),
        h("div", { className: "sb-card" },
          h("div", { className: "sb-eyebrow" }, failed ? "Scene paused" : "Building the scene"),
          h("div", { className: "sb-t" }, (failed ? "We couldn\u2019t finish " : "Creating ") + task.pageName),
          h("div", { className: "sb-s" }, "\u201c" + sceneLine(task.prompt) + "\u201d"),
          failed
            ? h("div", null,
                h("div", { className: "sb-fail" },
                  h("span", { className: "ic" }, h(Icon, { name: "circle-alert", size: 17 })),
                  h("div", null,
                    h("div", { className: "t" }, "Generation stopped"),
                    h("div", { className: "s" }, task.errorText))),
                h("div", { className: "sb-keep" }, h(Icon, { name: "check", size: 13 }),
                  h("span", null, "Your request is saved, nothing on the page was lost.")),
                h("div", { className: "sb-foot" },
                  h("button", { className: "sb-btn primary", onClick: onRetry }, h(Icon, { name: "refresh-cw", size: 13 }), "Try again"),
                  h("button", { className: "sb-btn", onClick: onAdjust }, "Adjust prompt")),
                h("div", { className: "sb-foot", style: { marginTop: 7 } },
                  h("button", { className: "sb-btn ghost", style: { flex: "1 1 auto" }, onClick: onBackground }, "Continue editing")))
            : h("div", null,
                h(StageList, { stage: task.stage, status: task.status }),
                h("div", { className: "sb-micro" },
                  h("span", { className: "spin" }, h(Icon, { name: "loader", size: 13, className: "spin" })),
                  h("span", null, MICRO[task.micro % MICRO.length])),
                chars && chars.length ? h("div", { className: "sb-chars" },
                  h("div", { className: "sb-chars-k" }, "Characters in this scene"),
                  h(CharChips, { chars: chars })) : null,
                h("div", { className: "sb-foot" },
                  h("button", { className: "sb-btn", onClick: onBackground }, "Continue editing"),
                  h("button", { className: "sb-btn ghost", onClick: onCancel }, "Cancel")))
        )));
  }

  /* ---- the same progress, inside the assistant thread (the page stays visible) ---- */
  function TaskCard(props) {
    const { task, chars, onCancel, onKeep, onEdit, onRegenerate, onUseVersion, onKeepPrevious, onRetry, onAdjust } = props;
    if (!task) return null;
    if (task.status === "done") {
      const isVer = (task.version || 1) > 1;
      return h("div", { className: "bubble ai tk", "data-state": "done" },
        h("div", { className: "tk-h" },
          h("span", { className: "sb-ok", style: { width: 22, height: 22 } }, h(Icon, { name: "check", size: 13 })),
          h("div", null,
            h("div", { className: "tk-t" }, isVer ? "Version " + task.version + " is ready" : "Scene ready"),
            h("div", { className: "tk-s" }, isVer ? "Version " + (task.version - 1) + " is kept until you choose." : "Added to " + task.pageName + "."))),
        h("div", { className: "ai-acts" }, isVer
          ? [h("button", { key: "u", className: "ai-act primary", onClick: onUseVersion }, "Use this version"),
             h("button", { key: "p", className: "ai-act", onClick: onKeepPrevious }, "Keep previous"),
             h("button", { key: "r", className: "ai-act", onClick: onRegenerate }, "Again")]
          : [h("button", { key: "k", className: "ai-act primary", onClick: onKeep }, "Keep scene"),
             h("button", { key: "e", className: "ai-act", onClick: onEdit }, "Edit"),
             h("button", { key: "r", className: "ai-act", onClick: onRegenerate }, "Regenerate")]));
    }
    const failed = task.status === "error";
    return h("div", { className: "bubble ai tk", "data-state": task.status },
      h("div", { className: "tk-h" },
        failed ? h("span", { className: "tk-ic err" }, h(Icon, { name: "circle-alert", size: 14 })) : h("span", { className: "dotpulse", style: { margin: "0 6px" } }),
        h("div", null,
          h("div", { className: "tk-t" }, failed ? "Couldn\u2019t finish " + task.pageName : "Working on " + task.pageName + "\u2026"),
          h("div", { className: "tk-s" }, "\u201c" + sceneLine(task.prompt) + "\u201d"))),
      failed
        ? h("div", null,
            h("div", { className: "tk-s", style: { marginTop: 8 } }, task.errorText),
            h("div", { className: "ai-acts" },
              h("button", { className: "ai-act primary", onClick: onRetry }, "Try again"),
              h("button", { className: "ai-act", onClick: onAdjust }, "Adjust prompt")))
        : h("div", null,
            h(StageList, { stage: task.stage, status: task.status }),
            h("div", { className: "tk-micro" }, MICRO[task.micro % MICRO.length]),
            chars && chars.length ? h(CharChips, { chars: chars }) : null,
            h("div", { className: "ai-acts" }, h("button", { className: "ai-act", onClick: onCancel }, "Cancel"))));
  }

  /* ---- background status + activity list ---- */
  function StatusPill({ tasks, onClick }) {
    const running = tasks.filter((t) => t.status === "running");
    const done = tasks.filter((t) => t.status === "done" && t.background);
    const failed = tasks.filter((t) => t.status === "error");
    if (!tasks.length) return null;
    const label = running.length ? running[0].pageName + "\u2026"
      : failed.length ? "1 scene needs attention"
      : done.length ? done[0].pageName + " is ready" : "AI activity";
    return h("button", { className: "ai-pill", onClick: onClick, title: "AI activity" },
      running.length ? h("span", { className: "dotpulse" })
        : failed.length ? h(Icon, { name: "circle-alert", size: 13, style: { color: "var(--destructive)" } })
        : h(Icon, { name: "check", size: 13, style: { color: "#16a34a" } }),
      h("span", null, running.length ? "Generating " : "", label),
      tasks.length > 1 ? h("span", { className: "n" }, "+" + (tasks.length - 1)) : null);
  }

  function ActivityPopover({ x, y, tasks, onClose, onGoto, onRetry, onDismiss }) {
    const ref = useRef(null);
    useEffect(() => {
      const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose(); };
      document.addEventListener("mousedown", onDoc, true);
      return () => document.removeEventListener("mousedown", onDoc, true);
    }, [onClose]);
    const left = Math.max(8, Math.min(window.innerWidth - 284, x - 268));
    return h("div", { className: "bb-menu", ref: ref, style: { left: left, top: y, width: 276, padding: "10px 12px 8px" } },
      h("div", { className: "ai-tasks-k" }, "AI activity"),
      tasks.map((t) => h("div", { className: "ai-task", key: t.id },
        h("span", { className: "st" }, t.status === "running" ? h("span", { className: "dotpulse" })
          : t.status === "error" ? h(Icon, { name: "circle-alert", size: 13, style: { color: "var(--destructive)" } })
          : h(Icon, { name: "check", size: 13, style: { color: "#16a34a" } })),
        h("div", { className: "txt" },
          h("div", { className: "tt" }, t.pageName),
          h("div", { className: "ts" }, statusLine(t))),
        t.status === "error"
          ? h("button", { className: "go", onClick: () => { onClose(); onRetry(t.id); } }, "Try again")
          : h("button", { className: "go", onClick: () => { onClose(); onGoto(t); } }, t.status === "done" ? "Open" : "View"))),
      h("div", { style: { borderTop: "1px solid var(--border)", marginTop: 6, paddingTop: 6 } },
        h("button", { className: "go", style: { fontSize: 11.5, border: 0, background: "transparent", color: "var(--muted-foreground)", cursor: "pointer", font: "inherit" },
          onClick: () => { tasks.filter((t) => t.status !== "running").forEach((t) => onDismiss(t.id)); onClose(); } }, "Clear finished")));
  }

  export default { SCENE_STAGES, MICRO, useAiTasks, SceneBuilder, TaskCard, StageList, CharChips, StatusPill, ActivityPopover,
    cannedScene, sceneLine, charsInPrompt, statusLine };

