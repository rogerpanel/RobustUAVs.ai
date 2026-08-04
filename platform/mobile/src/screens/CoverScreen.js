import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, Pressable } from 'react-native';
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
