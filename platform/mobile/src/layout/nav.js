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
        blurb: 'What the campaign has established',
        steps: [
          "Read the six cards top to bottom — each is one result from the campaign.",
          "Check the mono line at the bottom of a card: it names the committed CSV the number came from.",
          "Note MS5 and MS6 — both weaken an earlier draft. They are shown with the same weight as the favourable ones.",
          "Tap the orange bar to reproduce MS1 live on the Composition screen.",
        ],
        tip: "If an examiner asks about a limitation, it is already on this page rather than waiting to be found."  },
      { key: 'Composition', glyph: '⟶', title: 'Composition',
        blurb: 'θ ↦ Δ ↦ δ ↦ MCR, computed live',
        steps: [
          "Pick a detector operating point θ. 0.178 s is the measured benign ceiling; 0.25 s is the paper's.",
          "Pick a θ ↦ δ mapping. This is the control that decides the outcome.",
          "Pick a corridor margin m. JARUS SORA's default lateral terms total 7 m.",
          "Read the verdict. Flip Kinematic ↔ EKF at θ = 0.25 s to see the same theorem give opposite answers.",
        ],
        tip: "The verdict is computed by the certificate engine on each change, not read from a table."  },
    ],
  },
  {
    label: 'UAV / Aerial Defense',
    items: [
      { key: 'UAVMonitor', glyph: '✈', title: 'UAV Monitor', grounded: true,
        blurb: 'MCR vs jamming, four configurations',
        steps: [
          "Read the chart: MCR against jamming for four configurations. The dashed rule is the DO-326A 0.90 floor.",
          "Below it, tap a J/S value. Every one is a measured grid point, so nothing on the tiles is interpolated.",
          "Compare the four tiles — green border means that configuration clears the floor at that J/S.",
          "Check the 'holds the floor to' lines under the chart for each configuration's breaking point.",
        ],
        tip: "This is Spatial MCR only: a delay attack that lands safely but late passes every curve here."  },
      { key: 'SwarmGraph', glyph: '⬡', title: 'Swarm Graph', grounded: true,
        blurb: 'Mesh under delay and intrusion',
        steps: [
          "Switch between the three snapshots: clean, delayed within budget, past the contact window.",
          "Read the number on each edge — it is the per-hop residual delay in seconds.",
          "Red numbers exceed θ, so the detector fires; amber edges are delayed but under budget.",
          "Compare t₂ and t₃: the difference between an evading adversary and a detected one.",
        ],
        tip: "The knee at 5 s is the inter-UAV contact window, and it is what makes recall collapse."  },
      { key: 'FleetDemo', glyph: '◉', title: 'Live Fleet Demo', grounded: false,
        blurb: 'Flights moving under attack, in real time',
        steps: [
          "Press ▶ fly. Four aircraft begin a circuit; the dashed ring is the corridor, the filled ring the certified tube.",
          "Set UAV-01's attack to Relay delay — the class the theorem covers, and the stealthiest.",
          "Watch the solid line grow between nominal and actual position. That separation is γ·Δ.",
          "Now flip the mapping from EKF to Kinematic. The tube jumps outside the corridor with nothing about the attack changed.",
        ],
        tip: "Step 4 is the paper's central claim in one gesture: same theorem, same attack, opposite verdicts."  },
      { key: 'GNSSSpoof', glyph: '✳', title: 'GNSS Spoof Monitor', grounded: false,
        blurb: 'Sky plot and the measured γ',
        steps: [
          "Read the sky plot: red satellites are flagged as spoofed, size scales with confidence.",
          "Tap resample to redraw — the plot is illustrative, and this makes that obvious.",
          "Scroll to 'Measured interface'. Those γ values are the real content of this page.",
          "Compare 1.195/1.365 m/s against the 15 m/s kinematic bound — roughly 11× tighter.",
        ],
        tip: "The Whelan corpus records position error, not per-satellite C/N₀, so the plot cannot be measured."  },
      { key: 'Certification', glyph: '✓', title: 'Certification Dashboard', grounded: true,
        blurb: 'The four certificates and two floors',
        steps: [
          "Start with 'Two floors' — 0.80 certified and 0.90 operational are different quantities.",
          "Read the four certificate panels. Green is verified, amber is pending.",
          "Note PAC-Bayes shows no number: its KL term is pending data and is flagged rather than filled.",
          "Read 'How the four operate on a single flight' for why they are concurrent, not alternative.",
        ],
        tip: "Do not use radii from robustidps.ai's dashboard: those are per-visit 16-sample recomputes."  },
      { key: 'MissionPlan', glyph: '☰', title: 'Mission Plan Review', grounded: true,
        blurb: 'Preconditions the theorem needs',
        steps: [
          "Edit the sample plan, or paste your own.",
          "Press review plan.",
          "Read the findings — each maps to a quantity the composition theorem needs.",
          "Add the missing terms (geofence, deadline, altitude) and re-run to watch findings clear.",
        ],
        tip: "A plan that passes has well-defined MCR predicates. It is not thereby certified safe."  },
      { key: 'Perception', glyph: '⚡', title: 'Perception Tester', grounded: false,
        blurb: 'Adversarial attack suite',
        steps: [
          "Read the catalogue: seven attacks, grouped by family.",
          "Note the physical family — GNSS spoof and link jamming are the classes this paper addresses.",
          "Execution needs trained weights this deployment does not carry, so nothing runs here.",
          "For a certified comparison that does run live, use Composition or Live Fleet Demo.",
        ]  },
      { key: 'Dossier', glyph: '▦', title: 'Assurance Dossier', grounded: true,
        blurb: 'Evidence table, including the empty class',
        steps: [
          "Read the totals first: 431,773 events, 46.5% from real testbeds.",
          "Then read the zero — released measured_same_platform pairings.",
          "Scroll the per-source table; UAV-CAS shows NOT STAGED because its file is not reachable here.",
          "Use this page when asked what fraction of the benchmark is real measurement.",
        ],
        tip: "Offering this is more defensible than having it extracted."  },
    ],
  },
  {
    label: 'Evaluation',
    items: [
      { key: 'Robustness', glyph: '◐', title: 'Robustness', grounded: true,
        blurb: 'Certified floor as the detector loosens',
        steps: [
          "Read the curve: certified floor against the detector threshold θ, one line per mapping.",
          "The vertical rule is the paper's θ = 0.25 s.",
          "Check 'Where each mapping stops binding' — kinematic gives up at 0.05 s, measured at 0.67 s.",
          "Note the shape is a step, not a slope: the certificate binds or it does not.",
        ]  },
      { key: 'Ablations', glyph: '◑', title: 'Ablation studies', grounded: true,
        blurb: 'What each component is responsible for',
        steps: [
          "Read the mapping table: at each corridor margin, how tight γ must be for θ = 0.25 s to certify.",
          "Green ✓ means that mapping clears the requirement; red ✗ means it does not.",
          "Then read the amplification panel — measuring L honestly costs 21.9% of tube radius.",
          "Read the last panel for why per-certificate removal is not a meaningful ablation.",
        ]  },
      { key: 'ROC', glyph: '◭', title: 'Detector ROC', grounded: true,
        blurb: 'Recall, FPR, and the θ_eff generalisation',
        steps: [
          "Read recall against ε for each scenario and attack mode.",
          "Confirm FPR is identically zero across the whole grid.",
          "The marker at 5 s is the contact window — the knee, and the reason recall collapses.",
          "Read the generalisation panel: θ_eff = g⁻¹(P_th) is what makes this work for any scoring detector.",
        ],
        tip: "That last panel is the answer to 'your harness only supports DATAMUt'."  },
      { key: 'Statistics', glyph: '∑', title: 'Statistical tests', grounded: true,
        blurb: 'Wilcoxon signed-rank + Holm',
        steps: [
          "Read the headline first: dominance is 13/13 under every mapping.",
          "Then each family's table — ε, pairs, median difference, Holm-corrected p, significance.",
          "Note the comparisons that are NOT fully significant; they are shown, not hidden.",
          "Read the last panel for why Holm rather than Bonferroni.",
        ]  },
      { key: 'Calibration', glyph: '◔', title: 'Calibration (ECE)', grounded: false,
        blurb: 'Why it is not computable yet',
        steps: [
          "Read why ECE cannot be computed here: the detector emits a boolean, not a score.",
          "Read the method, so the gap is reproducible when the input exists.",
          "Read what would unblock it — a scoring detector, not a surrogate.",
          "Use the Detector ROC page for what IS derivable from a threshold detector.",
        ],
        tip: "A reliability diagram fitted to the residual-delay distribution would be calibrated against itself."  },
    ],
  },
  {
    label: 'Analyse',
    items: [
      { key: 'Upload', glyph: '⬆', title: 'Upload & Analyse', grounded: true,
        blurb: 'Bring your own UAV data',
        steps: [
          "Choose a CSV of UAV telemetry or network records, up to 1 GB.",
          "Press Analyse. The file is streamed and sampled, never loaded whole.",
          "Read the detected schema — it names which columns were recognised and which were ignored.",
          "Press Fly to push detected delay or position-error columns through the certificate engine.",
        ],
        tip: "Nothing is retained: the upload is parsed, summarised and discarded." },
    ],
  },
  {
    label: 'Build',
    items: [
      { key: 'AgentStudio', glyph: '⚒', title: 'Agent Studio', grounded: true,
        blurb: 'Compose and submit an experiment',
        steps: [
          "Pick a runner. Everything in the backend registry appears here automatically.",
          "Edit the parameters — these are what the experiment IS.",
          "Press run experiment. Runs complete in single-digit milliseconds.",
          "Read the result below, including the hyperparameters, which are how it was COMPUTED.",
        ],
        tip: "Keeping params and hyperparams apart is what lets you explain why two runs disagree."  },
      { key: 'Federated', glyph: '⇄', title: 'Federated Learning', grounded: false,
        blurb: 'M7 FedGTD, the MWU defender',
        steps: [
          "Read M7's role: the defender in the MWU regret certificate.",
          "Note trained weights are absent, so federated rounds are not runnable here.",
          "The MWU constant |S| = 4 comes from the dissertation, not from a run.",
          "See the Model registry for the rest of the M1–M7 stack.",
        ]  },
    ],
  },
  {
    label: 'Experiments',
    items: [
      { key: 'Runs', glyph: '▶', title: 'Runs',
        blurb: 'Drive the engine with your own settings',
        steps: [
          "Submit a run, or read the recent ones.",
          "Each row carries params, hyperparams and provenance.",
          "A 503 means the result was never produced here — that is a data gap, not a failure.",
          "For a guided composer, use Agent Studio.",
        ]  },
      { key: 'Copilot', glyph: '✦', title: 'Copilot',
        blurb: 'Ask; every answer cites its source file',
        steps: [
          "Tap a context chip — each one is a question about a result you just produced.",
          "Or type your own question about the corpus, the certificates or the guarantee.",
          "Read the citation under each answer: it names the committed file the number came from.",
          "With no LLM key configured the copilot still answers from the local result cache.",
        ],
        tip: "Chips appear as you visit pages. Visit UAV Monitor or Composition first and come back."  },
    ],
  },
  {
    label: 'Corpus',
    items: [
      { key: 'Overview', glyph: '◈', title: 'Datasets',
        blurb: 'Six sources under one schema',
        steps: [
          "Read the six sources and the layer each covers.",
          "Check the record counts against the Assurance Dossier's provenance split.",
          "Note which sources are staged in this deployment.",
          "Follow /artifact/ for the adapters that produced them.",
        ]  },
      { key: 'Registry', glyph: '▤', title: 'Model registry',
        blurb: 'M1–M7 with provenance and certificate status',
        steps: [
          "Browse the model cards, M1 through M7.",
          "Each card carries provenance and certificate status.",
          "Cards without weights say so — the definitions are here, the trained parameters are not.",
          "M7 = FedGTD has its own page under Build.",
        ]  },
    ],
  },
  {
    label: 'Present',
    items: [
      { key: 'Cover', glyph: '◇', title: 'Cover page',
        blurb: 'First slide of the talk',
        steps: [
          "Use this as the first slide of a talk.",
          "Switch to the print theme before projecting — the dark palette washes out.",
          "The 'Stated up front' panel is deliberate: lead with the limitation.",
          "The strip at the bottom is live deployment state, not a screenshot.",
        ]  },
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
