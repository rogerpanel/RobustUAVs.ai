import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { evalApi } from '../../api/evaluation';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV } from '../uav/parts';

/** M7 = FedGTD, the Stackelberg/MWU defender behind the regret certificate. */
export default function FederatedScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { evalApi.federated().then(setD).catch((e) => setError(e.message)); }, []);
  if (error) return <Unavailable message={error} />;
  if (!d) return <Text style={s.loading}>loading…</Text>;

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader eyebrow="Build" title="Federated Learning"
        lede={d.model} grounded={false} source={d.source} exportData={d} />

      <Panel title="Role in the composition" accent={t.info}>
        <Text style={s.body}>{d.role}</Text>
        <KV k="Phase-A stack" v={d.stack} />
        <KV k="trained weights present" v={d.trained_weights ? 'yes' : 'no'}
            tone={d.trained_weights ? t.ok : t.bridge} />
      </Panel>

      <Panel title="Not runnable here" accent={t.bridge}>
        <Text style={s.body}>{d.note}</Text>
      </Panel>

      {d.registry_entries.length ? (
        <Panel title="Registry">
          {d.registry_entries.map((e, i) => (
            <View key={i} style={s.entry}>
              {Object.entries(e).map(([k, v]) => (
                <KV key={k} k={k.replace(/_/g, ' ')}
                    v={typeof v === 'object' ? JSON.stringify(v) : String(v)} />
              ))}
            </View>
          ))}
        </Panel>
      ) : (
        <Panel title="Registry">
          <Text style={s.body}>
            No registry card matched M7 by identifier. The model registry is on
            the Model registry screen; this is a lookup gap rather than a
            missing model.
          </Text>
        </Panel>
      )}
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19, marginBottom: 6 },
  entry: { marginBottom: 10 },
});
