import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, Linking } from 'react-native';
import { api, API_BASE } from '../api/client';
import { useTheme, fonts } from '../theme';
import { CERTIFICATES, EXTERNAL_LINKS } from './nav';
import { RIGHT_RAIL_W } from './useLayout';

/**
 * Context rather than navigation: what this deployment is, what it can
 * currently prove, and where the underlying files are.
 *
 * It is deliberately the place the uncomfortable facts live. A demo interface
 * that only surfaces working features invites the question it is avoiding, so
 * the pending certificate and the empty evidence class are shown beside the
 * healthy chips rather than behind a tab nobody opens.
 */
export default function RightRail({ onDismiss, compact = false }) {
  const { t } = useTheme();
  const s = styles(t, compact);
  const [health, setHealth] = useState(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let live = true;
    api.health().then((h) => live && setHealth(h)).catch(() => live && setErr(true));
    return () => { live = false; };
  }, []);

  return (
    <View style={s.rail}>
      <ScrollView contentContainerStyle={s.body}>

        <Section t={t} label="Deployment">
          {err ? (
            <Text style={s.bad}>control plane unreachable</Text>
          ) : health ? (
            <View style={s.chips}>
              <Pill t={t} k="db" v={health.database} />
              <Pill t={t} k="cache" v={health.cache?.backend} />
              <Pill t={t} k="auth" v={health.auth?.mode}
                    tone={health.auth?.mode === 'open' ? t.bridge : t.ok} />
              <Pill t={t} k="models" v={health.models} />
              <Pill t={t} k="tools" v={health.copilot_tools} />
              {health.jobs ? (
                <Pill t={t} k="worker"
                      v={health.jobs.worker_alive ? 'alive' : 'down'}
                      tone={health.jobs.worker_alive ? t.ok : t.danger} />
              ) : null}
            </View>
          ) : (
            <Text style={s.note}>querying…</Text>
          )}
          <Text style={s.mono}>{API_BASE}</Text>
        </Section>

        <Section t={t} label="Certificates">
          {CERTIFICATES.map((c) => (
            <View key={c.name} style={s.cert}>
              <View style={s.certHead}>
                <View style={[s.dot, {
                  backgroundColor: c.tone === 'ok' ? t.ok : t.bridge,
                }]} />
                <Text style={s.certName}>{c.name}</Text>
              </View>
              <Text style={s.note}>{c.note}</Text>
            </View>
          ))}
        </Section>

        <Section t={t} label="Stated up front">
          <Text style={s.note}>
            46.5% of ingested events are real-hardware captures, but the number
            of released <Text style={s.monoInline}>measured_same_platform</Text>{' '}
            pairings is <Text style={{ color: t.bridge, fontWeight: '700' }}>zero</Text> —
            the one source observing both layers lacks machine-readable attack
            intervals. The δ calibration is still a real-flight measurement.
          </Text>
        </Section>

        <Section t={t} label="Artifact">
          {EXTERNAL_LINKS.map((l) => (
            <Pressable key={l.href} onPress={() => Linking.openURL(l.href)}
                       style={s.link} accessibilityRole="link">
              <Text style={s.linkLabel}>{l.label} →</Text>
              <Text style={s.note}>{l.note}</Text>
            </Pressable>
          ))}
        </Section>

        {compact ? (
          <Pressable onPress={onDismiss} style={s.close} accessibilityRole="button">
            <Text style={s.closeText}>Close</Text>
          </Pressable>
        ) : null}
      </ScrollView>
    </View>
  );
}

function Section({ t, label, children }) {
  const s = styles(t, false);
  return (
    <View style={s.section}>
      <Text style={s.sectionLabel}>{label}</Text>
      {children}
    </View>
  );
}

function Pill({ t, k, v, tone }) {
  const s = styles(t, false);
  return (
    <View style={[s.pill, tone ? { borderColor: tone } : null]}>
      <Text style={s.pillK}>{k}</Text>
      <Text style={[s.pillV, tone ? { color: tone } : null]}>{String(v ?? '—')}</Text>
    </View>
  );
}

const styles = (t, compact) => StyleSheet.create({
  rail: {
    width: compact ? '100%' : RIGHT_RAIL_W,
    flex: 1,
    backgroundColor: t.panel,
    borderLeftWidth: compact ? 0 : 1,
    borderLeftColor: t.border,
  },
  body: { padding: 14, paddingBottom: 40 },
  section: { marginBottom: 20 },
  sectionLabel: {
    color: t.muted, fontSize: 9, fontWeight: '800', letterSpacing: 1.1,
    textTransform: 'uppercase', marginBottom: 8,
  },
  chips: { flexDirection: 'row', flexWrap: 'wrap' },
  pill: {
    flexDirection: 'row', alignItems: 'center',
    borderWidth: 1, borderColor: t.border, borderRadius: 6,
    paddingHorizontal: 7, paddingVertical: 3, marginRight: 5, marginBottom: 5,
  },
  pillK: { color: t.muted, fontSize: 9.5, marginRight: 4 },
  pillV: { color: t.text, fontSize: 9.5, fontWeight: '700' },
  mono: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, marginTop: 6 },
  monoInline: { fontFamily: fonts.mono, fontSize: 10 },
  cert: { marginBottom: 9 },
  certHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 2 },
  dot: { width: 6, height: 6, borderRadius: 3, marginRight: 6 },
  certName: { color: t.text, fontSize: 11.5, fontWeight: '700' },
  note: { color: t.muted, fontSize: 10.5, lineHeight: 15.5 },
  bad: { color: t.danger, fontSize: 11 },
  link: {
    borderWidth: 1, borderColor: t.border, borderRadius: 8,
    padding: 9, marginBottom: 6,
  },
  linkLabel: { color: t.accent, fontSize: 11.5, fontWeight: '700' },
  close: {
    borderWidth: 1, borderColor: t.border, borderRadius: 8,
    paddingVertical: 12, alignItems: 'center', marginTop: 6,
  },
  closeText: { color: t.text, fontSize: 13, fontWeight: '700' },
});
