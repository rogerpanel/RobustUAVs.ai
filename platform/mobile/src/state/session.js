/**
 * A per-browser session id, so two visitors do not share one simulation.
 *
 * Opaque and random, generated client-side, and NOT a credential: it proves
 * nothing about who you are, and the server treats it the same way. It exists
 * so that your fleet, your runs and your uploads are yours for the duration of
 * a visit, not so that they are secret. Everything this artifact holds is
 * already published.
 *
 * Persisted in localStorage rather than sessionStorage so a reload during a
 * conference talk does not reset a demo mid-flight. `crypto.randomUUID` is used
 * where available, with a Math.random fallback for older browsers — this is an
 * identifier, not a key, so a weaker source is a collision risk rather than a
 * security one.
 */
const KEY = 'robustuavs.session';

function generate() {
  try {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID().replace(/-/g, '').slice(0, 32);
    }
  } catch { /* fall through */ }
  let out = '';
  for (let i = 0; i < 32; i += 1) {
    out += 'abcdefghijklmnopqrstuvwxyz0123456789'[Math.floor(Math.random() * 36)];
  }
  return out;
}

let cached = null;

export function sessionId() {
  if (cached) return cached;
  try {
    if (typeof localStorage !== 'undefined') {
      const found = localStorage.getItem(KEY);
      if (found && /^[A-Za-z0-9_-]{8,64}$/.test(found)) { cached = found; return cached; }
      cached = generate();
      localStorage.setItem(KEY, cached);
      return cached;
    }
  } catch { /* private mode, or native */ }
  cached = cached || generate();
  return cached;
}

/** New identity, and therefore a fresh fleet and empty run list. */
export function resetSession() {
  cached = generate();
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(KEY, cached);
  } catch { /* ignore */ }
  return cached;
}
