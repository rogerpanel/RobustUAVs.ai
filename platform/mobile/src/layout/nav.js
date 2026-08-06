/**
 * The navigation model, declared once and consumed by three presentations:
 * the left rail on wide screens, the overlay drawer on narrow ones, and the
 * bottom tab bar under the thumb.
 *
 * Keeping it as data rather than as JSX inside each presentation is what makes
 * the three stay in sync -- a route added here appears in all of them, and the
 * mobile tab bar cannot silently drift from the desktop sidebar.
 *
 * The grouping mirrors robustidps.ai's sidebar: short uppercase section labels
 * over a dense list, so a viewer scans headings first and items second.
 */

/** Primary operations. Left rail on wide screens, drawer on narrow ones. */
export const LEFT_GROUPS = [
  {
    label: 'Results',
    items: [
      { key: 'Milestones', glyph: '◆', title: 'Milestones',
        blurb: 'What the campaign has established' },
      { key: 'Composition', glyph: '⟶', title: 'Composition',
        blurb: 'θ ↦ Δ ↦ δ ↦ MCR, computed live' },
    ],
  },
  {
    label: 'Experiments',
    items: [
      { key: 'Runs', glyph: '▶', title: 'Runs',
        blurb: 'Drive the engine with your own settings' },
      { key: 'Copilot', glyph: '✦', title: 'Copilot',
        blurb: 'Ask; every answer cites its source file' },
    ],
  },
  {
    label: 'Corpus',
    items: [
      { key: 'Overview', glyph: '◈', title: 'Datasets',
        blurb: 'Six sources under one schema' },
      { key: 'Registry', glyph: '▤', title: 'Model registry',
        blurb: 'M1–M7 with provenance and certificate status' },
    ],
  },
  {
    label: 'Present',
    items: [
      { key: 'Cover', glyph: '◇', title: 'Cover page',
        blurb: 'First slide of the talk' },
    ],
  },
];

/** Flat list, for the router and for resolving a key to its metadata. */
export const ROUTES = LEFT_GROUPS.flatMap((g) => g.items);
export const DEFAULT_ROUTE = 'Milestones';

export function routeMeta(key) {
  return ROUTES.find((r) => r.key === key) ?? ROUTES[0];
}

/**
 * The five that earn a permanent slot under the thumb. Everything else stays
 * one tap away behind "More" -- a tab bar with eight items has no target big
 * enough to hit reliably on a phone, which defeats the point of having one.
 */
export const TAB_KEYS = ['Milestones', 'Composition', 'Runs', 'Copilot'];

/**
 * Right rail: reference and context rather than navigation. Sections are
 * rendered by RightRail itself, since each has a different shape (live chips,
 * static facts, external links) and forcing them into one item schema would
 * cost more than it saves.
 */
export const EXTERNAL_LINKS = [
  { label: 'Artifact tree', href: '/artifact/',
    note: 'schema, adapters, engine, results' },
  { label: 'Kaggle corpus', href: 'https://www.kaggle.com/datasets/rogernickanaedevha/uavs-network-and-navigation-end-to-end-security-data',
    note: 'DOI 10.34740/kaggle/dsv/18346203' },
  { label: 'API health', href: '/api/health',
    note: 'live deployment status' },
];

/** The four certificates, with the honest status of each. */
export const CERTIFICATES = [
  { name: 'Lipschitz–Grönwall', tone: 'ok',
    note: 'proved and empirically verified; the paper’s weight sits here' },
  { name: 'Randomized smoothing', tone: 'ok',
    note: 'Cohen bound, σ = 0.25, radius 0.44' },
  { name: 'PAC-Bayes', tone: 'pending',
    note: 'numeric KL term pending data — flagged, not substituted' },
  { name: 'MWU regret', tone: 'ok',
    note: 'adaptive jammer, |S| = 4' },
];
