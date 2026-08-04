/** Shared tokens. Colours match the paper's figure palette so a chart in the
 *  app and the same chart in the PDF read as one system. */
export const theme = {
  bg: '#0f1419',
  card: '#171d24',
  border: '#252d36',
  text: '#e8e8e4',
  muted: '#8b96a3',
  // Layer colours, identical to netcol/autocol/bridgecol in the .tex preamble.
  network: '#1f4e79',
  autonomy: '#12785a',
  bridge: '#b06000',
  accent: '#d08a5e',
  danger: '#c0392b',
  ok: '#12785a',
};

/** Provenance chips. The colour encodes evidence strength, not decoration. */
export const provenanceStyle = {
  real_corpus: { label: 'real corpus', color: theme.ok },
  simulation: { label: 'simulation', color: theme.network },
  fixture: { label: 'fixture', color: theme.bridge },
  pending: { label: 'pending', color: theme.danger },
};

export const certStatusStyle = {
  ok: { label: 'certified', color: theme.ok },
  unit_bridge_missing: { label: 'unit bridge missing', color: theme.bridge },
  kl_pending: { label: 'KL pending', color: theme.danger },
  not_applicable: { label: '—', color: theme.muted },
};
