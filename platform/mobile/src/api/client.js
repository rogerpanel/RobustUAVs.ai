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
import { sessionId } from '../state/session';

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

/**
 * The endpoint does not exist on this server.
 *
 * Distinct from `Unavailable` on purpose. A 503 means the endpoint is there and
 * its result has not been produced -- a data gap. A 404 means the client is
 * asking for something this API does not have, which is almost always a client
 * newer than the deployed backend. Reporting the second as the first sends the
 * reader to PENDING_ON_DATA.md when the actual fix is to restart the API.
 */
export class NotDeployed extends Error {
  constructor(path) {
    super(`This build calls ${path}, which the deployed API does not serve. `
      + 'The client and the control plane are out of step — the API needs the '
      + 'same commit the client was built from.');
    this.name = 'NotDeployed';
    this.path = path;
  }
}

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
      // Scopes the fleet, the run list and the rate allowance to this browser.
      // Not a credential -- see platform/backend/app/sessions.py.
      'X-Session-Id': sessionId(),
      ...(AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : {}),
      ...(options.headers || {}),
    },
  });

  if (res.status === 503) {
    const body = await res.json().catch(() => ({}));
    throw new Unavailable(body?.detail?.unavailable ?? path, body?.detail?.error);
  }
  if (res.status === 404) throw new NotDeployed(path);
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
  // A caller-supplied key is sent for this one request and is never stored
  // here, in localStorage, or on the server.
  ask: (question, provider, apiKey) =>
    request('/api/copilot/ask', {
      method: 'POST',
      body: JSON.stringify({
        question,
        ...(apiKey ? { provider, api_key: apiKey } : {}),
      }),
    }),
};

export { API_BASE };
