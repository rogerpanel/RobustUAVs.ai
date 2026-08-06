import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { uavApi } from '../../api/uav';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, Tag } from './parts';

/**
 * The adversarial attack suite, documented rather than executed.
 *
 * robustidps.ai runs these against loaded model weights. This deployment does
 * not carry weights, and the honest response is to say so rather than to run a
 * surrogate and present its output as an attack result. The catalogue is still
 * worth showing: it is the suite the framework was evaluated against, and the
 * page points at the certified comparison that does run live.
 */
export default function PerceptionScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    uavApi.attackCatalog().then(setD).catch((e) => setError(e.message));
  }, []);

  if (error) return <Unavailable message={error} />;
  if (!d) return <Text style={s.loading}>loading…</Text>;

  const familyColor = {
    gradient: t.danger, optimisation: t.info, geometric: t.bridge,
    baseline: t.muted, physical: t.network,
  };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader
        eyebrow="UAV / Aerial Defense"
        title="Perception Tester"
        lede="The attack suite the framework was evaluated against, grouped by
              family. Execution needs trained weights this deployment does not
              carry."
        grounded={false}
        source="models/uav_defense/attacks/"
      />

      <Panel title="Not executable here" accent={t.bridge}>
        <Text style={s.body}>{d.note}</Text>
      </Panel>

      <Panel title={`Attack catalogue (${d.count})`}>
        {d.attacks.map((a) => (
          <View key={a.id} style={s.row}>
            <View style={s.head}>
              <Text style={s.name}>{a.name}</Text>
              <Tag label={a.family} color={familyColor[a.family] ?? t.muted} />
            </View>
            <Text style={s.note}>{a.note}</Text>
            <Text style={s.param}>budget parameter: {a.budget_param}</Text>
          </View>
        ))}
      </Panel>

      <Panel title="The two that matter for this paper">
        <Text style={s.body}>
          <Text style={s.em}>GNSS spoof</Text> and <Text style={s.em}>link
          jamming</Text> are the physical classes the composition theorem
          addresses: the first drives the position error the certificate bounds,
          the second drives the J/S axis of the EW-Bench campaign. The gradient
          and optimisation families are evaluated in Chapter 6 against the
          perception stack, which is a different attack surface and a different
          bound — randomized smoothing rather than Grönwall.
        </Text>
      </Panel>
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  row: { borderTopWidth: 1, borderTopColor: t.border, paddingTop: 9, marginTop: 9 },
  head: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap' },
  name: { color: t.text, fontSize: 13, fontWeight: '700', marginRight: 8 },
  note: { color: t.muted, fontSize: 11, lineHeight: 16.5, marginTop: 2 },
  param: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, marginTop: 3, opacity: 0.8 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19 },
  em: { color: t.accent, fontWeight: '700' },
});
