import { request } from './client';

/**
 * UAV / Aerial Defense endpoints.
 *
 * Kept beside the core client rather than inside it because this group is a
 * self-contained surface ported from robustidps.ai: it can be lifted out, or
 * pointed at a different backend, without disturbing the composition API that
 * the paper's headline depends on.
 */
export const uavApi = {
  overview: () => request('/api/uav/overview'),
  curves: () => request('/api/uav/ew-bench/curves'),
  operatingPoint: (jsDb) => request(`/api/uav/ew-bench/operating-point?js_db=${jsDb}`),
  certificates: () => request('/api/uav/certificates'),
  swarm: () => request('/api/uav/swarm/snapshots'),
  gnss: (seed) => request(`/api/uav/gnss/sky${seed != null ? `?seed=${seed}` : ''}`),
  attackCatalog: () => request('/api/uav/perception/catalog'),
  dossier: () => request('/api/uav/dossier'),
  reviewPlan: (text, format = 'text') =>
    request('/api/uav/mission-plan/review', {
      method: 'POST', body: JSON.stringify({ text, format }),
    }),

  fleet: (session = 'demo') => request(`/api/uav/fleet?session=${session}`),
  fleetStep: (body) =>
    request('/api/uav/fleet/step', { method: 'POST', body: JSON.stringify(body) }),
  fleetReset: (body) =>
    request('/api/uav/fleet/reset', { method: 'POST', body: JSON.stringify(body) }),
};
