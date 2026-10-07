/* Shared API client for the BB-artists pages.
 *
 * Every page pulls this in with <script src="/static/api.js"></script> and then
 * uses window.BB.api.* instead of the old mock arrays / localStorage. All calls
 * send the session cookie automatically (credentials: 'same-origin').
 *
 * Long-running pipeline work (parse, generate) is a background job: kick it,
 * then BB.api.pollJob(slug, onProgress) until it finishes.
 */
(function () {
  const JSON_HEADERS = { "Content-Type": "application/json" };

  async function req(method, url, body, isForm) {
    const opts = { method, credentials: "same-origin" };
    if (body !== undefined) {
      if (isForm) opts.body = body;                       // FormData
      else { opts.headers = JSON_HEADERS; opts.body = JSON.stringify(body); }
    }
    const r = await fetch(url, opts);
    if (r.status === 401) {                               // gate expired -> login
      if (!/Login\.html$/.test(location.pathname)) location.href = "/Login.html";
      throw new Error("unauthorized");
    }
    if (!r.ok) {
      let detail = r.statusText;
      try { detail = (await r.json()).detail || detail; } catch (e) {}
      throw new Error(detail);
    }
    const ct = r.headers.get("content-type") || "";
    return ct.indexOf("application/json") !== -1 ? r.json() : r;
  }

  const api = {
    // --- auth ---
    login: (password) => req("POST", "/api/login", { password }),
    logout: () => req("POST", "/api/logout"),

    // --- projects ---
    listProjects: () => req("GET", "/api/projects").then((d) => d.projects),
    getProject: (slug) => req("GET", "/api/projects/" + slug),
    createProject: (data) => req("POST", "/api/projects", data),
    updateProject: (slug, patch) => req("PATCH", "/api/projects/" + slug, patch),
    duplicateProject: (slug) => req("POST", "/api/projects/" + slug + "/duplicate"),
    deleteProject: (slug) => req("DELETE", "/api/projects/" + slug),
    saveDraft: (slug, draft) => req("PUT", "/api/projects/" + slug + "/draft", draft),

    // --- manuscript / characters ---
    uploadManuscript: (slug, file) => {
      const fd = new FormData();
      fd.append("file", file);
      return req("POST", "/api/projects/" + slug + "/manuscript", fd, true);
    },
    getCharacters: (slug) =>
      req("GET", "/api/projects/" + slug + "/characters").then((d) => d.characters),

    // --- style SAMPLES (project-independent: one fixed scene per style, for the
    // New Project form before any manuscript is parsed) ---
    startStyleSamples: (force) =>
      req("POST", "/api/style-previews", force ? { force: true } : {}),
    getStyleSamples: () => req("GET", "/api/style-previews"),
    pollStyleSamples: (onProgress, intervalMs) =>
      new Promise((resolve, reject) => {
        const tick = async () => {
          let st;
          try { st = await api.getStyleSamples(); }
          catch (e) { return reject(e); }
          if (onProgress) try { onProgress(st); } catch (e) {}
          if (st.state === "running" || st.state === "pending") {
            setTimeout(tick, intervalMs || 2500); return;
          }
          resolve(st);
        };
        tick();
      }),

    // --- style previews (same page rendered once per style, pick by eye) ---
    startStylePreviews: (slug, page) =>
      req("POST", "/api/projects/" + slug + "/style-previews", page ? { page } : {}),
    getStylePreviews: (slug) =>
      req("GET", "/api/projects/" + slug + "/style-previews"),
    pickStyle: (slug, style, extra) =>
      req("POST", "/api/projects/" + slug + "/style",
          Object.assign({ style }, extra || {})),
    /* Poll style previews until the run leaves the "running" state.
     * onProgress(status) fires every tick; resolves with the terminal status. */
    pollStylePreviews: (slug, onProgress, intervalMs) =>
      new Promise((resolve, reject) => {
        const tick = async () => {
          let st;
          try { st = await api.getStylePreviews(slug); }
          catch (e) { return reject(e); }
          if (onProgress) try { onProgress(st); } catch (e) {}
          if (st.state === "running" || st.state === "pending") {
            setTimeout(tick, intervalMs || 2500); return;
          }
          resolve(st);
        };
        tick();
      }),
    designCharacter: (slug, name, instruction, photoFile) => {
      const fd = new FormData();
      fd.append("instruction", instruction);
      if (photoFile) fd.append("photo", photoFile);
      return req("POST", "/api/projects/" + slug + "/characters/" +
                 encodeURIComponent(name) + "/design", fd, true);
    },
    approveCharacter: (slug, name) =>
      req("POST", "/api/projects/" + slug + "/characters/" +
          encodeURIComponent(name) + "/approve"),

    // --- generation / pages ---
    startGenerate: (slug, only) =>
      req("POST", "/api/projects/" + slug + "/generate", only ? { only } : {}),
    getPages: (slug) =>
      req("GET", "/api/projects/" + slug + "/pages").then((d) => d.pages),
    correctPage: (slug, pageId, instruction) =>
      req("POST", "/api/projects/" + slug + "/pages/" + pageId + "/correct",
          { instruction }),

    // --- per-page correction CHAT (human-in-the-loop) ---
    // message: what's wrong; refPages: ["5"] named references; refFiles: dropped
    // image Files used as visual references. Returns {ok, reply, page_url, meta}.
    getChat: (slug, pageId) =>
      req("GET", "/api/projects/" + slug + "/pages/" + pageId + "/chat").then((d) => d.turns),
    chatPage: (slug, pageId, message, refPages, refFiles) => {
      const fd = new FormData();
      fd.append("message", message || "");
      if (refPages && refPages.length) fd.append("ref_pages", refPages.join(","));
      (refFiles || []).forEach((f) => fd.append("refs", f));
      return req("POST", "/api/projects/" + slug + "/pages/" + pageId + "/chat", fd, true);
    },
    revertChat: (slug, pageId) =>
      req("POST", "/api/projects/" + slug + "/pages/" + pageId + "/chat/revert"),
    getPageNote: (slug, pageId) =>
      req("GET", "/api/projects/" + slug + "/pages/" + pageId + "/note").then((d) => d.note),
    setPageNote: (slug, pageId, note) =>
      req("POST", "/api/projects/" + slug + "/pages/" + pageId + "/note", { note }),
    // Author edit: free-text fix that regenerates the page through the full
    // pipeline (edits accumulate on the scene). Then pollJob to watch progress.
    getPageEdits: (slug, pageId) =>
      req("GET", "/api/projects/" + slug + "/pages/" + pageId + "/edit").then((d) => d.edits),
    editPage: (slug, pageId, instruction) =>
      req("POST", "/api/projects/" + slug + "/pages/" + pageId + "/edit", { instruction }),
    clearPageEdits: (slug, pageId) =>
      req("DELETE", "/api/projects/" + slug + "/pages/" + pageId + "/edit"),

    // --- job status / export ---
    getJob: (slug) => req("GET", "/api/projects/" + slug + "/job"),
    pdfUrl: (slug) => "/api/projects/" + slug + "/pdf",

    /* Poll a job until it leaves the "running" state.
     * onProgress({state, stage, pct, log}) is called on every tick.
     * Resolves with the terminal status, rejects on "error". */
    pollJob: (slug, onProgress, intervalMs) =>
      new Promise((resolve, reject) => {
        const tick = async () => {
          let st;
          try { st = await api.getJob(slug); }
          catch (e) { return reject(e); }
          if (onProgress) try { onProgress(st); } catch (e) {}
          if (st.state === "running") { setTimeout(tick, intervalMs || 2000); return; }
          if (st.state === "error") reject(new Error(st.error || "job failed"));
          else resolve(st);
        };
        tick();
      }),
  };

  // Convenience: the "current" project id (slug) the flow is working on.
  const CURRENT = "bb_current";
  window.BB = {
    api,
    currentProject: () => { try { return localStorage.getItem(CURRENT); } catch (e) { return null; } },
    setCurrentProject: (slug) => { try { localStorage.setItem(CURRENT, slug); } catch (e) {} },
    // read ?key=... from the URL
    param: (k) => new URLSearchParams(location.search).get(k),
  };
})();
