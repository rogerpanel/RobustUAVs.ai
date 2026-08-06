import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { evalApi } from '../../api/evaluation';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV, Tag } from '../uav/parts';

/** Wilcoxon signed-rank with Holm correction, exactly as run for the paper. */
export default function StatisticsScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { evalApi.statistics().then(setD).catch((e) => setError(e.message)); }, []);
  if (error) return <Unavailable message={error} />;
  if (!d) return <Text style={s.loading}>loading…</Text>;

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader eyebrow="Evaluation" title="Statistical tests"
        lede={d.method} grounded source={d.source} />

      <Panel title="Headline" accent={t.ok}>
        <Text style={s.body}>{d.reading}</Text>
      </Panel>

      {d.families.map((f) => {
        const complete = f.n_significant === f.n_points;
        return (
          <Panel key={f.comparison} title={f.comparison.replace(/_/g, ' ')}
                 accent={complete ? t.ok : t.bridge}>
            <View style={s.tags}>
              <Tag label={f.verdict} color={complete ? t.ok : t.bridge} />
              {f.min_p_holm != null ? (
                <Tag label={`min p_holm ${f.min_p_holm.toExponential(1)}`} color={t.muted} />
              ) : null}
            </View>
            <View style={s.thead}>
              <Text style={[s.th, { flex: 1 }]}>ε</Text>
              <Text style={[s.th, { flex: 1.2 }]}>n</Text>
              <Text style={[s.th, { flex: 1.6 }]}>median Δ</Text>
              <Text style={[s.th, { flex: 2 }]}>p (Holm)</Text>
              <Text style={[s.th, { flex: 1 }]}>sig</Text>
            </View>
            {f.points.map((p) => (
              <View key={p.epsilon} style={s.tr}>
                <Text style={[s.td, { flex: 1 }]}>{p.epsilon}</Text>
                <Text style={[s.td, { flex: 1.2 }]}>{p.n_pairs}</Text>
                <Text style={[s.tdMono, { flex: 1.6 }]}>{p.median_diff}</Text>
                <Text style={[s.tdMono, { flex: 2 }]}>
                  {p.p_holm < 1e-4 ? p.p_holm.toExponential(1) : p.p_holm.toFixed(4)}
                </Text>
                <Text style={[s.td, { flex: 1, color: p.significant ? t.ok : t.muted,
                                      fontWeight: '700' }]}>
                  {p.significant ? '✓' : '—'}
                </Text>
              </View>
            ))}
          </Panel>
        );
      })}

      <Panel title="Why Holm and not Bonferroni">
        <Text style={s.body}>
          Holm is uniformly more powerful than Bonferroni at the same
          family-wise error rate, and the families here are small enough that
          the difference matters at the tail. Correction is applied within each
          family rather than across all of them, because the comparisons answer
          different questions and pooling them would over-correct.
        </Text>
      </Panel>
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', marginBottom: 8 },
  thead: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: t.border, paddingBottom: 4 },
  th: { color: t.muted, fontSize: 9, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
  tr: { flexDirection: 'row', paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: t.border },
  td: { color: t.text, fontSize: 10.5 },
  tdMono: { color: t.text, fontSize: 10, fontFamily: fonts.mono },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19 },
});
