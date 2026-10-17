import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, Pressable, Linking } from 'react-native';
import { papersApi } from '../../api/papers';
import { useTheme, fonts } from '../../theme';
import ExportMenu from '../../components/ExportMenu';
import { ScreenHeader, Panel, Unavailable, KV } from '../uav/parts';
import {
  usePaper, classify, fmt, Pills, Field, Button, DataTable, ResultsBrowser,
} from './parts';

const ANY = 'any';

/**
 * Paper II: the quantifier-gap SoK, as a filterable corpus.
 *
 * Each row is one coded guarantee (codebook fields: tier, component, scope,
 * modality, perturbation, lifts, assumption, evidence; the full study adds eligible
 * and class), joined to its year and venue. Filters are applied server-side to the
 * coded table the visitor picks -- the full study's adjudicated codes by default,
 * either coder's raw codes, each snowballing iteration, or the pilot -- and the
 * counts per category are recomputed on the filtered set, so the
 * page answers questions like "of the tier-A guarantees after 2020, how many
 * use a dynamics lift, and what evidence backs them?" directly.
 *
 * The field vocabularies come from CODEBOOK.md, parsed by the server, not from
 * a list typed into this file.
 */
export default function PaperIIScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const { paper } = usePaper('II');

  const [table, setTable] = useState(null);   // null: the server's default (full study)
  const [filters, setFilters] = useState({});
  const [yearMin, setYearMin] = useState('');
  const [yearMax, setYearMax] = useState('');
  const [d, setD] = useState(null);
  const [vocab, setVocab] = useState(null);
  const [state, setState] = useState({});
  const [busy, setBusy] = useState(false);

  // one paper's path through the study, and coder agreement on the selection
  const [traceId, setTraceId] = useState('');
  const [trace, setTrace] = useState(null);
  const [traceState, setTraceState] = useState({});
  const [agree, setAgree] = useState(null);
  const [agreeState, setAgreeState] = useState({});

  const follow = useCallback(async (id, tb) => {
    if (!id) return;
    setTraceId(id); setTraceState({ busy: true });
    try { setTrace(await papersApi.trace({ id, table: tb })); setTraceState({}); }
    catch (e) { setTraceState(classify(e)); }
  }, []);

  const load = useCallback(async (opts = {}) => {
    const ymin = opts.yearMin ?? yearMin;
    const ymax = opts.yearMax ?? yearMax;
    if ((ymin && !/^\d{4}$/.test(ymin)) || (ymax && !/^\d{4}$/.test(ymax))) {
      setState({ error: 'years must be four digits' });
      return;
    }
    setBusy(true); setState({});
    try {
      const r = await papersApi.corpus({
        table: opts.table ?? table, filters: opts.filters ?? filters,
        yearMin: ymin || null, yearMax: ymax || null,
      });
      setD(r);
      setTable(r.table);
      // Agreement on exactly this selection, from the two coders' tables.
      setAgreeState({ busy: true });
      papersApi.agreement({
        table: r.table, filters: opts.filters ?? filters,
        yearMin: ymin || null, yearMax: ymax || null,
      }).then((a) => { setAgree(a); setAgreeState({}); })
        .catch((e) => setAgreeState(classify(e)));
      // Follow the first matching paper unless the one shown is still in the set.
      const key = r.key ?? 'gid';
      const ids = r.rows.map((x) => String(x[key]));
      if (ids.length && (opts.table != null || !ids.includes(traceId))) {
        follow(ids.find((i) => r.rows.find((x) => String(x[key]) === i && Number(x.eligible) === 1)) ?? ids[0], r.table);
      }
      // Options for each field: the codebook's vocabulary plus anything coded
      // outside it, so an off-codebook code is visible rather than hidden.
      setVocab((v) => v ?? Object.fromEntries(r.fields.map((f) => [
        f, [...new Set([...(r.codebook?.[f] ?? []), ...Object.keys(r.counts[f] ?? {})])],
      ])));
    } catch (e) { setState(classify(e)); }
    finally { setBusy(false); }
  }, [table, filters, yearMin, yearMax, traceId, follow]);

  useEffect(() => {
    load();
    // First load only; later loads are driven by the controls.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tables differ in their fields (the full study adds eligible and class), so the
  // filters and the per-field vocabularies are rebuilt for the table picked.
  const pickTable = (tb) => {
    setTable(tb); setFilters({}); setVocab(null);
    load({ table: tb, filters: {} });
  };
  const pickFilter = (field) => (v) => {
    const next = { ...filters };
    if (v === ANY) delete next[field]; else next[field] = v;
    setFilters(next);
    load({ filters: next });
  };
  const clear = () => {
    setFilters({}); setYearMin(''); setYearMax('');
    load({ filters: {}, yearMin: '', yearMax: '' });
  };

  const title = paper?.title ?? 'Paper II - AirworthinessSoK';
  const exportRows = d?.rows ?? null;

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader eyebrow="Papers · Paper II - AirworthinessSoK" title={title}
        lede="Explore the coded corpus behind the SoK. Filter the guarantees by
              year and by any codebook field, read the counts per category for
              the filtered set, and export the rows. The PRISMA counts and the
              search-sensitivity check are shown beside them, and every result
              file Paper II's harness wrote can be browsed and exported below."
        grounded source={paper?.title_source ?? 'paperII/'}
        exportData={d ? { filters: d.filters, year_min: d.year_min, year_max: d.year_max,
                          table: d.table, counts: d.counts, rows: d.rows } : null}
        exportCsv={exportRows} />

      {paper && !paper.present ? (
        <Panel title="Where Paper II lives">
          <Text style={s.body}>{paper.note}</Text>
        </Panel>
      ) : null}

      {state.unavailable ? (
        <Panel title="Coded corpus"><Unavailable message={state.unavailable} /></Panel>
      ) : null}

      {d ? (
        <>
          {d.prisma ? (
            <Panel title="PRISMA flow" subtitle={`${d.prisma_source ?? 'paperII/corpus/prisma_counts.csv'} — an empty count is a stage not yet run, not zero`}>
              {d.prisma.map((p) => (
                <View key={p.stage}>
                  <KV k={p.stage} v={p.n == null ? 'not yet run' : fmt(p.n)}
                      tone={p.n == null ? t.bridge : undefined} />
                  {p.note ? <Text style={s.hint}>{p.note}</Text> : null}
                </View>
              ))}
            </Panel>
          ) : null}

          {d.search_sensitivity ? (
            <Panel title="Search sensitivity"
                   subtitle="how many of the pilot's guarantees the database search finds on its own">
              <DataTable rows={d.search_sensitivity} />
            </Panel>
          ) : null}

          {d.missing?.length ? (
            <Panel title="Not produced in this deployment">
              {d.missing.map((m) => <Text key={m} style={s.mono}>{m}</Text>)}
            </Panel>
          ) : null}

          <Panel title="Filters"
                 subtitle={`codebook v${d.codebook_version ?? '?'} · ${d.n_filtered} of ${d.n_total} guarantees match`}>
            <Text style={s.label}>coded table</Text>
            <Pills options={d.tables_available} value={table} onChange={pickTable}
                   labelOf={(tb) => d.table_labels?.[tb] ?? tb} />
            <View style={s.years}>
              <View style={{ flex: 1, marginRight: 8 }}>
                <Field label={`year from${d.year_range ? ` (${d.year_range[0]}…)` : ''}`}
                       value={yearMin} onChange={setYearMin} placeholder="any" />
              </View>
              <View style={{ flex: 1 }}>
                <Field label={`year to${d.year_range ? ` (…${d.year_range[1]})` : ''}`}
                       value={yearMax} onChange={setYearMax} placeholder="any" />
              </View>
            </View>
            <Button label="apply years" onPress={() => load()} busy={busy}
                    busyLabel="filtering…" subtle />
            {(vocab ? d.fields : []).map((f) => (
              <View key={f} style={{ marginTop: 8 }}>
                <Text style={s.label}>{f}{f === 'lifts' ? ' (row uses this lift)' : ''}</Text>
                <Pills options={[ANY, ...(vocab[f] ?? [])]} value={filters[f] ?? ANY}
                       onChange={pickFilter(f)} />
              </View>
            ))}
            <Button label="clear all filters" onPress={clear} subtle />
            {state.error ? <Text style={s.err}>{state.error}</Text> : null}
          </Panel>

          <Panel title="Counts per category" subtitle="on the filtered set; a row with several lifts counts once under each">
            {d.fields.map((f) => {
              const entries = Object.entries(d.counts[f] ?? {});
              const top = Math.max(1, ...entries.map(([, n]) => n));
              return (
                <View key={f} style={s.countBlock}>
                  <Text style={s.countField}>{f}</Text>
                  {entries.length === 0 ? <Text style={s.hint}>no rows</Text> : null}
                  {entries.map(([v, n]) => (
                    <View key={v} style={s.countRow}>
                      <Text style={s.countVal} numberOfLines={1}>{v}</Text>
                      <View style={s.barTrack}>
                        <View style={[s.bar, { width: `${(100 * n) / top}%` }]} />
                      </View>
                      <Text style={s.countN}>
                        {n}{d.n_filtered ? ` · ${Math.round((100 * n) / d.n_filtered)}%` : ''}
                      </Text>
                    </View>
                  ))}
                </View>
              );
            })}
            <View style={s.exportRow}>
              <ExportMenu title="Paper II corpus counts"
                          data={{ filters: d.filters, counts: d.counts }}
                          csv={Object.entries(d.counts).flatMap(([field, c]) =>
                            Object.entries(c).map(([value, n]) => ({ field, value, n })))}
                          sources={d.source} />
            </View>
          </Panel>

          <Panel title="Follow one paper through the study"
                 subtitle="Every stage this paper went through, read from the study's own files: how it was found, both screeners' decisions and reasons, whether it was drawn for coding, the full text, both coders' codes side by side, and how disagreements were adjudicated. Pick a paper from the selection or type its id.">
            <View style={s.pickList}>
              {d.rows.slice(0, 12).map((row) => {
                const id = String(row[d.key ?? 'gid']);
                const on = id === traceId;
                return (
                  <Pressable key={id} onPress={() => follow(id, d.table)}
                             style={[s.pick, on && s.pickOn]} accessibilityRole="button">
                    <Text style={[s.pickId, on && { color: t.accent }]}>{id}</Text>
                    <Text style={s.pickTitle} numberOfLines={1}>
                      {row.year ? `${row.year} · ` : ''}{row.title ?? ''}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
            <View style={s.years}>
              <View style={{ flex: 1, marginRight: 8 }}>
                <Field label="or type an id (O… or G…)" value={traceId} onChange={setTraceId} />
              </View>
            </View>
            <Button label="follow this paper" onPress={() => follow(traceId.trim(), d.table)}
                    busy={traceState.busy} busyLabel="reading the study's files…" subtle />
            {traceState.error ? <Text style={s.err}>{traceState.error}</Text> : null}
            {trace ? <Trace trace={trace} /> : null}
          </Panel>

          <Panel title="Do the two coders agree on this selection?"
                 subtitle={agree ? `${agree.study}: ${agree.coders.join(' vs ')}, recomputed for the ${agree.n_selected} papers selected above with the paper's own reliability functions` : 'recomputed for the papers selected above'}>
            {agreeState.busy && !agree ? <Text style={s.hint}>computing…</Text> : null}
            {agreeState.error ? <Text style={s.err}>{agreeState.error}</Text> : null}
            {agreeState.unavailable ? <Unavailable message={agreeState.unavailable} /> : null}
            {agree ? <Agreement a={agree} unfiltered={!Object.keys(d.filters ?? {}).length
                                                     && !d.year_min && !d.year_max}
                                onFollow={(id) => follow(id, d.table)} /> : null}
          </Panel>

          <Panel title="Matching guarantees" subtitle={d.source}>
            <DataTable rows={d.rows}
                       columns={[d.key ?? 'gid', 'year', 'venue', 'title', ...d.fields]}
                       max={60} />
            <View style={s.exportRow}>
              <ExportMenu title="Paper II filtered corpus" data={d} csv={d.rows}
                          sources={d.source} />
            </View>
          </Panel>
        </>
      ) : null}

      {!d && !state.unavailable && !state.error ? <Text style={s.loading}>loading…</Text> : null}
      {!d && state.error ? <Text style={s.err}>{state.error}</Text> : null}

      <ResultsBrowser pid="II" />
    </ScrollView>
  );
}

const OUTCOME_GOOD = /^(included|sampled|retrieved|candidate|adjudicated|C1=C2|0 field)/i;
const OUTCOME_BAD = /^(excluded|not retrieved|not coded)/i;

/** The stages as a vertical timeline. */
function Trace({ trace }) {
  const { t } = useTheme();
  const s = styles(t);
  const tone = (o) => (OUTCOME_GOOD.test(String(o)) ? t.ok
    : OUTCOME_BAD.test(String(o)) ? t.danger : t.bridge);
  return (
    <View style={{ marginTop: 12 }}>
      <Text style={s.traceTitle}>{trace.title ?? trace.id}</Text>
      <Text style={s.hint}>
        {[trace.id, trace.year, trace.venue, trace.study].filter(Boolean).join(' · ')}
      </Text>
      {trace.doi ? (
        <Text style={s.link} onPress={() => Linking.openURL(`https://doi.org/${trace.doi}`)}>
          doi:{trace.doi}
        </Text>
      ) : null}
      {trace.stages.map((st, i) => (
        <View key={`${st.stage}${i}`} style={s.stage}>
          <View style={s.rail}>
            <View style={[s.dot, { backgroundColor: tone(st.outcome) }]} />
            {i < trace.stages.length - 1 ? <View style={s.railLine} /> : null}
          </View>
          <View style={{ flex: 1, paddingBottom: 12 }}>
            <Text style={s.stageName}>
              {i + 1}. {st.stage}{'  '}
              <Text style={{ color: tone(st.outcome) }}>{st.outcome}</Text>
            </Text>
            {st.detail ? Object.entries(st.detail).filter(([, v]) => v != null && v !== '').map(([k, v]) => (
              <Text key={k} style={s.detail}><Text style={s.detailK}>{k}: </Text>{String(v)}</Text>
            )) : null}
            {st.codes ? (
              <View style={{ marginTop: 4 }}>
                <View style={s.codeRow}>
                  {['field', 'coder C1', 'coder C2', 'final'].map((h) => (
                    <Text key={h} style={[s.codeCell, s.codeHead]}>{h}</Text>))}
                </View>
                {st.codes.map((c) => (
                  <View key={c.field} style={[s.codeRow, c.agree === false && { backgroundColor: `${t.danger}1F` }]}>
                    <Text style={[s.codeCell, { color: t.text }]}>{c.field}</Text>
                    <Text style={s.codeCell}>{fmt(c.C1)}</Text>
                    <Text style={s.codeCell}>{fmt(c.C2)}</Text>
                    <Text style={[s.codeCell, { color: t.text }]}>{fmt(c.final)}</Text>
                  </View>
                ))}
                <Text style={s.hint}>rows tinted red: the two coders disagreed</Text>
              </View>
            ) : null}
            {st.adjudications?.length ? st.adjudications.map((a, j) => (
              // eslint-disable-next-line react/no-array-index-key
              <Text key={j} style={s.detail}>
                <Text style={s.detailK}>{a.field} → {a.value}: </Text>{a.rationale}
              </Text>
            )) : null}
          </View>
        </View>
      ))}
      <Text style={s.source}>source: {trace.source}</Text>
    </View>
  );
}

function Agreement({ a, unfiltered, onFollow }) {
  const { t } = useTheme();
  const s = styles(t);
  const committed = Object.fromEntries((a.committed ?? []).map((r) => [r.field, r]));
  const kTone = (k) => (k == null ? t.muted : k >= 0.8 ? t.ok : k >= 0.6 ? t.bridge : t.danger);
  return (
    <View>
      <View style={s.codeRow}>
        {['field', 'papers', 'agreement', "Cohen's κ", 'disagree',
          ...(unfiltered && a.committed ? ['κ in the paper'] : [])].map((h) => (
          <Text key={h} style={[s.codeCell, s.codeHead]}>{h}</Text>))}
      </View>
      {a.rows.map((r) => (
        <View key={r.field} style={s.codeRow}>
          <Text style={[s.codeCell, { color: t.text }]}>{r.field}</Text>
          <Text style={s.codeCell}>{r.n}</Text>
          <Text style={s.codeCell}>{r.agree == null ? '—' : `${(100 * r.agree).toFixed(1)}%`}</Text>
          <Text style={[s.codeCell, { color: kTone(r.kappa) }]}>{fmt(r.kappa)}</Text>
          <Text style={s.codeCell}>{r.disagree}</Text>
          {unfiltered && a.committed ? (
            <Text style={[s.codeCell, committed[r.field] && Number(committed[r.field].kappa) === Number(r.kappa)
              ? { color: t.ok } : null]}>
              {committed[r.field] ? `${fmt(committed[r.field].kappa)}${Number(committed[r.field].kappa) === Number(r.kappa) ? ' ✓' : ''}` : '—'}
            </Text>
          ) : null}
        </View>
      ))}
      <Text style={s.hint}>
        Eligibility is compared over every selected paper; the other fields over the
        {` ${a.n_coded_both_eligible}`} papers both coders found eligible (the paper's rule).
        {unfiltered && a.committed ? ` With no filter, ✓ marks a value identical to ${a.committed_source}.` : ''}
      </Text>
      {a.disagreements.length ? (
        <>
          <Text style={s.traceTitle}>
            Where they disagreed ({a.n_disagreements}{a.n_disagreements > a.disagreements.length ? `, first ${a.disagreements.length}` : ''}) — tap one to follow that paper
          </Text>
          {a.disagreements.slice(0, 40).map((x, i) => {
            const id = String(x.cid ?? x.gid);
            return (
              // eslint-disable-next-line react/no-array-index-key
              <Pressable key={i} onPress={() => onFollow(id)} style={s.codeRow} accessibilityRole="button">
                <Text style={[s.codeCell, { color: t.accent }]}>{id}</Text>
                <Text style={s.codeCell}>{x.field}</Text>
                <Text style={s.codeCell}>C1 {fmt(x.C1)}</Text>
                <Text style={s.codeCell}>C2 {fmt(x.C2)}</Text>
                <Text style={[s.codeCell, { color: t.text }]}>final {fmt(x.final)}</Text>
              </Pressable>
            );
          })}
        </>
      ) : null}
      <Text style={s.source}>source: {a.source}</Text>
    </View>
  );
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  loading: { color: t.muted, fontSize: 13, padding: 20 },
  label: {
    color: t.muted, fontSize: 9.5, fontWeight: '700', letterSpacing: 0.5,
    textTransform: 'uppercase', marginBottom: 4, marginTop: 6,
  },
  years: { flexDirection: 'row', marginTop: 6 },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 4 },
  err: { color: t.danger, fontSize: 11.5, marginTop: 8 },
  body: { color: t.text, fontSize: 12.5, lineHeight: 19 },
  mono: { color: t.text, fontSize: 10.5, fontFamily: fonts.mono, marginBottom: 3 },
  countBlock: { marginBottom: 10 },
  countField: {
    color: t.text, fontSize: 12, fontWeight: '700', marginBottom: 3,
    fontFamily: fonts.display,
  },
  countRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 2 },
  countVal: { color: t.text, fontSize: 10.5, fontFamily: fonts.mono, width: 96 },
  barTrack: { flex: 1, height: 8, backgroundColor: t.bg, borderRadius: 4, marginHorizontal: 8 },
  bar: { height: 8, backgroundColor: t.accent, borderRadius: 4 },
  countN: { color: t.muted, fontSize: 10, fontFamily: fonts.mono, width: 64, textAlign: 'right' },
  exportRow: { flexDirection: 'row', justifyContent: 'flex-end', marginTop: 10 },
  pickList: { marginBottom: 6 },
  pick: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 5, paddingHorizontal: 6,
    borderBottomWidth: 1, borderBottomColor: t.border, borderRadius: 4,
  },
  pickOn: { backgroundColor: `${t.accent}1A` },
  pickId: { color: t.muted, fontSize: 10.5, fontFamily: fonts.mono, width: 104 },
  pickTitle: { color: t.text, fontSize: 11, flex: 1 },
  traceTitle: {
    color: t.text, fontSize: 12.5, fontWeight: '700', fontFamily: fonts.display,
    marginTop: 10, marginBottom: 2,
  },
  link: { color: t.accent, fontSize: 10.5, fontFamily: fonts.mono, marginTop: 2 },
  stage: { flexDirection: 'row', marginTop: 8 },
  rail: { width: 18, alignItems: 'center' },
  dot: { width: 10, height: 10, borderRadius: 5, marginTop: 3 },
  railLine: { width: 2, flex: 1, backgroundColor: t.border, marginTop: 2 },
  stageName: { color: t.text, fontSize: 11.5, fontWeight: '700' },
  detail: { color: t.muted, fontSize: 10.5, lineHeight: 15, marginTop: 2 },
  detailK: { color: t.text, fontFamily: fonts.mono, fontSize: 10 },
  codeRow: {
    flexDirection: 'row', paddingVertical: 3, borderBottomWidth: 1, borderBottomColor: t.border,
  },
  codeCell: { flex: 1, color: t.muted, fontSize: 10.5, fontFamily: fonts.mono, paddingRight: 4 },
  codeHead: { color: t.muted, fontWeight: '800', fontSize: 9.5, textTransform: 'uppercase' },
  source: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, marginTop: 8 },
});
