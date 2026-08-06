import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, useWindowDimensions,
} from 'react-native';
import Svg, { Circle, Line, Path, Rect, Text as SvgText } from 'react-native-svg';
import { uavApi } from '../../api/uav';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV, Tag } from './parts';

const FLEET_SIZES = [1, 2, 3, 4, 5, 6, 7, 8];
const MAPPINGS = [
  { id: 'kinematic', label: 'Kinematic', note: 'v_max = 15 m/s' },
  { id: 'receiver', label: 'Receiver', note: 'γ = 1.195 m/s' },
  { id: 'ekf', label: 'EKF', note: 'γ = 1.365 m/s' },
];
const CORRIDORS = [2, 5, 10, 20];

/**
 * Live flight simulation: aircraft moving, under attack, with the certified
 * tube drawn around the nominal track.
 *
 * The reason this is worth building rather than screenshotting is that the
 * deviation on screen is not decorative. Position is computed as
 * nominal + γ·Δ, using the same γ the certificate consumes, and the tube ring
 * is γ·Δ·e^{LT} with the same locally-measured L = 1.181. So switching the
 * mapping mid-flight visibly moves the aircraft inside or outside its own
 * certificate -- which is the paper's central claim, animated, on data rather
 * than on a slide.
 *
 * `delay_relay` is flagged as the hero attack because it is the class the
 * theorem addresses: it is the stealthiest in the damage table, since staying
 * under θ is exactly what an evading adversary does.
 */
export default function FleetDemoScreen() {
  const { t } = useTheme();
  const { width } = useWindowDimensions();
  const s = styles(t);

  const [snap, setSnap] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [fleetSize, setFleetSize] = useState(4);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);
  const [attacks, setAttacks] = useState({});
  const [mapping, setMapping] = useState('ekf');
  const [corridor, setCorridor] = useState(10);
  const [js, setJs] = useState(10);
  const timer = useRef(null);
  const inflight = useRef(false);

  const reset = useCallback(async () => {
    setRunning(false);
    try {
      setSnap(await uavApi.fleetReset({
        n: fleetSize, corridor_m: corridor, mapping, js_db: js,
      }));
      setAttacks({});
      setError(null);
    } catch (e) { setError(e.message); }
  }, [corridor, mapping, js, fleetSize]);

  useEffect(() => {
    uavApi.fleetCatalog().then(setCatalog).catch(() => {});
    uavApi.fleet().then(setSnap).catch((e) => setError(e.message));
  }, []);

  const step = useCallback(async () => {
    // Never stack requests: a slow round trip on a conference network would
    // otherwise queue steps and make the fleet lurch when they all land.
    if (inflight.current) return;
    inflight.current = true;
    try {
      setSnap(await uavApi.fleetStep({
        attacks, js_db: js, dt_s: 1.0, corridor_m: corridor, mapping,
      }));
    } catch (e) {
      setError(e.message); setRunning(false);
    } finally { inflight.current = false; }
  }, [attacks, js, corridor, mapping]);

  useEffect(() => {
    if (!running) {
      if (timer.current) clearInterval(timer.current);
      return undefined;
    }
    timer.current = setInterval(step, 900);
    return () => clearInterval(timer.current);
  }, [running, step]);

  if (error && !snap) return <Unavailable message={error} />;
  if (!snap) return <Text style={s.loading}>starting the fleet…</Text>;

  const size = Math.min(width - 60, 520);
  const cert = snap.certificate;

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader
        eyebrow="UAV / Aerial Defense"
        title="Live Fleet Demo"
        lede="Four aircraft flying a circuit. Inject an attack per aircraft and
              watch the track separate from its nominal path — the separation is
              γ·Δ, the same quantity the certificate bounds."
        grounded={false}
        source="simulator; γ and L measured"
      />

      <Panel title="Fleet" subtitle={`t = ${snap.t_s}s · corridor ${snap.corridor_m} m · γ = ${snap.gamma_m_s} m/s`}>
        <FleetMap snap={snap} size={size} t={t} />
        <Text style={s.sub}>Fleet size</Text>
        <View style={s.row}>
          {FLEET_SIZES.map((n) => (
            <Pressable key={n} onPress={() => setFleetSize(n)}
                       style={[s.pill, fleetSize === n && s.pillOn]}>
              <Text style={[s.pillText, fleetSize === n && { color: t.accent }]}>{n}</Text>
            </Pressable>
          ))}
        </View>
        <Text style={s.hint}>
          {fleetSize === snap.fleet.n
            ? `${snap.fleet.n} aircraft airborne.`
            : `Reset to fly ${fleetSize} (currently ${snap.fleet.n}).`}
        </Text>

        <View style={s.controls}>
          <Pressable onPress={() => setRunning((r) => !r)}
                     style={[s.btn, running ? s.btnStop : s.btnGo]}>
            <Text style={[s.btnText, { color: running ? t.danger : t.ok }]}>
              {running ? '❚❚  pause' : '▶  fly'}
            </Text>
          </Pressable>
          <Pressable onPress={step} style={s.btn}>
            <Text style={s.btnText}>step 1 s</Text>
          </Pressable>
          <Pressable onPress={reset} style={s.btn}>
            <Text style={s.btnText}>reset</Text>
          </Pressable>
        </View>
      </Panel>

      <Panel title="Mission outcome" subtitle={`deadline ${snap.mission?.deadline_s ?? '—'} s = (1 + κ)·T, κ = ${snap.mission?.kappa ?? '—'}`}>
        <View style={s.mcrRow}>
          <Mcr t={t} label="Spatial MCR" v={snap.fleet.spatial_mcr}
               note="stayed inside the corridor" />
          <Mcr t={t} label="Temporal MCR" v={snap.fleet.temporal_mcr}
               note="arrived by the deadline" />
          <Mcr t={t} label="Composed" v={snap.fleet.composed_mcr}
               note="both, which is what is certified" />
        </View>
        <KV k="completed" v={snap.fleet.n_completed} />
        <KV k="failed" v={snap.fleet.n_failed} tone={snap.fleet.n_failed ? t.danger : undefined} />
        <KV k="late" v={snap.fleet.n_late} tone={snap.fleet.n_late ? t.bridge : undefined} />
        <KV k="in flight" v={snap.fleet.n_in_flight} />
        <KV k="mean detection rate"
            v={snap.fleet.mean_detection_rate == null ? 'no attacks yet'
               : `${(snap.fleet.mean_detection_rate * 100).toFixed(0)}%`} />
        <Text style={s.hint}>
          When Spatial exceeds Temporal, aircraft are finishing safely but late —
          the failure mode a purely spatial metric cannot see, and the reason MCR
          is a conjunction of two predicates rather than one.
        </Text>
      </Panel>

      {snap.uavs.some((u) => (u.history ?? []).length > 3) ? (
        <Panel title="Flight timelines" subtitle="mission progress against the deadline">
          <Timeline snap={snap} width={size} t={t} />
        </Panel>
      ) : null}

      <Panel title="Certified tube"
             subtitle="ρ = γ·Δ·e^{LT}, with L = 1.181 measured over the operating region"
             accent={cert.inside_corridor ? t.ok : t.danger}>
        <View style={[s.verdict, { borderColor: cert.inside_corridor ? t.ok : t.danger }]}>
          <Text style={[s.verdictText, { color: cert.inside_corridor ? t.ok : t.danger }]}>
            {cert.inside_corridor ? 'INSIDE the corridor' : 'OUTSIDE the corridor'}
          </Text>
        </View>
        <KV k="worst undetected staleness Δ" v={`${cert.worst_staleness_s} s`} />
        <KV k="tube radius ρ" v={`${cert.tube_m} m`} />
        <KV k="corridor margin m" v={`${snap.corridor_m} m`} />
        <KV k="max actual deviation" v={`${snap.fleet.max_deviation_m} m`} />
        <KV k="spatial MCR so far"
            v={snap.fleet.spatial_mcr == null ? 'no flight decided yet' : snap.fleet.spatial_mcr} />
        <Text style={s.hint}>{cert.reading}</Text>
      </Panel>

      <Panel title="θ ↦ δ mapping" subtitle="the control that decides the verdict">
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
        <Text style={s.hint}>
          {MAPPINGS.find((m) => m.id === mapping)?.note}
          {mapping === 'kinematic'
            ? ' — always sound, about 11× loose. Set a relay delay running and this is the one that puts the fleet outside its own tube.'
            : ' — measured on three real PX4 flights, hover regime.'}
        </Text>

        <Text style={s.sub}>Corridor margin</Text>
        <View style={s.row}>
          {CORRIDORS.map((v) => (
            <Pressable key={v} onPress={() => setCorridor(v)}
                       style={[s.pill, corridor === v && s.pillOn]}>
              <Text style={[s.pillText, corridor === v && { color: t.accent }]}>{v} m</Text>
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
      </Panel>

      <Panel title="Per-aircraft attack injection">
        {snap.uavs.map((u) => (
          <View key={u.uav_id} style={s.uav}>
            <View style={s.uavHead}>
              <Text style={s.uavId}>{u.uav_id}</Text>
              <Text style={s.uavKind}>{u.kind.replace(/_/g, ' ')} · {u.defense}</Text>
            </View>

            <View style={s.tags}>
              <Tag label={u.autopilot_mode.replace(/_/g, ' ')}
                   color={u.autopilot_mode === 'nominal' ? t.ok
                     : u.autopilot_mode === 'rtl' ? t.danger : t.bridge} />
              <Tag label={`Δ ${u.staleness_s.toFixed(2)} s`} color={t.network} />
              <Tag label={`dev ${u.deviation_m.toFixed(1)} m`}
                   color={u.deviation_m > snap.corridor_m ? t.danger : t.muted} />
              <Tag label={`batt ${u.battery_pct.toFixed(0)}%`} color={t.muted} />
              <Tag label={`link ${u.link_quality_pct.toFixed(0)}%`} color={t.muted} />
              {u.attack_caught ? <Tag label="detected" color={t.ok} /> : null}
              {u.completed === true ? <Tag label="completed" color={t.ok} /> : null}
              {u.completed === false ? <Tag label="failed" color={t.danger} /> : null}
              {u.detection_rate != null
                ? <Tag label={`caught ${(u.detection_rate * 100).toFixed(0)}%`} color={t.info} /> : null}
              {u.t_arr_s != null && u.completed
                ? <Tag label={`arrived ${u.t_arr_s}s`}
                       color={u.on_time ? t.ok : t.bridge} /> : null}
              {u.on_time === false
                ? <Tag label="LATE" color={t.bridge} /> : null}
            </View>

            <View style={s.row}>
              {(catalog?.attacks ?? [{ id: 'none', label: 'None' }]).map((a) => {
                const on = (attacks[u.uav_id] ?? 'none') === a.id;
                const hero = a.id === 'delay_relay';
                return (
                  <Pressable key={a.id}
                             onPress={() => setAttacks((p) => ({ ...p, [u.uav_id]: a.id }))}
                             style={[s.chip, on && s.pillOn,
                                     hero && !on && { borderColor: t.bridge }]}
                             accessibilityLabel={`${a.label}: ${a.note ?? ''}`}>
                    <Text style={[s.chipText, on && { color: t.accent },
                                  hero && !on && { color: t.bridge }]}>
                      {a.label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
            {attacks[u.uav_id] && attacks[u.uav_id] !== 'none' && catalog ? (
              <Text style={s.attackNote}>
                {catalog.attacks.find((a) => a.id === attacks[u.uav_id])?.note}
              </Text>
            ) : null}
          </View>
        ))}
      </Panel>

      <Panel title="What is real here and what is not">
        <Text style={s.body}>
          The flight dynamics are illustrative — this is not a PX4 SITL run. Two
          things in it are measured, and they are the two that matter: γ, which
          converts undetected network staleness into metres of position error,
          comes from three real PX4 flights; and L = 1.181, which amplifies it
          over the horizon, was measured over operating-region trajectories
          rather than by random power iteration.
        </Text>
        <Text style={s.body}>
          So the aircraft's separation from its nominal track and the radius of
          the tube drawn around it are the same quantity the theorem bounds. Set
          UAV-01 to <Text style={s.em}>Relay delay</Text>, let it run, then flip
          the mapping from EKF to Kinematic: the tube jumps past the corridor
          while nothing about the attack changed. That is the paper's result in
          one gesture.
        </Text>
        <Text style={s.hint}>{snap.note}</Text>
      </Panel>
    </ScrollView>
  );
}

function Mcr({ t, label, v, note }) {
  const s = styles(t);
  const pct = v == null ? null : Math.round(v * 100);
  const tone = v == null ? t.muted : v >= 0.9 ? t.ok : v >= 0.5 ? t.bridge : t.danger;
  return (
    <View style={s.mcrCell}>
      <Text style={s.mcrLabel}>{label}</Text>
      <Text style={[s.mcrValue, { color: tone }]}>
        {pct == null ? '—' : `${pct}%`}
      </Text>
      <Text style={s.mcrNote}>{note}</Text>
    </View>
  );
}

/**
 * Mission progress per aircraft against wall-clock time, with the deadline
 * drawn in. A line that reaches the top to the RIGHT of the deadline rule is a
 * flight that succeeded spatially and failed temporally -- the case this whole
 * panel exists to make visible.
 */
function Timeline({ snap, width, t }) {
  const h = 160;
  const pad = { l: 34, r: 10, tp: 10, b: 22 };
  const iw = width - pad.l - pad.r;
  const ih = h - pad.tp - pad.b;
  const tMax = Math.max(snap.mission?.deadline_s ?? 90, snap.t_s, 10);
  const X = (x) => pad.l + (x / tMax) * iw;
  const Y = (y) => pad.tp + ih - (y / 100) * ih;
  const palette = [t.ok, t.network, t.info, t.bridge, t.accent, t.danger,
                   t.autonomy, t.muted];
  const dl = snap.mission?.deadline_s;

  return (
    <Svg width={width} height={h}>
      {[0, 50, 100].map((v) => (
        <Line key={v} x1={pad.l} y1={Y(v)} x2={width - pad.r} y2={Y(v)}
              stroke={t.border} strokeWidth={1} />
      ))}
      <SvgText x={pad.l - 5} y={Y(100) + 4} fill={t.muted} fontSize="9"
               textAnchor="end">100%</SvgText>
      <SvgText x={pad.l - 5} y={Y(0) + 4} fill={t.muted} fontSize="9"
               textAnchor="end">0</SvgText>
      {dl ? (
        <>
          <Line x1={X(dl)} y1={pad.tp} x2={X(dl)} y2={pad.tp + ih}
                stroke={t.bridge} strokeWidth={1.5} strokeDasharray="5,4" />
          <SvgText x={X(dl)} y={h - 6} fill={t.bridge} fontSize="9"
                   textAnchor="middle">deadline {dl}s</SvgText>
        </>
      ) : null}
      {snap.uavs.map((u, i) => {
        const hist = u.history ?? [];
        if (hist.length < 2) return null;
        const d = hist.map((p, j) =>
          `${j === 0 ? 'M' : 'L'}${X(p.t).toFixed(1)},${Y(p.progress).toFixed(1)}`).join(' ');
        return (
          <Path key={u.uav_id} d={d} stroke={palette[i % palette.length]}
                strokeWidth={1.8} fill="none"
                opacity={u.completed === false ? 0.45 : 1} />
        );
      })}
    </Svg>
  );
}

/** Plan view: nominal track, actual track, and the certified tube around it. */
function FleetMap({ snap, size, t }) {
  const span = 420;                      // metres across the viewport
  const S = (v) => (v / span + 0.5) * size;
  const scale = size / span;             // metres -> px

  const colors = [t.ok, t.network, t.info, t.bridge, t.accent, t.danger];

  return (
    <Svg width={size} height={size}>
      <Rect x={0} y={0} width={size} height={size} fill={t.bg} rx={8} />
      {[0.25, 0.5, 0.75].map((f) => (
        <React.Fragment key={f}>
          <Line x1={0} y1={size * f} x2={size} y2={size * f} stroke={t.border} strokeWidth={0.5} />
          <Line x1={size * f} y1={0} x2={size * f} y2={size} stroke={t.border} strokeWidth={0.5} />
        </React.Fragment>
      ))}

      {snap.uavs.map((u, i) => {
        const c = colors[i % colors.length];
        const nx = S(u.nom_x); const ny = S(u.nom_y);
        const ax = S(u.x); const ay = S(u.y);
        const outside = u.deviation_m > snap.corridor_m;
        return (
          <React.Fragment key={u.uav_id}>
            {/* Corridor around the nominal track. */}
            <Circle cx={nx} cy={ny} r={Math.max(2, snap.corridor_m * scale)}
                    fill="none" stroke={t.border} strokeWidth={1} strokeDasharray="3,3" />
            {/* Certified tube -- the thing the theorem bounds. */}
            <Circle cx={nx} cy={ny} r={Math.max(1, snap.certificate.tube_m * scale)}
                    fill={snap.certificate.inside_corridor ? t.ok : t.danger}
                    opacity={0.12} />
            {/* Nominal position. */}
            <Circle cx={nx} cy={ny} r={3} fill="none" stroke={c} strokeWidth={1} />
            {/* Displacement the attack produced. */}
            <Line x1={nx} y1={ny} x2={ax} y2={ay}
                  stroke={outside ? t.danger : c} strokeWidth={1.5}
                  strokeDasharray={outside ? '4,3' : undefined} />
            {/* Actual position. */}
            <Circle cx={ax} cy={ay} r={6} fill={c}
                    stroke={outside ? t.danger : 'none'} strokeWidth={2} />
            <SvgText x={ax + 9} y={ay + 3} fill={t.text} fontSize="9">
              {u.uav_id.replace('UAV-', '')}
            </SvgText>
            {u.last_attack !== 'none' ? (
              <SvgText x={ax + 9} y={ay + 14} fill={u.attack_caught ? t.ok : t.danger}
                       fontSize="8">
                {u.attack_caught ? 'caught' : u.last_attack.replace(/_/g, ' ')}
              </SvgText>
            ) : null}
          </React.Fragment>
        );
      })}
      <SvgText x={8} y={size - 8} fill={t.muted} fontSize="9">
        {span} m across · dashed ring = corridor · filled ring = certified tube
      </SvgText>
    </Svg>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  controls: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 10 },
  btn: {
    borderWidth: 1, borderColor: t.border, borderRadius: 8,
    paddingHorizontal: 14, paddingVertical: 10, marginRight: 8, marginBottom: 6,
    minWidth: 84, alignItems: 'center',
  },
  btnGo: { borderColor: t.ok, backgroundColor: `${t.ok}18` },
  btnStop: { borderColor: t.danger, backgroundColor: `${t.danger}18` },
  btnText: { color: t.text, fontSize: 12.5, fontWeight: '700' },
  row: { flexDirection: 'row', flexWrap: 'wrap' },
  pill: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingHorizontal: 11, paddingVertical: 7, marginRight: 6, marginBottom: 6,
  },
  pillOn: { borderColor: t.accent, backgroundColor: `${t.accent}22` },
  pillText: { color: t.muted, fontSize: 12, fontWeight: '600' },
  chip: {
    borderWidth: 1, borderColor: t.border, borderRadius: 6,
    paddingHorizontal: 8, paddingVertical: 6, marginRight: 5, marginBottom: 5,
  },
  chipText: { color: t.muted, fontSize: 11, fontWeight: '600' },
  sub: {
    color: t.muted, fontSize: 9.5, fontWeight: '800', letterSpacing: 1,
    textTransform: 'uppercase', marginTop: 12, marginBottom: 6,
  },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 6 },
  verdict: {
    borderWidth: 1, borderRadius: 8, paddingVertical: 9,
    alignItems: 'center', marginBottom: 10,
  },
  verdictText: { fontSize: 13, fontWeight: '800', letterSpacing: 0.5 },
  uav: { borderTopWidth: 1, borderTopColor: t.border, paddingTop: 10, marginTop: 10 },
  uavHead: { flexDirection: 'row', alignItems: 'baseline', flexWrap: 'wrap' },
  uavId: { color: t.text, fontSize: 13, fontWeight: '800', fontFamily: fonts.mono, marginRight: 8 },
  uavKind: { color: t.muted, fontSize: 10.5 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 6, marginBottom: 4 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19, marginBottom: 8 },
  attackNote: { color: t.muted, fontSize: 10, lineHeight: 15, marginTop: 2, fontStyle: 'italic' },
  mcrRow: { flexDirection: 'row', flexWrap: 'wrap', marginBottom: 10 },
  mcrCell: { flexGrow: 1, flexBasis: '30%', paddingRight: 8, marginBottom: 6 },
  mcrLabel: {
    color: t.muted, fontSize: 9, fontWeight: '800', letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  mcrValue: { fontSize: 26, fontWeight: '800', fontFamily: fonts.display },
  mcrNote: { color: t.muted, fontSize: 9.5, lineHeight: 13.5 },
  em: { color: t.bridge, fontWeight: '700' },
});
