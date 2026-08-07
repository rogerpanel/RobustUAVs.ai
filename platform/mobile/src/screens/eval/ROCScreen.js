import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, useWindowDimensions } from 'react-native';
import { evalApi } from '../../api/evaluation';
import { useTheme, fonts } from '../../theme';
import LineChart from '../../components/LineChart';
import { ScreenHeader, Panel, Unavailable, KV } from '../uav/parts';

/**
 * Recall and FPR across the epsilon grid, plus the generalisation that makes
 * the composition detector-agnostic.
 */
export default function ROCScreen() {
  const { t } = useTheme();
  const { width } = useWindowDimensions();
  const s = styles(t);
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { evalApi.roc().then(setD).catch((e) => setError(e.message)); }, []);
  if (error) return <Unavailable message={error} />;
  if (!d) return <Text style={s.loading}>loading…</Text>;

  const w = Math.min(width - 60, 720);
  const palette = [t.ok, t.network, t.info, t.bridge, t.accent, t.danger];

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader eyebrow="Evaluation" title="Detector operating curve"
        lede="Recall against the threshold ε, per scenario and attack mode.
              False-positive rate is identically zero across the whole grid."
        grounded source={d.source}
        exportData={d} exportSvgId="roc-chart"
        exportCsv={d.curves.flatMap((c) => c.points.map((pt) => ({
          curve: c.label, epsilon: pt.epsilon, recall: pt.recall,
          fpr: pt.fpr, precision: pt.precision, n_runs: pt.n_runs,
        })))} />

      <Panel title="Recall vs ε">
        <View nativeID="roc-chart">
        <LineChart
          width={w} height={w < 420 ? 200 : 250}
          xLabel="ε" yLabel="recall" xUnit=" s" yMin={0} yMax={1.05}
          marker={{ x: 5, label: 'contact window' }}
          series={d.curves.map((c, i) => ({
            key: c.label, label: c.label, color: palette[i % palette.length],
            points: c.points.map((p) => ({ x: p.epsilon, y: p.recall })),
          }))}
        />
        </View>
        <KV k="FPR across the entire grid"
            v={d.fpr_is_identically_zero ? '0.000 — identically zero' : 'non-zero somewhere'}
            tone={d.fpr_is_identically_zero ? t.ok : t.bridge} />
        <KV k="benign residual ceiling" v={`${d.benign_ceiling_s} s (measured)`} />
      </Panel>

      <Panel title="The knee" accent={t.bridge}>
        <Text style={s.body}>{d.knee.explanation}</Text>
        <KV k="inter-UAV contact window" v={`${d.knee.contact_window_s} s`} />
        <KV k="cost of a missed window" v={`${d.knee.twig_period_s} s (full TWiG period)`} />
      </Panel>

      <Panel title="Generalising past a threshold detector" accent={t.ok}>
        <Text style={s.formula}>{d.generalisation.formula}</Text>
        <Text style={s.body}>{d.generalisation.reading}</Text>
        {d.generalisation.requirements.map((r) => (
          <KV key={r} k="requires" v={r} />
        ))}
        <Text style={s.hint}>
          This is what makes the harness a framework for any IDS rather than a
          wrapper around DATAMUt. Any detector reporting an ROC curve substitutes
          in without touching the theorem.
        </Text>
      </Panel>
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19, marginBottom: 6 },
  formula: {
    color: t.accent, fontSize: 14, fontFamily: fonts.mono, marginBottom: 8,
    textAlign: 'center',
  },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 8 },
});
