import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { uavApi } from '../../api/uav';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV } from './parts';

/**
 * The evidence table, including the part of it that is empty.
 *
 * This page exists because a reviewer will ask what fraction of the benchmark
 * rests on real measurement versus synthetic alignment, and the answer is more
 * defensible offered than extracted.
 */
export default function DossierScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    uavApi.dossier().then(setD).catch((e) => setError(e.message));
  }, []);

  if (error) return <Unavailable message={error} />;
  if (!d) return <Text style={s.loading}>loading…</Text>;

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader
        eyebrow="UAV / Aerial Defense"
        title="Assurance Dossier"
        lede="Where every event in the corpus came from, and what the benchmark
              cannot currently evidence."
        grounded
        source={d.source}
        exportData={d}
        exportCsv={d.sources} />

      <Panel title="Totals">
        <KV k="ingested events" v={d.totals.events.toLocaleString()} />
        <KV k="from real testbeds" v={d.totals.real_testbed_events.toLocaleString()} />
        <KV k="real share" v={`${d.totals.real_share_pct}%`} />
        <KV k="released measured_same_platform pairings"
            v={d.totals.released_measured_same_platform_pairings}
            tone={t.bridge} />
      </Panel>

      <Panel title="The empty class" accent={t.bridge}>
        <Text style={s.body}>{d.statement}</Text>
        <Text style={s.hint}>
          The δ calibration underlying the headline result is still a real-flight
          measurement, from three PX4 flights. What is missing is machine-readable
          attack intervals, which is a labelling gap rather than a measurement gap
          — and it is on the pending list rather than worked around.
        </Text>
      </Panel>

      <Panel title="By source">
        {d.sources.map((r) => (
          <View key={r.source} style={s.row}>
            <View style={s.head}>
              <Text style={s.name}>{r.source}</Text>
              <Text style={[s.share, {
                color: String(r.acquisition).includes('real testbed') ? t.ok : t.muted,
              }]}>
                {r.event_share_pct}%
              </Text>
            </View>
            <Text style={s.meta}>
              {r.acquisition} · {r.layer} · {Number(r.events).toLocaleString()} events
              {String(r.staged) === '0' ? ' · NOT STAGED' : ''}
            </Text>
            {r.note ? <Text style={s.note}>{r.note}</Text> : null}
          </View>
        ))}
      </Panel>
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  row: { borderTopWidth: 1, borderTopColor: t.border, paddingTop: 9, marginTop: 9 },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
  name: { color: t.text, fontSize: 12.5, fontWeight: '700', fontFamily: fonts.mono },
  share: { fontSize: 12, fontWeight: '800' },
  meta: { color: t.muted, fontSize: 10.5, marginTop: 2 },
  note: { color: t.muted, fontSize: 10.5, lineHeight: 15.5, marginTop: 3, fontStyle: 'italic' },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19 },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 8 },
});
