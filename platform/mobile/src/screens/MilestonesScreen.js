import React, { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, Linking, useWindowDimensions,
} from 'react-native';
import { api } from '../api/client';
import { useTheme, fonts } from '../theme';

/**
 * The landing screen: what the campaign has actually established, stated as
 * numbers with the committed file each came from.
 *
 * Every figure below was read out of `results/*.csv` in the repository, and the
 * `source` line on each card names the file, so any claim on this page can be
 * checked against the artifact in one step. Nothing here is illustrative and
 * nothing is rounded in the paper's favour -- MS5 and MS6 both report results
 * that weaken an earlier draft.
 *
 * These are committed constants rather than live fetches on purpose: a talk
 * cannot depend on six API calls succeeding in front of an audience, and these
 * numbers change only when a campaign is re-run and re-committed. The live
 * parts of this screen -- the run strip at the bottom -- degrade to nothing if
 * the control plane is unreachable, rather than taking the page with them.
 */

const MILESTONES = [
  {
    id: 'MS1',
    tone: 'headline',
    kicker: 'The certified window is nonempty — under the measured interface',
    stat: 'θ ≤ 1.28 s',
    unit: 'certified, m = 10 m',
    body:
      'At a 10 m corridor with H = 2 malicious hops, the kinematic worst case '
      + 'certifies only to θ* = 0.102 s — below the 0.178 s benign residual '
      + 'ceiling, so the window is empty and the detector’s operating point is '
      + 'not certifiable. The measured mapping certifies to θ* = 1.28 s '
      + '(receiver) and 1.12 s (EKF). The paper’s θ = 0.25 s sits outside the '
      + 'first and comfortably inside the second.',
    read: 'The verdict is parametric in a measurement, not in the proof.',
    source: 'results/certified_operating_window.csv',
  },
  {
    id: 'MS2',
    tone: 'ok',
    kicker: 'Composition dominates the autonomy-only baseline',
    stat: '13 / 13',
    unit: 'operating points, all three mappings',
    body:
      'Wilcoxon signed-rank over 192 paired seeds at each of 13 values of ε, '
      + 'Holm-corrected across the family. Every comparison is significant at '
      + 'α = 0.05, with p_holm below 1e-9 at the operating points that matter. '
      + 'The result holds under the kinematic, receiver and EKF mappings alike, '
      + 'so it does not depend on which interface calibration is believed.',
    read: 'The dominance claim survives the choice that decides MS1.',
    source: 'results/stats_wilcoxon.csv',
  },
  {
    id: 'MS3',
    tone: 'network',
    kicker: 'Detector operating curve, clean campaign',
    stat: 'FPR = 0',
    unit: 'recall 0.938 for ε ≤ 3 s',
    body:
      'Recall holds at 0.938 up to ε = 3 s, falls to 0.609 at 4 s and 0.234 '
      + 'from 5 s onward, with false-positive rate identically zero across the '
      + 'whole grid. The knee is the 5 s inter-UAV contact window: past it a '
      + 'delayed hop misses its window and costs a full 60 s TWiG period, which '
      + 'is flagged at any ε.',
    read: 'The plateau is missed contact windows, not path deviation.',
    source: 'results/theta_operating_curve.csv',
  },
  {
    id: 'MS4',
    tone: 'bridge',
    kicker: 'The θ ↦ δ interface is measured, not assumed',
    stat: '≈ 11×',
    unit: 'tighter than the kinematic bound',
    body:
      'Delay-to-position rate γ measured on three real PX4 flights: 1.195 m/s '
      + 'at the receiver and 1.365 m/s after the EKF, against a 15 m/s kinematic '
      + 'worst case. This is the single quantity that moves θ = 0.25 s across '
      + 'the certified boundary, which is why it is measured rather than bounded.',
    read: 'Three flights are a calibration sample, not a distribution — hover regime only, cruise pending.',
    source: 'results/whelan_delta_calibration.csv',
  },
  {
    id: 'MS5',
    tone: 'warn',
    kicker: 'The Lipschitz constant was re-measured, and it got worse',
    stat: 'L = 1.181',
    unit: 'was 0.983 by power iteration',
    body:
      'Measuring L over the actual operating-region trajectories rather than by '
      + 'random power iteration gives 1.181, which tightens the Grönwall radius '
      + 'from 0.187 to 0.153. We report the smaller, honest radius throughout. '
      + 'One earlier conclusion changed: θ = 0.25 s is certified at m ≥ 5 m but '
      + 'not at m = 2 m, where the tube reaches 2.22 m. The 10 m headline is '
      + 'unaffected.',
    read: 'Reported because it weakens a claim we had already made.',
    source: 'results/local_lipschitz.csv',
  },
  {
    id: 'MS6',
    tone: 'warn',
    kicker: 'Corpus provenance, including the part that is empty',
    stat: '46.5 %',
    unit: 'of 431,773 events are real hardware',
    body:
      'Six sources unified under one two-layer schema, every record '
      + 'schema-validated. 200,610 events come from real testbeds. But the '
      + 'number of released measured_same_platform pairings — the strongest '
      + 'evidence class the schema can express — is zero, because the only '
      + 'source observing both layers lacks machine-readable attack intervals.',
    read: 'Stated on the cover page rather than left to be discovered.',
    source: 'results/provenance_distribution.csv',
  },
];

export default function MilestonesScreen({ navigation }) {
  const { t } = useTheme();
  const { width } = useWindowDimensions();
  const s = styles(t);
  const [runs, setRuns] = useState(null);

  // Two columns only where a card still clears ~330 px. Below that the stat
  // and the body fight for the same line and both lose.
  const twoUp = width >= 760;

  useEffect(() => {
    let live = true;
    api.runs(4).then((r) => live && setRuns(r.runs ?? [])).catch(() => {});
    return () => { live = false; };
  }, []);

  const toneColor = {
    headline: t.accent, ok: t.ok, network: t.network,
    bridge: t.bridge, warn: t.bridge, info: t.info,
  };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <Text style={s.eyebrow}>Campaign status</Text>
      <Text style={s.h1}>What has been established</Text>
      <Text style={s.lede}>
        Six results, each with the committed file it was read from. Two of them
        weaken an earlier draft; they are here for the same reason the others
        are.
      </Text>

      <View style={[s.grid, twoUp && s.gridTwo]}>
        {MILESTONES.map((m) => (
          <View key={m.id}
                style={[s.card, twoUp && s.cardTwo,
                        { borderTopColor: toneColor[m.tone] ?? t.accent }]}>
            <View style={s.cardHead}>
              <Text style={[s.id, { color: toneColor[m.tone] }]}>{m.id}</Text>
              <Text style={s.kicker}>{m.kicker}</Text>
            </View>

            <Text style={[s.stat, { color: toneColor[m.tone] }]}>{m.stat}</Text>
            <Text style={s.unit}>{m.unit}</Text>

            <Text style={s.body}>{m.body}</Text>
            <Text style={s.read}>{m.read}</Text>
            <Text style={s.source}>{m.source}</Text>
          </View>
        ))}
      </View>

      <Pressable style={s.cta} onPress={() => navigation?.navigate('Composition')}>
        <Text style={s.ctaText}>Reproduce MS1 live — flip the mapping at θ = 0.25 s →</Text>
      </Pressable>

      {runs && runs.length ? (
        <View style={s.runs}>
          <Text style={s.sectionLabel}>Recent runs on this deployment</Text>
          {runs.map((r) => (
            <View key={r.run_id} style={s.run}>
              <Text style={s.runKind}>{r.label ?? r.kind}</Text>
              <Text style={s.runMeta}>
                {r.status} · {r.duration_s != null ? `${r.duration_s}s` : '—'} ·{' '}
                {r.provenance ?? 'unknown provenance'}
              </Text>
            </View>
          ))}
        </View>
      ) : null}

      <Pressable onPress={() => Linking.openURL('/artifact/')} style={s.foot}>
        <Text style={s.footText}>
          Every number above is reproducible from /artifact/ →
        </Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 18, paddingBottom: 56 },
  eyebrow: {
    color: t.accent, fontSize: 10, fontWeight: '800', letterSpacing: 1.3,
    textTransform: 'uppercase', marginBottom: 6,
  },
  h1: {
    color: t.text, fontSize: 26, fontWeight: '800', letterSpacing: -0.6,
    fontFamily: fonts.display,
  },
  lede: { color: t.muted, fontSize: 13.5, lineHeight: 20, marginTop: 8, marginBottom: 18 },

  grid: {},
  gridTwo: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -5 },
  card: {
    backgroundColor: t.panel, borderWidth: 1, borderColor: t.border,
    borderTopWidth: 3, borderRadius: 10, padding: 14, marginBottom: 10,
  },
  cardTwo: { width: '50%', marginHorizontal: 5, flexGrow: 1, flexBasis: '46%' },
  cardHead: { marginBottom: 8 },
  id: { fontSize: 10, fontWeight: '800', letterSpacing: 1, marginBottom: 3 },
  kicker: { color: t.text, fontSize: 14, fontWeight: '700', lineHeight: 19, fontFamily: fonts.display },
  stat: { fontSize: 30, fontWeight: '800', letterSpacing: -1, fontFamily: fonts.display },
  unit: { color: t.muted, fontSize: 11, marginTop: 1, marginBottom: 9 },
  body: { color: t.text, fontSize: 12, lineHeight: 18.5 },
  read: {
    color: t.muted, fontSize: 11.5, lineHeight: 17, marginTop: 8,
    fontStyle: 'italic',
  },
  source: {
    color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, marginTop: 8,
    opacity: 0.8,
  },

  cta: {
    borderWidth: 1, borderColor: t.accent, borderRadius: 9,
    paddingVertical: 13, alignItems: 'center', marginTop: 6, marginBottom: 20,
    backgroundColor: `${t.accent}14`,
  },
  ctaText: { color: t.accent, fontSize: 12.5, fontWeight: '700' },

  runs: { marginBottom: 18 },
  sectionLabel: {
    color: t.muted, fontSize: 9.5, fontWeight: '800', letterSpacing: 1.1,
    textTransform: 'uppercase', marginBottom: 8,
  },
  run: {
    borderBottomWidth: 1, borderBottomColor: t.border, paddingVertical: 7,
  },
  runKind: { color: t.text, fontSize: 12, fontWeight: '600' },
  runMeta: { color: t.muted, fontSize: 10.5, marginTop: 1 },

  foot: { paddingVertical: 10 },
  footText: { color: t.accent, fontSize: 11.5, fontWeight: '600' },
});
