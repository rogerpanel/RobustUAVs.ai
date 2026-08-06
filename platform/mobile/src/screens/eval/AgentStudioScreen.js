import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, TextInput,
} from 'react-native';
import { api } from '../../api/client';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, Unavailable, KV, Tag } from '../uav/parts';

/**
 * Compose an experiment from its parameters and hyperparameters, submit it,
 * and watch it complete.
 *
 * robustidps.ai's "Agent Studio (Build)" builds agents; this builds runs, which
 * is the analogous act for a benchmark. It is the one page in the group that
 * writes rather than reads, and it is genuinely functional: it drives the same
 * runner registry the API exposes, so anything added to `runners.py` appears
 * here without a frontend change.
 *
 * The params/hyperparams split is kept visible on purpose. Parameters are what
 * the experiment IS -- the operating point, the corridor, the hop count.
 * Hyperparameters are how it was COMPUTED -- the Lipschitz constant, the
 * horizon. Conflating them is how a campaign ends up unable to explain why two
 * runs disagree.
 */
export default function AgentStudioScreen() {
  const { t } = useTheme();
  const s = styles(t);

  const [runners, setRunners] = useState(null);
  const [kind, setKind] = useState(null);
  const [params, setParams] = useState({});
  const [runs, setRuns] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.runners()
      .then((r) => {
        const list = r.runners ?? r ?? [];
        setRunners(list);
        if (list.length) {
          setKind(list[0].kind ?? list[0].id ?? list[0].name);
          setParams(defaultsFor(list[0]));
        }
      })
      .catch((e) => setError(e.message));
  }, []);

  const refresh = useCallback(() => {
    api.runs(6).then((r) => setRuns(r.runs ?? [])).catch(() => {});
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const submit = async () => {
    setBusy(true); setError(null);
    try {
      const coerced = Object.fromEntries(
        Object.entries(params).map(([k, v]) => {
          const n = Number(v);
          return [k, v !== '' && !Number.isNaN(n) ? n : v];
        }));
      await api.submitRun({ kind, params: coerced });
      // Runs complete in single-digit milliseconds, so one refresh after a
      // short beat is enough; polling would be noise.
      setTimeout(refresh, 400);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };

  if (error && !runners) return <Unavailable message={error} />;
  if (!runners) return <Text style={s.loading}>loading runners…</Text>;

  const active = runners.find((r) => (r.kind ?? r.id ?? r.name) === kind);

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader eyebrow="Build" title="Agent Studio"
        lede="Compose an experiment, submit it, and read the result. Everything
              in the runner registry appears here automatically."
        grounded source="platform/backend/app/runners.py" />

      <Panel title="Runner">
        <View style={s.row}>
          {runners.map((r) => {
            const k = r.kind ?? r.id ?? r.name;
            return (
              <Pressable key={k}
                onPress={() => { setKind(k); setParams(defaultsFor(r)); }}
                style={[s.pill, kind === k && s.pillOn]}>
                <Text style={[s.pillText, kind === k && { color: t.accent }]}>
                  {r.label ?? k}
                </Text>
              </Pressable>
            );
          })}
        </View>
        {active?.description ? <Text style={s.hint}>{active.description}</Text> : null}
      </Panel>

      <Panel title="Parameters" subtitle="what the experiment is">
        {Object.keys(params).length === 0 ? (
          <Text style={s.hint}>This runner takes no parameters.</Text>
        ) : (
          Object.entries(params).map(([k, v]) => (
            <View key={k} style={s.field}>
              <Text style={s.label}>{k.replace(/_/g, ' ')}</Text>
              <TextInput
                value={String(v)}
                onChangeText={(nv) => setParams((p) => ({ ...p, [k]: nv }))}
                style={s.input}
                keyboardType="numbers-and-punctuation"
              />
            </View>
          ))
        )}
        <Pressable onPress={submit} style={s.submit} disabled={busy}>
          <Text style={s.submitText}>{busy ? 'submitting…' : 'run experiment'}</Text>
        </Pressable>
        {error ? <Text style={s.err}>{error}</Text> : null}
        <Text style={s.hint}>
          Hyperparameters — the Lipschitz constant and the horizon — are set by
          the deployment rather than the form, and are recorded separately on
          every run so two runs that disagree can be told apart.
        </Text>
      </Panel>

      <Panel title="Recent runs">
        <Pressable onPress={refresh} style={s.refresh}>
          <Text style={s.refreshText}>refresh</Text>
        </Pressable>
        {runs.length === 0 ? <Text style={s.hint}>none yet</Text> : null}
        {runs.map((r) => (
          <View key={r.run_id} style={s.run}>
            <View style={s.runHead}>
              <Text style={s.runKind}>{r.label ?? r.kind}</Text>
              <Tag label={r.status}
                   color={r.status === 'done' ? t.ok
                     : r.status === 'error' ? t.danger : t.bridge} />
            </View>
            <Text style={s.runMeta}>
              {r.run_id} · {r.duration_s != null ? `${r.duration_s}s` : '—'} · {r.provenance}
            </Text>
            <Text style={s.runParams}>
              params {JSON.stringify(r.params)}
            </Text>
            <Text style={s.runParams}>
              hyper {JSON.stringify(r.hyperparams)}
            </Text>
            {r.error ? <Text style={s.err}>{r.error}</Text> : null}
          </View>
        ))}
      </Panel>
    </ScrollView>
  );
}

/** Seed the form from whatever the runner advertises, falling back to nothing
 *  rather than to invented defaults. */
function defaultsFor(runner) {
  const spec = runner?.params ?? runner?.parameters ?? runner?.defaults;
  if (!spec) return {};
  if (Array.isArray(spec)) {
    return Object.fromEntries(spec.map((p) =>
      [p.name ?? p, p.default ?? '']));
  }
  return Object.fromEntries(Object.entries(spec).map(([k, v]) =>
    [k, typeof v === 'object' ? (v.default ?? '') : v]));
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
  field: { marginBottom: 9 },
  label: {
    color: t.muted, fontSize: 9.5, fontWeight: '700', letterSpacing: 0.5,
    textTransform: 'uppercase', marginBottom: 3,
  },
  input: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingHorizontal: 10, paddingVertical: 8, color: t.text,
    backgroundColor: t.bg, fontSize: 12.5, fontFamily: fonts.mono,
  },
  submit: {
    borderWidth: 1, borderColor: t.accent, backgroundColor: `${t.accent}18`,
    borderRadius: 8, paddingVertical: 11, alignItems: 'center', marginTop: 8,
  },
  submitText: { color: t.accent, fontSize: 12.5, fontWeight: '700' },
  refresh: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingVertical: 7, paddingHorizontal: 12, alignSelf: 'flex-start', marginBottom: 8,
  },
  refreshText: { color: t.muted, fontSize: 11, fontWeight: '700' },
  run: { borderTopWidth: 1, borderTopColor: t.border, paddingTop: 8, marginTop: 8 },
  runHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  runKind: { color: t.text, fontSize: 12, fontWeight: '700', flex: 1 },
  runMeta: { color: t.muted, fontSize: 10, fontFamily: fonts.mono, marginTop: 2 },
  runParams: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, marginTop: 2, opacity: 0.85 },
  err: { color: t.danger, fontSize: 11, marginTop: 6 },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 8 },
});
