import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, useWindowDimensions,
} from 'react-native';
import Svg, { Circle, Line, Text as SvgText } from 'react-native-svg';
import { uavApi } from '../../api/uav';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV, Tag } from './parts';
import { recordContext } from '../../state/context';

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
  const [sel, setSel] = useState(null);
  // Controls, so the plot answers questions rather than only showing one state.
  const [nSats, setNSats] = useState(9);
  const [nSpoofed, setNSpoofed] = useState(2);
  const [strength, setStrength] = useState(0.82);
  const [js, setJs] = useState(0);

  const load = useCallback((seed) => {
    uavApi.gnss({ n_sats: nSats, n_spoofed: nSpoofed, spoof_strength: strength,
                  js_db: js, seed })
      .then((r) => {
        setD(r); setError(null);
        recordContext({
          routeKey: 'GNSSSpoof',
          label: `${r.n_spoofed}/${r.n_sats} spoofed, J/S ${r.js_db} dB`,
          question: `With ${r.n_spoofed} of ${r.n_sats} satellites spoofed at `
            + `strength ${r.spoof_strength} and J/S ${r.js_db} dB, the receiver `
            + `reports "${r.mode}" with ${r.n_usable} usable satellites and a mean `
            + `healthy C/N₀ of ${r.mean_cno_healthy_db_hz} dB-Hz. What does that `
            + `regime imply for the measured γ and the certified tube?`,
          data: { mode: r.mode, n_usable: r.n_usable, js_db: r.js_db },
        });
      })
      .catch((e) => setError(e.message));
  }, [nSats, nSpoofed, strength, js]);

  useEffect(() => { load(); }, [load]);

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

      <Panel title="Sky plot"
             subtitle={`${d.n_spoofed} of ${d.n_sats} flagged · ${d.n_usable} usable · mode: ${d.mode}`}
             accent={d.mode === 'nominal' ? t.ok : d.mode === 'no fix' ? t.danger : t.bridge}>
        <SkyPlot sats={d.satellites} size={size} t={t}
                 onSelect={setSel} selected={sel} />
        <View style={s.tags}>
          <Tag label={d.mode} color={d.mode === 'nominal' ? t.ok
                                     : d.mode === 'no fix' ? t.danger : t.bridge} />
          <Tag label={`mean C/N₀ ${d.mean_cno_healthy_db_hz} dB-Hz`} color={t.muted} />
          {d.fallback ? <Tag label={`fallback: ${d.fallback}`} color={t.bridge} /> : null}
        </View>

        {sel ? (
          <View style={s.selBox}>
            <Text style={s.selTitle}>{sel.sv}{sel.spoofed ? '  — flagged' : ''}</Text>
            <KV k="azimuth" v={`${sel.azimuth_deg}°`} />
            <KV k="elevation" v={`${sel.elevation_deg}°`} />
            <KV k="C/N₀" v={`${sel.cno_db_hz} dB-Hz`}
                tone={sel.cno_db_hz < 25 ? t.danger : undefined} />
            <KV k="spoof confidence" v={`${(sel.spoof_confidence * 100).toFixed(0)}%`}
                tone={sel.spoofed ? t.danger : undefined} />
            <Text style={s.hint}>
              {sel.spoofed
                ? 'A spoofer transmits harder than the real constellation, so its '
                  + 'C/N₀ stays high while jamming pulls everything else down. That '
                  + 'gap is the classic tell — raise J/S and watch it open.'
                : 'A healthy satellite. Its C/N₀ falls as J/S rises; below about '
                  + '25 dB-Hz it stops contributing to the fix.'}
            </Text>
          </View>
        ) : (
          <Text style={s.hint}>Tap a satellite to inspect it.</Text>
        )}

        <Text style={s.sub}>Satellites in view</Text>
        <View style={s.row}>
          {[4, 6, 9, 12].map((v) => (
            <Pressable key={v} onPress={() => { setNSats(v); setNSpoofed(Math.min(nSpoofed, v)); }}
                       style={[s.pill, nSats === v && s.pillOn]}>
              <Text style={[s.pillText, nSats === v && { color: t.accent }]}>{v}</Text>
            </Pressable>
          ))}
        </View>

        <Text style={s.sub}>Spoofed satellites</Text>
        <View style={s.row}>
          {[0, 1, 2, 4, 6].filter((v) => v <= nSats).map((v) => (
            <Pressable key={v} onPress={() => setNSpoofed(v)}
                       style={[s.pill, nSpoofed === v && s.pillOn]}>
              <Text style={[s.pillText, nSpoofed === v && { color: t.accent }]}>{v}</Text>
            </Pressable>
          ))}
        </View>

        <Text style={s.sub}>Spoof strength</Text>
        <View style={s.row}>
          {[0.4, 0.6, 0.82, 0.95].map((v) => (
            <Pressable key={v} onPress={() => setStrength(v)}
                       style={[s.pill, strength === v && s.pillOn]}>
              <Text style={[s.pillText, strength === v && { color: t.accent }]}>{v}</Text>
            </Pressable>
          ))}
        </View>

        <Text style={s.sub}>Ambient jamming J/S</Text>
        <View style={s.row}>
          {[0, 10, 20, 30, 40].map((v) => (
            <Pressable key={v} onPress={() => setJs(v)}
                       style={[s.pill, js === v && s.pillOn]}>
              <Text style={[s.pillText, js === v && { color: t.accent }]}>{v} dB</Text>
            </Pressable>
          ))}
        </View>

        <Pressable onPress={() => load(Math.floor(Math.random() * 1e6))} style={s.btn}>
          <Text style={s.btnText}>↻  resample</Text>
        </Pressable>
        <Text style={s.hint}>
          Try J/S = 30 dB with 6 satellites: healthy C/N₀ falls below the 25 dB-Hz
          usability line, fewer than four satellites remain, and the receiver
          reports <Text style={{ color: t.danger }}>no fix</Text> — a different
          failure from a spoofed one, and one the sky plot alone would not tell you.
        </Text>
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

function SkyPlot({ sats, size, t, onSelect, selected }) {
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
    <Svg width={size} height={size} nativeID="gnss-sky">
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
            {/* Radius carries confidence and fill carries state, so the plot
                does not rely on hue alone. Weak satellites dim rather than
                vanish: "present but unusable" is information. */}
            <Circle cx={x} cy={y} r={sv.spoofed ? 7 + 3 * sv.spoof_confidence : 6}
                    fill={sv.spoofed ? t.danger : (sv.cno_db_hz < 25 ? t.muted : t.ok)}
                    opacity={sv.spoofed ? 0.95 : (sv.cno_db_hz < 25 ? 0.45 : 0.8)}
                    stroke={selected?.sv === sv.sv ? t.accent : 'none'}
                    strokeWidth={2}
                    onPress={() => onSelect?.(sv)} />
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
  row: { flexDirection: 'row', flexWrap: 'wrap' },
  pill: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingHorizontal: 11, paddingVertical: 7, marginRight: 6, marginBottom: 6,
    minWidth: 40, alignItems: 'center',
  },
  pillOn: { borderColor: t.accent, backgroundColor: `${t.accent}22` },
  pillText: { color: t.muted, fontSize: 11.5, fontWeight: '600' },
  sub: {
    color: t.muted, fontSize: 9.5, fontWeight: '800', letterSpacing: 1,
    textTransform: 'uppercase', marginTop: 12, marginBottom: 6,
  },
  selBox: {
    borderWidth: 1, borderColor: t.border, borderRadius: 8,
    padding: 10, marginTop: 10, backgroundColor: t.bg,
  },
  selTitle: { color: t.text, fontSize: 12.5, fontWeight: '800', fontFamily: fonts.mono, marginBottom: 4 },
  satRow: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 5,
    borderBottomWidth: 1, borderBottomColor: t.border,
  },
  satId: { color: t.text, fontSize: 11, fontWeight: '700', fontFamily: fonts.mono, width: 38 },
  satMeta: { color: t.muted, fontSize: 10, flex: 1 },
  satConf: { fontSize: 11, fontWeight: '700' },
});
