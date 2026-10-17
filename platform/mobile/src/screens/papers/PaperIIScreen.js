import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
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
      // Options for each field: the codebook's vocabulary plus anything coded
      // outside it, so an off-codebook code is visible rather than hidden.
      setVocab((v) => v ?? Object.fromEntries(r.fields.map((f) => [
        f, [...new Set([...(r.codebook?.[f] ?? []), ...Object.keys(r.counts[f] ?? {})])],
      ])));
    } catch (e) { setState(classify(e)); }
    finally { setBusy(false); }
  }, [table, filters, yearMin, yearMax]);

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
});
