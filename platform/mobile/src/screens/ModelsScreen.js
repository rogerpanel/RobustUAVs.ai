import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import { api } from '../api/client';
import { theme, provenanceStyle, certStatusStyle } from '../theme';
import Card from '../components/Card';
import Chip from '../components/Chip';

/** The registry, rendered generically. No screen code knows any model by name;
 *  adding a row to the backend registry adds it here for free -- the same
 *  indirection that let RobustIDPS ship three detectors without a UI change. */
export default function ModelsScreen() {
  const [data, setData] = useState(null);
  const [cat, setCat] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.models(cat).then(setData).catch((e) => setErr(e.message));
  }, [cat]);

  if (err) return <Center><Text style={styles.err}>{err}</Text></Center>;
  if (!data) return <Center><ActivityIndicator color={theme.accent} /></Center>;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Registry</Text>
      <View style={styles.row}>
        <Pressable onPress={() => setCat(null)} style={[styles.pill, !cat && styles.pillOn]}>
          <Text style={[styles.pillText, !cat && styles.pillTextOn]}>all</Text>
        </Pressable>
        {data.categories.map((c) => (
          <Pressable key={c} onPress={() => setCat(c)} style={[styles.pill, cat === c && styles.pillOn]}>
            <Text style={[styles.pillText, cat === c && styles.pillTextOn]}>{c}</Text>
          </Pressable>
        ))}
      </View>

      {data.models.map((m) => (
        <Card key={m.model_id} title={m.display_name} subtitle={m.summary} source={m.source}>
          <View style={styles.chips}>
            <Chip label={m.category} color={theme.network} />
            <Chip {...provenanceStyle[m.provenance]} />
            {m.certificate_status !== 'not_applicable'
              ? <Chip {...certStatusStyle[m.certificate_status]} /> : null}
          </View>
          {Object.keys(m.constants || {}).length ? (
            <View style={styles.constants}>
              {Object.entries(m.constants).map(([k, v]) => (
                <Text key={k} style={styles.constant}>
                  <Text style={styles.ck}>{k}</Text> = {JSON.stringify(v)}
                </Text>
              ))}
            </View>
          ) : null}
          {m.caveat ? <Text style={styles.caveat}>⚠ {m.caveat}</Text> : null}
        </Card>
      ))}
    </ScrollView>
  );
}

const Center = ({ children }) => <View style={styles.center}>{children}</View>;

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg },
  center: { flex: 1, backgroundColor: theme.bg, alignItems: 'center', justifyContent: 'center' },
  content: { padding: 16, paddingBottom: 48 },
  h1: { color: theme.text, fontSize: 24, fontWeight: '800', marginBottom: 12 },
  row: { flexDirection: 'row', flexWrap: 'wrap', marginBottom: 12 },
  pill: { borderWidth: 1, borderColor: theme.border, borderRadius: 8, paddingHorizontal: 11, paddingVertical: 6, marginRight: 8, marginBottom: 8 },
  pillOn: { borderColor: theme.accent, backgroundColor: `${theme.accent}22` },
  pillText: { color: theme.muted, fontSize: 12, fontWeight: '600' },
  pillTextOn: { color: theme.accent },
  chips: { flexDirection: 'row', flexWrap: 'wrap', marginBottom: 6 },
  constants: { marginTop: 6 },
  constant: { color: theme.text, fontSize: 11, fontFamily: 'monospace', marginTop: 2 },
  ck: { color: theme.muted },
  caveat: { color: theme.bridge, fontSize: 11, marginTop: 8, lineHeight: 16 },
  err: { color: theme.danger, padding: 20 },
});
