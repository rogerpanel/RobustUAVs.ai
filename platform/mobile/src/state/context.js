/**
 * A small session store of what the user has looked at and what came back.
 *
 * This is what makes the copilot chips work the way robustidps.ai's do: a chip
 * is not a canned question, it is a question about a result the user has
 * actually just produced. Visiting UAV Monitor at J/S = 20 dB and then opening
 * the copilot should offer "why does the framework pass DO-326A at 20 dB when
 * Seq2Seq does not?" -- a question that only makes sense because of where they
 * have been.
 *
 * Deliberately in-memory and per-session. Persisting it would mean storing a
 * visitor's browsing trail, which this artifact has no reason to keep, and a
 * demo that starts clean for the next person is the right default.
 */

const MAX_ENTRIES = 12;

let entries = [];          // most recent first
const listeners = new Set();

function emit() {
  const snapshot = entries.slice();
  listeners.forEach((fn) => { try { fn(snapshot); } catch { /* listener's problem */ } });
}

/**
 * Record that a page produced something worth asking about.
 *
 * @param routeKey  the route the result came from
 * @param label     short chip text, imperative or noun phrase
 * @param question  the query to hand the copilot when the chip is tapped
 * @param data      optional payload the copilot can cite
 */
export function recordContext({ routeKey, label, question, data }) {
  if (!routeKey || !label || !question) return;
  // Replace rather than append when the same page reports again: a user who
  // drags a slider ten times should leave one chip, not ten.
  entries = [
    { routeKey, label, question, data, at: nowIso() },
    ...entries.filter((e) => !(e.routeKey === routeKey && e.label === label)),
  ].slice(0, MAX_ENTRIES);
  emit();
}

export function getContext() {
  return entries.slice();
}

export function clearContext() {
  entries = [];
  emit();
}

export function subscribeContext(fn) {
  listeners.add(fn);
  fn(entries.slice());
  return () => listeners.delete(fn);
}

// `new Date()` is fine in the client; the ban on it applies to workflow
// scripts, not to app code.
function nowIso() {
  try { return new Date().toISOString(); } catch { return ''; }
}
