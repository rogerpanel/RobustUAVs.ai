import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, TextInput, ActivityIndicator,
} from 'react-native';
import { api } from '../api/client';
import { useTheme, runStatusStyle, fonts } from '../theme';
import Card from '../components/Card';
import Chip from '../components/Chip';

/**
 * The conference demo surface.
 *
 * Parameters and hyperparameters are rendered as two SEPARATE panels because
 * they answer different questions in front of an audience:
 *
 *   parameters       what the experiment IS      — changing one is a finding
 *   hyperparameters  how it was COMPUTED        — changing one and getting the
 *                                                 same answer is robustness
 *
 * Collapsing them into one form would make that distinction invisible, which
 * is exactly the thing a sceptical reviewer is listening for.
 */
export default function RunsScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const [runners, setRunners] = useState([]);
  const [kind, setKind] = useState(null);
  const [params, setParams] = useState({});
  const [hyper, setHyper] = useState({});
  const [run, setRun] = useState(null);
  const [history, setHistory] = useState([]);
  const [err, setErr] = useState(null);
  const poll = useRef(null);

  useEffect(() => {
    api.runners().then((d) => {
      setRunners(d.runners);
      if (d.runners.length) selectRunner(d.runners[0]);
    }).catch((e) => setErr(e.message));
    refreshHistory();
    return () => clearInterval(poll.current);
  }, []);

  const refreshHistory = () =>
    api.runs(12).then((d) => setHistory(d.runs)).catch(() => {});

  const selectRunner = (r) => {
    setKind(r.kind);
    setParams(Object.fromEntries(Object.entries(r.params).map(([k, v]) => [k, v.default])));
    setHyper(Object.fromEntries(Object.entries(r.hyperparams).map(([k, v]) => [k, v.default])));
    setRun(null);
  };

  const active = runners.find((r) => r.kind === kind);

  const submit = useCallback(async () => {
    setErr(null);
    try {
      const started = await api.submitRun({ kind, params, hyperparams: hyper });
      setRun(started);
      clearInterval(poll.current);
      poll.current = setInterval(async () => {
        try {
          const cur = await api.run(started.run_id);
          setRun(cur);
          if (['done', 'failed', 'cancelled'].includes(cur.status)) {
            clearInterval(poll.current);
            refreshHistory();
          }
        } catch (e) { clearInterval(poll.current); setErr(e.message); }
      }, 700);
    } catch (e) { setErr(e.message); }
  }, [kind, params, hyper]);

  const cancel = async () => {
    if (run) { try { await api.cancelRun(run.run_id); } catch { /* terminal already */ } }
  };

  const status = runStatusStyle(t)[run?.status] ?? {};

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <Text style={s.h1}>Experiment runner</Text>
      <Text style={s.lede}>
        Runs execute on the server against the real certificate engine. Nothing
        below is a stored number replayed.
      </Text>

      <Card title="Experiment">
        <View style={s.row}>
          {runners.map((r) => (
            <Pressable key={r.kind} onPress={() => selectRunner(r)}
              style={[s.pill, kind === r.kind && s.pillOn]}>
              <Text style={[s.pillText, kind === r.kind && s.pillTextOn]}>{r.title}</Text>
            </Pressable>
          ))}
        </View>
        {active ? <Text style={s.hint}>{active.description}</Text> : null}
      </Card>

      {active ? (
        <>
          <Panel title="Parameters" accent={t.network}
                 note="What the experiment is. Changing one of these changes the finding."
                 spec={active.params} values={params} onChange={setParams} t={t} />
          <Panel title="Hyperparameters" accent={t.info}
                 note="How it is computed. Changing one of these and getting the same answer is a robustness claim."
                 spec={active.hyperparams} values={hyper} onChange={setHyper} t={t} />
        </>
      ) : null}

      <View style={s.actions}>
        <Pressable onPress={submit} style={[s.btn, { backgroundColor: t.accent }]}>
          <Text style={s.btnText}>Run</Text>
        </Pressable>
        {run && ['queued', 'running'].includes(run.status) ? (
          <Pressable onPress={cancel} style={[s.btn, s.btnGhost]}>
            <Text style={[s.btnText, { color: t.danger }]}>Cancel</Text>
          </Pressable>
        ) : null}
      </View>

      {err ? <Card title="Error"><Text style={{ color: t.danger }}>{err}</Text></Card> : null}

      {run ? (
        <Card title={`Run ${run.run_id}`} source={`provenance: ${run.provenance}`}>
          <View style={s.row}>
            <Chip label={status.label ?? run.status} color={status.color ?? t.muted} />
            {run.duration_s != null ? <Chip label={`${run.duration_s}s`} color={t.muted} /> : null}
          </View>
          {['queued', 'running'].includes(run.status) ? (
            <>
              <View style={s.track}>
                <View style={[s.fill, { width: `${run.progress || 0}%`, backgroundColor: t.accentBlue }]} />
              </View>
              <Text style={s.hint}>{run.message || 'waiting for a worker…'}</Text>
              <ActivityIndicator color={t.accent} style={{ marginTop: 8 }} />
            </>
          ) : null}
          {run.error ? <Text style={{ color: t.danger, fontSize: 11 }}>{run.error}</Text> : null}
          {run.result ? <Result result={run.result} t={t} /> : null}
        </Card>
      ) : null}

      {history.length ? (
        <Card title="Recent runs" subtitle="Persisted, so a demo survives a restart.">
          {history.map((h) => {
            const st = runStatusStyle(t)[h.status] ?? {};
            return (
              <View key={h.run_id} style={s.hist}>
                <Text style={s.histLabel} numberOfLines={1}>{h.label}</Text>
                <Chip label={st.label ?? h.status} color={st.color ?? t.muted} />
              </View>
            );
          })}
        </Card>
      ) : null}
    </ScrollView>
  );
}

function Panel({ title, note, spec, values, onChange, accent, t }) {
  const s = styles(t);
  return (
    <Card title={title} subtitle={note}>
      <View style={[s.accentBar, { backgroundColor: accent }]} />
      {Object.entries(spec).map(([key, def]) => (
        <View key={key} style={s.field}>
          <Text style={s.label}>
            {def.label}{def.unit ? ` (${def.unit})` : ''}
          </Text>
          {def.type === 'choice' ? (
            <View style={s.row}>
              {def.options.map((o) => (
                <Pressable key={o} onPress={() => onChange({ ...values, [key]: o })}
                  style={[s.mini, values[key] === o && s.miniOn]}>
                  <Text style={[s.miniText, values[key] === o && s.miniTextOn]}>{o}</Text>
                </Pressable>
              ))}
            </View>
          ) : (
            <TextInput
              style={s.input}
              value={String(values[key] ?? '')}
              keyboardType={def.type === 'number' ? 'numeric' : 'default'}
              onChangeText={(v) =>
                onChange({ ...values, [key]: def.type === 'number' ? (v === '' ? '' : Number(v)) : v })}
            />
          )}
        </View>
      ))}
    </Card>
  );
}

function Result({ result, t }) {
  const s = styles(t);
  const rows = result.rows || [];
  const cols = rows.length ? Object.keys(rows[0]) : [];
  return (
    <View style={{ marginTop: 10 }}>
      {result.note ? <Text style={s.note}>{result.note}</Text> : null}
      {result.certified_window_s ? (
        <Text style={s.headline}>
          certified window: [{result.certified_window_s[0]}, {result.certified_window_s[1]}] s
        </Text>
      ) : null}
      {result.mappings_disagree ? (
        <Text style={[s.headline, { color: t.bridge }]}>mappings disagree at this θ</Text>
      ) : null}
      {rows.length ? (
        <ScrollView horizontal style={s.tableWrap}>
          <View>
            <View style={s.tr}>
              {cols.map((c) => <Text key={c} style={[s.th, s.cell]}>{c}</Text>)}
            </View>
            {rows.slice(0, 40).map((r, i) => (
              <View key={i} style={s.tr}>
                {cols.map((c) => (
                  <Text key={c} style={[s.td, s.cell,
                    typeof r[c] === 'boolean' && { color: r[c] ? t.ok : t.danger }]}>
                    {String(r[c])}
                  </Text>
                ))}
              </View>
            ))}
          </View>
        </ScrollView>
      ) : null}
      {rows.length > 40 ? <Text style={s.hint}>showing first 40 of {rows.length} rows</Text> : null}
    </View>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  h1: { color: t.text, fontSize: 24, fontWeight: '800', fontFamily: fonts.display },
  lede: { color: t.muted, fontSize: 13, lineHeight: 19, marginTop: 4, marginBottom: 16 },
  row: { flexDirection: 'row', flexWrap: 'wrap' },
  pill: { borderWidth: 1, borderColor: t.border, borderRadius: 8, paddingHorizontal: 11, paddingVertical: 7, marginRight: 8, marginBottom: 8 },
  pillOn: { borderColor: t.accent, backgroundColor: `${t.accent}22` },
  pillText: { color: t.muted, fontSize: 12, fontWeight: '600' },
  pillTextOn: { color: t.accent },
  hint: { color: t.muted, fontSize: 11, lineHeight: 16, marginTop: 4 },
  accentBar: { height: 3, borderRadius: 2, marginBottom: 10, width: 48 },
  field: { marginBottom: 12 },
  label: { color: t.muted, fontSize: 11, marginBottom: 4 },
  input: {
    backgroundColor: t.bg, borderWidth: 1, borderColor: t.border, borderRadius: 6,
    paddingHorizontal: 10, paddingVertical: 7, color: t.text, fontSize: 13,
    fontFamily: fonts.mono,
  },
  mini: { borderWidth: 1, borderColor: t.border, borderRadius: 6, paddingHorizontal: 9, paddingVertical: 5, marginRight: 6, marginBottom: 6 },
  miniOn: { borderColor: t.accentBlue, backgroundColor: `${t.accentBlue}22` },
  miniText: { color: t.muted, fontSize: 11, fontWeight: '600' },
  miniTextOn: { color: t.accentBlue },
  actions: { flexDirection: 'row', marginBottom: 14 },
  btn: { paddingHorizontal: 22, paddingVertical: 11, borderRadius: 8, marginRight: 10 },
  btnGhost: { borderWidth: 1, borderColor: t.danger, backgroundColor: 'transparent' },
  btnText: { color: t.bg, fontWeight: '800', fontSize: 14 },
  track: { height: 6, backgroundColor: t.bg, borderRadius: 3, marginTop: 10, overflow: 'hidden' },
  fill: { height: 6, borderRadius: 3 },
  note: { color: t.muted, fontSize: 11, lineHeight: 16, marginBottom: 8, fontStyle: 'italic' },
  headline: { color: t.ok, fontSize: 13, fontWeight: '800', marginBottom: 8 },
  tableWrap: { marginTop: 6 },
  tr: { flexDirection: 'row' },
  cell: { minWidth: 96, paddingVertical: 3, paddingRight: 10, fontSize: 10, fontFamily: fonts.mono },
  th: { color: t.muted, fontWeight: '700' },
  td: { color: t.text },
  hist: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 5, borderBottomWidth: 1, borderBottomColor: t.border },
  histLabel: { color: t.text, fontSize: 12, flex: 1, marginRight: 8 },
});
