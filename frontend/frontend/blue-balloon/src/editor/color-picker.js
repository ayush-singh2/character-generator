import { storage as localStorage } from '../services/storage';
import React from 'react';
import ModuleBBColorPicker from './color-picker.js';
import ModuleShadcnUiDesignSystem_6211ba from './ui.jsx';
/* Blue Balloon color picker — hue wheel + saturation/lightness square, hex/rgb/hsl, presets, recents. Exposes ModuleBBColorPicker (React, uses shadcn Dialog). */

  const e = React.createElement;
  const { useState, useRef, useEffect, useCallback } = React;
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  function hsvToRgb(h, s, v) { const c = v * s, x = c * (1 - Math.abs(((h / 60) % 2) - 1)), m = v - c; let r, g, b; if (h < 60) [r, g, b] = [c, x, 0]; else if (h < 120) [r, g, b] = [x, c, 0]; else if (h < 180) [r, g, b] = [0, c, x]; else if (h < 240) [r, g, b] = [0, x, c]; else if (h < 300) [r, g, b] = [x, 0, c]; else [r, g, b] = [c, 0, x]; return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)]; }
  function rgbToHsv(r, g, b) { r /= 255; g /= 255; b /= 255; const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn; let h = 0; if (d) { if (mx === r) h = 60 * (((g - b) / d) % 6); else if (mx === g) h = 60 * ((b - r) / d + 2); else h = 60 * ((r - g) / d + 4); } if (h < 0) h += 360; return [h, mx ? d / mx : 0, mx]; }
  const toHex = (r, g, b) => "#" + [r, g, b].map(n => n.toString(16).padStart(2, "0")).join("").toUpperCase();
  function parseHex(s) { const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(s.trim()); if (!m) return null; let h = m[1]; if (h.length === 3) h = h.split("").map(c => c + c).join(""); return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]; }
  function hsvToHsl(h, s, v) { const l = v * (1 - s / 2); const sl = (l === 0 || l === 1) ? 0 : (v - l) / Math.min(l, 1 - l); return [Math.round(h), Math.round(sl * 100), Math.round(l * 100)]; }
  const PRESETS = ["#1F3A5F", "#2F5FA8", "#3B74C9", "#5B8FD6", "#9FD0F5", "#2F8F9D", "#6A5FC4", "#E8A84B", "#3B74C9", "#EAF2FB", "#FFFFFF", "#1B2333"];
  const RECENT_KEY = "bb_recent_colors";
  const readRecent = () => { try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch (err) { return []; } };
  const pushRecent = (hex) => { try { const r = [hex].concat(readRecent().filter(c => c !== hex)).slice(0, 8); localStorage.setItem(RECENT_KEY, JSON.stringify(r)); } catch (err) { /* Optional browser capability or local cache is unavailable. */ } };

  function useDrag(onMove) {
    const ref = useRef(null);
    const handler = useCallback((ev) => {
      const el = ref.current; if (!el) return;
      const move = (m) => { const r = el.getBoundingClientRect(); onMove((m.clientX - r.left) / r.width, (m.clientY - r.top) / r.height, r); };
      move(ev); ev.preventDefault();
      const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
      window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
    }, [onMove]);
    return [ref, handler];
  }

  function Picker({ value, onChange }) {
    const [hsv, setHsv] = useState(() => { const rgb = parseHex(value || "#3B74C9") || [196, 87, 58]; return rgbToHsv(...rgb); });
    const [h, s, v] = hsv;
    const rgb = hsvToRgb(h, s, v); const hex = toHex(...rgb); const hsl = hsvToHsl(h, s, v);
    const [hexText, setHexText] = useState(hex);
    useEffect(() => { setHexText(hex); onChange(hex); }, [hex]);
    const [wheelRef, onWheel] = useDrag((x, y) => { const dx = x - .5, dy = y - .5; let a = Math.atan2(dy, dx) * 180 / Math.PI + 90; if (a < 0) a += 360; setHsv(p => [a, p[1], p[2]]); });
    const [sqRef, onSq] = useDrag((x, y) => setHsv(p => [p[0], clamp(x, 0, 1), clamp(1 - y, 0, 1)]));
    const setFromHex = (t) => { setHexText(t); const p = parseHex(t); if (p) setHsv(rgbToHsv(...p)); };
    const pureHue = toHex(...hsvToRgb(h, 1, 1));
    const rad = (h - 90) * Math.PI / 180;
    const recent = readRecent();
    const swatchRow = (label, list) => e("div", { className: "cp-row" }, e("div", { className: "cp-lbl" }, label), e("div", { className: "cp-swatches" }, list.map(c => e("button", { key: c, type: "button", className: "cp-sw" + (c === hex ? " on" : ""), style: { background: c }, title: c, onClick: () => setFromHex(c) }))));
    return e("div", { className: "cp" },
      e("div", { className: "cp-main" },
        e("div", { className: "cp-wheel", ref: wheelRef, onPointerDown: onWheel },
          e("div", { className: "cp-square-wrap" },
            e("div", { className: "cp-square", ref: sqRef, onPointerDown: onSq, style: { background: "linear-gradient(to top,#000,transparent),linear-gradient(to right,#fff," + pureHue + ")" } },
              e("span", { className: "cp-dot", style: { left: s * 100 + "%", top: (1 - v) * 100 + "%", background: hex } }))),
          e("span", { className: "cp-hue-dot", style: { left: 50 + Math.cos(rad) * 44 + "%", top: 50 + Math.sin(rad) * 44 + "%", background: pureHue } })
        ),
        e("div", { className: "cp-side" },
          e("div", { className: "cp-preview", style: { background: hex } }),
          e("label", { className: "cp-field" }, e("span", null, "HEX"), e("input", { className: "cp-in", value: hexText, onChange: ev => setFromHex(ev.target.value), spellCheck: false })),
          e("div", { className: "cp-field" }, e("span", null, "RGB"), e("div", { className: "cp-vals" }, rgb.map((n, i) => e("span", { key: i }, n)))),
          e("div", { className: "cp-field" }, e("span", null, "HSL"), e("div", { className: "cp-vals" }, e("span", null, hsl[0] + "°"), e("span", null, hsl[1] + "%"), e("span", null, hsl[2] + "%"))),
          e("label", { className: "cp-field" }, e("span", null, "Hue"), e("input", { type: "range", min: 0, max: 360, value: Math.round(h), onChange: ev => setHsv(p => [+ev.target.value, p[1], p[2]]), className: "cp-range", style: { background: "linear-gradient(to right,#f00,#ff0,#0f0,#0ff,#00f,#f0f,#f00)" } }))
        )
      ),
      recent.length ? swatchRow("Recent", recent) : null,
      swatchRow("Presets", PRESETS)
    );
  }

  function BBColorPicker({ open, initial, onClose, onPick, title }) {
    const { Dialog, DialogHeader, DialogTitle, DialogDescription, DialogFooter, Button } = ModuleShadcnUiDesignSystem_6211ba;
    const [cur, setCur] = useState(initial || "#3B74C9");
    if (!open) return null;
    return e(Dialog, { open: true, onOpenChange: (v) => { if (!v) onClose(); } },
      e(DialogHeader, null, e(DialogTitle, null, title || "Pick a color"), e(DialogDescription, null, "Drag on the wheel for hue, in the square for tone, or type a value.")),
      e(Picker, { value: initial, onChange: setCur }),
      e(DialogFooter, null, e(Button, { variant: "outline", onClick: onClose }, "Cancel"), e(Button, { onClick: () => { pushRecent(cur); onPick(cur); onClose(); } }, e("span", { className: "cp-btn-dot", style: { background: cur } }), "Use " + cur))
    );
  }
  const css = `
.cp{display:flex;flex-direction:column;gap:16px;margin:8px 0 4px}
.cp-main{display:grid;grid-template-columns:220px 1fr;gap:20px;align-items:start}
.cp-wheel{position:relative;width:220px;height:220px;border-radius:50%;cursor:crosshair;touch-action:none}
.cp-wheel::before{content:"";position:absolute;inset:0;border-radius:50%;background:conic-gradient(from 0deg,#f00,#ff0,#0f0,#0ff,#00f,#f0f,#f00);-webkit-mask:radial-gradient(circle,transparent 0 68%,#000 68.5%);mask:radial-gradient(circle,transparent 0 68%,#000 68.5%)}
.cp-wheel .cp-square-wrap{position:absolute;inset:0;display:grid;place-items:center;pointer-events:none}
.cp-square{position:relative;width:104px;height:104px;border-radius:8px;cursor:crosshair;pointer-events:auto;touch-action:none;box-shadow:0 0 0 1px rgba(0,0,0,.08)}
.cp-dot{position:absolute;width:14px;height:14px;border-radius:50%;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.35);transform:translate(-50%,-50%);pointer-events:none}
.cp-hue-dot{position:absolute;width:20px;height:20px;border-radius:50%;border:3px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.35);transform:translate(-50%,-50%);pointer-events:none}
.cp-side{display:flex;flex-direction:column;gap:10px}
.cp-preview{height:52px;border-radius:10px;border:1px solid var(--border)}
.cp-field{display:grid;grid-template-columns:36px 1fr;align-items:center;gap:8px;font-size:12px;color:var(--muted-foreground)}
.cp-field>span:first-child{font-weight:600;letter-spacing:.04em}
.cp-in{height:32px;border:1px solid var(--input);border-radius:8px;padding:0 10px;font:inherit;font-size:13px;font-variant-numeric:tabular-nums;color:var(--foreground);background:var(--card);width:100%}
.cp-in:focus{outline:none;border-color:var(--ring);box-shadow:0 0 0 3px color-mix(in oklab,var(--ring) 20%,transparent)}
.cp-vals{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.cp-vals span{height:32px;display:grid;place-items:center;border:1px solid var(--border);border-radius:8px;font-size:13px;color:var(--foreground);font-variant-numeric:tabular-nums;background:var(--muted)}
.cp-range{-webkit-appearance:none;appearance:none;height:10px;border-radius:999px;width:100%;outline:none}
.cp-range::-webkit-slider-thumb{-webkit-appearance:none;width:18px;height:18px;border-radius:50%;background:#fff;border:1px solid rgba(0,0,0,.2);box-shadow:0 1px 3px rgba(0,0,0,.25);cursor:pointer}
.cp-row{display:flex;flex-direction:column;gap:8px}
.cp-lbl{font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--muted-foreground)}
.cp-swatches{display:flex;flex-wrap:wrap;gap:8px}
.cp-sw{width:28px;height:28px;border-radius:8px;border:1px solid rgba(0,0,0,.1);cursor:pointer;transition:transform 140ms ease,box-shadow 140ms ease;padding:0}
.cp-sw:hover{transform:scale(1.1)}
.cp-sw.on{box-shadow:0 0 0 2px var(--card),0 0 0 4px var(--ring)}
.cp-btn-dot{width:12px;height:12px;border-radius:50%;border:1px solid rgba(255,255,255,.5);display:inline-block}
@media (max-width:520px){.cp-main{grid-template-columns:1fr;justify-items:center}.cp-side{width:100%}}`;
  const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
  export default BBColorPicker;
