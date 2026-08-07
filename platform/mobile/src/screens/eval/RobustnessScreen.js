import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, useWindowDimensions } from 'react-native';
import { evalApi } from '../../api/evaluation';
import { useTheme, fonts } from '../../theme';
import LineChart from '../../components/LineChart';
import { ScreenHeader, Panel, Unavailable, KV } from '../uav/parts';

/**
 * Certified floor against the detector operating point, one curve per mapping.
 *
 * This is the paper's headline figure as an interactive object. The floor is a
 * step rather than a slope, and the page says so: below theta* the tube fits
 * inside the corridor and the floor is 1.0; above it the certificate simply
 * stops binding. Presenting it as a smooth degradation would misdescribe it.
 */
export default function RobustnessScreen() {
  const { t } = useTheme();
  const { width } = useWindowDimensions();
  const s = styles(t);
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    evalApi.robustness().then(setD).catch((e) => setError(e.message));
  }, []);

  if (error) return <Unavailable message={error} />;
  if (!d) return <Text style={s.loading}>loading…</Text>;

  const colors = {
    kinematic_v15: t.danger, empirical_receiver: t.ok, empirical_ekf: t.network,
  };
  const w = Math.min(width - 60, 720);

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader eyebrow="Evaluation" title="Robustness"
        lede="How the certified floor holds as the detector is loosened, under
              each θ ↦ δ mapping."
        grounded source={d.source}
        exportData={d} exportSvgId="robustness-chart"
        exportCsv={d.series.flatMap((ss) => ss.points.map((pt) => ({
          mapping: ss.mapping, theta_s: pt.theta_s, delta_pos_m: pt.delta_pos_m,
          tube_m: pt.tube_m, certified_floor: pt.certified_floor,
        })))} />

      <Panel title="Certified floor vs θ" subtitle="the vertical rule is the paper's operating point">
        <View nativeID="robustness-chart">
        <LineChart
          width={w} height={w < 420 ? 200 : 250}
          xLabel="θ (s)" yLabel="certified floor" yMin={0} yMax={1.05}
          marker={{ x: d.paper_theta_s, label: `θ = ${d.paper_theta_s}` }}
          series={d.series.map((ss) => ({
            key: ss.mapping, label: ss.label, color: colors[ss.mapping] ?? t.accent,
            points: ss.points.map((p) => ({ x: p.theta_s, y: p.certified_floor })),
          }))}
        />
        </View>
      </Panel>

      <Panel title="Where each mapping stops binding">
        {d.series.map((ss) => (
          <KV key={ss.mapping} k={ss.label}
              v={ss.binds_to_theta_s == null ? 'never binds'
                 : `binds to θ = ${ss.binds_to_theta_s} s`}
              tone={ss.binds_to_theta_s != null
                    && ss.binds_to_theta_s >= d.paper_theta_s ? t.ok : t.danger} />
        ))}
        <Text style={s.hint}>
          θ = {d.paper_theta_s} s falls between them. Under the kinematic worst
          case the certificate has already stopped binding by then; under either
          measured mapping it still binds with room to spare. The measured
          benign residual ceiling is {d.benign_ceiling_s} s, which is the floor
          of any usable operating window.
        </Text>
      </Panel>

      <Panel title="Reading the shape">
        <Text style={s.body}>{d.reading}</Text>
      </Panel>
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 8 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19 },
});
