import { request, API_BASE } from './client';

/**
 * The follow-on papers: result browser plus each paper's calculator.
 *
 * Result names are relative paths (`e5_marl_N24/references_eval.csv`), so each
 * segment is encoded on its own and the slashes are kept: encoding the whole
 * name would send `%2F`, which the server treats as part of a filename.
 */
const encodePath = (name) => String(name).split('/').map(encodeURIComponent).join('/');

const query = (opts = {}) => {
  const q = new URLSearchParams(
    Object.entries(opts)
      .filter(([, v]) => v != null && v !== '')
      .map(([k, v]) => [k, String(v)]),
  ).toString();
  return q ? `?${q}` : '';
};

const post = (path, body) =>
  request(path, { method: 'POST', body: JSON.stringify(body ?? {}) });

export const papersApi = {
  catalogue: () => request('/api/papers'),
  results: (pid) => request(`/api/papers/${pid}/results`),
  result: (pid, name) => request(`/api/papers/${pid}/results/${encodePath(name)}`),
  /** The committed file itself, for a download link rather than a fetch. */
  resultCsvUrl: (pid, name) =>
    `${API_BASE}/api/papers/${pid}/results/${encodePath(name)}?format=csv`,

  // Paper I -- the authentication budget.
  budgetDefaults: () => request('/api/papers/I/budget'),
  budget: (body) => post('/api/papers/I/budget', body),
  /** rho across one input: { vary, lo, hi, n, base } -- base is a budget request. */
  budgetSweep: (body) => post('/api/papers/I/budget/sweep', body),
  /** Every signature scheme on one transport, each through the same budget. */
  budgetSchemes: (body) => post('/api/papers/I/budget/schemes', body),

  // Paper II -- the coded corpus. `filters` is { field: value }.
  corpus: ({ table, yearMin, yearMax, filters } = {}) =>
    request(`/api/papers/II/corpus${query({
      table, year_min: yearMin, year_max: yearMax, ...(filters ?? {}),
    })}`),

  /** One paper's record at every stage of the study. */
  trace: ({ id, table }) => request(`/api/papers/II/trace${query({ id, table })}`),
  /** Coder agreement recomputed for the papers the filters select. */
  agreement: ({ table, yearMin, yearMax, filters } = {}) =>
    request(`/api/papers/II/agreement${query({
      table, year_min: yearMin, year_max: yearMax, ...(filters ?? {}),
    })}`),

  // Paper III -- certificate combinatorics, the i.i.d. lift, the MARL tables.
  certifyDefaults: () => request('/api/papers/III/certify'),
  certify: (body) => post('/api/papers/III/certify', body),
  lift: (body) => post('/api/papers/III/lift', body),
  liftSimulate: (body) => post('/api/papers/III/lift/simulate', body),
  marl: () => request('/api/papers/III/marl'),

  // Paper IV -- the dependence-uncertainty floor of the unified budget.
  floorDefaults: () => request('/api/papers/IV/floor'),
  floor: (body) => post('/api/papers/IV/floor', body),
  floorSweep: (body) => post('/api/papers/IV/floor/sweep', body),
  marginals: (alpha) => request(`/api/papers/IV/marginals${query({ alpha })}`),
};
