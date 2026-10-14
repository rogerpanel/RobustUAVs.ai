import { request, API_BASE } from './client';

/**
 * The three follow-on papers: result browser plus each paper's calculator.
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

  // Paper II -- the coded corpus. `filters` is { field: value }.
  corpus: ({ table, yearMin, yearMax, filters } = {}) =>
    request(`/api/papers/II/corpus${query({
      table, year_min: yearMin, year_max: yearMax, ...(filters ?? {}),
    })}`),

  // Paper III -- certificate combinatorics, the i.i.d. lift, the MARL tables.
  certifyDefaults: () => request('/api/papers/III/certify'),
  certify: (body) => post('/api/papers/III/certify', body),
  lift: (body) => post('/api/papers/III/lift', body),
  marl: () => request('/api/papers/III/marl'),
};
