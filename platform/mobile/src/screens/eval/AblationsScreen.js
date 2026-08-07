import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { evalApi } from '../../api/evaluation';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV, Tag } from '../uav/parts';

const MAPPINGS = ['kinematic_v15', 'empirical_receiver', 'empirical_ekf'];
const SHORT = { kinematic_v15: 'kinematic', empirical_receiver: 'receiver', empirical_ekf: 'EKF' };

/**
 * Two ablations that are derivable, and one that is not.
 *
 * The third -- removing a certificate and re-measuring -- has no coherent
 * meaning here, because the four bound different objects and do not compose
 * additively. Saying that is more useful than drawing a bar chart with four
 * bars that cannot be compared.
 */
export default function AblationsScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    evalApi.ablations().then(setD).catch((e) => setError(e.message));
  }, []);

  if (error) return <Unavailable message={error} />;
  if (!d) return <Text style={s.loading}>loading…</Text>;

  const ms = d.mapping_sensitivity;
  const amp = d.amplification;

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader eyebrow="Evaluation" title="Ablation studies"
        lede="What each part of the composition is responsible for."
        grounded source={ms.source}
        exportData={d}
        exportCsv={ms.grid.map((r) => ({
          theta_target_s: r.theta_target_s, margin_m: r.margin_m,
          gamma_required_m_s: r.gamma_required_m_s,
          ...Object.fromEntries(Object.entries(r.ok).map(([k, v]) => [`ok_${k}`, v ? 1 : 0])),
        }))} />

      <Panel title="Interface mapping" subtitle={ms.question}>
        <View style={s.thead}>
          <Text style={[s.th, { flex: 1.1 }]}>margin</Text>
          <Text style={[s.th, { flex: 1.5 }]}>γ required</Text>
          {MAPPINGS.map((m) => (
            <Text key={m} style={[s.th, { flex: 1.2, textAlign: 'center' }]}>{SHORT[m]}</Text>
          ))}
        </View>
        {ms.grid.map((r) => (
          <View key={`${r.theta_target_s}-${r.margin_m}`} style={s.tr}>
            <Text style={[s.td, { flex: 1.1 }]}>{r.margin_m} m</Text>
            <Text style={[s.tdMono, { flex: 1.5 }]}>{r.gamma_required_m_s} m/s</Text>
            {MAPPINGS.map((m) => (
              <Text key={m} style={[s.td, {
                flex: 1.2, textAlign: 'center',
                color: r.ok[m] ? t.ok : t.danger, fontWeight: '700',
              }]}>{r.ok[m] ? '✓' : '✗'}</Text>
            ))}
          </View>
        ))}
        <Text style={s.hint}>
          Read a row as: at this corridor margin, γ must be at or below the
          stated rate for θ = 0.25 s to certify. The kinematic bound of 15 m/s
          fails every row; the measured rates clear all but the tightest.
        </Text>
      </Panel>

      <Panel title="Grönwall amplification" accent={t.bridge}>
        <KV k="L, power iteration (global)" v={amp.L_global} />
        <KV k="L, measured over trajectories" v={amp.L_local} />
        <KV k="e^{LT} global" v={amp.factor_global} />
        <KV k="e^{LT} local" v={amp.factor_local} />
        <KV k="radius penalty for honesty" v={`${amp.penalty_pct}%`} tone={t.bridge} />
        <Text style={s.hint}>{amp.reading}</Text>
        <Text style={s.source}>{amp.source}</Text>
      </Panel>

      <Panel title={`Not ablatable: ${d.not_ablatable.item}`} accent={t.muted}>
        <Text style={s.body}>{d.not_ablatable.reason}</Text>
      </Panel>
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  thead: {
    flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: t.border,
    paddingBottom: 5, marginBottom: 3,
  },
  th: { color: t.muted, fontSize: 9.5, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.6 },
  tr: { flexDirection: 'row', paddingVertical: 5, borderBottomWidth: 1, borderBottomColor: t.border },
  td: { color: t.text, fontSize: 11 },
  tdMono: { color: t.text, fontSize: 11, fontFamily: fonts.mono },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 8 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19 },
  source: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, marginTop: 6, opacity: 0.8 },
});
