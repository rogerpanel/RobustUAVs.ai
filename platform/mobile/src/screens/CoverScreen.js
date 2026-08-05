import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, Pressable, Linking } from 'react-native';
import { api, API_BASE } from '../api/client';
import { useTheme, fonts } from '../theme';
import Chip from '../components/Chip';

/**
 * Cover page, mirroring the robustidps.ai landing layout: a display-font
 * wordmark over the slate canvas, a one-line thesis, the deliverables as
 * cards, and a live deployment strip.
 *
 * Written for the first slide of a talk, so the numbers on it are the ones an
 * audience should leave with — including the uncomfortable one (zero released
 * measured_same_platform pairings), because a cover page that only shows
 * favourable figures is the kind of artifact this project argues against.
 */
/** Carried over from the static landing page this screen replaced. Counts are
 *  the ingested totals, and match results/provenance_distribution.csv. */
const SOURCES = [
  ['UAV-EW-Bench', 'autonomy · mission/GNSS', '93,600 flights'],
  ['UAVIDS-2025', 'network · mesh', '122,171 flows'],
  ['DATAMUt (sim)', 'network · mesh', 'per-hop traces'],
  ['HCRL UAVCAN', 'network · intra-bus', '10 scenarios'],
  ['UAV Attack Dataset', 'autonomy · GNSS', '3 live flights'],
  ['UAV-CAS', 'network · mesh', 'flow statistics'],
];

export default function CoverScreen({ navigation }) {
  const { t, mode, toggle } = useTheme();
  const s = styles(t);
  const [health, setHealth] = useState(null);

  useEffect(() => { api.health().then(setHealth).catch(() => {}); }, []);

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <View style={s.hero}>
        <Text style={s.eyebrow}>NDSS 2027 · artifact</Text>
        <Text style={s.wordmark}>
          RobustUAVs<Text style={{ color: t.accent }}>.ai</Text>
        </Text>
        <Text style={s.thesis}>
          From wire to flight: an end-to-end framework composing network
          intrusion detection with certified mission safety for autonomous UAVs.
        </Text>
        <View style={s.row}>
          <Chip label="cross-layer benchmark" color={t.network} />
          <Chip label="composition theorem" color={t.autonomy} />
          <Chip label="open artifact" color={t.bridge} />
        </View>
      </View>

      <View style={s.grid}>
        <Tile t={t} accent={t.network} title="Six datasets"
              body="Unified under one two-layer schema, 431,773 events, every record schema-validated."
              onPress={() => navigation.navigate('Registry')} />
        <Tile t={t} accent={t.autonomy} title="Composition theorem"
              body="θ ↦ Δ(θ) ↦ δ(θ) ↦ MCR ≥ f(δ(θ)), with a certified window that is nonempty under the measured interface."
              onPress={() => navigation.navigate('Composition')} />
        <Tile t={t} accent={t.bridge} title="Live experiments"
              body="Drive the certificate engine with your own parameters and hyperparameters."
              onPress={() => navigation.navigate('Runs')} />
        <Tile t={t} accent={t.info} title="Copilot"
              body="Ask about the corpus or the guarantee; every answer cites the committed file it came from."
              onPress={() => navigation.navigate('Copilot')} />
      </View>

      <Text style={s.h2}>The six sources</Text>
      <View style={s.table}>
        {SOURCES.map((r) => (
          <View key={r[0]} style={s.tr}>
            <Text style={[s.td, s.tdName]}>{r[0]}</Text>
            <Text style={[s.td, s.tdLayer]}>{r[1]}</Text>
            <Text style={[s.td, s.tdCount]}>{r[2]}</Text>
          </View>
        ))}
      </View>

      <Text style={s.h2}>Artifact and data</Text>
      <View style={s.links}>
        <LinkRow t={t} label="/artifact/"
                 note="schema, adapters, certificate engine, every committed result"
                 href="/artifact/" />
        <LinkRow t={t} label="Kaggle corpus"
                 note="all six datasets and the DATAMUt program · DOI 10.34740/kaggle/dsv/18346203"
                 href="https://www.kaggle.com/datasets/rogernickanaedevha/uavs-network-and-navigation-end-to-end-security-data" />
      </View>

      <View style={s.honest}>
        <Text style={s.honestTitle}>Stated up front</Text>
        <Text style={s.honestBody}>
          46.5% of ingested events are real-hardware captures — but the number of
          released <Text style={s.mono}>measured_same_platform</Text> pairings is
          zero, because the one source observing both layers lacks
          machine-readable attack intervals. The δ calibration is still a
          real-flight measurement. The strongest evidence class the schema can
          express is, today, unpopulated.
        </Text>
      </View>

      <View style={s.strip}>
        <Text style={s.stripText}>{API_BASE}</Text>
        {health ? (
          <View style={s.row}>
            <Chip label={`db: ${health.database}`} color={t.muted} />
            <Chip label={`cache: ${health.cache?.backend}`} color={t.muted} />
            <Chip label={`auth: ${health.auth?.mode}`}
                  color={health.auth?.mode === 'open' ? t.bridge : t.ok} />
            <Chip label={`${health.models} models`} color={t.muted} />
            <Chip label={`${health.copilot_tools} tools`} color={t.muted} />
          </View>
        ) : null}
      </View>

      <Pressable onPress={toggle} style={s.themeBtn}>
        <Text style={s.themeText}>
          {mode === 'dark' ? '☀  switch to print theme (for projectors)' : '☾  switch to dark theme'}
        </Text>
      </Pressable>

      <Text style={s.footer}>
        Roger Nick Anaedevha · Institute of Cyber Intelligent Systems, MEPhI ·
        Keiwan Soltani, Missouri S&T · Federico Corò, University of Padova
      </Text>
    </ScrollView>
  );
}

function LinkRow({ t, label, note, href }) {
  const s = styles(t);
  return (
    <Pressable onPress={() => Linking.openURL(href)} style={s.link}>
      <Text style={s.linkLabel}>{label} &rarr;</Text>
      <Text style={s.linkNote}>{note}</Text>
    </Pressable>
  );
}

function Tile({ t, title, body, accent, onPress }) {
  const s = styles(t);
  return (
    <Pressable onPress={onPress} style={[s.tile, { borderTopColor: accent }]}>
      <Text style={s.tileTitle}>{title}</Text>
      <Text style={s.tileBody}>{body}</Text>
    </Pressable>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 20, paddingBottom: 48 },
  hero: { paddingVertical: 26 },
  eyebrow: {
    color: t.accent, fontSize: 11, fontWeight: '700', letterSpacing: 1.4,
    textTransform: 'uppercase', marginBottom: 10,
  },
  wordmark: {
    color: t.text, fontSize: 40, fontWeight: '800', letterSpacing: -1,
    fontFamily: fonts.display,
  },
  thesis: { color: t.muted, fontSize: 15, lineHeight: 22, marginTop: 12, marginBottom: 14 },
  row: { flexDirection: 'row', flexWrap: 'wrap' },
  grid: { marginTop: 8 },
  tile: {
    backgroundColor: t.panel, borderWidth: 1, borderColor: t.border,
    borderTopWidth: 3, borderRadius: 10, padding: 14, marginBottom: 10,
  },
  tileTitle: { color: t.text, fontSize: 15, fontWeight: '700', fontFamily: fonts.display },
  tileBody: { color: t.muted, fontSize: 12, lineHeight: 18, marginTop: 5 },
  h2: {
    color: t.text, fontSize: 13, fontWeight: '800', letterSpacing: 0.6,
    textTransform: 'uppercase', marginTop: 20, marginBottom: 8,
    fontFamily: fonts.display,
  },
  table: {
    borderWidth: 1, borderColor: t.border, borderRadius: 10,
    backgroundColor: t.panel, overflow: 'hidden',
  },
  tr: {
    flexDirection: 'row', paddingVertical: 8, paddingHorizontal: 12,
    borderBottomWidth: 1, borderBottomColor: t.border,
  },
  td: { fontSize: 11, lineHeight: 16 },
  tdName: { color: t.text, fontWeight: '700', flex: 2.2 },
  tdLayer: { color: t.muted, flex: 2.6 },
  tdCount: { color: t.muted, flex: 1.8, textAlign: 'right' },
  links: { marginBottom: 4 },
  link: {
    borderWidth: 1, borderColor: t.border, borderRadius: 10,
    backgroundColor: t.panel, padding: 12, marginBottom: 8,
  },
  linkLabel: { color: t.accent, fontSize: 13, fontWeight: '700', fontFamily: fonts.mono },
  linkNote: { color: t.muted, fontSize: 11, lineHeight: 16, marginTop: 3 },
  honest: {
    borderLeftWidth: 3, borderLeftColor: t.bridge, paddingLeft: 12,
    marginTop: 14, marginBottom: 20,
  },
  honestTitle: { color: t.bridge, fontSize: 12, fontWeight: '800', letterSpacing: 0.6, textTransform: 'uppercase' },
  honestBody: { color: t.text, fontSize: 12, lineHeight: 19, marginTop: 6 },
  mono: { fontFamily: fonts.mono, fontSize: 11 },
  strip: {
    backgroundColor: t.panel, borderRadius: 10, borderWidth: 1,
    borderColor: t.border, padding: 12, marginBottom: 14,
  },
  stripText: { color: t.muted, fontSize: 11, fontFamily: fonts.mono, marginBottom: 4 },
  themeBtn: {
    borderWidth: 1, borderColor: t.border, borderRadius: 8,
    paddingVertical: 10, alignItems: 'center', marginBottom: 20,
  },
  themeText: { color: t.muted, fontSize: 12, fontWeight: '600' },
  footer: { color: t.muted, fontSize: 10, lineHeight: 16, textAlign: 'center' },
});
