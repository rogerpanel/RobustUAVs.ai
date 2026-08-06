import React, { useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, TextInput,
} from 'react-native';
import { uavApi } from '../../api/uav';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, KV, Tag } from './parts';

const SAMPLE = `mission: urban_delivery_07
waypoints: 12
altitude: 60-90 m AGL
speed: 12 m/s
`;

const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

/**
 * Checks a mission plan for the preconditions the composition theorem needs.
 *
 * robustidps.ai framed the equivalent page as an LLM review. This one is
 * deliberately a deterministic rule set, and says so: every rule maps to a
 * quantity the theorem requires, so a plan that passes is one whose MCR
 * predicates are well defined -- not one certified safe. Presenting a heuristic
 * as a model would overclaim in exactly the direction reviewers probe.
 */
export default function MissionPlanScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const [text, setText] = useState(SAMPLE);
  const [out, setOut] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const review = async () => {
    setBusy(true); setError(null);
    try { setOut(await uavApi.reviewPlan(text)); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };

  const tone = {
    critical: t.danger, high: t.danger, medium: t.bridge,
    low: t.muted, info: t.network,
  };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader
        eyebrow="UAV / Aerial Defense"
        title="Mission Plan Review"
        lede="Each rule below maps to a precondition the composition theorem
              needs. A plan that passes has well-defined MCR predicates; it is
              not thereby certified safe."
        grounded
        source="deterministic rule set"
      />

      <Panel title="Plan" subtitle="Paste a plan, or edit the sample.">
        <TextInput
          value={text}
          onChangeText={setText}
          multiline
          style={s.input}
          placeholder="mission plan text"
          placeholderTextColor={t.muted}
        />
        <Pressable onPress={review} style={s.btn} disabled={busy}>
          <Text style={s.btnText}>{busy ? 'reviewing…' : 'review plan'}</Text>
        </Pressable>
        {error ? <Text style={s.err}>{error}</Text> : null}
      </Panel>

      {out ? (
        <Panel title="Verdict"
               accent={out.verdict === 'approve' ? t.ok : t.danger}>
          <View style={[s.verdict, { borderColor: out.verdict === 'approve' ? t.ok : t.danger }]}>
            <Text style={[s.verdictText, { color: out.verdict === 'approve' ? t.ok : t.danger }]}>
              {out.verdict.toUpperCase()}
            </Text>
          </View>
          <KV k="findings" v={out.n_findings} />
          <KV k="method" v={out.method} />

          {[...out.findings]
            .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])
            .map((f) => (
              <View key={f.code} style={s.finding}>
                <View style={s.findingHead}>
                  <Tag label={f.severity} color={tone[f.severity]} />
                  <Text style={s.code}>{f.code}</Text>
                </View>
                <Text style={s.msg}>{f.message}</Text>
              </View>
            ))}

          <Text style={s.hint}>{out.note}</Text>
        </Panel>
      ) : null}

      <Panel title="Why these rules and not others">
        <Text style={s.body}>
          A geofence gives the corridor margin m, without which the spatial
          predicate has no threshold. A schedule tolerance gives κ, without which
          only Spatial MCR is certifiable — and a delay attack that lands the
          aircraft safely but thirty minutes late would pass. An altitude band
          bounds the operating region over which F is L-Lipschitz, which is the
          hypothesis the Grönwall tube rests on. Each rule is a quantity the
          theorem consumes, not a style guide.
        </Text>
      </Panel>
    </ScrollView>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  input: {
    borderWidth: 1, borderColor: t.border, borderRadius: 8, padding: 10,
    color: t.text, backgroundColor: t.bg, minHeight: 120,
    fontSize: 12, fontFamily: fonts.mono, textAlignVertical: 'top',
  },
  btn: {
    borderWidth: 1, borderColor: t.accent, backgroundColor: `${t.accent}18`,
    borderRadius: 8, paddingVertical: 11, alignItems: 'center', marginTop: 10,
  },
  btnText: { color: t.accent, fontSize: 12.5, fontWeight: '700' },
  err: { color: t.danger, fontSize: 11.5, marginTop: 8 },
  verdict: {
    borderWidth: 1, borderRadius: 8, paddingVertical: 9,
    alignItems: 'center', marginBottom: 10,
  },
  verdictText: { fontSize: 14, fontWeight: '800', letterSpacing: 1 },
  finding: { borderTopWidth: 1, borderTopColor: t.border, paddingTop: 8, marginTop: 8 },
  findingHead: { flexDirection: 'row', alignItems: 'center' },
  code: { color: t.muted, fontSize: 10, fontFamily: fonts.mono },
  msg: { color: t.text, fontSize: 11.5, lineHeight: 17, marginTop: 3 },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 10 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19 },
});
