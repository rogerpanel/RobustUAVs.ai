import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, useWindowDimensions,
} from 'react-native';
import { papersApi } from '../../api/papers';
import { useTheme, fonts } from '../../theme';
import Chip from '../../components/Chip';
import ExportMenu from '../../components/ExportMenu';
import LineChart from '../../components/LineChart';
import { Steps, SweepControls } from './demo';
import { ScreenHeader, Panel, Unavailable, KV } from '../uav/parts';
import {
  usePaper, classify, fmt, provColor, Pills, Field, Button, DataTable, ResultsBrowser,
} from './parts';

const FIELDS = [
  ['theta_s', 'θ — detector operating point (s)'],
  ['delta_s', 'Δ — undetected delay (s)'],
  ['delta_auth_s', 'Δ_auth — authentication delay (s)'],
  ['gamma_m_s', 'γ — delay-to-position rate (m/s)'],
  ['L', 'L — local Lipschitz constant (1/s)'],
  ['T_c_s', 'T_c — certification horizon (s)'],
  ['alert_limit_m', 'm — alert limit / corridor half-width (m)'],
];

const NONE = '(none)';

const SWEEP = {
  theta_s: 'θ (s)', delta_auth_s: 'Δ_auth (s)', gamma_m_s: 'γ (m/s)',
  L: 'L (1/s)', T_c_s: 'T_c (s)', alert_limit_m: 'm (m)',
};
// A default range per input: wide enough that the verdict usually flips
// inside it, so the sweep shows where the budget runs out.
const RANGE = {
  theta_s: [0, 3], delta_auth_s: [0, 2], gamma_m_s: [0, 6],
  L: [0, 3], T_c_s: [0, 3], alert_limit_m: [1, 30],
};

/**
 * Paper I: what authenticity costs in metres.
 *
 * The calculator is the paper's budget inequality, rho = (Δ + Δ_auth)·γ·e^{L·T_c}
 * <= m, with every input prefilled from paperI/experiments/constants.py. Only
 * the fields a visitor actually types into are sent as overrides; everything
 * else is left to the server so that, for example, changing θ re-derives Δ
 * through the paper's own Lemma 1 rather than keeping a stale Δ in the form.
 * Picking a signature scheme reads its certified Δ_auth from dauth.csv and
 * switches γ to the authenticated rate γ_a, which is the swap the paper prices.
 */
export default function PaperIScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const { paper } = usePaper('I');

  const [defaults, setDefaults] = useState(null);
  const [loadState, setLoadState] = useState({});
  const [form, setForm] = useState({});
  const [dirty, setDirty] = useState({});
  const [transport, setTransport] = useState('can');
  const [scheme, setScheme] = useState(NONE);
  const [scenario, setScenario] = useState('headline');
  const [out, setOut] = useState(null);
  const [runState, setRunState] = useState({});
  const [busy, setBusy] = useState(false);
  const { width } = useWindowDimensions();

  // sweep and scheme comparison
  const [vary, setVary] = useState('theta_s');
  const [lo, setLo] = useState(String(RANGE.theta_s[0]));
  const [hi, setHi] = useState(String(RANGE.theta_s[1]));
  const [sweep, setSweep] = useState(null);
  const [sweepState, setSweepState] = useState({});
  const [sweepBusy, setSweepBusy] = useState(false);
  const [schemesOut, setSchemesOut] = useState(null);

  const runSweep = useCallback(async (opts = {}) => {
    const v = opts.vary ?? vary;
    const a = Number(opts.lo ?? lo); const b = Number(opts.hi ?? hi);
    const base = opts.base ?? out?.request ?? {};
    if (!Number.isFinite(a) || !Number.isFinite(b) || b <= a) {
      setSweepState({ error: '"to" must be a number greater than "from"' }); return;
    }
    setSweepBusy(true); setSweepState({});
    try { setSweep(await papersApi.budgetSweep({ vary: v, lo: a, hi: b, n: 41, base })); }
    catch (e) { setSweepState(classify(e)); }
    finally { setSweepBusy(false); }
  }, [vary, lo, hi, out]);

  const runSchemes = useCallback(async (base) => {
    const { scheme: _s, delta_auth_s: _d, ...rest } = base ?? {};
    try { setSchemesOut(await papersApi.budgetSchemes(rest)); }
    catch { setSchemesOut(null); }
  }, []);

  const fill = useCallback((inputs) => {
    setForm((f) => {
      const next = { ...f };
      Object.entries(inputs).forEach(([k, v]) => {
        if (v && v.value != null) next[k] = String(v.value);
      });
      return next;
    });
  }, []);

  const compute = useCallback(async (opts = {}) => {
    const d = opts.dirty ?? dirty;
    const f = opts.form ?? form;
    const sch = opts.scheme ?? scheme;
    const body = {
      gamma_scenario: opts.scenario ?? scenario,
      ...(sch !== NONE ? { scheme: sch, transport: opts.transport ?? transport } : {}),
    };
    for (const k of Object.keys(d)) {
      const v = Number(f[k]);
      if (f[k] === '' || !Number.isFinite(v)) {
        setRunState({ error: `${k} is not a number` });
        return;
      }
      body[k] = v;
    }
    setBusy(true); setRunState({});
    try {
      const r = await papersApi.budget(body);
      setOut({ request: body, result: r });
      // Keep the sweep and the scheme comparison on the inputs just computed.
      runSchemes({ ...body, transport: opts.transport ?? transport });
      if (opts.sweep !== false) runSweep({ base: body });
      // Show the values actually used, except where the visitor typed one.
      fill(Object.fromEntries(Object.entries(r.inputs).filter(([k]) => !d[k])));
    } catch (e) { setRunState(classify(e)); }
    finally { setBusy(false); }
  }, [dirty, form, scheme, scenario, transport, fill, runSweep, runSchemes]);

  useEffect(() => {
    papersApi.budgetDefaults()
      .then((d) => {
        setDefaults(d);
        const f = Object.fromEntries(
          Object.entries(d.fields).map(([k, v]) => [k, String(v.value)]));
        setForm(f);
        compute({ dirty: {}, form: f, scheme: NONE });
      })
      .catch((e) => setLoadState(classify(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const edit = (k) => (v) => {
    setForm((f) => ({ ...f, [k]: v }));
    // Typing Δ overrides θ's derivation; typing θ hands Δ back to it.
    setDirty((d) => {
      const next = { ...d, [k]: true };
      if (k === 'theta_s') delete next.delta_s;
      return next;
    });
  };

  const pickScheme = (sch) => {
    setScheme(sch);
    // A scheme supplies Δ_auth and selects γ_a; drop any typed values for both.
    const d = { ...dirty };
    delete d.delta_auth_s; delete d.gamma_m_s;
    const f = sch === NONE
      ? { ...form, delta_auth_s: String(defaults.fields.delta_auth_s.value) } : form;
    setDirty(d); setForm(f);
    compute({ dirty: d, form: f, scheme: sch });
  };

  const pickScenario = (sc) => {
    setScenario(sc);
    const d = { ...dirty }; delete d.gamma_m_s;
    setDirty(d);
    compute({ dirty: d, scenario: sc });
  };

  const pickTransport = (tr) => {
    setTransport(tr);
    // Scheme rows are per transport, so the old choice no longer applies.
    if (scheme !== NONE) pickScheme(NONE);
  };

  const reset = () => {
    const f = Object.fromEntries(
      Object.entries(defaults.fields).map(([k, v]) => [k, String(v.value)]));
    setForm(f); setDirty({}); setScheme(NONE); setScenario('headline');
    compute({ dirty: {}, form: f, scheme: NONE, scenario: 'headline' });
  };

  const title = paper?.title ?? 'Paper I - UAVAuthentication';
  const header = (
    <ScreenHeader eyebrow="Papers · Paper I - UAVAuthentication" title={title}
      lede="Price authentication in metres. Edit the budget inequality's inputs —
            each starts at the paper's own constant — or pick a signature scheme
            and transport to read its certified authentication delay, and see
            whether the certified tube still fits inside the alert limit. Below,
            browse and export every result file Paper I's harness wrote."
      grounded source={paper?.title_source ?? 'paperI/'}
      exportData={out}
      exportCsv={out ? budgetCsv(out.result) : null} />
  );

  if (loadState.error && !defaults) {
    return (
      <ScrollView style={s.screen} contentContainerStyle={s.content}>
        {header}
        <Panel title="Budget calculator"><Text style={s.err}>{loadState.error}</Text></Panel>
        <ResultsBrowser pid="I" />
      </ScrollView>
    );
  }

  const transports = defaults
    ? [...new Set(defaults.schemes.map((r) => r.transport))] : [];
  const schemes = defaults
    ? [NONE, ...defaults.schemes.filter((r) => r.transport === transport).map((r) => r.scheme)]
    : [NONE];
  const r = out?.result;
  const w = Math.min(width - 60, 720);
  const pickVary = (v) => {
    setVary(v); setLo(String(RANGE[v][0])); setHi(String(RANGE[v][1]));
    runSweep({ vary: v, lo: RANGE[v][0], hi: RANGE[v][1] });
  };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      {header}

      {loadState.unavailable ? (
        <Panel title="Budget calculator"><Unavailable message={loadState.unavailable} /></Panel>
      ) : null}

      {defaults ? (
        <Panel title="Budget calculator" subtitle={defaults.formula}>
          <Text style={s.label}>authentication: transport</Text>
          <Pills options={transports} value={transport} onChange={pickTransport} />
          <Text style={s.label}>signature scheme (Δ_auth from dauth.csv)</Text>
          <Pills options={schemes} value={scheme} onChange={pickScheme}
                 labelOf={(sc) => {
                   if (sc === NONE) return 'none — unauthenticated';
                   const row = defaults.schemes.find((x) =>
                     x.scheme === sc && x.transport === transport);
                   return `${sc} · ${fmt(row?.dauth_cert_ms)} ms`;
                 }} />
          <Text style={s.label}>γ scenario</Text>
          <Pills options={defaults.gamma_scenarios.map((g) => g.name)} value={scenario}
                 onChange={pickScenario} />
          <Text style={s.hint}>
            {defaults.gamma_scenarios.find((g) => g.name === scenario)?.note}
          </Text>

          <View style={{ marginTop: 10 }}>
            {FIELDS.map(([k, label]) => {
              const f = defaults.fields[k];
              return (
                <Field key={k} label={`${label}${dirty[k] ? ' · edited' : ''}`}
                       value={form[k] ?? ''} onChange={edit(k)}
                       hint={`paper: ${f.constant} = ${fmt(f.value)} ${f.unit}`
                             + `${f.provenance ? ` [${f.provenance}]` : ''}`
                             + `${f.note ? ` — ${f.note}` : ''}`} />
              );
            })}
          </View>
          <Button label="compute ρ" onPress={() => compute()} busy={busy} />
          <Button label="reset to the paper's constants" onPress={reset} subtle />
          {runState.error ? <Text style={s.err}>{runState.error}</Text> : null}
          {runState.unavailable ? <Unavailable message={runState.unavailable} /> : null}
        </Panel>
      ) : null}

      {r ? (
        <Panel title="Verdict" accent={r.pass ? t.ok : t.danger}>
          <View style={[s.verdict, { borderColor: r.pass ? t.ok : t.danger }]}>
            <Text style={[s.verdictText, { color: r.pass ? t.ok : t.danger }]}>
              {r.pass ? 'CERTIFIED — ρ ≤ m' : 'NOT CERTIFIED — ρ > m'}
            </Text>
          </View>
          <KV k="ρ, certified tube radius" v={`${fmt(r.rho_m)} m`} />
          <KV k="m, alert limit" v={`${fmt(r.alert_limit_m)} m`} />
          <KV k="margin m − ρ" v={`${fmt(r.margin_m)} m`} tone={r.pass ? t.ok : t.danger} />
          <KV k="amplification e^{L·T_c}" v={fmt(r.amplification)} />
          <KV k="Δ_auth budget at this Δ, γ, m" v={`${fmt(r.dauth_budget_s)} s`} />
          <Text style={s.hint}>{r.dauth_budget_note}</Text>
          {r.unauthenticated ? (
            <>
              <KV k="ρ without authentication (γ_u)" v={`${fmt(r.unauthenticated.rho_m)} m`} />
              <KV k="benefit of authenticating"
                  v={`${fmt(r.unauthenticated.benefit_m)} m`}
                  tone={Number(r.unauthenticated.benefit_m) > 0 ? t.ok : t.danger} />
              <Text style={s.hint}>{r.unauthenticated.note}</Text>
            </>
          ) : null}
        </Panel>
      ) : null}

      {r?.steps ? (
        <Panel title="How ρ was computed"
               subtitle="The budget inequality written out with the values used in this run — change any input above and press compute ρ to redo it.">
          <Steps steps={r.steps} />
        </Panel>
      ) : null}

      {r ? (
        <Panel title="Explore: sweep one input"
               subtitle="Every other input stays as computed above; each point is a full run of the budget, and the dashed line marks where the verdict flips (found by bisection on the same budget).">
          <SweepControls options={SWEEP} vary={vary} onVary={pickVary}
                         lo={lo} hi={hi} onLo={setLo} onHi={setHi}
                         onRun={() => runSweep()} busy={sweepBusy} label="run sweep" />
          {sweepState.error ? <Text style={s.err}>{sweepState.error}</Text> : null}
          {sweep ? (
            <View nativeID="paper1-sweep" style={{ marginTop: 10 }}>
              <LineChart width={w} height={w < 420 ? 200 : 240}
                xLabel={sweep.label} yLabel="ρ (m)" yMin={0}
                yMax={Math.max(1, ...sweep.points.map((p) => Number(p.alert_limit_m)),
                  ...sweep.points.map((p) => Number(p.rho_m)).filter(Number.isFinite)) * 1.08}
                series={[
                  { key: 'rho', label: 'ρ, certified tube radius', color: t.accent,
                    points: sweep.points.map((p) => ({ x: p.x, y: Number(p.rho_m) })) },
                  { key: 'm', label: 'm, alert limit', color: t.ok, dash: true,
                    points: sweep.points.map((p) => ({ x: p.x, y: Number(p.alert_limit_m) })) },
                ]}
                vlines={sweep.flips.map((f) => ({ x: f.x, label: `flips at ${fmt(f.x)}` }))} />
              {sweep.flips.length ? sweep.flips.map((f) => (
                <KV key={f.x} k={`verdict changes from ${f.from} to ${f.to} at`}
                    v={`${SWEEP[sweep.vary]} = ${fmt(f.x)}`} tone={t.accent} />
              )) : (
                <Text style={s.hint}>
                  The verdict does not change in this range
                  ({sweep.points[0]?.pass ? 'certified throughout' : 'not certified anywhere'}).
                </Text>
              )}
              {sweep.notes.map((n) => <Text key={n} style={s.hint}>{n}</Text>)}
              <View style={s.exportRow}>
                <ExportMenu title={`Paper I sweep over ${sweep.vary}`} data={sweep}
                            csv={sweep.points} sources={sweep.source} svgId="paper1-sweep" />
              </View>
            </View>
          ) : null}
        </Panel>
      ) : null}

      {schemesOut ? (
        <Panel title={`Every signature scheme on ${schemesOut.transport}`}
               subtitle="Each row is the same budget with that scheme's certified Δ_auth and the authenticated rate γ_a — tap a row to load it into the calculator.">
          <View style={s.schemeHead}>
            <Text style={[s.schemeCell, { flex: 2 }]}>scheme</Text>
            <Text style={s.schemeCell}>Δ_auth (ms)</Text>
            <Text style={s.schemeCell}>ρ (m)</Text>
            <Text style={s.schemeCell}>benefit (m)</Text>
            <Text style={s.schemeCell}>verdict</Text>
          </View>
          {schemesOut.rows.map((row) => {
            const sch = row.scheme.startsWith('none') ? NONE : row.scheme;
            const on = sch === scheme;
            return (
              <Pressable key={row.scheme} onPress={() => pickScheme(sch)}
                         style={[s.schemeRow, on && { backgroundColor: `${t.accent}1A` }]}
                         accessibilityRole="button">
                <Text style={[s.schemeCell, { flex: 2, color: t.text }]}>{row.scheme}</Text>
                <Text style={s.schemeCell}>{fmt(row.dauth_ms)}</Text>
                <Text style={s.schemeCell}>{fmt(row.rho_m)}</Text>
                <Text style={[s.schemeCell, row.benefit_m != null
                  ? { color: Number(row.benefit_m) > 0 ? t.ok : t.danger } : null]}>
                  {fmt(row.benefit_m)}</Text>
                <Text style={[s.schemeCell, { color: row.pass ? t.ok : t.danger }]}>
                  {row.pass ? 'certified' : 'fails'}</Text>
              </Pressable>
            );
          })}
          <Text style={s.hint}>{schemesOut.note}. Alert limit m = {fmt(schemesOut.alert_limit_m)} m.</Text>
        </Panel>
      ) : null}

      {r ? (
        <Panel title="Inputs used, with provenance"
               subtitle="'user' marks a value typed here; everything else is the paper's.">
          {Object.entries(r.inputs).map(([k, v]) => (
            <View key={k} style={s.inputRow}>
              <View style={{ flex: 1 }}>
                <Text style={s.inputKey}>{k}</Text>
                <Text style={s.inputSrc}>{v.source}{v.note ? ` — ${v.note}` : ''}</Text>
              </View>
              <Text style={s.inputVal}>{fmt(v.value)}</Text>
              <Chip label={v.provenance ?? '—'} color={provColor(t, v.provenance)} />
            </View>
          ))}
          <View style={s.exportRow}>
            <ExportMenu title="Paper I budget computation" data={out}
                        csv={budgetCsv(r)} sources={r.source} />
          </View>
        </Panel>
      ) : null}

      {r?.constants_provenance?.length ? (
        <Panel title="Which value each overridable constant used"
               subtitle="paperI/results/provenance_paperI.csv — a measured value never silently replaces a proxy">
          <DataTable rows={r.constants_provenance}
                     columns={['constant', 'used', 'source', 'value_used', 'detail']}
                     colWidth={130} />
        </Panel>
      ) : null}

      <ResultsBrowser pid="I" />
    </ScrollView>
  );
}

function budgetCsv(r) {
  const rows = Object.entries(r.inputs).map(([k, v]) => ({
    quantity: k, value: v.value, provenance: v.provenance, source: v.source,
  }));
  return [
    ...rows,
    { quantity: 'rho_m', value: r.rho_m, provenance: 'computed', source: r.formula },
    { quantity: 'margin_m', value: r.margin_m, provenance: 'computed', source: 'm - rho' },
    { quantity: 'pass', value: r.pass, provenance: 'computed', source: 'rho <= m' },
    { quantity: 'dauth_budget_s', value: r.dauth_budget_s, provenance: 'computed',
      source: 'm / (gamma e^{L T_c}) - Delta' },
  ];
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  label: {
    color: t.muted, fontSize: 9.5, fontWeight: '700', letterSpacing: 0.5,
    textTransform: 'uppercase', marginBottom: 4, marginTop: 6,
  },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 4 },
  err: { color: t.danger, fontSize: 11.5, marginTop: 8 },
  verdict: {
    borderWidth: 1, borderRadius: 8, paddingVertical: 9,
    alignItems: 'center', marginBottom: 10,
  },
  verdictText: { fontSize: 14, fontWeight: '800', letterSpacing: 1 },
  inputRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 5, borderBottomWidth: 1, borderBottomColor: t.border,
  },
  inputKey: { color: t.text, fontSize: 11.5, fontWeight: '700', fontFamily: fonts.mono },
  inputSrc: { color: t.muted, fontSize: 9.5, marginTop: 1, paddingRight: 8 },
  inputVal: {
    color: t.text, fontSize: 11.5, fontFamily: fonts.mono, marginRight: 8,
  },
  exportRow: { flexDirection: 'row', justifyContent: 'flex-end', marginTop: 10 },
  schemeHead: {
    flexDirection: 'row', paddingBottom: 4, borderBottomWidth: 1, borderBottomColor: t.border,
  },
  schemeRow: {
    flexDirection: 'row', paddingVertical: 6, borderBottomWidth: 1,
    borderBottomColor: t.border, borderRadius: 4,
  },
  schemeCell: { flex: 1, color: t.muted, fontSize: 10.5, fontFamily: fonts.mono },
});
