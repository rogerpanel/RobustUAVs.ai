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

const API_BASE =
  Constants?.expoConfig?.extra?.apiBase ??
  (typeof window !== 'undefined' && window.location?.origin) ??
  'http://localhost:8000';

export class Unavailable extends Error {
  constructor(name, detail) {
    super(detail ?? `${name} has not been produced in this deployment`);
    this.name = 'Unavailable';
    this.resource = name;
  }
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
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

  copilotTools: () => request('/api/copilot/tools'),
  ask: (question) =>
    request('/api/copilot/ask', { method: 'POST', body: JSON.stringify({ question }) }),
};

export { API_BASE };
