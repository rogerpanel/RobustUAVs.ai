import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { uavApi } from '../../api/uav';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV, Tag } from './parts';

/**
 * The four certificates, from the engine rather than recomputed per visit.
 *
 * robustidps.ai's version recomputes Lipschitz and smoothing radii on a
 * 16-sample synthetic batch every time the page loads, so its pills drift and
 * do not equal the dissertation constants. Those numbers are demo artifacts and
 * CLAUDE.md says not to use them. This page reads the locked values.
 */
export default function CertificationScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    uavApi.certificates().then(setD).catch((e) => setError(e.message));
  }, []);

  if (error) return <Unavailable message={error} />;
  if (!d) return <Text style={s.loading}>loading…</Text>;

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader
        eyebrow="UAV / Aerial Defense"
        title="Certification Dashboard"
        lede="Four certificates, concurrent rather than alternative: they bound
              four different objects on the same flight."
        grounded
        source="certificates/engine.py"
      />

      <Panel title="Two floors — never conflate them" accent={t.bridge}>
        <KV k="Ch.6 §6.6 certified MCR at 20 dB" v={d.floors.certified_mcr_at_20db} />
        <KV k="DO-326A operational floor" v={d.floors.operational_mcr} />
        <Text style={s.hint}>{d.floors.note}</Text>
      </Panel>

      {d.certificates.map((c) => (
        <Panel key={c.id} title={c.name}
               accent={c.status === 'verified' ? t.ok : t.bridge}>
          <View style={s.tags}>
            <Tag label={c.status} color={c.status === 'verified' ? t.ok : t.bridge} />
            {c.primary ? <Tag label="load-bearing" color={t.accent} /> : null}
          </View>
          {Object.entries(c.values).map(([k, v]) => (
            <KV key={k} k={k.replace(/_/g, ' ')}
                v={v == null ? 'pending — not substituted' : v}
                tone={v == null ? t.bridge : undefined} />
          ))}
          <Text style={s.reading}>{c.reading}</Text>
          <Text style={s.source}>{c.source}</Text>
        </Panel>
      ))}

      <Panel title="How the four operate on a single flight">
        <Text style={s.body}>
          Hold one ten-minute delivery sortie fixed: flown by a model trained on
          last season's mission mix, through a corridor where a compromised relay
          delays peer corrections and a ground jammer varies transmit power. Four
          claims are in force at once, about four different objects.
        </Text>
        <Text style={s.body}>
          The Lipschitz–Grönwall tube bounds the trajectory. Randomized smoothing
          bounds the classifier under input perturbation. PAC-Bayes bounds
          generalisation from the training mix to this sortie. MWU bounds regret
          against the adaptive jammer. They are concurrent, not alternative — and
          the paper's weight sits on the first, which is the one both proved and
          empirically verified.
        </Text>
        <Text style={s.hint}>
          PAC-Bayes awaits a numeric KL term. It is flagged pending rather than
          filled with a plausible value, which is why the panel above shows no
          number for it.
        </Text>
      </Panel>

      <Panel title="On the Lipschitz constant">
        <Text style={s.body}>
          L was re-measured over operating-region trajectories rather than by
          random power iteration, giving 1.181 against 0.983 and tightening the
          radius from 0.187 to 0.153. We report the smaller, honest radius. One
          earlier conclusion changed with it: θ = 0.25 s is certified at m ≥ 5 m
          but not at m = 2 m, where the tube reaches 2.22 m. The 10 m headline is
          unaffected.
        </Text>
      </Panel>
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', marginBottom: 6 },
  reading: { color: t.muted, fontSize: 11, lineHeight: 16.5, marginTop: 8, fontStyle: 'italic' },
  source: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, marginTop: 6, opacity: 0.8 },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 8 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19, marginBottom: 8 },
});
