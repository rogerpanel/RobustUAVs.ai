import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, ActivityIndicator } from 'react-native';
import { api, Unavailable, API_BASE } from '../api/client';
import { theme } from '../theme';
import Card from '../components/Card';
import Chip from '../components/Chip';

/** Dashboard: deployment health, corpus size, and the provenance split --
 *  including the fact that the released measured_same_platform pairing count
 *  is zero, which is the number a reviewer will look for first. */
export default function OverviewScreen() {
  const [health, setHealth] = useState(null);
  const [prov, setProv] = useState(null);
  const [note, setNote] = useState(null);

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setNote(e.message));
    api.result('provenance').then(setProv)
      .catch((e) => setNote(e instanceof Unavailable
        ? 'Provenance ledger not generated in this deployment (run experiments/provenance_ledger.py).'
        : e.message));
  }, []);

  const totals = prov?.rows?.reduce((a, r) => {
    a.events += r.events || 0;
    if (r.acquisition === 'real testbed') a.real += r.events || 0;
    return a;
  }, { events: 0, real: 0 });

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>RobustUAVs.ai</Text>
      <Text style={styles.lede}>
        End-to-end UAV security: a cross-layer benchmark and a composed
        network-to-navigation certificate.
      </Text>

      {health ? (
        <Card title="Deployment" source={API_BASE}>
          <Row k="registered models" v={health.models} />
          <Row k="copilot tools" v={health.copilot_tools} />
          <Row k="result files" v={health.result_files} />
          <View style={styles.chips}>
            {health.providers.map((p) => (
              <Chip key={p.name}
                    label={p.active ? `${p.name} ●` : p.name}
                    color={p.active ? theme.ok : p.configured ? theme.network : theme.muted} />
            ))}
          </View>
          <Text style={styles.hint}>
            A dimmed provider has no key configured; the copilot then answers
            from the local result cache rather than failing.
          </Text>
        </Card>
      ) : <ActivityIndicator color={theme.accent} />}

      {totals ? (
        <Card title="Corpus provenance" source={prov ? 'results/provenance_distribution.csv' : null}
              subtitle="Acquisition is a property of the source. The pairing basis is strictly stronger.">
          <Row k="ingested events" v={totals.events.toLocaleString()} />
          <Row k="captured on real hardware"
               v={`${totals.real.toLocaleString()} (${(100 * totals.real / totals.events).toFixed(1)}%)`} />
          <View style={styles.warn}>
            <Text style={styles.warnText}>
              Released measured_same_platform pairings: 0. The one source
              observing both layers lacks machine-readable attack intervals, so
              the strongest evidence class is currently unpopulated. The δ
              calibration is still a real-flight measurement.
            </Text>
          </View>
        </Card>
      ) : null}

      {note ? <Card title="Note"><Text style={styles.hint}>{note}</Text></Card> : null}
    </ScrollView>
  );
}

const Row = ({ k, v }) => (
  <View style={styles.kv}><Text style={styles.k}>{k}</Text><Text style={styles.v}>{String(v)}</Text></View>
);

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg },
  content: { padding: 16, paddingBottom: 48 },
  h1: { color: theme.text, fontSize: 26, fontWeight: '800' },
  lede: { color: theme.muted, fontSize: 14, lineHeight: 20, marginBottom: 18, marginTop: 4 },
  kv: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 5, borderBottomWidth: 1, borderBottomColor: theme.border },
  k: { color: theme.muted, fontSize: 12, flex: 1 },
  v: { color: theme.text, fontSize: 12, fontWeight: '700' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 10 },
  hint: { color: theme.muted, fontSize: 11, lineHeight: 16, marginTop: 6 },
  warn: { borderLeftWidth: 3, borderLeftColor: theme.bridge, paddingLeft: 10, marginTop: 12 },
  warnText: { color: theme.text, fontSize: 12, lineHeight: 18 },
});
