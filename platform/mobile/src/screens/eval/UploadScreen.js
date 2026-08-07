import React, { useCallback, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator,
  useWindowDimensions, Platform,
} from 'react-native';
import Svg, { Rect, Line, Text as SvgText } from 'react-native-svg';
import { API_BASE } from '../../api/client';
import { request } from '../../api/client';
import { useTheme, fonts } from '../../theme';
import { ScreenHeader, Panel, KV, Tag } from '../uav/parts';
import { recordContext } from '../../state/context';

const MAPPINGS = [
  { id: 'kinematic', label: 'Kinematic', note: '15 m/s worst case' },
  { id: 'receiver', label: 'Receiver', note: 'γ = 1.195 m/s' },
  { id: 'ekf', label: 'EKF', note: 'γ = 1.365 m/s' },
];
const CORRIDORS = [2, 5, 10, 20];
const SLOTS = 4;

/**
 * Bring your own data: upload a UAV dataset, analyse it, then fly it through
 * the certificate engine.
 *
 * The upload goes straight to the server rather than being read in the browser
 * first -- a 1 GB file read into a JS string is several GB of heap and would
 * take the tab down before the request started. `fetch` streams a File object
 * without materialising it.
 */
export default function UploadScreen() {
  const { t } = useTheme();
  const { width } = useWindowDimensions();
  const s = styles(t);

  // Two modes. Single is the fast path; multi is where cross-validation,
  // cross-attack coverage and distribution shift live, because none of those
  // questions can be asked of one capture.
  const [mode, setMode] = useState('single');
  const [file, setFile] = useState(null);
  const [slots, setSlots] = useState(Array(SLOTS).fill(null));   // {file, summary}
  const [comparison, setComparison] = useState(null);
  const [summary, setSummary] = useState(null);
  const [verdict, setVerdict] = useState(null);
  const [busy, setBusy] = useState(null);   // 'analyse' | 'fly' | null
  const [error, setError] = useState(null);
  const [mapping, setMapping] = useState('ekf');
  const [corridor, setCorridor] = useState(10);

  const pick = useCallback(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') {
      setError('File selection is available in the browser build.');
      return;
    }
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv,.tsv,.txt,text/csv';
    input.onchange = () => {
      const f = input.files && input.files[0];
      if (f) { setFile(f); setSummary(null); setVerdict(null); setError(null); }
    };
    input.click();
  }, []);

  const analyse = useCallback(async () => {
    if (!file) return;
    setBusy('analyse'); setError(null); setVerdict(null);
    try {
      const body = new FormData();
      body.append('file', file);
      // Not `request()`: that sets Content-Type: application/json, which would
      // destroy the multipart boundary. The browser must set it itself.
      const res = await fetch(`${API_BASE}/api/upload/analyse`, { method: 'POST', body });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail ?? `HTTP ${res.status}`);
      if (!json.ok) throw new Error(json.error ?? 'could not parse');
      setSummary(json);
      recordContext({
        routeKey: 'Upload',
        label: `uploaded ${json.filename}`,
        question: `I uploaded ${json.filename}: ${json.n_rows} rows, `
          + `${json.n_columns} columns, detected roles `
          + `${JSON.stringify(json.detected_roles)}. What can this benchmark `
          + `say about it, and what would I need to measure to certify it?`,
        data: { detected_roles: json.detected_roles, n_rows: json.n_rows },
      });
    } catch (e) { setError(e.message); }
    finally { setBusy(null); }
  }, [file]);

  const fly = useCallback(async () => {
    if (!summary) return;
    setBusy('fly'); setError(null);
    try {
      const json = await request('/api/upload/fly', {
        method: 'POST',
        body: JSON.stringify({ summary, corridor_m: corridor, mapping }),
      });
      setVerdict(json);
      if (json.ok && json.from_delay) {
        recordContext({
          routeKey: 'Upload',
          label: `flew at ${mapping}, m = ${corridor} m`,
          question: `My uploaded data gives θ_p95 = ${json.from_delay.theta_p95_s} s, `
            + `a tube of ${json.from_delay.tube_m} m under the ${mapping} mapping, `
            + `and it is ${json.from_delay.inside_corridor ? 'inside' : 'outside'} `
            + `a ${corridor} m corridor. How should I read that?`,
          data: json,
        });
      }
    } catch (e) { setError(e.message); }
    finally { setBusy(null); }
  }, [summary, corridor, mapping]);

  const pickSlot = useCallback((i) => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return;
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv,.tsv,.txt,text/csv';
    input.onchange = () => {
      const f = input.files && input.files[0];
      if (!f) return;
      setSlots((prev) => prev.map((v, j) => (j === i ? { file: f, summary: null } : v)));
      setComparison(null);
    };
    input.click();
  }, []);

  const analyseAll = useCallback(async () => {
    setBusy('multi'); setError(null); setComparison(null);
    try {
      const next = [...slots];
      // Sequential rather than parallel: four concurrent 1 GB uploads would
      // put the server back in the memory state that took it down before.
      for (let i = 0; i < next.length; i += 1) {
        const slot = next[i];
        if (!slot?.file || slot.summary) continue;
        const body = new FormData();
        body.append('file', slot.file);
        const res = await fetch(`${API_BASE}/api/upload/analyse`, { method: 'POST', body });
        const json = await res.json();
        if (!res.ok || !json.ok) throw new Error(json.detail ?? json.error ?? `HTTP ${res.status}`);
        next[i] = { ...slot, summary: json };
        setSlots([...next]);
      }
      const summaries = next.filter((x) => x?.summary).map((x) => x.summary);
      if (summaries.length < 2) throw new Error('Load at least two datasets to compare.');
      const cmp = await request('/api/upload/compare', {
        method: 'POST',
        body: JSON.stringify({ summaries, corridor_m: corridor, mapping }),
      });
      if (!cmp.ok) throw new Error(cmp.reason ?? 'comparison failed');
      setComparison(cmp);
      recordContext({
        routeKey: 'Upload',
        label: `compared ${cmp.n_datasets} datasets`,
        question: `I compared ${cmp.n_datasets} UAV datasets. Schema agreement `
          + `(Jaccard) is ${cmp.schema_agreement.jaccard}, leave-one-out MAE on `
          + `the delay p95 is ${cmp.cross_validation?.mae_s ?? 'n/a'} s, and `
          + `${cmp.consensus.n_inside_corridor} of ${cmp.n_datasets} certify inside `
          + `a ${cmp.corridor_m} m corridor. What does that say about whether the `
          + `interface mapping transfers across platforms?`,
        data: { schema: cmp.schema_agreement, cv: cmp.cross_validation },
      });
    } catch (e) { setError(e.message); }
    finally { setBusy(null); }
  }, [slots, corridor, mapping]);

  const chartW = Math.min(width - 60, 640);
  const loaded = slots.filter((x) => x?.file).length;

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader
        eyebrow="Analyse"
        title="Upload & Analyse"
        lede="Bring your own UAV telemetry or network capture. It is streamed,
              sampled and discarded — nothing is stored."
        grounded
        source="platform/backend/app/upload.py"
      />

      <Panel title="Mode">
        <View style={s.row}>
          {[
            { id: 'single', label: 'Single dataset', note: 'schema, statistics, one certified verdict' },
            { id: 'multi', label: 'Multiple datasets', note: 'cross-validation, cross-attack, distribution shift' },
          ].map((m) => (
            <Pressable key={m.id} onPress={() => { setMode(m.id); setError(null); }}
                       style={[s.modeBtn, mode === m.id && s.modeOn]}>
              <Text style={[s.modeLabel, mode === m.id && { color: t.accent }]}>{m.label}</Text>
              <Text style={s.modeNote}>{m.note}</Text>
            </Pressable>
          ))}
        </View>
      </Panel>

      {mode === 'multi' ? (
        <>
          <Panel title={`Datasets (${loaded} of ${SLOTS})`}
                 subtitle="Two to four captures. Different platforms, seasons or attack conditions is the interesting case.">
            {slots.map((slot, i) => (
              <View key={i} style={s.slot}>
                <Pressable onPress={() => pickSlot(i)} style={s.slotPick}>
                  <Text style={s.slotText} numberOfLines={1}>
                    {slot?.file ? `▣  ${slot.file.name}` : `⬆  dataset ${i + 1}`}
                  </Text>
                  {slot?.file ? (
                    <Text style={s.slotMeta}>
                      {(slot.file.size / 1e6).toFixed(1)} MB
                      {slot.summary ? ` · ${slot.summary.n_rows.toLocaleString()} rows` : ' · not parsed'}
                    </Text>
                  ) : null}
                </Pressable>
                {slot?.file ? (
                  <Pressable onPress={() => { setSlots((p) => p.map((v, j) => (j === i ? null : v))); setComparison(null); }}
                             style={s.slotClear}>
                    <Text style={s.slotClearText}>✕</Text>
                  </Pressable>
                ) : null}
              </View>
            ))}
            <Pressable onPress={analyseAll} disabled={loaded < 2 || busy === 'multi'}
                       style={[s.action, (loaded < 2 || busy) && s.actionOff]}>
              <Text style={s.actionText}>
                {busy === 'multi' ? 'analysing…' : `Analyse ${loaded} datasets`}
              </Text>
            </Pressable>
            {error ? <Text style={s.err}>{error}</Text> : null}
            <Text style={s.hint}>
              Files are parsed one at a time, not in parallel: four concurrent
              gigabyte uploads is exactly the memory spike that has taken this
              host down before.
            </Text>
          </Panel>

          {comparison ? <Comparison c={comparison} t={t} s={s} width={chartW} /> : null}
        </>
      ) : null}

      {mode === 'single' ? (
      <Panel title="1 · Choose a file" subtitle="CSV, TSV or delimited text, up to 1 GB">
        <Pressable onPress={pick} style={s.pick}>
          <Text style={s.pickText}>
            {file ? `▣  ${file.name}` : '⬆  choose a file'}
          </Text>
        </Pressable>
        {file ? (
          <Text style={s.hint}>{(file.size / 1e6).toFixed(1)} MB</Text>
        ) : (
          <Text style={s.hint}>
            The analyser looks for columns whose names mention delay, latency,
            residual or staleness; position or error; J/S, SNR or C/N₀; a
            timestamp; and a label. Anything else is reported as unmatched
            rather than silently dropped.
          </Text>
        )}
        <Pressable onPress={analyse} disabled={!file || busy === 'analyse'}
                   style={[s.action, (!file || busy) && s.actionOff]}>
          <Text style={s.actionText}>
            {busy === 'analyse' ? 'analysing…' : 'Analyse'}
          </Text>
        </Pressable>
        {error ? <Text style={s.err}>{error}</Text> : null}
      </Panel>
      ) : null}

      {mode === 'single' && busy === 'analyse' ? <ActivityIndicator color={t.accent} /> : null}

      {mode === 'single' && summary ? (
        <>
          <Panel title="2 · Detected schema" accent={t.ok}>
            <KV k="rows" v={summary.n_rows.toLocaleString()} />
            <KV k="columns" v={summary.n_columns} />
            <KV k="read" v={`${(summary.bytes_read / 1e6).toFixed(1)} MB`} />
            {summary.truncated ? (
              <KV k="truncated" v="yes — hit the 1 GB cap" tone={t.bridge} />
            ) : null}

            <Text style={s.sub}>Recognised</Text>
            {Object.entries(summary.detected_roles).map(([role, col]) => (
              <KV key={role} k={role.replace(/_/g, ' ')} v={col} tone={t.ok} />
            ))}
            {Object.keys(summary.detected_roles).length === 0 ? (
              <Text style={s.hint}>No columns recognised.</Text>
            ) : null}

            {summary.n_unmatched ? (
              <>
                <Text style={s.sub}>Ignored ({summary.n_unmatched})</Text>
                <View style={s.tags}>
                  {summary.unmatched_columns.map((c) => (
                    <Tag key={c} label={c} color={t.muted} />
                  ))}
                </View>
              </>
            ) : null}

            {summary.warnings.map((w) => (
              <Text key={w} style={s.warn}>⚠  {w}</Text>
            ))}
            <Text style={s.hint}>{summary.method.note}</Text>
          </Panel>

          {Object.entries(summary.histograms)
            .filter(([, h]) => h && !h.degenerate)
            .map(([name, h]) => (
              <Panel key={name} title={`Distribution · ${name}`}>
                <Histogram h={h} width={chartW} t={t} />
                <Text style={s.hint}>{h.note}</Text>
              </Panel>
            ))}

          <Panel title="3 · Fly it" subtitle="push the detected columns through the certificate engine">
            <Text style={s.sub}>θ ↦ δ mapping</Text>
            <View style={s.row}>
              {MAPPINGS.map((m) => (
                <Pressable key={m.id} onPress={() => setMapping(m.id)}
                           style={[s.pill, mapping === m.id && s.pillOn]}>
                  <Text style={[s.pillText, mapping === m.id && { color: t.accent }]}>
                    {m.label}
                  </Text>
                </Pressable>
              ))}
            </View>
            <Text style={s.sub}>Corridor margin</Text>
            <View style={s.row}>
              {CORRIDORS.map((v) => (
                <Pressable key={v} onPress={() => setCorridor(v)}
                           style={[s.pill, corridor === v && s.pillOn]}>
                  <Text style={[s.pillText, corridor === v && { color: t.accent }]}>{v} m</Text>
                </Pressable>
              ))}
            </View>
            <Pressable onPress={fly} disabled={busy === 'fly'}
                       style={[s.action, busy && s.actionOff]}>
              <Text style={s.actionText}>{busy === 'fly' ? 'flying…' : '✈  Fly'}</Text>
            </Pressable>
          </Panel>
        </>
      ) : null}

      {mode === 'single' && verdict && !verdict.ok ? (
        <Panel title="Cannot certify this file" accent={t.bridge}>
          <Text style={s.body}>{verdict.detail}</Text>
        </Panel>
      ) : null}

      {mode === 'single' && verdict && verdict.ok ? (
        <>
          {verdict.from_delay ? (
            <Panel title="4 · Certified verdict"
                   accent={verdict.from_delay.inside_corridor ? t.ok : t.danger}>
              <View style={[s.verdict, {
                borderColor: verdict.from_delay.inside_corridor ? t.ok : t.danger,
              }]}>
                <Text style={[s.verdictText, {
                  color: verdict.from_delay.inside_corridor ? t.ok : t.danger,
                }]}>
                  {verdict.from_delay.inside_corridor
                    ? 'INSIDE the corridor' : 'OUTSIDE the corridor'}
                </Text>
              </View>
              <KV k="source column" v={verdict.from_delay.column} />
              <KV k="θ (p95 of your delays)" v={`${verdict.from_delay.theta_p95_s} s`} />
              <KV k="γ" v={`${verdict.gamma_m_s} m/s (${verdict.mapping})`} />
              <KV k="δ" v={`${verdict.from_delay.delta_pos_m} m`} />
              <KV k="tube ρ = δ·e^{LT}" v={`${verdict.from_delay.tube_m} m`} />
              <KV k="corridor" v={`${verdict.corridor_m} m`} />
              <Text style={s.hint}>{verdict.from_delay.reading}</Text>
            </Panel>
          ) : null}

          {verdict.from_position_error ? (
            <Panel title="Observed position error">
              <KV k="source column" v={verdict.from_position_error.column} />
              <KV k="p95" v={`${verdict.from_position_error.p95_m} m`}
                  tone={verdict.from_position_error.within_corridor_p95 ? t.ok : t.danger} />
              <KV k="max" v={`${verdict.from_position_error.max_m} m`}
                  tone={verdict.from_position_error.within_corridor_max ? t.ok : t.danger} />
              <Text style={s.hint}>{verdict.from_position_error.reading}</Text>
            </Panel>
          ) : null}

          {verdict.consistency ? (
            <Panel title="Consistency check"
                   accent={verdict.consistency.observed_p95_within_certified_tube ? t.ok : t.bridge}>
              <KV k="observed / certified" v={verdict.consistency.ratio}
                  tone={verdict.consistency.observed_p95_within_certified_tube ? t.ok : t.bridge} />
              <Text style={s.body}>{verdict.consistency.reading}</Text>
            </Panel>
          ) : null}

          <Panel title="Before you quote this" accent={t.bridge}>
            <Text style={s.body}>{verdict.caveat}</Text>
          </Panel>
        </>
      ) : null}
    </ScrollView>
  );
}

/**
 * Cross-dataset findings.
 *
 * Ordered by what a reviewer asks first: do the files even describe the same
 * thing (schema), does the interface constant transfer (leave-one-out), which
 * attack classes are learnable across the set (coverage), and are the captures
 * from the same regime at all (shift).
 */
function Comparison({ c, t, s, width }) {
  const cv = c.cross_validation;
  const cls = c.cross_attack.classes;
  return (
    <>
      <Panel title="Verdict per dataset"
             accent={c.consensus.unanimous ? t.ok : t.bridge}>
        {c.per_dataset.map((v) => (
          <View key={v.filename} style={s.cmpRow}>
            <Text style={s.cmpName} numberOfLines={1}>{v.filename}</Text>
            {v.from_delay ? (
              <>
                <Text style={s.cmpVal}>θ₉₅ {v.from_delay.theta_p95_s} s</Text>
                <Text style={s.cmpVal}>tube {v.from_delay.tube_m} m</Text>
                <Text style={[s.cmpVerdict, {
                  color: v.from_delay.inside_corridor ? t.ok : t.danger,
                }]}>
                  {v.from_delay.inside_corridor ? 'inside' : 'outside'}
                </Text>
              </>
            ) : <Text style={s.cmpVal}>no delay column</Text>}
          </View>
        ))}
        <Text style={s.hint}>{c.consensus.reading}</Text>
      </Panel>

      <Panel title="Schema agreement"
             subtitle={`Jaccard ${c.schema_agreement.jaccard} across ${c.n_datasets} files`}>
        <KV k="roles in every file" v={c.schema_agreement.common_roles.join(', ') || 'none'}
            tone={t.ok} />
        <KV k="roles missing somewhere"
            v={c.schema_agreement.roles_missing_somewhere.join(', ') || 'none'}
            tone={c.schema_agreement.roles_missing_somewhere.length ? t.bridge : undefined} />
        <Text style={s.hint}>{c.schema_agreement.reading}</Text>
      </Panel>

      {cv?.available ? (
        <Panel title="Leave-one-out cross-validation"
               subtitle={`k = ${cv.k}, MAE ${cv.mae_s} s on the delay p95`}
               accent={cv.mae_s < 0.05 ? t.ok : t.bridge}>
          {cv.folds.map((f) => (
            <View key={f.held_out} style={s.cmpRow}>
              <Text style={s.cmpName} numberOfLines={1}>{f.held_out}</Text>
              <Text style={s.cmpVal}>obs {f.observed_p95_s}</Text>
              <Text style={s.cmpVal}>pred {f.predicted_p95_s}</Text>
              <Text style={[s.cmpVerdict, {
                color: (f.rel_error ?? 1) < 0.25 ? t.ok : t.bridge,
              }]}>
                {f.rel_error == null ? '—' : `${(f.rel_error * 100).toFixed(0)}%`}
              </Text>
            </View>
          ))}
          <Text style={s.hint}>{cv.reading}</Text>
        </Panel>
      ) : (
        <Panel title="Leave-one-out cross-validation" accent={t.bridge}>
          <Text style={s.hint}>{cv?.reason ?? 'not available for this set'}</Text>
        </Panel>
      )}

      <Panel title="Cross-attack coverage"
             subtitle="which classes each dataset carries">
        {cls.length === 0 ? (
          <Text style={s.hint}>No label column detected in any file.</Text>
        ) : (
          <>
            <View style={s.matrixHead}>
              <Text style={[s.mCell, s.mName]}>dataset</Text>
              {cls.map((k) => (
                <Text key={k} style={s.mCell} numberOfLines={1}>{k}</Text>
              ))}
            </View>
            {c.cross_attack.matrix.map((r) => (
              <View key={r.filename} style={s.matrixRow}>
                <Text style={[s.mCell, s.mName]} numberOfLines={1}>{r.filename}</Text>
                {cls.map((k) => (
                  <Text key={k} style={[s.mCell, {
                    color: r.present[k] ? t.ok : t.border, fontWeight: '800',
                  }]}>{r.present[k] ? '●' : '○'}</Text>
                ))}
              </View>
            ))}
            <View style={s.matrixRow}>
              <Text style={[s.mCell, s.mName, { color: t.muted }]}>coverage</Text>
              {cls.map((k) => (
                <Text key={k} style={[s.mCell, {
                  color: c.cross_attack.coverage[k] === c.n_datasets ? t.ok : t.bridge,
                }]}>{c.cross_attack.coverage[k]}/{c.n_datasets}</Text>
              ))}
            </View>
          </>
        )}
        <Text style={s.hint}>{c.cross_attack.reading}</Text>
        <Text style={s.hint}>{c.cross_attack.note}</Text>
      </Panel>

      <Panel title="Distribution shift">
        {c.distribution_shift.roles.length === 0 ? (
          <Text style={s.hint}>No numeric role shared by two or more files.</Text>
        ) : c.distribution_shift.roles.map((r) => (
          <View key={r.role} style={s.shiftBlock}>
            <View style={s.cmpRow}>
              <Text style={s.cmpName}>{r.role.replace(/_/g, ' ')}</Text>
              <Text style={[s.cmpVerdict, { color: r.shifted ? t.bridge : t.ok }]}>
                ×{r.spread_ratio} {r.shifted ? 'shifted' : 'consistent'}
              </Text>
            </View>
            {r.per_dataset.map((x) => (
              <Text key={x.filename} style={s.shiftLine}>
                {x.filename} · mean {x.mean} · p95 {x.p95}
              </Text>
            ))}
          </View>
        ))}
        <Text style={s.hint}>{c.distribution_shift.reading}</Text>
      </Panel>

      <Panel title="Before you quote this" accent={t.bridge}>
        <Text style={s.body}>{c.caveat}</Text>
      </Panel>
    </>
  );
}

function Histogram({ h, width, t }) {
  const height = 130;
  const pad = { l: 34, r: 8, t: 8, b: 22 };
  const iw = width - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const max = Math.max(...h.bins.map((b) => b.count), 1);
  const bw = iw / h.bins.length;
  return (
    <Svg width={width} height={height}>
      <Line x1={pad.l} y1={pad.t + ih} x2={width - pad.r} y2={pad.t + ih}
            stroke={t.border} strokeWidth={1} />
      {h.bins.map((b, i) => {
        const bh = (b.count / max) * ih;
        return (
          <Rect key={i} x={pad.l + i * bw + 0.5} y={pad.t + ih - bh}
                width={Math.max(1, bw - 1)} height={bh} fill={t.accent} opacity={0.75} />
        );
      })}
      <SvgText x={pad.l} y={height - 6} fill={t.muted} fontSize="9">
        {h.bins[0].x.toPrecision(3)}
      </SvgText>
      <SvgText x={width - pad.r} y={height - 6} fill={t.muted} fontSize="9"
               textAnchor="end">
        {h.bins[h.bins.length - 1].x.toPrecision(3)}
      </SvgText>
      <SvgText x={pad.l - 5} y={pad.t + 8} fill={t.muted} fontSize="9"
               textAnchor="end">{max}</SvgText>
    </Svg>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  pick: {
    borderWidth: 1, borderColor: t.border, borderStyle: 'dashed',
    borderRadius: 9, paddingVertical: 20, alignItems: 'center',
  },
  pickText: { color: t.text, fontSize: 13, fontWeight: '700' },
  action: {
    borderWidth: 1, borderColor: t.accent, backgroundColor: `${t.accent}18`,
    borderRadius: 8, paddingVertical: 12, alignItems: 'center', marginTop: 10,
  },
  actionOff: { opacity: 0.45 },
  actionText: { color: t.accent, fontSize: 13, fontWeight: '800' },
  row: { flexDirection: 'row', flexWrap: 'wrap' },
  pill: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingHorizontal: 11, paddingVertical: 7, marginRight: 6, marginBottom: 6,
  },
  pillOn: { borderColor: t.accent, backgroundColor: `${t.accent}22` },
  pillText: { color: t.muted, fontSize: 11.5, fontWeight: '600' },
  sub: {
    color: t.muted, fontSize: 9.5, fontWeight: '800', letterSpacing: 1,
    textTransform: 'uppercase', marginTop: 12, marginBottom: 6,
  },
  tags: { flexDirection: 'row', flexWrap: 'wrap' },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 8 },
  warn: { color: t.bridge, fontSize: 11, lineHeight: 16.5, marginTop: 8 },
  err: { color: t.danger, fontSize: 11.5, marginTop: 8 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19 },
  verdict: {
    borderWidth: 1, borderRadius: 8, paddingVertical: 10,
    alignItems: 'center', marginBottom: 10,
  },
  verdictText: { fontSize: 13, fontWeight: '800', letterSpacing: 0.5 },
  modeBtn: {
    borderWidth: 1, borderColor: t.border, borderRadius: 9, padding: 11,
    marginRight: 8, marginBottom: 8, flexGrow: 1, flexBasis: '44%',
  },
  modeOn: { borderColor: t.accent, backgroundColor: `${t.accent}14` },
  modeLabel: { color: t.text, fontSize: 12.5, fontWeight: '700' },
  modeNote: { color: t.muted, fontSize: 10, marginTop: 2 },
  slot: { flexDirection: 'row', alignItems: 'center', marginBottom: 7 },
  slotPick: {
    flex: 1, borderWidth: 1, borderColor: t.border, borderStyle: 'dashed',
    borderRadius: 8, paddingVertical: 11, paddingHorizontal: 11,
  },
  slotText: { color: t.text, fontSize: 12, fontWeight: '600' },
  slotMeta: { color: t.muted, fontSize: 9.5, marginTop: 2 },
  slotClear: { width: 34, height: 34, alignItems: 'center', justifyContent: 'center' },
  slotClearText: { color: t.muted, fontSize: 13 },
  cmpRow: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 5,
    borderBottomWidth: 1, borderBottomColor: t.border,
  },
  cmpName: { color: t.text, fontSize: 11, fontFamily: fonts.mono, flex: 1.6 },
  cmpVal: { color: t.muted, fontSize: 10.5, flex: 1, textAlign: 'right' },
  cmpVerdict: { fontSize: 10.5, fontWeight: '800', flex: 0.9, textAlign: 'right' },
  matrixHead: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: t.border, paddingBottom: 4 },
  matrixRow: { flexDirection: 'row', paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: t.border },
  mCell: { flex: 1, fontSize: 9.5, color: t.muted, textAlign: 'center' },
  mName: { flex: 2, textAlign: 'left', fontFamily: fonts.mono, color: t.text },
  shiftBlock: { marginBottom: 8 },
  shiftLine: { color: t.muted, fontSize: 10, fontFamily: fonts.mono, marginTop: 2 },
});
