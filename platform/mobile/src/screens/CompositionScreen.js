import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator,
} from 'react-native';
import { api, Unavailable } from '../api/client';
import { useTheme } from '../theme';
import Card from '../components/Card';
import Chip from '../components/Chip';
import { recordContext } from '../state/context';

/**
 * The headline screen: an interactive version of the paper's Figure 3.
 *
 * The point of the paper is that the certified verdict is PARAMETRIC in the
 * theta->delta mapping -- the kinematic worst case puts theta=0.25 s outside
 * the certified window, the measured mapping puts it comfortably inside. That
 * is exactly the thing a static PDF cannot show and a live demo can, so the
 * mapping is a control here rather than a footnote.
 */

const MAPPINGS = [
  { id: 'kinematic', label: 'Kinematic', note: 'v_max = 15 m/s worst case' },
  { id: 'receiver', label: 'Receiver', note: 'γ = 1.20 m/s, measured' },
  { id: 'ekf', label: 'EKF', note: 'γ = 1.37 m/s, measured' },
];
const MARGINS = [2, 5, 10, 20];

export default function CompositionScreen() {
  const { t } = useTheme();
  const styles = makeStyles(t);
  const [theta, setTheta] = useState(0.25);
  const [mapping, setMapping] = useState('ekf');
  const [margin, setMargin] = useState(10);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const certify = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await api.certifyStaleness({
        theta_s: theta, n_malicious_hops: 2, margin_m: margin, mapping,
      });
      setResult(r);
      const p = r?.data?.params;
      if (p) {
        recordContext({
          routeKey: 'Composition',
          label: `θ=${theta}s · ${mapping} · m=${margin}m`,
          question: `On the Composition screen at θ = ${theta} s with the `
            + `${mapping} mapping and a ${margin} m corridor, the tube is `
            + `${p.tube_m} m and the point is `
            + `${p.inside_tube ? 'inside' : 'outside'} the certified window. `
            + `Explain what decides that, and cite the file.`,
          data: p,
        });
      }
    } catch (e) {
      setError(e instanceof Unavailable ? `Not produced yet: ${e.message}` : e.message);
    } finally {
      setBusy(false);
    }
  }, [theta, mapping, margin]);

  useEffect(() => { certify(); }, [certify]);

  const p = result?.data?.params;
  const inside = p?.inside_tube;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Composed guarantee</Text>
      <Text style={styles.lede}>
        θ ↦ Δ(θ) ↦ δ(θ) ↦ MCR ≥ f(δ(θ)). The verdict below is computed live by
        the certificate engine, not read from a table.
      </Text>

      <Card title="Detector operating point θ" subtitle="seconds of tolerated per-hop residual delay">
        <View style={styles.row}>
          {[0.1, 0.178, 0.25, 0.5, 1.0, 2.0, 5.0].map((v) => (
            <Pressable key={v} onPress={() => setTheta(v)}
              style={[styles.pill, theta === v && styles.pillOn]}>
              <Text style={[styles.pillText, theta === v && styles.pillTextOn]}>{v}</Text>
            </Pressable>
          ))}
        </View>
        <Text style={styles.hint}>
          0.178 s is the measured benign residual ceiling (the FPR = 0 floor);
          0.25 s is the detector's paper operating point.
        </Text>
      </Card>

      <Card title="θ ↦ δ mapping" subtitle="the choice that decides the outcome">
        <View style={styles.row}>
          {MAPPINGS.map((m) => (
            <Pressable key={m.id} onPress={() => setMapping(m.id)}
              style={[styles.pill, mapping === m.id && styles.pillOn]}>
              <Text style={[styles.pillText, mapping === m.id && styles.pillTextOn]}>
                {m.label}
              </Text>
            </Pressable>
          ))}
        </View>
        <Text style={styles.hint}>
          {MAPPINGS.find((m) => m.id === mapping)?.note}
          {mapping !== 'kinematic'
            ? ' — three real PX4 flights, hover regime; cruise pending.'
            : ' — always sound, about 11× loose.'}
        </Text>
      </Card>

      <Card title="Corridor margin m" subtitle="metres of allowed lateral deviation">
        <View style={styles.row}>
          {MARGINS.map((v) => (
            <Pressable key={v} onPress={() => setMargin(v)}
              style={[styles.pill, margin === v && styles.pillOn]}>
              <Text style={[styles.pillText, margin === v && styles.pillTextOn]}>{v} m</Text>
            </Pressable>
          ))}
        </View>
        <Text style={styles.hint}>
          JARUS SORA's default lateral contingency terms total 7 m before any
          manoeuvre term, so 2 m is tighter than any compliant buffer and 10 m
          is a small multirotor's full extent.
        </Text>
      </Card>

      {busy ? <ActivityIndicator color={t.accent} style={{ marginVertical: 20 }} /> : null}

      {error ? (
        <Card title="Unavailable"><Text style={styles.err}>{error}</Text></Card>
      ) : null}

      {p ? (
        <Card
          title="Verdict"
          source={result.source}
          subtitle={result.note}
        >
          <View style={[styles.verdict, { borderColor: inside ? t.ok : t.danger }]}>
            <Text style={[styles.verdictText, { color: inside ? t.ok : t.danger }]}>
              {inside ? 'INSIDE the certified window' : 'OUTSIDE the certified window'}
            </Text>
          </View>

          <Row k="undetected staleness Δ(θ)" v={`${p.delta_staleness_s} s`} />
          <Row k="delay-to-position rate γ" v={`${p.gamma_m_s} m/s`} />
          <Row k="perturbation δ" v={`${p.delta_pos_m} m`} />
          <Row k="Grönwall tube ρ = δ·e^{LT}" v={`${p.tube_m} m`} />
          <Row k="corridor margin m" v={`${p.margin_m} m`} />
          <Row k="certified MCR floor"
               v={result.data.certified_mcr ?? 'none at this point'} />

          <View style={styles.chips}>
            <Chip label={p.mapping} color={p.mapping === 'kinematic' ? t.bridge : t.ok} />
            <Chip label={`H = ${p.n_malicious_hops} hops`} color={t.network} />
            <Chip label={`slack s = ${p.slack_s} s`} color={t.network} />
          </View>
          <Text style={styles.hint}>{p.mapping_note}</Text>
        </Card>
      ) : null}

      <Card title="Why this screen is interactive">
        <Text style={styles.body}>
          The certified floor is not a single number; it is a function of the
          mapping used to turn network delay into position error. Flipping
          between Kinematic and EKF at θ = 0.25 s reproduces the paper's central
          claim in one tap: the same theorem, the same detector setting, and two
          opposite verdicts, decided entirely by a measurement rather than by
          the proof.
        </Text>
      </Card>
    </ScrollView>
  );
}

function Row({ k, v }) {
  const { t } = useTheme();
  const styles = makeStyles(t);
  return (
    <View style={styles.kv}>
      <Text style={styles.k}>{k}</Text>
      <Text style={styles.v}>{String(v)}</Text>
    </View>
  );
}

const makeStyles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  h1: { color: t.text, fontSize: 24, fontWeight: '800', marginBottom: 6 },
  lede: { color: t.muted, fontSize: 14, lineHeight: 20, marginBottom: 18 },
  row: { flexDirection: 'row', flexWrap: 'wrap' },
  pill: {
    borderWidth: 1, borderColor: t.border, borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 7, marginRight: 8, marginBottom: 8,
  },
  pillOn: { borderColor: t.accent, backgroundColor: `${t.accent}22` },
  pillText: { color: t.muted, fontSize: 13, fontWeight: '600' },
  pillTextOn: { color: t.accent },
  hint: { color: t.muted, fontSize: 11, lineHeight: 16, marginTop: 4 },
  verdict: {
    borderWidth: 1, borderRadius: 8, paddingVertical: 10, alignItems: 'center',
    marginBottom: 12,
  },
  verdictText: { fontSize: 14, fontWeight: '800', letterSpacing: 0.5 },
  kv: {
    flexDirection: 'row', justifyContent: 'space-between',
    paddingVertical: 5, borderBottomWidth: 1, borderBottomColor: t.border,
  },
  k: { color: t.muted, fontSize: 12, flex: 1 },
  v: { color: t.text, fontSize: 12, fontWeight: '700' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 10 },
  body: { color: t.text, fontSize: 13, lineHeight: 19 },
  err: { color: t.danger, fontSize: 13 },
});
