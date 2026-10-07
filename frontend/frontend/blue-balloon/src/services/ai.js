// Free-text AI completion (manuscript rewrites, canvas assistant chat).
//
// The FastAPI backend in server/app.py does NOT expose a general text-completion
// endpoint — it only drives the image pipeline (generate/correct/edit pages,
// design character sheets). There is deliberately no /ai/complete route to call.
// So this stays an honest, explicit "unavailable" fallback; callers in
// workspace.js / manuscript.js already catch it and preserve the original text.
//
// If a text endpoint is added later, wire it here via `request('/…', {…})`.
export const aiService = {
  async complete() {throw new Error('AI generation is unavailable in this local demo.');},
};
