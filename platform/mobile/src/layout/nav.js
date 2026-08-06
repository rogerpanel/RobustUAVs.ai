/**
 * The navigation model, declared once and consumed by three presentations:
 * the left rail on wide screens, the overlay drawer on narrow ones, and the
 * bottom tab bar under the thumb.
 *
 * Keeping it as data rather than as JSX inside each presentation is what makes
 * the three stay in sync -- a route added here appears in all of them, and the
 * phone tab bar cannot silently drift from the desktop sidebar.
 *
 * The UAV / Aerial Defense group is the Chapter 6 operator surface, ported from
 * robustidps.ai. `grounded: false` marks a page whose figures are illustrative
 * rather than read from a committed result; the page says so on its face, and
 * the rail shows a dot so it is visible before you open it.
 */

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
    label: 'UAV / Aerial Defense',
    items: [
      { key: 'UAVMonitor', glyph: '✈', title: 'UAV Monitor', grounded: true,
        blurb: 'MCR vs jamming, four configurations' },
      { key: 'SwarmGraph', glyph: '⬡', title: 'Swarm Graph', grounded: true,
        blurb: 'Mesh under delay and intrusion' },
      { key: 'FleetDemo', glyph: '◉', title: 'Live Fleet Demo', grounded: false,
        blurb: 'Flights moving under attack, in real time' },
      { key: 'GNSSSpoof', glyph: '✳', title: 'GNSS Spoof Monitor', grounded: false,
        blurb: 'Sky plot and the measured γ' },
      { key: 'Certification', glyph: '✓', title: 'Certification Dashboard', grounded: true,
        blurb: 'The four certificates and two floors' },
      { key: 'MissionPlan', glyph: '☰', title: 'Mission Plan Review', grounded: true,
        blurb: 'Preconditions the theorem needs' },
      { key: 'Perception', glyph: '⚡', title: 'Perception Tester', grounded: false,
        blurb: 'Adversarial attack suite' },
      { key: 'Dossier', glyph: '▦', title: 'Assurance Dossier', grounded: true,
        blurb: 'Evidence table, including the empty class' },
    ],
  },
  {
    label: 'Evaluation',
    items: [
      { key: 'Robustness', glyph: '◐', title: 'Robustness', grounded: true,
        blurb: 'Certified floor as the detector loosens' },
      { key: 'Ablations', glyph: '◑', title: 'Ablation studies', grounded: true,
        blurb: 'What each component is responsible for' },
      { key: 'ROC', glyph: '◭', title: 'Detector ROC', grounded: true,
        blurb: 'Recall, FPR, and the θ_eff generalisation' },
      { key: 'Statistics', glyph: '∑', title: 'Statistical tests', grounded: true,
        blurb: 'Wilcoxon signed-rank + Holm' },
      { key: 'Calibration', glyph: '◔', title: 'Calibration (ECE)', grounded: false,
        blurb: 'Why it is not computable yet' },
    ],
  },
  {
    label: 'Build',
    items: [
      { key: 'AgentStudio', glyph: '⚒', title: 'Agent Studio', grounded: true,
        blurb: 'Compose and submit an experiment' },
      { key: 'Federated', glyph: '⇄', title: 'Federated Learning', grounded: false,
        blurb: 'M7 FedGTD, the MWU defender' },
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

export const ROUTES = LEFT_GROUPS.flatMap((g) => g.items);
export const DEFAULT_ROUTE = 'Milestones';

export function routeMeta(key) {
  return ROUTES.find((r) => r.key === key) ?? ROUTES[0];
}

/**
 * The four that earn a permanent slot under the thumb. Everything else stays
 * one tap away behind "More" -- a tab bar with fourteen items has no target
 * big enough to hit reliably, which defeats the point of having one.
 */
export const TAB_KEYS = ['Milestones', 'UAVMonitor', 'FleetDemo', 'Composition'];

export const EXTERNAL_LINKS = [
  { label: 'Artifact tree', href: '/artifact/',
    note: 'schema, adapters, engine, results' },
  { label: 'Kaggle corpus', href: 'https://www.kaggle.com/datasets/rogernickanaedevha/uavs-network-and-navigation-end-to-end-security-data',
    note: 'DOI 10.34740/kaggle/dsv/18346203' },
  { label: 'API health', href: '/api/health',
    note: 'live deployment status' },
];

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
