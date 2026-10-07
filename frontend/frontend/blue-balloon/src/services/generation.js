import {generate, getJob, listPages} from './book';

// Resolve a backend asset path (the pipeline returns "/api/projects/..." paths)
// against the configured API base so it works whether VITE_API_URL is "/api" or
// an absolute origin. Backend page urls already start with "/api/…".
export function assetUrl(url) {
  if (!url) return url;
  if (/^https?:\/\//.test(url)) return url;
  const base = import.meta.env.VITE_API_URL || '/api';
  // page urls come as "/api/projects/…"; if base is an absolute origin swap the
  // leading "/api" for it, otherwise the same-origin path is already correct.
  if (base === '/api' || base.startsWith('/')) return url;
  return url.replace(/^\/api/, base.replace(/\/$/, ''));
}

// Poll an already-started job (e.g. the manuscript "parse" job) until it
// settles. Does NOT kick a new job. Reports progress via onProgress.
export async function waitForJob(slug, {onProgress, signal} = {}) {
  for (;;) {
    if (signal?.aborted) throw new Error('cancelled');
    const st = await getJob(slug);
    if (onProgress) onProgress({state: st.state, stage: st.stage || st.group || '', pct: st.pct || 0});
    if (st.state === 'done') return st;
    if (st.state === 'error') {
      const e = new Error(st.error || 'The server job failed.');
      e.bbMessage = st.error || 'That step failed on the server.';
      throw e;
    }
    if (st.state === 'idle' || st.state === 'unknown') return st;
    await new Promise(r => setTimeout(r, 2500));
  }
}

// Kick a real generation job and poll it to completion, reporting progress via
// onProgress({state, stage, pct}). Resolves with the backend page list
// ([{id, url}]) once the book PDF/pages are built. `only` scopes to one page.
export async function runGeneration(slug, {only, onProgress, signal} = {}) {
  await generate(slug, only);
  // poll the job status until it settles
  for (;;) {
    if (signal?.aborted) throw new Error('cancelled');
    const st = await getJob(slug);
    if (onProgress) onProgress({state: st.state, stage: st.stage || st.group || '', pct: st.pct || 0});
    if (st.state === 'done') break;
    if (st.state === 'error') {
      const e = new Error(st.error || 'Generation failed on the server.');
      e.bbMessage = st.error || 'Generation failed. Nothing was changed.';
      throw e;
    }
    if (st.state === 'idle' || st.state === 'unknown') break;
    await new Promise(r => setTimeout(r, 2500));
  }
  const pages = await listPages(slug);
  return pages.map(p => ({...p, url: assetUrl(p.url)}));
}
