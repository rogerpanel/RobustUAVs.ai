import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { evalApi } from '../../api/evaluation';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV, Tag } from '../uav/parts';

/**
 * The interface characterisation campaign.
 *
 * This page exists because the honest answer to "is gamma a constant?" is no,
 * and a platform that showed a single rate would be asserting the opposite. It
 * leads with the estimator argument rather than the numbers, because the
 * estimator is what decides the answer: the uncorrected rate diverges at short
 * staleness and would have condemned the framework on a detector artifact.
 *
 * Coverage is rendered as a first-class panel, not a footnote. A factor the
 * released flights could not vary is shown as "not varied", never as an
 * absent effect.
 */
export default function InterfaceScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { evalApi.interface().then(setD).catch((e) => setError(e.message)); }, []);
  if (error) return <Unavailable message={error} />;
  if (!d) return <Text style={s.loading}>loading…</Text>;

  const statusTone = (st) =>
    st === 'varied' ? t.ok : st === 'poor' ? t.bridge : t.danger;

  // Group the binned rows by factor so each becomes its own small table.
  const byFactor = {};
  (d.factors || []).forEach((f) => {
    (byFactor[f.factor] = byFactor[f.factor] || []).push(f);
  });

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader
        eyebrow="Evaluation"
        title="Interface stability (γ)"
        lede={`${d.question} ${d.answer}`}
        grounded source={d.source} exportData={d} />

      <Panel title="What the certificate uses" accent={t.ok}>
        <KV k="γ used by the certificate" v={`${d.gamma_used_by_certificate} m/s`} tone={t.ok} />
        <KV k="γ from the per-flight secant" v={`${d.gamma_previous_per_flight_secant} m/s`} />
        <KV k="understatement of the coarser estimate" v={`${d.understatement_factor}×`} tone={t.bridge} />
        <KV k="post-onset samples" v={d.n_samples} />
        <KV k="median γ" v={`${d.gamma_median} m/s`} />
        <KV k="max γ (the supremum used)" v={`${d.gamma_max} m/s`} />
        <KV k="spread, median → max" v={`${d.spread_median_to_max}×`} tone={t.bridge} />
        <Text style={s.body}>{d.effect_on_certificate}</Text>
      </Panel>

      <Panel title="Why the estimator matters more than the number"
             subtitle="Read this before the tables below."
             accent={t.danger}>
        <Text style={s.body}>{d.estimator_note}</Text>
      </Panel>

      <Panel title="Coverage"
             subtitle="What the released flights let us vary, and what they do not.">
        {(d.coverage || []).map((c) => (
          <View key={c.factor} style={s.covRow}>
            <Text style={s.covName}>{c.factor.replace(/_/g, ' ')}</Text>
            <Tag label={c.status} color={statusTone(c.status)} />
            <Text style={s.covNote}>{c.note}</Text>
          </View>
        ))}
        <Text style={s.caveat}>
          A factor shown as “not varied” is untested, not shown to have no
          effect. The spread above is therefore a lower bound on the
          variability a deployment would meet.
        </Text>
      </Panel>

      {Object.entries(byFactor).map(([name, rows]) => (
        <Panel key={name} title={name}>
          <View style={s.hdr}>
            <Text style={[s.h, { flex: 2 }]}>bin</Text>
            <Text style={[s.h, s.num]}>n</Text>
            <Text style={[s.h, s.num]}>median</Text>
            <Text style={[s.h, s.num]}>max</Text>
          </View>
          {rows.map((r) => (
            <View key={r.bin} style={s.row}>
              <Text style={[s.cell, { flex: 2 }]}>{String(r.bin).replace(/_/g, ' ')}</Text>
              <Text style={[s.cell, s.num, s.dim]}>{r.n}</Text>
              <Text style={[s.cell, s.num]}>{r.gamma_median}</Text>
              <Text style={[s.cell, s.num, { color: t.bridge }]}>{r.gamma_max}</Text>
            </View>
          ))}
        </Panel>
      ))}

      <Panel title="Descriptive fit"
             subtitle={`R² = ${d.ols?.r_squared} over ${d.ols?.n_samples} samples`}>
        {Object.entries(d.ols?.standardised_coefficients || {}).map(([k, v]) => (
          <KV key={k} k={k.replace(/_/g, ' ')} v={v}
              tone={Number(v) > 0 ? t.danger : t.ok} />
        ))}
        <Text style={s.caveat}>{d.ols?.note}</Text>
      </Panel>
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19, marginTop: 6 },
  caveat: { color: t.muted, fontSize: 11, lineHeight: 17, marginTop: 10, fontStyle: 'italic' },

  covRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 5,
            borderBottomWidth: 1, borderBottomColor: t.border, flexWrap: 'wrap' },
  covName: { color: t.text, fontSize: 11.5, fontWeight: '700', width: 108 },
  covNote: { color: t.muted, fontSize: 10.5, flex: 1, minWidth: 140 },

  hdr: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: t.border,
         paddingBottom: 4, marginBottom: 2 },
  h: { color: t.muted, fontSize: 9.5, fontWeight: '800', textTransform: 'uppercase',
       letterSpacing: 0.6, flex: 1 },
  row: { flexDirection: 'row', paddingVertical: 3.5 },
  cell: { color: t.text, fontSize: 11.5, flex: 1, fontFamily: fonts.mono },
  num: { textAlign: 'right', flex: 1 },
  dim: { color: t.muted },
});
