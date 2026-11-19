import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { papersApi } from '../../api/papers';
import { useTheme, fonts } from '../../theme';
import LineChart from '../../components/LineChart';
import ExportMenu from '../../components/ExportMenu';
import { Panel, KV } from '../uav/parts';
import { classify, fmt, Pills, DataTable } from './parts';

const CORRIDORS = [5, 10, 20, 30];
const NETS = [0, 2.65];

/**
 * Paper IV's design rule: how often to re-anchor for a given corridor.
 *
 * The proved stealth budget against the trusted re-anchoring interval comes from
 * paperIV/results/r10_bound_conf.csv (linear loop, every causal adaptive
 * GNSS-offset attacker, with and without the finite-sample correction). The
 * recommendation is the largest evaluated interval whose corrected bound, plus the
 * network tube, fits the corridor; nothing is interpolated. The PX4 rows are what
 * the software-in-the-loop study measured, not proofs.
 */
export default function DesignRulePanel({ width }) {
  const { t } = useTheme();
  const s = styles(t);
  const [m, setM] = useState(20);
  const [net, setNet] = useState(0);
  const [d, setD] = useState(null);
  const [state, setState] = useState({});

  useEffect(() => {
    let live = true;
    setState({});
    papersApi.designRule(m, net)
      .then((x) => { if (live) setD(x); })
      .catch((e) => { if (live) setState(classify(e)); });
    return () => { live = false; };
  }, [m, net]);

  if (state.unavailable || state.error) {
    return (
      <Panel title="Design rule: how often to re-anchor">
        <Text style={s.err}>{state.unavailable ?? state.error}</Text>
      </Panel>
    );
  }
  if (!d) return null;

  const rec = d.recommendation;
  const px = d.px4 ?? {};
  const w = Math.min(width - 60, 720);
  const conf = d.confidence ?? {};
  return (
    <Panel title="Design rule: how often to re-anchor"
           accent={rec?.T_a_s != null ? t.accent : t.danger}
           subtitle={`Proved worst-case undetected deviation for every adaptive GNSS-offset attacker, against the trusted re-anchoring interval (linear loop, D1 + anchor gate + saturation alarm, ${fmt((conf.fpr ?? 0.01) * 100)}% FPR). Corrected: holds with probability ≥ ${fmt(1 - (conf.eps ?? 0.01))} over benign noise, with confidence ≥ ${fmt(1 - (conf.delta ?? 0.05))} over the calibration sample.`}>
      <Text style={s.label}>corridor half-width m</Text>
      <Pills options={CORRIDORS} value={m} onChange={setM} labelOf={(v) => `${v} m`} />
      <Text style={s.label}>network tube subtracted</Text>
      <Pills options={NETS} value={net} onChange={setNet}
             labelOf={(v) => (v ? `${v} m (θ_net 0.25 s, H 2)` : 'none')} />

      <View style={[s.verdict, { borderColor: rec?.T_a_s != null ? t.accent : t.danger }]}>
        <Text style={[s.verdictText, { color: rec?.T_a_s != null ? t.accent : t.danger }]}>
          {rec?.T_a_s != null
            ? `re-anchor at least every ${fmt(rec.T_a_s)} s  (bound ${fmt(rec.bound_corrected_m)} m)`
            : 'no evaluated interval fits'}
        </Text>
      </View>
      <Text style={s.hint}>{rec?.note}</Text>

      <View nativeID="paper4-design-rule" style={{ marginTop: 10 }}>
        <LineChart width={w} height={w < 420 ? 200 : 240}
          xLabel="re-anchoring interval T_a (s)" yLabel="bound (m)" yMin={0}
          yMax={Math.ceil((Math.max(...d.table.map((b) => b.bound_corrected_m), m) * 1.1) / 10) * 10}
          threshold={{ y: m - net, label: net ? `corridor ${m} m − tube` : `corridor ${m} m`, color: t.danger }}
          series={[
            { key: 'cor', label: 'proved bound, finite-sample corrected', color: t.accent,
              points: d.table.map((b) => ({ x: b.T_a_s, y: b.bound_corrected_m })) },
            { key: 'emp', label: 'large-sample margins', color: t.network, dash: true,
              points: d.table.map((b) => ({ x: b.T_a_s, y: b.bound_large_sample_m })) },
          ]}
          marker={rec?.T_a_s != null ? { x: rec.T_a_s, label: 'recommended' } : null} />
      </View>
      <DataTable rows={d.table} columns={['T_a_s', 'bound_large_sample_m', 'bound_corrected_m']}
                 colWidth={120} />

      <Text style={[s.label, { marginTop: 14 }]}>measured in PX4 software-in-the-loop (worst undetected deviation)</Text>
      <KV k="bound's detectors, re-anchoring 1 s / 5 s"
          v={`${fmt(px.worst_D1_gate_1s_m)} m / ${fmt(px.worst_D1_gate_5s_m)} m`} />
      <KV k="full detector stack, re-anchoring 1 s / 5 s"
          v={`${fmt(px.worst_ALL_gate_1s_m)} m / ${fmt(px.worst_ALL_gate_5s_m)} m`} />
      <KV k="full stack without the anchor gate, 1 s / 5 s"
          v={`${fmt(px.worst_ALL_nogate_1s_m)} m / ${fmt(px.worst_ALL_nogate_5s_m)} m`} />
      {px.no_anchor_ramp_evasion != null ? (
        <KV k="no trusted fix: slow ramp evades / drifts" tone={t.danger}
            v={`${fmt(px.no_anchor_ramp_evasion * 100)}% / ${fmt(px.no_anchor_ramp_deviation_m)} m`} />
      ) : null}
      <Text style={s.hint}>{d.scope}</Text>
      <Text style={s.source}>source: {d.source}</Text>
      <View style={s.exportRow}>
        <ExportMenu title="Paper IV design rule" data={d} csv={d.table} sources={d.source}
                    svgId="paper4-design-rule" />
      </View>
    </Panel>
  );
}

const styles = (t) => StyleSheet.create({
  label: {
    color: t.muted, fontSize: 9.5, fontWeight: '700', letterSpacing: 0.5,
    textTransform: 'uppercase', marginBottom: 4, marginTop: 6,
  },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 4 },
  err: { color: t.danger, fontSize: 11.5, marginTop: 8 },
  source: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, marginTop: 8 },
  verdict: {
    borderWidth: 1, borderRadius: 8, paddingVertical: 9,
    alignItems: 'center', marginTop: 12, marginBottom: 4,
  },
  verdictText: { fontSize: 13.5, fontWeight: '800', letterSpacing: 0.5, textAlign: 'center' },
  exportRow: { flexDirection: 'row', justifyContent: 'flex-end', marginTop: 10 },
});
