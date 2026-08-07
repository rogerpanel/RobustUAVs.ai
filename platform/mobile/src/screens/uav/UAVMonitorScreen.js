import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator,
  useWindowDimensions,
} from 'react-native';
import { uavApi } from '../../api/uav';
import { useTheme, fonts } from '../../theme';
import LineChart from '../../components/LineChart';
import { ScreenHeader, Panel, Unavailable, KV } from './parts';
import { recordContext } from '../../state/context';

const JS_STEPS = [0, 5, 10, 15, 20, 25, 30, 35, 40];

/**
 * The group's hero page: mission completion under jamming, for the four
 * evaluated configurations, with an operating-point selector beneath it.
 *
 * The J/S control is a row of measured grid points rather than a continuous
 * slider. robustidps.ai used a slider, which reads better but silently
 * interpolates -- and an audience watching a number move smoothly will assume
 * every value was measured. Snapping to the grid means every figure on the
 * page is one that was actually run; the API still interpolates on request and
 * flags `measured: false` when it does.
 */
export default function UAVMonitorScreen() {
  const { t } = useTheme();
  const { width } = useWindowDimensions();
  const s = styles(t);

  const [curves, setCurves] = useState(null);
  const [point, setPoint] = useState(null);
  const [js, setJs] = useState(20);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    uavApi.curves().then(setCurves).catch((e) => setError(e.message));
  }, []);

  const load = useCallback(async (v) => {
    setBusy(true);
    try {
      const pt = await uavApi.operatingPoint(v);
      setPoint(pt);
      const passing = pt.configurations.filter((c) => c.passes_floor).map((c) => c.label);
      recordContext({
        routeKey: 'UAVMonitor',
        label: `J/S = ${v} dB`,
        question: `At J/S = ${v} dB the configurations score `
          + pt.configurations.map((c) => `${c.label} ${(c.mcr * 100).toFixed(1)}%`).join(', ')
          + `. ${passing.length ? passing.join(' and ') + ' clear' : 'None clears'} `
          + `the DO-326A 0.90 floor. Why, and what does the certified floor say `
          + `at the same point?`,
        data: pt,
      });
    }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }, []);

  useEffect(() => { load(js); }, [js, load]);

  if (error) return <Unavailable message={error} />;
  if (!curves) return <ActivityIndicator color={t.accent} style={{ marginTop: 30 }} />;

  const colors = {
    no_def: t.danger,
    caf_cnn: t.accentOrange ?? t.bridge,
    seq2seq_tr: t.info,
    ours_m1m4m6m7: t.ok,
  };
  const chartW = Math.min(width - 60, 720);

  const series = curves.curves.map((c) => ({
    key: c.defense,
    label: c.label,
    color: colors[c.defense] ?? t.accent,
    points: c.points.map((p) => ({ x: p.js_db, y: p.mcr, lo: p.ci_low, hi: p.ci_high })),
  }));

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader
        eyebrow="UAV / Aerial Defense"
        title="UAV Monitor"
        lede="Spatial Mission-Completion-Rate against jamming-to-signal ratio, for
              the four configurations in the EW-Bench campaign. The dashed rule
              is the DO-326A 0.90 operational floor."
        grounded
        source={curves.source}
        exportData={{ curves, operating_point: point }}
        exportSvgId="uav-mcr-chart"
        exportCsv={curves.curves.flatMap((c) => c.points.map((pt) => ({
          defense: c.defense, label: c.label, js_db: pt.js_db, mcr: pt.mcr,
          ci_low: pt.ci_low, ci_high: pt.ci_high, n: pt.n,
        })))}
      />

      <Panel title="Mission completion vs jamming"
             subtitle={`${curves.provenance} · shaded band is the Wilson 95% CI`}>
        <View nativeID="uav-mcr-chart">
        <LineChart
          series={series}
          width={chartW}
          height={chartW < 420 ? 200 : 260}
          xLabel="J/S (dB)"
          yLabel="Spatial MCR"
          threshold={{ y: curves.floor.mcr, label: `${curves.floor.label} ${curves.floor.mcr}`, color: t.bridge }}
          marker={{ x: js, label: `${js} dB` }}
        />
        </View>
        <View style={s.holds}>
          {curves.curves.map((c) => (
            <Text key={c.defense} style={s.holdsRow}>
              <Text style={{ color: colors[c.defense] ?? t.accent, fontWeight: '700' }}>
                {c.label}
              </Text>
              <Text style={{ color: t.muted }}>
                {c.holds_floor_to_db == null
                  ? ' — never reaches the floor'
                  : ` holds the floor to ${c.holds_floor_to_db} dB`}
              </Text>
            </Text>
          ))}
        </View>
      </Panel>

      <Panel title="Operating point"
             subtitle="Every value below was measured at that grid point, not interpolated.">
        <View style={s.row}>
          {JS_STEPS.map((v) => (
            <Pressable key={v} onPress={() => setJs(v)}
                       style={[s.pill, js === v && s.pillOn]}>
              <Text style={[s.pillText, js === v && { color: t.accent }]}>{v}</Text>
            </Pressable>
          ))}
        </View>
        <Text style={s.hint}>jamming-to-signal ratio, dB</Text>

        {busy ? <ActivityIndicator color={t.accent} style={{ marginTop: 12 }} /> : null}

        {point ? (
          <View style={s.tiles}>
            {point.configurations.map((c) => (
              <View key={c.defense}
                    style={[s.tile, { borderColor: c.passes_floor ? t.ok : t.danger }]}>
                <Text style={[s.tileName, { color: colors[c.defense] ?? t.accent }]}>
                  {c.label}
                </Text>
                <Text style={s.tileStat}>{(c.mcr * 100).toFixed(1)}%</Text>
                <Text style={s.tileCi}>
                  95% CI [{(c.ci_low * 100).toFixed(1)}, {(c.ci_high * 100).toFixed(1)}]
                </Text>
                <Text style={[s.tileVerdict, { color: c.passes_floor ? t.ok : t.danger }]}>
                  {c.passes_floor ? '✓ DO-326A pass' : '✗ below DO-326A'}
                </Text>
                {c.measured ? null : (
                  <Text style={s.interp}>interpolated</Text>
                )}
              </View>
            ))}
          </View>
        ) : null}
      </Panel>

      <Panel title="What this page does not show">
        <Text style={s.body}>
          This is <Text style={s.em}>Spatial</Text> MCR: it asks whether the
          aircraft stayed inside its corridor, not whether it arrived on time. A
          delay attack that lands the aircraft safely thirty minutes late passes
          every curve above. The temporal predicate is certified separately, and
          the two together are what the composition theorem discharges.
        </Text>
        <KV k="floor shown here" v="DO-326A 0.90, operational, empirical" />
        <KV k="the other floor" v="Ch.6 §6.6 certified MCR ≥ 0.80 at 20 dB" />
        <Text style={s.hint}>
          Different quantities. The paper labels both; conflating them is the
          single easiest way to misread this figure.
        </Text>
      </Panel>
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  row: { flexDirection: 'row', flexWrap: 'wrap' },
  pill: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingHorizontal: 11, paddingVertical: 7, marginRight: 6, marginBottom: 6,
    minWidth: 40, alignItems: 'center',
  },
  pillOn: { borderColor: t.accent, backgroundColor: `${t.accent}22` },
  pillText: { color: t.muted, fontSize: 12.5, fontWeight: '700' },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 15.5, marginTop: 4 },
  holds: { marginTop: 10 },
  holdsRow: { fontSize: 11, lineHeight: 17 },
  tiles: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 12 },
  tile: {
    borderWidth: 1, borderRadius: 9, padding: 10, marginRight: 8, marginBottom: 8,
    minWidth: 150, flexGrow: 1, flexBasis: '45%', backgroundColor: t.bg,
  },
  tileName: { fontSize: 10.5, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
  tileStat: { color: t.text, fontSize: 24, fontWeight: '800', fontFamily: fonts.display, marginTop: 3 },
  tileCi: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono },
  tileVerdict: { fontSize: 10, fontWeight: '700', marginTop: 5 },
  interp: { color: t.bridge, fontSize: 9, marginTop: 2, fontStyle: 'italic' },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19, marginBottom: 8 },
  em: { fontStyle: 'italic', color: t.accent },
});
