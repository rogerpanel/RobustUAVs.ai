import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { evalApi } from '../../api/evaluation';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV } from '../uav/parts';

/**
 * ECE, and why it cannot be computed here.
 *
 * The page exists so the question has a visible answer. A reviewer asking "is
 * your detector calibrated?" should find the method, the missing input, and
 * what would unblock it -- not a surrogate reliability diagram fitted to a
 * boolean, which would be calibrated against itself.
 */
export default function CalibrationScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { evalApi.calibration().then(setD).catch((e) => setError(e.message)); }, []);
  if (error) return <Unavailable message={error} />;
  if (!d) return <Text style={s.loading}>loading…</Text>;

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader eyebrow="Evaluation" title="Calibration (ECE)"
        lede="Expected Calibration Error is not derivable from what this
              deployment carries. This page states why rather than omitting the
              question."
        grounded={false} source={d.tracked_in} />

      <Panel title="Not available" accent={t.bridge}>
        <KV k="metric" v={d.metric} />
        <KV k="missing input" v={d.missing_input} tone={t.bridge} />
        <Text style={s.body}>{d.why}</Text>
      </Panel>

      <Panel title="The method, for when the input exists">
        <Text style={s.mono}>{d.method}</Text>
      </Panel>

      <Panel title="What would unblock it">
        <Text style={s.body}>{d.what_would_unblock_it}</Text>
      </Panel>

      <Panel title="What is derivable today" accent={t.ok}>
        <Text style={s.body}>{d.related}</Text>
      </Panel>
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19 },
  mono: { color: t.muted, fontSize: 11, lineHeight: 18, fontFamily: fonts.mono },
});
