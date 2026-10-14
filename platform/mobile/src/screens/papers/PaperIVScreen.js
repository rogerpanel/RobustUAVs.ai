import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { papersApi } from '../../api/papers';
import { useTheme, fonts } from '../../theme';
import Chip from '../../components/Chip';
import ExportMenu from '../../components/ExportMenu';
import { ScreenHeader, Panel, Unavailable, KV } from '../uav/parts';
import {
  usePaper, classify, fmt, provColor, Pills, Field, Button, DataTable, ResultsBrowser,
} from './parts';

const REF_COLUMNS = ['fpr', 'm', 'theta_net', 'delta_adv', 's_available_m', 'floor_cp_sim'];
const CUSTOM = '(typed)';

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
    try { setOut({ request: body, result: await papersApi.floor(body) }); }
    catch (e) { setRunState(classify(e)); }
    finally { setBusy(false); }
  }, [form]);

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
  const title = paper?.title ?? 'Paper IV';
  const header = (
    <ScreenHeader eyebrow="Papers · Paper IV" title={title}
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
});
