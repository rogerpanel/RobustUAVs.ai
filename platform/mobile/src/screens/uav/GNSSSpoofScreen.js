import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, useWindowDimensions,
} from 'react-native';
import Svg, { Circle, Line, Text as SvgText } from 'react-native-svg';
import { uavApi } from '../../api/uav';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV, Tag } from './parts';

/**
 * Sky plot with per-satellite spoof confidence.
 *
 * Flagged illustrative, and the page says why on its face: the Whelan corpus
 * records position error against a benign reference, not per-SV C/N0, so a real
 * sky plot is not derivable from anything in this repository. The measured
 * quantities on this page are the gamma values below the plot -- which are the
 * ones the certificate actually consumes.
 */
export default function GNSSSpoofScreen() {
  const { t } = useTheme();
  const { width } = useWindowDimensions();
  const s = styles(t);
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    uavApi.gnss().then(setD).catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  if (error) return <Unavailable message={error} />;
  if (!d) return <Text style={s.loading}>loading…</Text>;

  const size = Math.min(width - 60, 380);
  const m = d.measured_reference;

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader
        eyebrow="UAV / Aerial Defense"
        title="GNSS Spoof Monitor"
        lede="Per-satellite spoof confidence over the sky, and beneath it the
              measured delay-to-position rate the certificate consumes."
        grounded={false}
        source={m.source}
      />

      <Panel title="Sky plot" subtitle={`${d.n_spoofed} of ${d.satellites.length} satellites flagged · mode: ${d.mode}`}>
        <SkyPlot sats={d.satellites} size={size} t={t} />
        <View style={s.tags}>
          <Tag label={d.mode} color={d.n_spoofed ? t.danger : t.ok} />
          {d.fallback ? <Tag label={`fallback: ${d.fallback}`} color={t.bridge} /> : null}
        </View>
        <Pressable onPress={load} style={s.btn}>
          <Text style={s.btnText}>resample</Text>
        </Pressable>
        <Text style={s.caveat}>{d.caveat}</Text>
      </Panel>

      <Panel title="Measured interface" accent={t.ok}
             subtitle="These are the numbers this page exists to show.">
        <KV k="γ at the receiver" v={`${m.gamma_receiver_m_s} m/s`} />
        <KV k="γ after the EKF" v={`${m.gamma_ekf_m_s} m/s`} />
        <KV k="kinematic worst case" v="15 m/s" />
        <KV k="flights" v={`${m.n_flights} (${m.regime} regime)`} />
        <Text style={s.hint}>
          Three flights are a calibration sample, not a distribution, and the
          regime is hover — cruise remains pending. The ratio is what matters:
          the measured mapping is roughly 11× tighter than the kinematic bound,
          which is exactly enough to move θ = 0.25 s inside the certified window.
        </Text>
      </Panel>

      <Panel title="Satellites">
        {d.satellites.map((sv) => (
          <View key={sv.sv} style={s.satRow}>
            <Text style={s.satId}>{sv.sv}</Text>
            <Text style={s.satMeta}>
              az {sv.azimuth_deg}° · el {sv.elevation_deg}° · C/N₀ {sv.cno_db_hz} dB-Hz
            </Text>
            <Text style={[s.satConf, { color: sv.spoofed ? t.danger : t.muted }]}>
              {(sv.spoof_confidence * 100).toFixed(0)}%
            </Text>
          </View>
        ))}
      </Panel>
    </ScrollView>
  );
}

function SkyPlot({ sats, size, t }) {
  const c = size / 2;
  const R = c - 18;
  // Elevation 90 deg at the centre, 0 at the horizon: standard sky-plot
  // convention, so anyone who has read one before can read this one.
  const pos = (az, el) => {
    const r = R * (1 - el / 90);
    const a = ((az - 90) * Math.PI) / 180;
    return [c + r * Math.cos(a), c + r * Math.sin(a)];
  };
  return (
    <Svg width={size} height={size}>
      {[0, 30, 60].map((el) => (
        <Circle key={el} cx={c} cy={c} r={R * (1 - el / 90)} fill="none"
                stroke={t.border} strokeWidth={1} />
      ))}
      <Line x1={c} y1={c - R} x2={c} y2={c + R} stroke={t.border} strokeWidth={0.5} />
      <Line x1={c - R} y1={c} x2={c + R} y2={c} stroke={t.border} strokeWidth={0.5} />
      <SvgText x={c} y={12} fill={t.muted} fontSize="9" textAnchor="middle">N</SvgText>
      {sats.map((sv) => {
        const [x, y] = pos(sv.azimuth_deg, sv.elevation_deg);
        return (
          <React.Fragment key={sv.sv}>
            <Circle cx={x} cy={y} r={sv.spoofed ? 8 : 6}
                    fill={sv.spoofed ? t.danger : t.ok}
                    opacity={sv.spoofed ? 0.95 : 0.75} />
            <SvgText x={x} y={y + 3} fill={t.bg} fontSize="7" textAnchor="middle">
              {sv.sv.replace('G', '')}
            </SvgText>
          </React.Fragment>
        );
      })}
    </Svg>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 8 },
  btn: {
    borderWidth: 1, borderColor: t.border, borderRadius: 8,
    paddingVertical: 9, paddingHorizontal: 14, alignSelf: 'flex-start', marginTop: 6,
  },
  btnText: { color: t.muted, fontSize: 11.5, fontWeight: '700' },
  caveat: { color: t.bridge, fontSize: 10.5, lineHeight: 16, marginTop: 10 },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 8 },
  satRow: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 5,
    borderBottomWidth: 1, borderBottomColor: t.border,
  },
  satId: { color: t.text, fontSize: 11, fontWeight: '700', fontFamily: fonts.mono, width: 38 },
  satMeta: { color: t.muted, fontSize: 10, flex: 1 },
  satConf: { fontSize: 11, fontWeight: '700' },
});
