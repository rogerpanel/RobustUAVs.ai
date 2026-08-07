import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, useWindowDimensions,
} from 'react-native';
import Svg, { Circle, Line, Path, Text as SvgText } from 'react-native-svg';
import { uavApi } from '../../api/uav';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV, Tag } from './parts';
import { recordContext } from '../../state/context';

const SATS = [4, 6, 9, 12];
const SPOOFED = [1, 2, 3, 6];
const MAPPINGS = [
  { id: 'kinematic', label: 'Kinematic', note: '15 m/s' },
  { id: 'receiver', label: 'Receiver', note: 'γ = 1.195 m/s' },
  { id: 'ekf', label: 'EKF', note: 'γ = 1.365 m/s' },
];
const THRESHOLDS = [2, 5, 8, 15];

/**
 * A GNSS spoof as a process, not a photograph.
 *
 * The static sky plot could only ever say "two satellites look wrong". A spoof
 * is a sequence — probe, match power, capture the tracking loops, walk the
 * solution off — and each phase looks different on the plot. Stepping through
 * it is what teaches the thing that matters: during Capture the C/N₀ reads
 * HEALTHY, so a monitor watching signal strength alone passes it, and only a
 * cross-check against inertial or fleet consensus disagrees.
 *
 * Position error is γ × capture time, with the same γ the certificate engine
 * consumes, so the error growing on this page and the tube on the Composition
 * page are one quantity rather than two unrelated animations.
 */
export default function GNSSSpoofScreen() {
  const { t } = useTheme();
  const { width } = useWindowDimensions();
  const s = styles(t);

  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);
  const [sel, setSel] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [nSats, setNSats] = useState(9);
  const [nSpoofed, setNSpoofed] = useState(2);
  const [js, setJs] = useState(0);
  const [mapping, setMapping] = useState('ekf');
  const [threshold, setThreshold] = useState(8);
  const timer = useRef(null);
  const inflight = useRef(false);

  const cfg = { n_sats: nSats, n_spoofed: nSpoofed, js_db: js,
                mapping, detect_threshold_m: threshold };

  const reset = useCallback(async () => {
    setPlaying(false);
    try { setRun(await uavApi.gnssRunReset(cfg)); setError(null); setSel(null); }
    catch (e) { setError(e.message); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nSats, nSpoofed, js, mapping, threshold]);

  useEffect(() => { uavApi.gnssRun().then(setRun).catch((e) => setError(e.message)); }, []);

  const step = useCallback(async () => {
    if (inflight.current) return;
    inflight.current = true;
    try {
      const r = await uavApi.gnssRunStep({ dt_s: 1.0 });
      setRun(r);
      if (r.detected_at_s) {
        setPlaying(false);
        recordContext({
          routeKey: 'GNSSSpoof',
          label: `spoof detected at ${r.detected_at_s}s`,
          question: `A GNSS spoof against ${r.sky.n_spoofed} of ${r.sky.n_sats} `
            + `satellites reached ${r.pos_error_m} m of position error and was `
            + `caught at t = ${r.detected_at_s} s under the ${r.mapping} mapping `
            + `(γ = ${r.gamma_m_s} m/s), against a ${r.detect_threshold_m} m `
            + `threshold. What does that imply for the certified tube?`,
          data: { detected_at_s: r.detected_at_s, pos_error_m: r.pos_error_m },
        });
      }
    } catch (e) { setError(e.message); setPlaying(false); }
    finally { inflight.current = false; }
  }, []);

  useEffect(() => {
    if (!playing) { if (timer.current) clearInterval(timer.current); return undefined; }
    timer.current = setInterval(step, 800);
    return () => clearInterval(timer.current);
  }, [playing, step]);

  if (error && !run) return <Unavailable message={error} />;
  if (!run) return <Text style={s.loading}>arming the receiver…</Text>;

  const size = Math.min(width - 60, 380);
  const chartW = Math.min(width - 60, 640);
  const sky = run.sky;
  const phaseTone = [t.ok, t.muted, t.bridge, t.danger, t.danger, t.info][run.phase_index];

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader
        eyebrow="UAV / Aerial Defense"
        title="GNSS Spoof Monitor"
        lede="Run a spoof through its phases and watch what each one does to the
              sky plot and to position error. Press play, then look at C/N₀ during
              Capture."
        grounded={false}
        source="process illustrative; γ measured"
        exportData={run}
        exportSvgId="gnss-sky"
        exportCsv={run.history}
      />

      <Panel title={`Phase ${run.phase_index + 1} of 6 — ${run.phase.label}`}
             subtitle={run.phase.detail} accent={phaseTone}>
        <View style={s.phases}>
          {run.phases.map((p, i) => (
            <View key={p.id} style={[s.phaseDot, {
              backgroundColor: i < run.phase_index ? t.border
                : i === run.phase_index ? phaseTone : 'transparent',
              borderColor: i === run.phase_index ? phaseTone : t.border,
            }]} />
          ))}
        </View>

        <View style={s.controls}>
          <Pressable onPress={() => setPlaying((p) => !p)}
                     style={[s.btn, playing ? s.btnStop : s.btnGo]}>
            <Text style={[s.btnText, { color: playing ? t.danger : t.ok }]}>
              {playing ? '❚❚  pause' : '▶  run the spoof'}
            </Text>
          </Pressable>
          <Pressable onPress={step} style={s.btn}>
            <Text style={s.btnText}>step 1 s</Text>
          </Pressable>
          <Pressable onPress={reset} style={s.btn}>
            <Text style={s.btnText}>↻  remark / reset</Text>
          </Pressable>
        </View>

        <KV k="elapsed" v={`${run.t_s} s`} />
        <KV k="time under capture" v={`${run.captured_s} s`} />
        <KV k="position error" v={`${run.pos_error_m} m`}
            tone={run.pos_error_m > run.detect_threshold_m ? t.danger
                  : run.pos_error_m > 0 ? t.bridge : undefined} />
        <KV k="γ" v={`${run.gamma_m_s} m/s (${run.mapping})`} />
        <KV k="detection threshold" v={`${run.detect_threshold_m} m`} />
        <KV k="caught at" v={run.detected_at_s ? `${run.detected_at_s} s` : 'still undetected'}
            tone={run.detected_at_s ? t.ok : t.bridge} />

        {run.phase_index === 3 ? (
          <Text style={s.alert}>
            Look at the mean healthy C/N₀ now: {sky.mean_cno_healthy_db_hz} dB-Hz,
            and every satellite reads strong. A signal-strength monitor passes
            this. The receiver is already tracking the counterfeit.
          </Text>
        ) : null}
      </Panel>

      <Panel title="Sky"
             subtitle={`${sky.n_spoofed} of ${sky.n_sats} flagged · ${sky.n_usable} usable · ${sky.mode}`}>
        <SkyPlot sats={sky.satellites} size={size} t={t}
                 onSelect={setSel} selected={sel} />
        <View style={s.tags}>
          <Tag label={sky.mode} color={sky.mode === 'nominal' ? t.ok
                                       : sky.mode === 'no fix' ? t.danger : t.bridge} />
          <Tag label={`mean C/N₀ ${sky.mean_cno_healthy_db_hz} dB-Hz`} color={t.muted} />
          <Tag label={`mean spoof conf ${(run.mean_spoof_confidence * 100).toFixed(0)}%`}
               color={t.info} />
        </View>
        {sel ? (
          <View style={s.selBox}>
            <Text style={s.selTitle}>{sel.sv}{sel.spoofed ? '  — counterfeit' : ''}</Text>
            <KV k="azimuth / elevation" v={`${sel.azimuth_deg}° / ${sel.elevation_deg}°`} />
            <KV k="C/N₀" v={`${sel.cno_db_hz} dB-Hz`}
                tone={sel.cno_db_hz < 25 ? t.danger : undefined} />
            <KV k="spoof confidence" v={`${(sel.spoof_confidence * 100).toFixed(0)}%`}
                tone={sel.spoofed ? t.danger : undefined} />
          </View>
        ) : (
          <Text style={s.hint}>Tap a satellite to inspect it.</Text>
        )}
      </Panel>

      {run.history.length > 2 ? (
        <Panel title="Attack timeline"
               subtitle="position error against the detection threshold">
          <RunChart run={run} width={chartW} t={t} />
        </Panel>
      ) : null}

      <Panel title="Scenario">
        <Text style={s.sub}>Satellites in view</Text>
        <Row t={t} opts={SATS} value={nSats} onPick={setNSats} />
        <Text style={s.sub}>Satellites the spoofer targets</Text>
        <Row t={t} opts={SPOOFED.filter((v) => v <= nSats)} value={nSpoofed} onPick={setNSpoofed} />
        <Text style={s.sub}>Ambient jamming J/S</Text>
        <Row t={t} opts={[0, 10, 20, 30]} value={js} onPick={setJs} suffix=" dB" />
        <Text style={s.sub}>θ ↦ δ mapping</Text>
        <View style={s.row}>
          {MAPPINGS.map((m) => (
            <Pressable key={m.id} onPress={() => setMapping(m.id)}
                       style={[s.pill, mapping === m.id && s.pillOn]}>
              <Text style={[s.pillText, mapping === m.id && { color: t.accent }]}>
                {m.label}
              </Text>
            </Pressable>
          ))}
        </View>
        <Text style={s.sub}>Detection threshold</Text>
        <Row t={t} opts={THRESHOLDS} value={threshold} onPick={setThreshold} suffix=" m" />
        <Text style={s.hint}>
          Changes take effect on reset. Try Kinematic against EKF: the same
          capture walks the solution off 11× faster, so detection fires far
          sooner — which is the mapping question again, in the time domain.
        </Text>
      </Panel>

      <Panel title="What is measured here" accent={t.ok}>
        <KV k="γ at the receiver" v="1.195 m/s" />
        <KV k="γ after the EKF" v="1.365 m/s" />
        <KV k="flights" v="3 (hover regime)" />
        <Text style={s.hint}>
          The phase timings and the sky plot are illustrative — the Whelan corpus
          records position error, not per-satellite C/N₀. The γ values are the
          measured content, and they are what turns capture time into metres.
        </Text>
        <Text style={s.caveat}>{run.reading}</Text>
      </Panel>
    </ScrollView>
  );
}

function Row({ t, opts, value, onPick, suffix = '' }) {
  const s = styles(t);
  return (
    <View style={s.row}>
      {opts.map((v) => (
        <Pressable key={v} onPress={() => onPick(v)}
                   style={[s.pill, value === v && s.pillOn]}>
          <Text style={[s.pillText, value === v && { color: t.accent }]}>{v}{suffix}</Text>
        </Pressable>
      ))}
    </View>
  );
}

/** Position error over time, with the detection threshold drawn in. */
function RunChart({ run, width, t }) {
  const h = 170;
  const pad = { l: 38, r: 12, tp: 12, b: 24 };
  const iw = width - pad.l - pad.r;
  const ih = h - pad.tp - pad.b;
  const hist = run.history;
  const tMax = Math.max(...hist.map((p) => p.t), 10);
  const eMax = Math.max(run.detect_threshold_m * 1.3, ...hist.map((p) => p.pos_error_m), 1);
  const X = (x) => pad.l + (x / tMax) * iw;
  const Y = (y) => pad.tp + ih - (y / eMax) * ih;
  const d = hist.map((p, i) => `${i === 0 ? 'M' : 'L'}${X(p.t).toFixed(1)},${Y(p.pos_error_m).toFixed(1)}`).join(' ');
  const phaseCols = [t.ok, t.muted, t.bridge, t.danger, t.danger, t.info];

  return (
    <Svg width={width} height={h}>
      {[0, 0.5, 1].map((f) => (
        <Line key={f} x1={pad.l} y1={Y(eMax * f)} x2={width - pad.r} y2={Y(eMax * f)}
              stroke={t.border} strokeWidth={1} />
      ))}
      <SvgText x={pad.l - 5} y={Y(eMax) + 4} fill={t.muted} fontSize="9" textAnchor="end">
        {eMax.toFixed(0)} m
      </SvgText>
      <Line x1={pad.l} y1={Y(run.detect_threshold_m)} x2={width - pad.r}
            y2={Y(run.detect_threshold_m)} stroke={t.danger} strokeWidth={1.5}
            strokeDasharray="5,4" />
      <SvgText x={width - pad.r - 2} y={Y(run.detect_threshold_m) - 4}
               fill={t.danger} fontSize="9" textAnchor="end">
        detect {run.detect_threshold_m} m
      </SvgText>
      {/* Phase bands along the foot, so the shape of the curve can be read
          against what the attacker was doing at the time. */}
      {hist.map((p, i) => (
        <Line key={`p${i}`} x1={X(p.t)} y1={h - 14} x2={X(p.t)} y2={h - 8}
              stroke={phaseCols[p.phase]} strokeWidth={2.5} />
      ))}
      <Path d={d} stroke={t.accent} strokeWidth={2} fill="none" />
      <SvgText x={pad.l} y={h - 1} fill={t.muted} fontSize="9">0 s</SvgText>
      <SvgText x={width - pad.r} y={h - 1} fill={t.muted} fontSize="9" textAnchor="end">
        {tMax.toFixed(0)} s
      </SvgText>
    </Svg>
  );
}

function SkyPlot({ sats, size, t, onSelect, selected }) {
  const c = size / 2;
  const R = c - 18;
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
  phases: { flexDirection: 'row', marginBottom: 10 },
  phaseDot: {
    width: 26, height: 5, borderRadius: 3, borderWidth: 1, marginRight: 4,
  },
  controls: { flexDirection: 'row', flexWrap: 'wrap', marginBottom: 8 },
  btn: {
    borderWidth: 1, borderColor: t.border, borderRadius: 8,
    paddingHorizontal: 13, paddingVertical: 10, marginRight: 7, marginBottom: 6,
  },
  btnGo: { borderColor: t.ok, backgroundColor: `${t.ok}18` },
  btnStop: { borderColor: t.danger, backgroundColor: `${t.danger}18` },
  btnText: { color: t.text, fontSize: 12, fontWeight: '700' },
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
  tags: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 8 },
  selBox: {
    borderWidth: 1, borderColor: t.border, borderRadius: 8,
    padding: 10, marginTop: 10, backgroundColor: t.bg,
  },
  selTitle: {
    color: t.text, fontSize: 12.5, fontWeight: '800',
    fontFamily: fonts.mono, marginBottom: 4,
  },
  alert: {
    color: t.danger, fontSize: 11.5, lineHeight: 17, marginTop: 10,
    borderLeftWidth: 3, borderLeftColor: t.danger, paddingLeft: 9,
  },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 8 },
  caveat: { color: t.bridge, fontSize: 10.5, lineHeight: 16, marginTop: 10 },
});
