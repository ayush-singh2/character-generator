import {request} from './api';
import {read, write, storage} from './storage';

// Config switch: when VITE_API_URL is set the app talks to the FastAPI backend
// (same-origin `/api` in production). When it is empty we fall back to the
// original local-first browser-storage implementation so the demo still runs
// with no server.
export const backendEnabled = !!import.meta.env.VITE_API_URL;

export const demoProject = {id: 'default', title: 'The Lantern Boy', updatedAt: '2026-09-17T00:00:00.000Z', style: 'Storybook Illustration'};

// Map a backend project card (server/app.py `_card`) into the shape the UI
// consumes. Home.jsx reads `id`, `title`, `style`, `updatedAt`; NewProject.jsx
// navigates by `id`. `editedTs` is a ms-epoch integer — turn it into an ISO
// string so Home's existing lexical `updatedAt` sort keeps working.
function mapCard(p) {
  return {
    id: p.id,
    title: p.title,
    style: p.style || p.bookType || '',
    author: p.author || '',
    status: p.status || 'Draft',
    pages: p.pages || 0,
    progress: p.progress || 0,
    draft: p.draft || {},
    settings: p.settings || {},
    updatedAt: p.editedTs ? new Date(p.editedTs).toISOString() : '',
  };
}

export async function listProjects() {
  if (!backendEnabled) return read('bb_projects', [demoProject]);
  const data = await request('/projects');
  return (data.projects || []).map(mapCard);
}

// createProject stays synchronous for the local path (callers `location.assign`
// immediately). With the backend enabled it is async and returns the slug the
// server assigned. NewProject.jsx already `await`s the result, so both work.
export function createProject(settings) {
  if (!backendEnabled) {
    const id = crypto.randomUUID();
    const list = read('bb_projects', [demoProject]);
    write('bb_projects', [{id, title: settings.name, style: settings.style, updatedAt: new Date().toISOString()}, ...list]);
    storage.setItem('bb_current', id);
    write('bb_draft', {...settings, fresh: true});
    return id;
  }
  return request('/projects', {
    method: 'POST',
    body: {
      title: settings.name,
      author: settings.author || '',
      style: settings.style || '',
      bookType: settings.style || '',
      draft: {...settings, fresh: true},
    },
  }).then(card => {
    const slug = card.id;
    // The workspace editor still bootstraps its settings from these local keys
    // (loadSettings/docKey read `bb_current` + `bb_draft`), so mirror them.
    storage.setItem('bb_current', slug);
    write('bb_draft', {...settings, fresh: true});
    return slug;
  });
}

export function projectHref(id) {return `/workspace?project=${encodeURIComponent(id)}`;}

// Duplicate a book (server copies its book dir + db row). Local fallback clones
// the projects-list card so the demo library still works with no backend.
export async function duplicateProject(id) {
  if (!backendEnabled) {
    const list = read('bb_projects', [demoProject]);
    const src = list.find(p => p.id === id);
    if (!src) return null;
    const copy = {...src, id: crypto.randomUUID(), title: `${src.title} (copy)`, updatedAt: new Date().toISOString()};
    write('bb_projects', [copy, ...list]);
    return copy;
  }
  return mapCard(await request(`/projects/${encodeURIComponent(id)}/duplicate`, {method: 'POST'}));
}

// Delete a book (server removes its book dir + db row). Local fallback drops it
// from the projects list.
export async function deleteProject(id) {
  if (!backendEnabled) {
    const list = read('bb_projects', [demoProject]);
    write('bb_projects', list.filter(p => p.id !== id));
    return true;
  }
  await request(`/projects/${encodeURIComponent(id)}`, {method: 'DELETE'});
  return true;
}

// Persist the New-Project / settings draft to the server (PUT .../draft). Local
// path keeps the existing bb_draft mirror. Best-effort — never blocks the UI.
export async function saveDraft(id, draft) {
  if (!backendEnabled) {
    write('bb_draft', draft);
    return draft;
  }
  return mapCard(await request(`/projects/${encodeURIComponent(id)}/draft`, {method: 'PUT', body: draft}));
}
