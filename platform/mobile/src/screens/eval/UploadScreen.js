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

  const [file, setFile] = useState(null);
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

  const chartW = Math.min(width - 60, 640);

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

      {busy === 'analyse' ? <ActivityIndicator color={t.accent} /> : null}

      {summary ? (
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

      {verdict && !verdict.ok ? (
        <Panel title="Cannot certify this file" accent={t.bridge}>
          <Text style={s.body}>{verdict.detail}</Text>
        </Panel>
      ) : null}

      {verdict && verdict.ok ? (
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
});
