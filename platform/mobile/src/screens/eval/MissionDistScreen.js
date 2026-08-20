import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { evalApi } from '../../api/evaluation';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV } from '../uav/parts';

/**
 * What MCR's dependence on the mission distribution costs.
 *
 * MCR is a probability over a distribution of missions, so a bound on it is a
 * statement about a population rather than about any one flight. That is
 * usually noted and rarely quantified. This page quantifies it, and leads with
 * the contrast that makes it interesting: marginalised over the adversary the
 * dependence looks negligible, and conditioned on the adversary it is large.
 */
export default function MissionDistScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    evalApi.missionDistribution().then(setD).catch((e) => setError(e.message));
  }, []);
  if (error) return <Unavailable message={error} />;
  if (!d) return <Text style={s.loading}>loading…</Text>;

  const label = (v) => String(v).replace(/_/g, ' ');

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader
        eyebrow="Evaluation"
        title="Mission-distribution sensitivity"
        lede={`${d.question} ${d.answer}`}
        grounded={false} source={d.provenance} exportData={d} />

      <Panel title="The contrast" accent={t.bridge}>
        <KV k="spread, marginalised over the 0–40 dB sweep"
            v={d.marginal_spread} tone={t.ok} />
        <KV k="spread from mission profile, at fixed J/S"
            v={d.conditional_spread_mission} tone={t.danger} />
        <KV k="spread from receiver model, at fixed J/S"
            v={d.conditional_spread_receiver} tone={t.danger} />
        <KV k="range of J/S at which MCR crosses 0.90"
            v={`${d.js_spread_db} dB`} tone={t.danger} />
        <Text style={s.body}>{d.interpretation}</Text>
      </Panel>

      <Panel title="MCR per mission distribution"
             subtitle="Composed defence, marginalised over the jamming sweep, Wilson 95% intervals.">
        <View style={s.hdr}>
          <Text style={[s.h, { flex: 2.2 }]}>mission</Text>
          <Text style={[s.h, { flex: 1.6 }]}>receiver</Text>
          <Text style={[s.h, s.num]}>MCR</Text>
          <Text style={[s.h, { flex: 1.4, textAlign: 'right' }]}>95% CI</Text>
        </View>
        {(d.distributions || []).map((r, i) => (
          <View key={i} style={s.row}>
            <Text style={[s.cell, { flex: 2.2 }]}>{label(r.mission)}</Text>
            <Text style={[s.cell, { flex: 1.6 }, s.dim]}>{label(r.receiver)}</Text>
            <Text style={[s.cell, s.num]}>{Number(r.mcr).toFixed(3)}</Text>
            <Text style={[s.cell, { flex: 1.4, textAlign: 'right' }, s.dim]}>
              [{Number(r.ci_low).toFixed(3)}, {Number(r.ci_high).toFixed(3)}]
            </Text>
          </View>
        ))}
      </Panel>

      <Panel title="Where each distribution falls below the 0.90 reference"
             subtitle="Jamming power, in dB. The spread here is the operationally meaningful number.">
        <View style={s.hdr}>
          <Text style={[s.h, { flex: 2.2 }]}>mission</Text>
          <Text style={[s.h, { flex: 1.6 }]}>receiver</Text>
          <Text style={[s.h, s.num]}>J/S (dB)</Text>
        </View>
        {(d.js_at_mcr_0_90 || []).map((r, i) => (
          <View key={i} style={s.row}>
            <Text style={[s.cell, { flex: 2.2 }]}>{label(r.mission)}</Text>
            <Text style={[s.cell, { flex: 1.6 }, s.dim]}>{label(r.receiver)}</Text>
            <Text style={[s.cell, s.num, { color: t.bridge }]}>
              {typeof r.js_db === 'number' ? r.js_db.toFixed(1) : r.js_db}
            </Text>
          </View>
        ))}
        <Text style={s.caveat}>
          A certified floor quoted without naming its mission distribution
          carries roughly {d.js_spread_db} dB of ambiguity — about a factor of
          eight in adversary transmit power.
        </Text>
      </Panel>
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19, marginTop: 8 },
  caveat: { color: t.muted, fontSize: 11, lineHeight: 17, marginTop: 10, fontStyle: 'italic' },

  hdr: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: t.border,
         paddingBottom: 4, marginBottom: 2 },
  h: { color: t.muted, fontSize: 9.5, fontWeight: '800', textTransform: 'uppercase',
       letterSpacing: 0.6, flex: 1 },
  row: { flexDirection: 'row', paddingVertical: 3.5 },
  cell: { color: t.text, fontSize: 11.5, flex: 1, fontFamily: fonts.mono },
  num: { textAlign: 'right', flex: 1 },
  dim: { color: t.muted },
});
