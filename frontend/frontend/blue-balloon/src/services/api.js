export class ApiError extends Error {constructor(message, status) {super(message); this.status = status;}}
export async function request(path, {signal, body, ...options} = {}) {
  const response = await fetch(`${import.meta.env.VITE_API_URL || '/api'}${path}`, {...options, signal, credentials: 'include', headers: {'Content-Type': 'application/json', ...options.headers}, body: body === undefined ? undefined : JSON.stringify(body)});
  if (!response.ok) {if (response.status === 401) window.dispatchEvent(new Event('bb-session-expired')); throw new ApiError(`Request failed (${response.status})`, response.status);}
  return response.status === 204 ? undefined : response.json();
}
// No live adapter is enabled until the endpoints in docs/frontend-api-endpoints.md exist.
