import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, useWindowDimensions } from 'react-native';
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

const REF_COLUMNS = ['fpr', 'm', 'theta_net', 'delta_adv', 's_available_m', 'floor_cp_sim'];
const CUSTOM = '(typed)';
const SWEEP = { m: 'm (m)', delta_adv: 'δ_adv (m)', net: 'net (m)' };
const RANGE = { m: [4, 20], delta_adv: [0, 9], net: [0, 6] };

/**
 * Paper IV: the attacker indistinguishable from the weather.
 *
 * The calculator is the paper's certified floor. With margin m, stealth budget
 * δ_adv and network tube net, the benign perturbations (GNSS error, benign
 * fault, wind) must fit in s = m − δ_adv − net. Their marginals are known
 * (paperIV/results/e3_marginals.npz) but their coupling is not, so the server
 * calls paperIV/experiments/depbounds.py for two bounds on Pr[sum > s] over
 * every coupling: the union bound on the empirical marginals (a point
 * estimate) and the same bound on simultaneous Clopper–Pearson tails (valid
 * with probability ≥ 1 − α). The floor is one minus each. δ_adv and net
 * presets are read from the paper's own result files.
 */
export default function PaperIVScreen() {
  const { t } = useTheme();
  const s = styles(t);
  const { paper } = usePaper('IV');

  const [defaults, setDefaults] = useState(null);
  const [loadState, setLoadState] = useState({});
  const [form, setForm] = useState({ m: '10', delta_adv: '', net: '0', alpha: '' });
  const [dadvPreset, setDadvPreset] = useState(CUSTOM);
  const [netPreset, setNetPreset] = useState(CUSTOM);
  const [out, setOut] = useState(null);
  const [runState, setRunState] = useState({});
  const [busy, setBusy] = useState(false);
  const { width } = useWindowDimensions();

  const [vary, setVary] = useState('m');
  const [lo, setLo] = useState(String(RANGE.m[0]));
  const [hi, setHi] = useState(String(RANGE.m[1]));
  const [sweep, setSweep] = useState(null);
  const [sweepState, setSweepState] = useState({});
  const [sweepBusy, setSweepBusy] = useState(false);
  const [margs, setMargs] = useState(null);

  const runSweep = useCallback(async (opts = {}) => {
    const v = opts.vary ?? vary;
    const a = Number(opts.lo ?? lo); const b = Number(opts.hi ?? hi);
    const base = opts.base ?? out?.request;
    if (!base) return;
    if (!Number.isFinite(a) || !Number.isFinite(b) || b <= a) {
      setSweepState({ error: '"to" must be a number greater than "from"' }); return;
    }
    setSweepBusy(true); setSweepState({});
    try { setSweep(await papersApi.floorSweep({ vary: v, lo: a, hi: b, n: 33, base })); }
    catch (e) { setSweepState(classify(e)); }
    finally { setSweepBusy(false); }
  }, [vary, lo, hi, out]);

  const compute = useCallback(async (f = form) => {
    const body = {};
    for (const k of ['m', 'delta_adv', 'net', 'alpha']) {
      const v = Number(f[k]);
      if (f[k] === '' || !Number.isFinite(v)) {
        setRunState({ error: `${k} is not a number` });
        return;
      }
      body[k] = v;
    }
    setBusy(true); setRunState({});
    try {
      setOut({ request: body, result: await papersApi.floor(body) });
      runSweep({ base: body });
      papersApi.marginals(body.alpha).then(setMargs).catch(() => setMargs(null));
    }
    catch (e) { setRunState(classify(e)); }
    finally { setBusy(false); }
  }, [form, runSweep]);

  useEffect(() => {
    papersApi.floorDefaults()
      .then((d) => {
        setDefaults(d);
        const pre = d.delta_adv_presets.find((p) => p.label.startsWith('R1') && Number(p.fpr) === 0.05)
          ?? d.delta_adv_presets[0];
        const net = d.net_presets.find((p) => Number(p.net_m) === 0) ?? null;
        const f = {
          m: '10',
          delta_adv: pre ? String(pre.delta_adv_m) : '0',
          net: net ? String(net.net_m) : '0',
          alpha: String(d.alpha_default),
        };
        setForm(f);
        setDadvPreset(pre ? pre.label : CUSTOM);
        setNetPreset(net ? netLabel(net) : CUSTOM);
        compute(f);
      })
      .catch((e) => setLoadState(classify(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const edit = (k) => (v) => {
    setForm((f) => ({ ...f, [k]: v }));
    if (k === 'delta_adv') setDadvPreset(CUSTOM);
    if (k === 'net') setNetPreset(CUSTOM);
  };

  const pickDadv = (label) => {
    setDadvPreset(label);
    const p = defaults.delta_adv_presets.find((x) => x.label === label);
    if (!p) return;
    const f = { ...form, delta_adv: String(p.delta_adv_m) };
    setForm(f); compute(f);
  };

  const pickNet = (label) => {
    setNetPreset(label);
    const p = defaults.net_presets.find((x) => netLabel(x) === label);
    if (!p) return;
    const f = { ...form, net: String(p.net_m) };
    setForm(f); compute(f);
  };

  const r = out?.result;
  const w = Math.min(width - 60, 720);
  const pickVary = (v) => {
    setVary(v); setLo(String(RANGE[v][0])); setHi(String(RANGE[v][1]));
    runSweep({ vary: v, lo: RANGE[v][0], hi: RANGE[v][1] });
  };
  const SRC_COLOR = { gnss: t.accent, fault: t.danger, env: t.ok };
  const title = paper?.title ?? 'Paper IV - UAVPerturbation';
  const header = (
    <ScreenHeader eyebrow="Papers · Paper IV - UAVPerturbation" title={title}
      lede="Read the certified floor of the unified perturbation budget. Set the
            margin, the stealth budget δ_adv and the network tube; what is left
            must absorb GNSS error, benign faults and wind, whose coupling is
            unknown. The floor is computed by the paper's own dependence bounds
            on its simulated marginals. Below, browse and export every result
            file Paper IV's harness wrote."
      grounded source={paper?.title_source ?? 'paperIV/'}
      exportData={out}
      exportCsv={r ? floorCsv(r) : null} />
  );

  const dadvSource = defaults?.delta_adv_presets.find((p) => p.label === dadvPreset);

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      {header}

      {loadState.unavailable ? (
        <Panel title="Floor calculator"><Unavailable message={loadState.unavailable} /></Panel>
      ) : null}
      {loadState.error ? (
        <Panel title="Floor calculator"><Text style={s.err}>{loadState.error}</Text></Panel>
      ) : null}

      {defaults ? (
        <Panel title="Floor calculator" subtitle={defaults.formula}>
          {defaults.delta_adv_presets.length ? (
            <>
              <Text style={s.label}>δ_adv — stealth budget preset</Text>
              <Pills options={[...defaults.delta_adv_presets.map((p) => p.label), CUSTOM]}
                     value={dadvPreset} onChange={pickDadv}
                     labelOf={(l) => {
                       const p = defaults.delta_adv_presets.find((x) => x.label === l);
                       return p ? `${l} · ${fmt(p.delta_adv_m)} m` : 'typed';
                     }} />
            </>
          ) : null}
          {defaults.net_presets.length ? (
            <>
              <Text style={s.label}>net — network tube preset</Text>
              <Pills options={[...defaults.net_presets.map(netLabel), CUSTOM]}
                     value={netPreset} onChange={pickNet}
                     labelOf={(l) => (l === CUSTOM ? 'typed' : l)} />
            </>
          ) : null}

          <View style={{ marginTop: 10 }}>
            <Field label="m — margin (m)" value={form.m} onChange={edit('m')}
                   hint={`0 < m ≤ ${fmt(defaults.limits.m_max)} m; the paper evaluates 5, 10 and 20 m`} />
            <Field label="δ_adv — stealth budget (m)" value={form.delta_adv}
                   onChange={edit('delta_adv')}
                   hint={dadvSource ? `from ${dadvSource.source}` : 'typed here'} />
            <Field label="net — network tube term (m)" value={form.net} onChange={edit('net')}
                   hint={netPreset !== CUSTOM ? `from ${defaults.net_presets[0].source}` : 'typed here'} />
            <Field label="α — confidence parameter of the CP band" value={form.alpha}
                   onChange={edit('alpha')}
                   hint={`depbounds.cp_tails default α = ${fmt(defaults.alpha_default)}`} />
          </View>
          <Button label="compute floor" onPress={() => compute()} busy={busy} />
          {runState.error ? <Text style={s.err}>{runState.error}</Text> : null}
          {runState.unavailable ? <Unavailable message={runState.unavailable} /> : null}
        </Panel>
      ) : null}

      {r ? (
        <Panel title="Certified floor" accent={r.s > 0 ? t.accent : t.danger}>
          <View style={[s.verdict, { borderColor: r.s > 0 ? t.accent : t.danger }]}>
            <Text style={[s.verdictText, { color: r.s > 0 ? t.accent : t.danger }]}>
              {r.s > 0 ? `FLOOR ${fmt(r.floor_cp)} at ${fmt(r.confidence)} confidence`
                       : 'NO ROOM — m − δ_adv − net ≤ 0'}
            </Text>
          </View>
          <KV k="s = m − δ_adv − net" v={`${fmt(r.s)} m`} tone={r.s > 0 ? t.ok : t.danger} />
          <KV k="union bound p_U(s), empirical marginals" v={fmt(r.union_bound)} />
          <KV k="floor 1 − p_U(s) · point estimate" v={fmt(r.floor_union)} />
          <KV k="CP union bound p̄_U(s)" v={fmt(r.pbar_union_cp)} />
          <KV k={`floor 1 − p̄_U(s) · valid w.p. ≥ ${fmt(r.confidence)}`} v={fmt(r.floor_cp)}
              tone={t.accent} />
          <View style={s.chips}>
            <Chip label={r.provenance} color={provColor(t, r.provenance)} />
            {Object.entries(r.marginals).map(([k, n]) => (
              <Chip key={k} label={`${k} n = ${n}`} color={t.muted} />
            ))}
          </View>
          <Text style={s.hint}>{r.note}</Text>
          <Text style={s.source}>source: {r.source}</Text>
          <View style={s.exportRow}>
            <ExportMenu title="Paper IV floor computation" data={out}
                        csv={floorCsv(r)} sources={r.source} />
          </View>
        </Panel>
      ) : null}

      {r && r.s > 0 && r.split_cp?.length ? (
        <Panel title="Where the floor comes from"
               subtitle={r.split_note}>
          <Steps steps={[
            { step: 'slack left for benign perturbation',
              expr: `s = m − δ_adv − net = ${fmt(r.inputs.m)} − ${fmt(r.inputs.delta_adv)} − ${fmt(r.inputs.net)}`,
              value: r.s, unit: 'm' },
            ...r.split_cp.map((x) => ({
              step: `${x.source}: share of the slack and its tail`,
              expr: `s_${x.source} = ${fmt(x.s_i_m)} m → Pr[${x.source} > s_${x.source}] = ${fmt(x.empirical_tail)} observed, ≤ ${fmt(x.cp_upper_tail)} (CP upper)`,
              value: x.cp_upper_tail, unit: '' })),
            { step: 'sum of the three upper tails (the best split)',
              expr: r.split_cp.map((x) => fmt(x.cp_upper_tail)).join(' + '),
              value: r.pbar_union_cp, unit: '' },
            { step: `floor, valid with probability ≥ ${fmt(r.confidence)}`,
              expr: `1 − ${fmt(r.pbar_union_cp)}`, value: r.floor_cp, unit: '' },
          ]} />
          <View style={s.splitBar}>
            {r.split_cp.map((x) => (
              <View key={x.source} style={{ flex: Math.max(0.0001, x.s_i_m),
                                            backgroundColor: SRC_COLOR[x.source] ?? t.muted }} />
            ))}
            {r.s - r.split_cp.reduce((a, x) => a + x.s_i_m, 0) > 1e-9 ? (
              <View style={{ flex: r.s - r.split_cp.reduce((a, x) => a + x.s_i_m, 0),
                             backgroundColor: t.border }} />
            ) : null}
          </View>
          <Text style={s.hint}>
            {r.split_cp.map((x) => `${x.source} ${fmt(x.s_i_m)} m`).join(' · ')} of s = {fmt(r.s)} m
            (the CP grid is {'0.05'} m, so the shares sum to at most s). The point-estimate bound
            splits it as {r.split_union.map((x) => `${x.source} ${fmt(x.s_i_m)} m`).join(', ')}.
          </Text>
        </Panel>
      ) : null}

      {r?.couplings ? (
        <Panel title="Does the coupling matter?"
               subtitle="The three benign sources have known marginals but an unknown coupling. The floor is what holds under every coupling; two particular couplings show how much of the gap is the unknown dependence.">
          {r.couplings.map((c) => (
            <View key={c.coupling} style={s.coupRow}>
              <View style={{ flex: 1 }}>
                <Text style={s.coupName}>{c.coupling}</Text>
                <Text style={s.coupHow}>{c.how}</Text>
              </View>
              <View style={s.coupTrack}>
                <View style={[s.coupBar, { width: `${Math.max(0, Math.min(1, c.floor)) * 100}%` }]} />
              </View>
              <Text style={s.coupVal}>{fmt(c.floor)}</Text>
            </View>
          ))}
          <Text style={s.hint}>
            Probability that the benign perturbations fit inside s, i.e. one minus Pr[gnss + fault + env &gt; s].
            Independent and comonotone are two particular couplings; the last two rows hold for any coupling at all.
          </Text>
        </Panel>
      ) : null}

      {r ? (
        <Panel title="Explore: sweep one input"
               subtitle="The other inputs stay as computed above; each point is a full run of the paper's bounds. Rings are the paper's own rows from r5_floor_sensitivity.csv at the same δ_adv and network tube.">
          <SweepControls options={SWEEP} vary={vary} onVary={pickVary}
                         lo={lo} hi={hi} onLo={setLo} onHi={setHi}
                         onRun={() => runSweep()} busy={sweepBusy} label="run sweep" />
          {sweepState.error ? <Text style={s.err}>{sweepState.error}</Text> : null}
          {sweep ? (
            <View nativeID="paper4-sweep" style={{ marginTop: 10 }}>
              <LineChart width={w} height={w < 420 ? 200 : 240}
                xLabel={sweep.label} yLabel="floor" yMin={0} yMax={1.05}
                series={[
                  { key: 'cp', label: `floor, valid w.p. ≥ ${fmt(r.confidence)}`, color: t.accent,
                    points: sweep.points.map((p) => ({ x: p.x, y: p.floor_cp })) },
                  { key: 'u', label: 'floor, point estimate', color: t.network, dash: true,
                    points: sweep.points.map((p) => ({ x: p.x, y: p.floor_union })) },
                ]}
                overlay={sweep.reference.map((p) => ({ x: p.x, y: p.floor_cp, color: t.ok }))}
                marker={sweep.points.length && Number(r.inputs[sweep.vary]) >= sweep.points[0].x
                  && Number(r.inputs[sweep.vary]) <= sweep.points[sweep.points.length - 1].x
                  ? { x: Number(r.inputs[sweep.vary]), label: 'current' } : null} />
              {sweep.reference.length ? (
                <Text style={s.hint}>
                  ○ the paper's rows: {sweep.reference.map((p) => `m = ${fmt(p.x)} → ${fmt(p.floor_cp)}`)
                    .filter((v, i, a) => a.indexOf(v) === i).join(' · ')}
                </Text>
              ) : null}
              <View style={s.exportRow}>
                <ExportMenu title={`Paper IV floor sweep over ${sweep.vary}`} data={sweep}
                            csv={sweep.points} sources={sweep.source} svgId="paper4-sweep" />
              </View>
            </View>
          ) : null}
        </Panel>
      ) : null}

      {margs ? (
        <Panel title="The three benign perturbations"
               subtitle={`Pr[X > t] for each source: solid is what the ${margs.marginals[0]?.n ?? ''} simulated samples show, dashed is the Clopper–Pearson upper tail the floor uses. Dotted lines mark each source's share of the slack in the current computation.`}>
          <View nativeID="paper4-marginals">
            <LineChart width={w} height={w < 420 ? 200 : 240}
              xLabel="t (m)" yLabel="Pr[X > t]" yMin={0} yMax={1.05}
              series={margs.marginals.flatMap((m) => [
                { key: `${m.source}e`, label: `${m.source} observed`, color: SRC_COLOR[m.source] ?? t.muted,
                  points: m.points.map((p) => ({ x: p.t, y: p.empirical })) },
                { key: `${m.source}c`, label: `${m.source} CP upper`, color: SRC_COLOR[m.source] ?? t.muted,
                  dash: true, points: m.points.map((p) => ({ x: p.t, y: p.cp_upper })) },
              ])}
              vlines={(r?.split_cp ?? []).map((x) => ({
                x: x.s_i_m, label: `s_${x.source}`, color: SRC_COLOR[x.source] }))} />
          </View>
          {margs.marginals.map((m) => (
            <KV key={m.source} k={`${m.source}: median · 99th · 99.9th percentile · max`}
                v={`${fmt(m.quantiles_m['0.5'])} · ${fmt(m.quantiles_m['0.99'])} · ${fmt(m.quantiles_m['0.999'])} · ${fmt(m.max_m)} m`} />
          ))}
          <Text style={s.source}>source: {margs.source}</Text>
        </Panel>
      ) : null}

      {defaults?.reference?.length ? (
        <Panel title="The paper's check"
               subtitle="paperIV/results/r5_floor_sensitivity.csv — floor_cp_sim was computed by the same depbounds functions; the calculator reproduces it at the same m, δ_adv and net">
          <DataTable rows={defaults.reference} columns={REF_COLUMNS} max={40} />
        </Panel>
      ) : null}

      {defaults?.marginal_summary?.length ? (
        <Panel title="The benign marginals"
               subtitle="paperIV/results/e3_marginal_summary.csv — metres; gnss, fault and env enter the bound">
          <DataTable rows={defaults.marginal_summary} />
        </Panel>
      ) : null}

      <ResultsBrowser pid="IV" />
    </ScrollView>
  );
}

function netLabel(p) {
  return `θ_net ${fmt(p.theta_net_s)} s · ${fmt(p.net_m)} m`;
}

function floorCsv(r) {
  return [
    ...Object.entries(r.inputs).map(([k, v]) => ({
      quantity: k, value: v, provenance: 'request', source: 'request',
    })),
    { quantity: 's', value: r.s, provenance: 'computed', source: 'm - delta_adv - net' },
    { quantity: 'union_bound', value: r.union_bound, provenance: r.provenance,
      source: 'depbounds.union_bound' },
    { quantity: 'floor_union', value: r.floor_union, provenance: r.provenance,
      source: '1 - union_bound' },
    { quantity: 'pbar_union_cp', value: r.pbar_union_cp, provenance: r.provenance,
      source: 'depbounds.pbar_union_cp(cp_tails(alpha))' },
    { quantity: 'floor_cp', value: r.floor_cp, provenance: r.provenance,
      source: '1 - pbar_union_cp' },
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
  source: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, marginTop: 8 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 8 },
  verdict: {
    borderWidth: 1, borderRadius: 8, paddingVertical: 9,
    alignItems: 'center', marginBottom: 10,
  },
  verdictText: { fontSize: 14, fontWeight: '800', letterSpacing: 1 },
  exportRow: { flexDirection: 'row', justifyContent: 'flex-end', marginTop: 10 },
  splitBar: {
    flexDirection: 'row', height: 14, borderRadius: 7, overflow: 'hidden', marginTop: 10,
    borderWidth: 1, borderColor: t.border,
  },
  coupRow: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 6,
    borderBottomWidth: 1, borderBottomColor: t.border,
  },
  coupName: { color: t.text, fontSize: 11.5, fontWeight: '700' },
  coupHow: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, marginTop: 1 },
  coupTrack: { width: 140, height: 8, backgroundColor: t.bg, borderRadius: 4, marginHorizontal: 8 },
  coupBar: { height: 8, backgroundColor: t.accent, borderRadius: 4 },
  coupVal: { color: t.text, fontSize: 12, fontWeight: '800', fontFamily: fonts.mono, width: 56, textAlign: 'right' },
});
