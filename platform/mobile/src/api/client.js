/**
 * API client for the RobustUAVs.ai control plane.
 *
 * Two behaviours matter more than they look:
 *
 *  - A 503 is NOT an error to swallow. The backend returns 503 when an endpoint
 *    exists but its result file has not been produced in this deployment (a
 *    data-gated item). The UI must say "not produced yet" rather than "failed",
 *    because those mean different things to a reviewer.
 *  - Every payload carries a `source`. Screens render it, so a viewer can
 *    always see which committed file a number came from.
 */
import Constants from 'expo-constants';

/**
 * Origin first, config second.
 *
 * On the web the client is served from the same origin as the API, so the page
 * it loaded from is always the correct answer -- and asking it keeps the build
 * host-agnostic, which a hardcoded https://robustuavs.ai does not: the same
 * bundle then works on the server, on a staging host, and against a local
 * `uvicorn` with no rebuild. Native builds have no `window`, so they fall
 * through to `extra.apiBase`.
 */
const API_BASE =
  (typeof window !== 'undefined' && window.location?.origin) ||
  Constants?.expoConfig?.extra?.apiBase ||
  'http://localhost:8000';

export class Unavailable extends Error {
  constructor(name, detail) {
    super(detail ?? `${name} has not been produced in this deployment`);
    this.name = 'Unavailable';
    this.resource = name;
  }
}

let AUTH_TOKEN = null;
/** Set when a deployment runs with API_TOKENS. There is no login screen by
 *  design; the token is supplied out of band. */
export function setToken(token) { AUTH_TOKEN = token || null; }

export async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : {}),
      ...(options.headers || {}),
    },
  });

  if (res.status === 503) {
    const body = await res.json().catch(() => ({}));
    throw new Unavailable(body?.detail?.unavailable ?? path, body?.detail?.error);
  }
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}${body ? `: ${body}` : ''}`);
  }
  return res.json();
}

export const api = {
  health: () => request('/api/health'),

  models: (category) =>
    request(`/api/models${category ? `?category=${encodeURIComponent(category)}` : ''}`),
  model: (id) => request(`/api/models/${encodeURIComponent(id)}`),

  resultsIndex: () => request('/api/results'),
  result: (name) => request(`/api/results/${encodeURIComponent(name)}`),

  certifyStaleness: (body) =>
    request('/api/certify/staleness', { method: 'POST', body: JSON.stringify(body) }),

  runners: () => request('/api/runners'),
  runs: (limit = 25, kind) =>
    request(`/api/runs?limit=${limit}${kind ? `&kind=${encodeURIComponent(kind)}` : ''}`),
  run: (id) => request(`/api/runs/${encodeURIComponent(id)}`),
  submitRun: (body) =>
    request('/api/runs', { method: 'POST', body: JSON.stringify(body) }),
  cancelRun: (id) =>
    request(`/api/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),

  copilotTools: () => request('/api/copilot/tools'),
  ask: (question) =>
    request('/api/copilot/ask', { method: 'POST', body: JSON.stringify({ question }) }),
};

export { API_BASE };
