/**
 * Design tokens, taken verbatim from robustidps.ai `frontend/src/index.css`
 * so the two platforms read as one product family.
 *
 * Two palettes, exactly as there:
 *   dark   — the working interface (slate-950 canvas)
 *   print  — ivory canvas with darkened accents, for screenshots that must
 *            survive a projector or a printed manuscript at 300 dpi
 *
 * The print theme is not decoration. A conference projector washes out a dark
 * UI badly, so the presenter can flip the whole app from the Overview screen
 * and still have every status colour distinguishable.
 */
import React, { createContext, useContext, useMemo, useState } from 'react';

const dark = {
  name: 'dark',
  bgPrimary: '#0F172A',    // slate-950
  bgSecondary: '#1E293B',  // slate-800 — sidebar / panel
  bgCard: '#334155',       // slate-700
  textPrimary: '#F8FAFC',
  textSecondary: '#94A3B8',
  accentBlue: '#3B82F6',
  accentRed: '#EF4444',
  accentAmber: '#F59E0B',
  accentGreen: '#22C55E',
  accentPurple: '#A855F7',
  accentOrange: '#F97316',
  border: '#334155',
};

const print = {
  name: 'print',
  bgPrimary: '#F8FAFC',    // ivory
  bgSecondary: '#EEF2F7',  // soft mist
  bgCard: '#FFFFFF',
  textPrimary: '#0F172A',  // deep navy
  textSecondary: '#475569',
  accentBlue: '#1D4ED8',
  accentRed: '#B91C1C',
  accentAmber: '#B45309',
  accentGreen: '#15803D',
  accentPurple: '#7E22CE',
  accentOrange: '#B45309',  // burnished gold
  border: '#CBD5E1',
};

export const palettes = { dark, print };

/** Matches the tailwind config: Inter / Space Grotesk / JetBrains Mono. React
 *  Native falls back to the platform sans when a family is not bundled; the
 *  weights carry most of the identity. */
export const fonts = { sans: 'Inter', display: 'Space Grotesk', mono: 'JetBrains Mono' };

/** Semantic layer, so a screen never reaches for a raw hex. The layer colours
 *  also match the papers' pgfplots palette, which is why a chart in the app and
 *  the same chart in the PDF read as one system. */
function semantic(p) {
  return {
    ...p,
    bg: p.bgPrimary,
    panel: p.bgSecondary,
    card: p.bgCard,
    text: p.textPrimary,
    muted: p.textSecondary,
    accent: p.accentOrange,
    network: p.accentBlue,
    autonomy: p.accentGreen,
    bridge: p.accentAmber,
    ok: p.accentGreen,
    danger: p.accentRed,
    info: p.accentPurple,
  };
}

const ThemeContext = createContext({ t: semantic(dark), mode: 'dark', toggle: () => {} });

export function ThemeProvider({ children }) {
  const [mode, setMode] = useState('dark');
  const value = useMemo(() => ({
    mode,
    t: semantic(palettes[mode]),
    toggle: () => setMode((m) => (m === 'dark' ? 'print' : 'dark')),
  }), [mode]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);

export const provenanceStyle = (t) => ({
  real_corpus: { label: 'real corpus', color: t.ok },
  simulation: { label: 'simulation', color: t.network },
  fixture: { label: 'fixture', color: t.bridge },
  pending: { label: 'pending', color: t.danger },
});

export const certStatusStyle = (t) => ({
  ok: { label: 'certified', color: t.ok },
  unit_bridge_missing: { label: 'unit bridge missing', color: t.bridge },
  kl_pending: { label: 'KL pending', color: t.danger },
  not_applicable: { label: '—', color: t.muted },
});

export const runStatusStyle = (t) => ({
  queued: { label: 'queued', color: t.muted },
  running: { label: 'running', color: t.accentBlue },
  done: { label: 'done', color: t.ok },
  failed: { label: 'failed', color: t.danger },
  cancelled: { label: 'cancelled', color: t.bridge },
});
