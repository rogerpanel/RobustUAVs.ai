import React, { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, useWindowDimensions,
} from 'react-native';
import Svg, { Circle, Line, Text as SvgText } from 'react-native-svg';
import { uavApi } from '../../api/uav';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV } from './parts';
import { recordContext } from '../../state/context';

/**
 * Three temporal snapshots of the mesh. Same three-scene structure as the
 * robustidps page, but each edge carries its measured residual delay, so the
 * picture and the theorem describe the same object rather than two loosely
 * related ones.
 */
export default function SwarmGraphScreen() {
  const { t } = useTheme();
  const { width } = useWindowDimensions();
  const s = styles(t);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [idx, setIdx] = useState(0);
  // t4 is a composite rather than a fourth measurement: it overlays whichever
  // snapshots are ticked, so the three moments can be compared on one figure
  // instead of by flicking between them and holding the difference in memory.
  const [overlay, setOverlay] = useState([true, true, true]);
  const composite = idx === 3;

  useEffect(() => {
    uavApi.swarm().then((d) => {
      setData(d);
      recordContext({
        routeKey: 'SwarmGraph',
        label: 'swarm snapshots',
        question: `The swarm graph shows three moments at θ = ${d.operating_point.theta_s} s `
          + `with a ${d.operating_point.contact_window_s} s contact window and a `
          + `${d.operating_point.twig_period_s} s TWiG period. Explain why the third `
          + `snapshot is flagged at any ε while the second is not.`,
        data: d.operating_point,
      });
    }).catch((e) => setError(e.message));
  }, []);

  if (error) return <Unavailable message={error} />;
  if (!data) return <Text style={s.loading}>loading…</Text>;

  const snap = composite ? null : data.snapshots[idx];
  const shown = data.snapshots.filter((_, i) => overlay[i]);
  const size = Math.min(width - 60, 460);
  const op = data.operating_point;

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader
        eyebrow="UAV / Aerial Defense"
        title="Swarm Graph"
        lede="The mesh at three moments: clean, delayed within the detector's
              budget, and past the contact window. Each edge is labelled with the
              per-hop residual delay that decides whether the detector fires."
        grounded
        source={data.source}
      />

      <Panel title="Snapshot"
             subtitle={composite
               ? 'All ticked snapshots on one figure. Edge colour is the worst state that edge reaches.'
               : snap.caption}>
        <View style={s.row}>
          {data.snapshots.map((sn, i) => (
            <Pressable key={sn.t} onPress={() => setIdx(i)}
                       style={[s.pill, idx === i && s.pillOn]}>
              <Text style={[s.pillText, idx === i && { color: t.accent }]}>{sn.label}</Text>
            </Pressable>
          ))}
          <Pressable onPress={() => setIdx(3)}
                     style={[s.pill, composite && s.pillOn,
                             !composite && { borderColor: t.bridge }]}>
            <Text style={[s.pillText, composite ? { color: t.accent } : { color: t.bridge }]}>
              t₄ — all together
            </Text>
          </Pressable>
        </View>

        {composite ? (
          <>
            <View style={s.row}>
              {data.snapshots.map((sn, i) => (
                <Pressable key={`o${sn.t}`}
                           onPress={() => setOverlay((p) => p.map((v, j) => (j === i ? !v : v)))}
                           style={s.checkRow}>
                  <View style={[s.box, overlay[i] && { borderColor: t.accent, backgroundColor: `${t.accent}33` }]}>
                    {overlay[i] ? <Text style={s.tick}>✓</Text> : null}
                  </View>
                  <Text style={s.checkLabel}>{sn.label}</Text>
                </Pressable>
              ))}
            </View>
            <Composite snaps={shown} size={size} t={t} theta={op.theta_s} />
            <Text style={s.hint}>
              Reading the composite: an edge drawn solid green is trusted in every
              ticked moment. An edge that turns amber is delayed but still inside
              the detector's budget. A red edge exceeded it. The topology is fixed,
              so what changes between moments is only the delay on each link —
              which is the point the three separate figures make one at a time.
            </Text>
          </>
        ) : (
          <Graph snap={snap} size={size} t={t} theta={op.theta_s} />
        )}
      </Panel>

      <Panel title="Operating point">
        <KV k="detector threshold θ" v={`${op.theta_s} s`} />
        <KV k="benign residual ceiling" v={`${op.benign_ceiling_s} s (measured, FPR = 0)`} />
        <KV k="inter-UAV contact window s" v={`${op.contact_window_s} s`} />
        <KV k="TWiG period cost of a miss" v={`${op.twig_period_s} s`} />
        <Text style={s.hint}>
          Lemma 1 tightens to Δ(θ) ≤ H·min(θ, s): past the contact window the
          slack, not the threshold, bounds what an evading adversary can bank.
          No undetected malicious residual exceeded 4.84 s over 15,392 hops.
        </Text>
      </Panel>

      <Panel title="Reading the third snapshot">
        <Text style={s.body}>
          The compromised relay in t₃ is not subtle, and that is the point: a
          delay past the 5 s slack costs a full 60 s TWiG period, so it is
          flagged at any ε. This is the knee in the operating curve — recall
          holds at 0.938 to ε = 3 s, then falls to 0.234 from 5 s on, and the
          survivors at high ε are all missed-window residuals rather than path
          deviations.
        </Text>
        <Text style={s.hint}>{data.provenance}</Text>
      </Panel>
    </ScrollView>
  );
}

/**
 * t4: every ticked snapshot drawn together.
 *
 * Each edge is coloured by the WORST state it reaches across the selection and
 * annotated with the range of residual delays it takes, so one figure carries
 * what the three separate ones say sequentially. The layout is identical to
 * `Graph`, deliberately: a composite that re-arranged the nodes would make the
 * reader re-find them instead of reading the change.
 */
function Composite({ snaps, size, t, theta }) {
  const POS = {
    u1: [0.18, 0.34], u2: [0.5, 0.14], u3: [0.82, 0.34],
    p: [0.5, 0.82], b: [0.5, 0.5],
  };
  const kindColor = { uav: t.ok, droneport: t.network, intruder: t.danger };
  const RANK = { trust: 0, delayed: 1, jammed: 1, hostile: 2 };
  const EDGE = [t.ok, t.bridge, t.danger];

  const edges = new Map();
  const nodes = new Map();
  snaps.forEach((sn) => {
    sn.nodes.forEach((n) => nodes.set(n.id, n));
    sn.edges.forEach((e) => {
      const key = `${e.src}-${e.dst}`;
      const prev = edges.get(key);
      const rank = RANK[e.kind] ?? 0;
      if (!prev || rank > prev.rank) {
        edges.set(key, { ...e, rank, lo: e.residual_s, hi: e.residual_s });
      } else {
        prev.lo = Math.min(prev.lo, e.residual_s);
        prev.hi = Math.max(prev.hi, e.residual_s);
      }
    });
  });

  const fmt = (v) => (v >= 1 ? v.toFixed(1) : v.toFixed(2));

  return (
    <Svg width={size} height={size * 0.86} style={{ marginTop: 8 }} nativeID="swarm-composite">
      {[...edges.values()].map((e) => {
        const a = POS[e.src]; const b = POS[e.dst];
        if (!a || !b) return null;
        const [x1, y1] = [a[0] * size, a[1] * size * 0.86];
        const [x2, y2] = [b[0] * size, b[1] * size * 0.86];
        const col = EDGE[e.rank];
        return (
          <React.Fragment key={`${e.src}-${e.dst}`}>
            <Line x1={x1} y1={y1} x2={x2} y2={y2} stroke={col}
                  strokeWidth={e.rank === 2 ? 2.6 : 1.9}
                  strokeDasharray={e.rank === 0 ? undefined : '5,4'} />
            <SvgText x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 4} fill={col}
                     fontSize="9" textAnchor="middle">
              {e.lo === e.hi ? `${fmt(e.lo)} s` : `${fmt(e.lo)}–${fmt(e.hi)} s`}
            </SvgText>
          </React.Fragment>
        );
      })}
      {[...nodes.values()].map((n) => {
        const p = POS[n.id]; if (!p) return null;
        const [x, y] = [p[0] * size, p[1] * size * 0.86];
        return (
          <React.Fragment key={n.id}>
            <Circle cx={x} cy={y} r={n.kind === 'droneport' ? 13 : 11}
                    fill={kindColor[n.kind] ?? t.muted} />
            <SvgText x={x} y={y - 18} fill={t.text} fontSize="10" textAnchor="middle">
              {n.label}
            </SvgText>
          </React.Fragment>
        );
      })}
    </Svg>
  );
}

function Graph({ snap, size, t, theta }) {
  // Fixed layout: three aircraft over a droneport, intruder off to the side.
  // Deterministic positions matter here -- a graph that reshuffles between
  // snapshots makes the viewer re-find the nodes instead of reading the change.
  const POS = {
    u1: [0.18, 0.34], u2: [0.5, 0.14], u3: [0.82, 0.34],
    p: [0.5, 0.82], b: [0.5, 0.5],
  };
  const kindColor = { uav: t.ok, droneport: t.network, intruder: t.danger };
  const edgeColor = { trust: t.ok, delayed: t.bridge, jammed: t.bridge, hostile: t.danger };

  return (
    <Svg width={size} height={size * 0.86} style={{ marginTop: 8 }} nativeID="swarm-graph">
      {snap.edges.map((e) => {
        const a = POS[e.src]; const b = POS[e.dst];
        if (!a || !b) return null;
        const [x1, y1] = [a[0] * size, a[1] * size * 0.86];
        const [x2, y2] = [b[0] * size, b[1] * size * 0.86];
        const over = e.residual_s > theta;
        return (
          <React.Fragment key={`${e.src}-${e.dst}`}>
            <Line x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={edgeColor[e.kind] ?? t.muted}
                  strokeWidth={e.kind === 'hostile' ? 2.5 : 1.8}
                  strokeDasharray={e.kind === 'trust' ? undefined : '5,4'} />
            <SvgText x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 4}
                     fill={over ? t.danger : t.muted} fontSize="9" textAnchor="middle">
              {e.residual_s >= 1 ? `${e.residual_s.toFixed(1)} s` : `${e.residual_s.toFixed(2)} s`}
            </SvgText>
          </React.Fragment>
        );
      })}
      {snap.nodes.map((n) => {
        const p = POS[n.id]; if (!p) return null;
        const [x, y] = [p[0] * size, p[1] * size * 0.86];
        return (
          <React.Fragment key={n.id}>
            <Circle cx={x} cy={y} r={n.kind === 'droneport' ? 13 : 11}
                    fill={kindColor[n.kind] ?? t.muted} />
            <SvgText x={x} y={y - 18} fill={t.text} fontSize="10" textAnchor="middle">
              {n.label}
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
  row: { flexDirection: 'row', flexWrap: 'wrap' },
  pill: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingHorizontal: 11, paddingVertical: 7, marginRight: 6, marginBottom: 6,
  },
  pillOn: { borderColor: t.accent, backgroundColor: `${t.accent}22` },
  pillText: { color: t.muted, fontSize: 11.5, fontWeight: '600' },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 8 },
  checkRow: { flexDirection: 'row', alignItems: 'center', marginRight: 14, marginBottom: 6 },
  box: {
    width: 15, height: 15, borderRadius: 4, borderWidth: 1, borderColor: t.border,
    marginRight: 6, alignItems: 'center', justifyContent: 'center',
  },
  tick: { color: t.accent, fontSize: 10, fontWeight: '800' },
  checkLabel: { color: t.muted, fontSize: 11 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19 },
});
