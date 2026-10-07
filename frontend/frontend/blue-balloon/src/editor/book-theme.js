import { storage as localStorage } from '../services/storage';
import React from 'react';
import ModuleBBTH from './book-theme.js';
import ModuleBBR from './render.js';
/* Blue Balloon — bookTheme.
   One source of truth for the book's colors, typography and page-layout defaults.
   Created by New Storybook setup (bb_draft), read + updated by the editor's Book
   style panel. Elements may override any of it locally; the theme is never
   mutated when a single element is formatted. ModuleBBTH */

  const FONTS = ["Geist", "Geist Mono", "Inter", "Lora", "Merriweather", "Playfair Display"];
  const FONT_STACKS = {
    "Geist": "'Geist', system-ui, sans-serif",
    "Geist Mono": "'Geist Mono', ui-monospace, monospace",
    "Inter": "'Inter', system-ui, sans-serif",
    "Lora": "'Lora', Georgia, serif",
    "Merriweather": "'Merriweather', Georgia, serif",
    "Playfair Display": "'Playfair Display', Georgia, serif"
  };
  const WEIGHTS = [{ v: 300, label: "Light" }, { v: 400, label: "Regular" }, { v: 500, label: "Medium" },
    { v: 600, label: "Semi Bold" }, { v: 700, label: "Bold" }];
  const weightLabel = (v) => (WEIGHTS.find((w) => w.v === +v) || { label: "Regular" }).label;

  const COLOR_ROLES = [
    { key: "primary", label: "Primary", hint: "Headings and cover" },
    { key: "secondary", label: "Secondary", hint: "Cover type and fills" },
    { key: "accent", label: "Accent", hint: "Details and page numbers" },
    { key: "background", label: "Background", hint: "Page paper" },
    { key: "text", label: "Text", hint: "Story copy" }
  ];
  const TYPE_ROLES = [
    { key: "heading", label: "Heading", sample: "The Lantern Boy", used: "Titles and page headings" },
    { key: "body", label: "Body", sample: "Once upon a time, the lantern woke the whole garden.", used: "Story text" },
    { key: "accent", label: "Accent", sample: "A bedtime story", used: "Subtitles and page numbers" }
  ];

  const ROLE_OF_KIND = { title: "heading", heading: "heading", subtitle: "accent", paragraph: "body", pageno: "accent" };
  // one modular scale off each role's base size, so a cover title and a page
  // heading stay related without needing separate controls
  const SIZE_SCALE = { title: 1.35, heading: 0.78, subtitle: 0.9, paragraph: 1, pageno: 0.62 };
  const PAGE_COLOR = { title: "primary", subtitle: "accent", heading: "primary", paragraph: "text", pageno: "accent" };
  const COVER_COLOR = { title: "secondary", subtitle: "accent", heading: "secondary", paragraph: "secondary", pageno: "accent" };
  const OVERRIDE_KEYS = ["font", "size", "bold", "italic", "underline", "color", "lineHeight", "letterSpacing", "align"];

  /* ---- color maths (hex only, no dependencies) ---- */
  const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
  function rgb(hex) {
    let s = String(hex == null ? "" : hex).trim().replace("#", "");
    if (s.length === 3) s = s.split("").map((c) => c + c).join("");
    if (!/^[0-9a-f]{6}$/i.test(s)) s = "888888";
    const n = parseInt(s, 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
  }
  function hex(c) {
    return "#" + ["r", "g", "b"].map((k) => clamp(Math.round(c[k]), 0, 255).toString(16).padStart(2, "0")).join("").toUpperCase();
  }
  function lum(h) {
    const c = rgb(h), f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }
  function mix(a, b, t) {
    const x = rgb(a), y = rgb(b);
    return hex({ r: x.r + (y.r - x.r) * t, g: x.g + (y.g - x.g) * t, b: x.b + (y.b - x.b) * t });
  }
  function hsl(h) {
    const c = rgb(h), r = c.r / 255, g = c.g / 255, b = c.b / 255;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
    let hu = 0;
    if (d) {
      if (mx === r) hu = ((g - b) / d) % 6;
      else if (mx === g) hu = (b - r) / d + 2;
      else hu = (r - g) / d + 4;
      hu *= 60; if (hu < 0) hu += 360;
    }
    const l = (mx + mn) / 2;
    return { h: hu, s: d ? d / (1 - Math.abs(2 * l - 1)) : 0, l: l };
  }
  const isHex = (v) => /^#?[0-9a-f]{3}$|^#?[0-9a-f]{6}$/i.test(String(v || "").trim());
  const norm = (v) => hex(rgb(v));

  const HUES = [[14, "red"], [34, "amber"], [56, "gold"], [78, "olive"], [158, "green"], [196, "teal"],
    [252, "blue"], [288, "violet"], [330, "plum"], [361, "rose"]];
  function nameColor(h) {
    const c = hsl(h);
    if (c.s < 0.1) return c.l < 0.16 ? "Ink" : c.l < 0.34 ? "Charcoal" : c.l < 0.56 ? "Slate" : c.l < 0.82 ? "Stone" : "Chalk";
    let base = "blue";
    for (let i = 0; i < HUES.length; i++) if (c.h <= HUES[i][0]) { base = HUES[i][1]; break; }
    if ((base === "gold" || base === "amber") && c.l > 0.78) return "Warm cream";
    if (base === "blue" && c.l < 0.34) base = "navy";
    const pre = c.l < 0.22 ? "Deep " : c.l < 0.4 ? "Dark " : c.l > 0.86 ? "Pale " : c.l > 0.7 ? "Soft " : "";
    const s = pre + base;
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  /* ---- derive a theme from the setup choices (palette + fonts) ---- */
  function deriveTheme(settings) {
    const pal = ((settings && settings.palette && settings.palette.length)
      ? settings.palette : ["#1F3A5F", "#5B8FD6", "#9FD0F5", "#EAF2FB"]).filter(isHex).map(norm);
    const list = pal.length ? pal : ["#1F3A5F", "#5B8FD6", "#9FD0F5", "#EAF2FB"];
    const byLum = list.slice().sort((a, b) => lum(a) - lum(b));
    const primary = byLum[0];
    const lightest = byLum[byLum.length - 1];
    const background = lum(lightest) > 0.7 ? lightest : mix(lightest, "#FFFFFF", 0.62);
    const secondary = byLum.length > 2 ? byLum[byLum.length - 2] : mix(background, "#FFFFFF", 0.35);
    const mids = byLum.slice(1, Math.max(1, byLum.length - 2));
    const accent = mids.length ? mids.slice().sort((a, b) => hsl(b).s - hsl(a).s)[0] : mix(primary, "#FFFFFF", 0.42);
    const text = mix(primary, "#0A0E16", 0.5);
    const fonts = (settings && settings.fonts) || [];
    const pick = (re, fb) => fonts.find((f) => re.test(f.role || "")) || fb;
    const hf = pick(/head/i, { family: "Geist", size: 32 });
    const bf = pick(/body/i, { family: "Lora", size: 14 });
    const af = pick(/sub|quote|caption/i, { family: "Lora", size: 20 });
    return {
      colors: { primary: primary, secondary: secondary, accent: accent, background: background, text: text },
      typography: {
        heading: { fontFamily: hf.family || "Geist", fontSize: +hf.size || 32, fontWeight: 700, lineHeight: 1.1, letterSpacing: -0.01 },
        body: { fontFamily: bf.family || "Lora", fontSize: +bf.size || 14, fontWeight: 400, lineHeight: 1.7, letterSpacing: 0 },
        accent: { fontFamily: af.family || "Lora", fontSize: +af.size || 20, fontWeight: 400, lineHeight: 1.3, letterSpacing: 0.04, italic: true }
      },
      layouts: { page: "imagetext" }
    };
  }
  function ensureTheme(settings) {
    const base = deriveTheme(settings);
    const t = settings && settings.theme;
    if (!t) return base;
    return {
      colors: Object.assign({}, base.colors, t.colors || {}),
      typography: {
        heading: Object.assign({}, base.typography.heading, (t.typography || {}).heading || {}),
        body: Object.assign({}, base.typography.body, (t.typography || {}).body || {}),
        accent: Object.assign({}, base.typography.accent, (t.typography || {}).accent || {})
      },
      layouts: Object.assign({}, base.layouts, t.layouts || {})
    };
  }
  const paletteOf = (theme) => [theme.colors.primary, theme.colors.accent, theme.colors.secondary, theme.colors.background];

  /* ---- keep the setup screen reading the same values ---- */
  function saveDraftTheme(theme) {
    try {
      const d = JSON.parse(localStorage.getItem("bb_draft") || "{}");
      d.theme = theme;
      d.palette = paletteOf(theme);
      d.fonts = [
        { family: theme.typography.heading.fontFamily, role: "Heading", size: theme.typography.heading.fontSize },
        { family: theme.typography.accent.fontFamily, role: "Subheading", size: theme.typography.accent.fontSize },
        { family: theme.typography.body.fontFamily, role: "Body Text", size: theme.typography.body.fontSize }
      ];
      localStorage.setItem("bb_draft", JSON.stringify(d));
    } catch (e) { /* Optional browser capability or local cache is unavailable. */ }
  }

  /* ---- resolution: theme role defaults, then element overrides ---- */
  function colorOf(el, theme, pg) {
    if (el.color) return el.color;
    const c = (theme && theme.colors) || {};
    const cover = pg && pg.bgRole === "cover";
    const key = el.colorRole || (cover ? (COVER_COLOR[el.kind] || "secondary") : (PAGE_COLOR[el.kind] || "text"));
    return c[key] || "#333333";
  }
  function resolveText(el, theme, pg) {
    const K = (ModuleBBR && ModuleBBR.KIND[el.kind]) || { fs: 14, fw: 400, ff: "Georgia, serif", ls: "0", lh: 1.6, ta: "left" };
    const role = ROLE_OF_KIND[el.kind] || "body";
    const t = ((theme && theme.typography) || {})[role] || {};
    const fam = el.font || t.fontFamily;
    const base = (t.fontSize || K.fs) * (SIZE_SCALE[el.kind] || 1);
    return {
      role: role, family: fam || null,
      fontFamily: FONT_STACKS[fam] || fam || K.ff,
      fontSize: el.size != null ? el.size : Math.round(base * 10) / 10,
      themeSize: Math.round(base * 10) / 10,
      fontWeight: el.bold != null ? (el.bold ? 700 : 400) : (t.fontWeight != null ? t.fontWeight : K.fw),
      lineHeight: el.lineHeight != null ? el.lineHeight : (t.lineHeight || K.lh),
      letterSpacing: el.letterSpacing != null ? el.letterSpacing + "em" : (t.letterSpacing != null ? t.letterSpacing + "em" : K.ls),
      italic: el.italic != null ? !!el.italic : (t.italic != null ? !!t.italic : !!K.italic),
      align: el.align || K.ta,
      color: colorOf(el, theme, pg)
    };
  }
  const shapeColor = (el, theme) => el.color || (theme && theme.colors ? theme.colors.accent : "#D4A83A");
  function pageBg(pg, theme) {
    const c = (theme && theme.colors) || {};
    if (pg && pg.bgRole === "cover") {
      if (pg.bg) return pg.bg;   // set in the Cover designer
      const p = c.primary || "#1F3A5F";
      return "radial-gradient(120% 100% at 50% 0%," + mix(p, "#FFFFFF", 0.2) + " 0%," + p + " 55%," + mix(p, "#000000", 0.45) + " 100%)";
    }
    if (pg && pg.bgRole === "background") return c.background || "#F7F4EC";
    return (pg && pg.bg) || c.background || "#F7F4EC";
  }
  function artGrad(theme, i) {
    const c = (theme && theme.colors) || {};
    const p = c.primary || "#1F3A5F", a = c.accent || "#5B8FD6", s = c.secondary || "#9FD0F5";
    const sets = [
      [mix(p, "#FFFFFF", 0.1), mix(a, "#000000", 0.2), mix(p, "#000000", 0.5)],
      [mix(a, "#FFFFFF", 0.25), mix(p, "#000000", 0.1), mix(p, "#000000", 0.55)],
      [mix(s, "#FFFFFF", 0.1), mix(a, "#000000", 0.05), mix(p, "#000000", 0.35)],
      [mix(p, a, 0.4), mix(p, "#000000", 0.25), mix(a, "#000000", 0.6)]
    ];
    const g = sets[Math.abs(i || 0) % sets.length];
    return "linear-gradient(165deg," + g[0] + "," + g[1] + " 62%," + g[2] + ")";
  }

  /* ---- element overrides ---- */
  const hasOverrides = (el) => !!el && OVERRIDE_KEYS.some((k) => el[k] != null);
  function clearOverrides() {
    const p = {}; OVERRIDE_KEYS.forEach((k) => p[k] = null); return p;
  }
  /* push a selected element's own formatting into the theme role, so every
     element of that role picks it up and the local override can go away */
  function promote(el, theme, pg) {
    const r = resolveText(el, theme, pg);
    const role = r.role;
    const next = Object.assign({}, theme, { typography: Object.assign({}, theme.typography) });
    const scale = SIZE_SCALE[el.kind] || 1;
    next.typography[role] = Object.assign({}, theme.typography[role], {
      fontFamily: r.family || theme.typography[role].fontFamily,
      fontSize: Math.round((r.fontSize / scale) * 10) / 10,
      fontWeight: r.fontWeight,
      lineHeight: r.lineHeight,
      letterSpacing: parseFloat(r.letterSpacing) || 0,
      italic: r.italic
    });
    return next;
  }

  /* ---- migrate pages authored before the theme existed ---- */
  const LEGACY_COLOR = { "#5b3a1e": "primary", "#4b3a2a": "text", "#9a7b52": "accent", "#f4e3b8": "secondary",
    "#d9b27a": "accent", "#c79a63": "accent", "#333": "text", "#333333": "text" };
  // illustrations authored before the theme carried a baked-in gradient
  const LEGACY_ART = ["#7c3aed", "#1d4ed8", "#065f46", "#1e1b4b"];
  function migratePages(pages) {
    return (pages || []).map((pg) => {
      const out = Object.assign({}, pg);
      if (!out.bgRole) out.bgRole = out.kind === "cover" ? "cover" : "background";
      out.els = (pg.els || []).map((e) => {
        let c = e;
        if (c.grad) {
          const i = LEGACY_ART.findIndex((h) => String(c.grad).indexOf(h) >= 0);
          if (i >= 0) { c = Object.assign({}, c, { art: i }); delete c.grad; }
        }
        if (c.color && !c.colorRole) {
          const role = LEGACY_COLOR[String(c.color).toLowerCase()];
          if (role) { c = Object.assign({}, c, { colorRole: role }); delete c.color; }
        }
        return c;
      });
      return out;
    });
  }

  export default { FONTS, FONT_STACKS, WEIGHTS, weightLabel, COLOR_ROLES, TYPE_ROLES, ROLE_OF_KIND, SIZE_SCALE,
    OVERRIDE_KEYS, deriveTheme, ensureTheme, paletteOf, saveDraftTheme, resolveText, colorOf, shapeColor,
    pageBg, artGrad, nameColor, hasOverrides, clearOverrides, promote, migratePages, mix, lum, hsl, isHex, norm };
