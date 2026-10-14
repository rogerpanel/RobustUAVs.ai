import React, { useEffect, useMemo, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, TextInput, Linking,
} from 'react-native';
import { papersApi } from '../../api/papers';
import { Unavailable as NotProduced } from '../../api/client';
import { useTheme, fonts } from '../../theme';
import Chip from '../../components/Chip';
import ExportMenu from '../../components/ExportMenu';
import { Panel, Unavailable } from '../uav/parts';

/**
 * Chrome shared by the three paper pages: the catalogue entry, the results
 * browser, a scrolling table, and the small form controls.
 *
 * The results browser is the same component on every page on purpose. Each
 * paper's harness writes CSVs with different shapes, and the browser does not
 * try to understand them -- it lists what is there, shows each file's
 * provenance column as chips, and exports the file unchanged. Interpretation
 * belongs to the calculators above it.
 */

/** The paper's catalogue entry: title read from its manuscript, folder, files. */
export function usePaper(pid) {
  const [paper, setPaper] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    papersApi.catalogue()
      .then((c) => setPaper(c.papers.find((p) => p.id === pid) ?? null))
      .catch((e) => setError(e.message));
  }, [pid]);
  return { paper, error };
}

/**
 * Sorts a thrown error into the two cases a page must tell apart: a 503
 * ("not produced in this deployment", a data gap) and anything else (a bad
 * input or a real failure). The first is never shown as an error.
 */
export function classify(e) {
  return e instanceof NotProduced
    ? { unavailable: e.message }
    : { error: e?.message ?? String(e) };
}

/** "1, 2.5 3;4" -> [1, 2.5, 3, 4]; null when any entry is not a number. */
export function parseList(text) {
  const parts = String(text ?? '').split(/[\s,;]+/).filter(Boolean);
  const xs = parts.map(Number);
  return xs.some((x) => !Number.isFinite(x)) ? null : xs;
}

export function fmt(v) {
  if (v == null || v === '') return '—';
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return String(v);
    return String(Number(v.toPrecision(4)));
  }
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  return String(v);
}

export const provColor = (t, p) => ({
  measured: t.ok,
  derived: t.network,
  assumption: t.bridge,
  measured_proxy: t.bridge,
  proxy: t.bridge,
  literature: t.info,
  physics_model: t.info,
  user: t.accent,
  pilot_llm: t.bridge,
  human: t.ok,
  adjudicated: t.network,
}[String(p).split(' ')[0]] ?? t.muted);

export function Pills({ options, value, onChange, labelOf }) {
  const { t } = useTheme();
  const s = styles(t);
  return (
    <View style={s.row}>
      {options.map((o) => {
        const on = o === value;
        return (
          <Pressable key={String(o)} onPress={() => onChange(o)}
                     style={[s.pill, on && s.pillOn]} accessibilityRole="button"
                     accessibilityState={{ selected: on }}>
            <Text style={[s.pillText, on && { color: t.accent }]}>
              {labelOf ? labelOf(o) : String(o)}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Field({ label, value, onChange, hint, multiline, placeholder }) {
  const { t } = useTheme();
  const s = styles(t);
  return (
    <View style={s.field}>
      <Text style={s.label}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChange}
        style={[s.input, multiline && s.inputMulti]}
        keyboardType={multiline ? 'default' : 'numbers-and-punctuation'}
        multiline={multiline}
        placeholder={placeholder}
        placeholderTextColor={t.muted}
      />
      {hint ? <Text style={s.fieldHint}>{hint}</Text> : null}
    </View>
  );
}

export function Button({ label, onPress, busy, busyLabel, subtle }) {
  const { t } = useTheme();
  const s = styles(t);
  return (
    <Pressable onPress={onPress} disabled={busy}
               style={subtle ? s.subtle : s.submit} accessibilityRole="button">
      <Text style={subtle ? s.subtleText : s.submitText}>
        {busy ? (busyLabel ?? 'computing…') : label}
      </Text>
    </Pressable>
  );
}

/** Horizontal-scrolling table: CSVs here run to twenty-odd columns. */
export function DataTable({ rows, columns, max = 40, colWidth = 92 }) {
  const { t } = useTheme();
  const s = styles(t);
  if (!rows || rows.length === 0) return <Text style={s.hint}>no rows</Text>;
  const cols = columns ?? Object.keys(rows[0]);
  const shown = rows.slice(0, max);
  return (
    <View>
      <ScrollView horizontal>
        <View>
          <View style={s.thead}>
            {cols.map((c) => (
              <Text key={c} style={[s.th, { width: colWidth }]} numberOfLines={2}>{c}</Text>
            ))}
          </View>
          {shown.map((r, i) => (
            // eslint-disable-next-line react/no-array-index-key
            <View key={i} style={s.tr}>
              {cols.map((c) => (
                <Text key={c} style={[s.td, { width: colWidth }]} numberOfLines={2}>
                  {fmt(r[c])}
                </Text>
              ))}
            </View>
          ))}
        </View>
      </ScrollView>
      {rows.length > shown.length ? (
        <Text style={s.hint}>
          showing {shown.length} of {rows.length} rows — export for the whole file
        </Text>
      ) : null}
    </View>
  );
}

/**
 * Every CSV under the paper's results/, each with its provenance chips; pick
 * one to preview it and export it as CSV or JSON.
 */
export function ResultsBrowser({ pid }) {
  const { t } = useTheme();
  const s = styles(t);
  const [index, setIndex] = useState(null);
  const [state, setState] = useState({});
  const [filter, setFilter] = useState('');
  const [name, setName] = useState(null);
  const [file, setFile] = useState(null);
  const [fileState, setFileState] = useState({});

  useEffect(() => {
    papersApi.results(pid).then(setIndex).catch((e) => setState(classify(e)));
  }, [pid]);

  useEffect(() => {
    if (!name) return;
    setFile(null); setFileState({});
    papersApi.result(pid, name).then(setFile).catch((e) => setFileState(classify(e)));
  }, [pid, name]);

  const files = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return (index?.files ?? []).filter((f) => !q || f.name.toLowerCase().includes(q));
  }, [index, filter]);

  if (state.unavailable) {
    return (
      <Panel title="Results browser">
        <Unavailable message={state.unavailable} />
      </Panel>
    );
  }
  if (state.error) {
    return <Panel title="Results browser"><Text style={s.err}>{state.error}</Text></Panel>;
  }
  if (!index) return <Panel title="Results browser"><Text style={s.hint}>loading…</Text></Panel>;

  return (
    <Panel title="Results browser"
           subtitle={`${index.n_files} CSV files under ${index.results_dir}/ — run logs and checkpoints are not listed. Pick one to preview and export it.`}>
      {index.n_files > 8 ? (
        <Field label="filter by name" value={filter} onChange={setFilter}
               placeholder="e.g. e5_marl_N24" />
      ) : null}
      {files.map((f) => {
        const on = f.name === name;
        return (
          <Pressable key={f.name} onPress={() => setName(on ? null : f.name)}
                     style={[s.fileRow, on && s.fileRowOn]} accessibilityRole="button"
                     accessibilityState={{ selected: on }}>
            <View style={s.fileHead}>
              <Text style={[s.fileName, on && { color: t.accent }]} numberOfLines={1}>
                {f.name}
              </Text>
              <Text style={s.fileMeta}>
                {f.error ? 'unreadable' : `${f.rows} × ${f.columns.length}`}
              </Text>
            </View>
            {f.provenance?.length ? (
              <View style={s.chips}>
                {f.provenance.map((p) => (
                  <Chip key={p} label={p} color={provColor(t, p)} />
                ))}
              </View>
            ) : null}
          </Pressable>
        );
      })}
      {files.length === 0 ? <Text style={s.hint}>no file matches</Text> : null}

      {name ? (
        <View style={s.preview}>
          <View style={s.previewHead}>
            <Text style={s.previewTitle} numberOfLines={1}>{name}</Text>
            {file ? (
              <ExportMenu title={`${index.folder} ${name}`} data={file}
                          csv={file.rows} sources={file.source} />
            ) : null}
          </View>
          {fileState.unavailable ? <Unavailable message={fileState.unavailable} /> : null}
          {fileState.error ? <Text style={s.err}>{fileState.error}</Text> : null}
          {!file && !fileState.unavailable && !fileState.error
            ? <Text style={s.hint}>loading…</Text> : null}
          {file ? (
            <>
              <Text style={s.source}>source: {file.source}</Text>
              <DataTable rows={file.rows} columns={file.columns} />
              <Pressable onPress={() => Linking.openURL(papersApi.resultCsvUrl(pid, name))}
                         style={s.subtle} accessibilityRole="link">
                <Text style={s.subtleText}>⤓ the committed file, byte for byte</Text>
              </Pressable>
            </>
          ) : null}
        </View>
      ) : null}
    </Panel>
  );
}

export const styles = (t) => StyleSheet.create({
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
  inputMulti: { minHeight: 64, textAlignVertical: 'top' },
  fieldHint: { color: t.muted, fontSize: 9.5, lineHeight: 14, marginTop: 3 },
  submit: {
    borderWidth: 1, borderColor: t.accent, backgroundColor: `${t.accent}18`,
    borderRadius: 8, paddingVertical: 11, alignItems: 'center', marginTop: 8,
  },
  submitText: { color: t.accent, fontSize: 12.5, fontWeight: '700' },
  subtle: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingVertical: 7, paddingHorizontal: 12, alignSelf: 'flex-start', marginTop: 8,
  },
  subtleText: { color: t.muted, fontSize: 11, fontWeight: '700' },
  thead: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: t.border, paddingBottom: 4 },
  th: {
    color: t.muted, fontSize: 9, fontWeight: '800', textTransform: 'uppercase',
    letterSpacing: 0.5, paddingRight: 6,
  },
  tr: { flexDirection: 'row', paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: t.border },
  td: { color: t.text, fontSize: 10, fontFamily: fonts.mono, paddingRight: 6 },
  fileRow: { borderTopWidth: 1, borderTopColor: t.border, paddingVertical: 7 },
  fileRowOn: { backgroundColor: `${t.accent}12` },
  fileHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  fileName: { color: t.text, fontSize: 11.5, fontFamily: fonts.mono, flex: 1, paddingRight: 8 },
  fileMeta: { color: t.muted, fontSize: 10, fontFamily: fonts.mono },
  chips: { flexDirection: 'row', flexWrap: 'wrap' },
  preview: { borderTopWidth: 2, borderTopColor: t.accent, marginTop: 10, paddingTop: 10 },
  previewHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  previewTitle: {
    color: t.text, fontSize: 13, fontWeight: '700', flex: 1, paddingRight: 8,
    fontFamily: fonts.display,
  },
  source: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, marginBottom: 6 },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 8 },
  err: { color: t.danger, fontSize: 11.5, marginTop: 8 },
});
