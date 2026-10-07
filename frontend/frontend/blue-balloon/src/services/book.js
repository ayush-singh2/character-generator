import {request} from './api';
import {backendEnabled} from './projects';

// Backend adapter for the real v3 pipeline (server/app.py). These are the
// "clean" project-scoped flows: read one project, upload a manuscript, list &
// design characters, kick generation, poll the job, list pages, request a PDF.
// All require the session cookie (Depends(require_auth)); `request()` already
// sends `credentials:'include'` and fires `bb-session-expired` on 401.
//
// The canvas document itself (pages as freely-positioned elements) is NOT
// modelled by this backend — the pipeline produces flat page PNGs, not an
// editable element tree. So the workspace's local canvas doc stays local; these
// helpers cover the generation/asset side that the backend actually owns.

export {backendEnabled};

// ---- read / manuscript -------------------------------------------------- //
export async function getProject(slug) {
  return request(`/projects/${encodeURIComponent(slug)}`);
}

// The manuscript endpoint is multipart/form-data (UploadFile), so it bypasses
// the JSON `request()` wrapper and posts a FormData directly.
export async function uploadManuscript(slug, file) {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(`${import.meta.env.VITE_API_URL || '/api'}/projects/${encodeURIComponent(slug)}/manuscript`, {
    method: 'POST', body: fd, credentials: 'include',
  });
  if (!res.ok) {
    if (res.status === 401) window.dispatchEvent(new Event('bb-session-expired'));
    throw new Error(`Manuscript upload failed (${res.status})`);
  }
  return res.json();
}

// ---- characters --------------------------------------------------------- //
export async function listCharacters(slug) {
  const data = await request(`/projects/${encodeURIComponent(slug)}/characters`);
  return data.characters || [];
}

// design is multipart (instruction + optional photo).
export async function designCharacter(slug, name, instruction, photo) {
  const fd = new FormData();
  fd.append('instruction', instruction);
  if (photo) fd.append('photo', photo);
  const res = await fetch(`${import.meta.env.VITE_API_URL || '/api'}/projects/${encodeURIComponent(slug)}/characters/${encodeURIComponent(name)}/design`, {
    method: 'POST', body: fd, credentials: 'include',
  });
  if (!res.ok) {
    if (res.status === 401) window.dispatchEvent(new Event('bb-session-expired'));
    throw new Error(`Character design failed (${res.status})`);
  }
  return res.json();
}

export async function approveCharacter(slug, name) {
  return request(`/projects/${encodeURIComponent(slug)}/characters/${encodeURIComponent(name)}/approve`, {method: 'POST'});
}

// ---- generate + poll ---------------------------------------------------- //
// `only` optionally scopes generation to a single page id.
export async function generate(slug, only) {
  return request(`/projects/${encodeURIComponent(slug)}/generate`, {
    method: 'POST', body: only ? {only} : {},
  });
}

// One job-status read: {state, group, stage, pct, log}. Poll this on an
// interval after `generate()` until state is "done"/"error".
export async function getJob(slug) {
  return request(`/projects/${encodeURIComponent(slug)}/job`);
}

// ---- pages -------------------------------------------------------------- //
// Returns [{id, url}] — url is a backend asset path for the composed PNG.
export async function listPages(slug) {
  const data = await request(`/projects/${encodeURIComponent(slug)}/pages`);
  return data.pages || [];
}

export async function getPageNote(slug, pageId) {
  const data = await request(`/projects/${encodeURIComponent(slug)}/pages/${encodeURIComponent(pageId)}/note`);
  return data.note || '';
}

// Save an authoritative per-page direction and re-illustrate just that page.
export async function setPageNote(slug, pageId, note) {
  return request(`/projects/${encodeURIComponent(slug)}/pages/${encodeURIComponent(pageId)}/note`, {
    method: 'POST', body: {note},
  });
}

// Free-text author edit -> full-pipeline regen of that page.
export async function editPage(slug, pageId, instruction) {
  return request(`/projects/${encodeURIComponent(slug)}/pages/${encodeURIComponent(pageId)}/edit`, {
    method: 'POST', body: {instruction},
  });
}

// Quick i2i correction of one composed page. Returns {url} (cache-busted).
export async function correctPage(slug, pageId, instruction) {
  return request(`/projects/${encodeURIComponent(slug)}/pages/${encodeURIComponent(pageId)}/correct`, {
    method: 'POST', body: {instruction},
  });
}

// ---- per-page correction CHAT (human-in-the-loop) ----------------------- //
// Multi-turn page fix: say what's wrong and reference a CORRECT page either by
// naming it ("…like page 5" — parsed server-side) or by dropping its image
// (`refFiles`). Multipart like the manuscript/design uploads. Returns
// {ok, reply, page_url?, meta}: ok=false (e.g. a referenced page is missing) is
// a normal result with a friendly `reply`, not an error.
export async function chatPage(slug, pageId, message, refPages, refFiles, area) {
  const fd = new FormData();
  fd.append('message', message || '');
  if (refPages && refPages.length) fd.append('ref_pages', refPages.join(','));
  // Selected region as a normalised [x0,y0,x1,y1] box -> server does a masked edit.
  if (area && area.length === 4) fd.append('area', JSON.stringify(area));
  (refFiles || []).forEach((f) => fd.append('refs', f));
  const res = await fetch(`${import.meta.env.VITE_API_URL || '/api'}/projects/${encodeURIComponent(slug)}/pages/${encodeURIComponent(pageId)}/chat`, {
    method: 'POST', body: fd, credentials: 'include',
  });
  if (!res.ok) {
    if (res.status === 401) window.dispatchEvent(new Event('bb-session-expired'));
    throw new Error(`Chat failed (${res.status})`);
  }
  return res.json();
}

// Saved transcript for a page (survives reloads). Returns an array of turns.
export async function getPageChat(slug, pageId) {
  const d = await request(`/projects/${encodeURIComponent(slug)}/pages/${encodeURIComponent(pageId)}/chat`);
  return (d && d.turns) || [];
}

// Undo the last chat change on a page. Returns {ok, page_url}.
export async function revertPageChat(slug, pageId) {
  return request(`/projects/${encodeURIComponent(slug)}/pages/${encodeURIComponent(pageId)}/chat/revert`, {method: 'POST'});
}

// ---- pdf ---------------------------------------------------------------- //
// Same-origin link the browser can open/download once the book is built.
export function pdfHref(slug) {
  return `${import.meta.env.VITE_API_URL || '/api'}/projects/${encodeURIComponent(slug)}/pdf`;
}
