import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, useWindowDimensions } from 'react-native';
import { papersApi } from '../../api/papers';
import { useTheme, fonts } from '../../theme';
import LineChart from '../../components/LineChart';
import ExportMenu from '../../components/ExportMenu';
import { ScreenHeader, Panel, Unavailable, KV } from '../uav/parts';
import {
  usePaper, classify, fmt, parseList, Pills, Field, Button, DataTable, ResultsBrowser,
} from './parts';

const MARL_COLUMNS = ['method', 'n_runs', 'r_cert_iqm', 'r_cert_lo', 'r_cert_hi',
  'viol_iqm', 'cov_ratio_iqm', 'exposure_iqm', 'switches_iqm', 'eval_viol_cp95'];
const LIFT_COLUMNS = ['dependence', 'N', 'M', 'q_le2', 'q_le10', 'q_le20',
  'p_iid_exact', 'p_sim', 'p_sim_lo', 'p_sim_hi'];

/**
 * Paper III: certificates as constraints.
 *
 * Three instruments, each calling the paper's own code on the server:
 *
 *   certificate   the nested-eligibility closed forms (count profile, Ore
 *                 deficiency, coverage margin, worst case under b collapses)
 *                 and the two projection layers, on a fleet the visitor types
 *   lift          P(full coverage) for N agents under the i.i.d. lift -- the
 *                 prediction whose independence obligation spatial jamming
 *                 breaks, which the reference rows below it show
 *   MARL          the aggregated training tables, one per run directory
 */
export default function PaperIIIScreen() {
  const { t } = useTheme();
  const { width } = useWindowDimensions();
  const s = styles(t);
  const { paper } = usePaper('III');

  const [defaults, setDefaults] = useState(null);
  const [loadState, setLoadState] = useState({});

  // certificate
  const [mode, setMode] = useState('staleness');
  const [values, setValues] = useState('0, 0.2, 0.5, 1, 2, 4');
  const [alpha, setAlpha] = useState('');
  const [b, setB] = useState('1');
  const [proposal, setProposal] = useState('');
  const [cert, setCert] = useState(null);
  const [certState, setCertState] = useState({});
  const [certBusy, setCertBusy] = useState(false);

  // lift
  const [liftN, setLiftN] = useState('');
  const [liftAlpha, setLiftAlpha] = useState('');
  const [q, setQ] = useState(['', '', '', '', '']);
  const [lift, setLift] = useState(null);
  const [liftState, setLiftState] = useState({});
  const [liftBusy, setLiftBusy] = useState(false);

  // MARL
  const [marl, setMarl] = useState(null);
  const [marlState, setMarlState] = useState({});
  const [dir, setDir] = useState(null);

  const runCertify = useCallback(async (opts = {}) => {
    const xs = parseList(opts.values ?? values);
    const al = parseList(opts.alpha ?? alpha);
    if (!xs || !xs.length) { setCertState({ error: `${mode} values must be numbers` }); return; }
    if (!al || !al.length) { setCertState({ error: 'alert limits must be numbers' }); return; }
    const body = { [mode === 'staleness' ? 'staleness_s' : 'rho']: xs, alpha: al };
    const bb = (opts.b ?? b).trim();
    if (bb) {
      if (!/^\d+$/.test(bb)) { setCertState({ error: 'b must be a whole number' }); return; }
      body.b = Number(bb);
    }
    if (proposal.trim()) {
      const p = parseList(proposal);
      if (!p || p.some((x) => !Number.isInteger(x))) {
        setCertState({ error: 'proposal must be task indices, -1 for idle' }); return;
      }
      body.proposal = p;
    }
    setCertBusy(true); setCertState({});
    try { setCert({ request: body, result: await papersApi.certify(body) }); }
    catch (e) { setCertState(classify(e)); }
    finally { setCertBusy(false); }
  }, [values, alpha, b, proposal, mode]);

  const runLift = async () => {
    const N = Number(liftN);
    const al = parseList(liftAlpha);
    const qs = q.map(Number);
    if (!Number.isInteger(N)) { setLiftState({ error: 'N must be a whole number' }); return; }
    if (!al || !al.length) { setLiftState({ error: 'alert limits must be numbers' }); return; }
    if (qs.some((x) => !Number.isFinite(x))) { setLiftState({ error: 'q must be numbers' }); return; }
    setLiftBusy(true); setLiftState({});
    try { setLift(await papersApi.lift({ N, alpha: al, q: qs })); }
    catch (e) { setLiftState(classify(e)); }
    finally { setLiftBusy(false); }
  };

  useEffect(() => {
    papersApi.certifyDefaults()
      .then((d) => {
        setDefaults(d);
        const al = d.alert_limits_m.join(', ');
        setAlpha(al); setLiftAlpha(al);
        const ref = d.lift_reference.find((r) => r.dependence === 'independent')
          ?? d.lift_reference[0];
        if (ref) {
          setLiftN(String(ref.N));
          const c2 = Number(ref.q_le2); const c10 = Number(ref.q_le10);
          const c20 = Number(ref.q_le20);
          // Only meaningful for the paper's four levels; otherwise leave q blank.
          if (d.alert_limits_m.length === 4) {
            setQ([c2, 0, c10 - c2, c20 - c10, 1 - c20]
              .map((x) => String(Number(x.toFixed(6)))));
          } else {
            setQ(Array(d.alert_limits_m.length + 1).fill(''));
          }
        }
        runCertify({ alpha: al });
      })
      .catch((e) => setLoadState(classify(e)));
    papersApi.marl()
      .then((m) => { setMarl(m); setDir(m.dirs[0] ?? null); })
      .catch((e) => setMarlState(classify(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const r = cert?.result;
  const w = Math.min(width - 60, 720);
  const agentRows = r ? r.rho.map((rho, i) => ({
    agent: i, rho_m: rho,
    greedy_task: r.greedy_assignment[i],
    greedy_alpha_m: r.greedy_assignment[i] >= 0 ? r.alpha[r.greedy_assignment[i]] : null,
    ...(r.projection ? {
      proposed_task: r.projection.proposal[i],
      projected_task: r.projection.assignment[i],
    } : {}),
  })) : null;
  const profileRows = r ? r.count_profile.map((n, k) => ({
    k: k + 1, 'alpha_(k)': r.alpha_sorted[k], n_k: n, 'k − n_k': k + 1 - n,
  })) : null;

  const title = paper?.title ?? 'Paper III - UAVCertification';
  const marlRows = marl && dir ? marl.tables[dir] : null;

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <ScreenHeader eyebrow="Papers · Paper III - UAVCertification" title={title}
        lede="Type a fleet's certified protection levels (or their navigation
              staleness) and the tasks' alert limits, and read off how many tasks
              can be covered, how many certificate collapses that survives, and
              the assignment the projection layer would make. Predict full
              coverage for a larger fleet under the independence lift, compare
              the MARL results across run directories, and browse every result
              file Paper III's harness wrote."
        grounded source={paper?.title_source ?? 'paperIII/'}
        exportData={{ certificate: cert, lift, marl_dir: dir, marl: marlRows }}
        exportCsv={agentRows} />

      {loadState.unavailable ? (
        <Panel title="Certificate calculator"><Unavailable message={loadState.unavailable} /></Panel>
      ) : null}
      {loadState.error ? <Text style={s.err}>{loadState.error}</Text> : null}

      {defaults ? (
        <Panel title="Certificate calculator"
               subtitle={`agent i may hold task j iff ρ_i ≤ α_j · ${defaults.rho_of_staleness}, κ = ${fmt(defaults.constants.KAPPA_m_per_s)} m/s, θ_benign = ${defaults.constants.THETA_BENIGN_s} s`}>
          <Text style={s.label}>agents given as</Text>
          <Pills options={['staleness', 'rho']} value={mode} onChange={setMode}
                 labelOf={(m) => (m === 'staleness' ? 'staleness Δ (s)' : 'ρ (m)')} />
          <Field label={mode === 'staleness' ? 'staleness per agent, s (comma-separated)'
                                             : 'ρ per agent, m (comma-separated)'}
                 value={values} onChange={setValues} multiline
                 hint={`one value per agent; at most ${defaults.limits.N}`} />
          <Field label="alert limits α per task, m (comma-separated)" value={alpha}
                 onChange={setAlpha} multiline
                 hint={`prefilled with the paper's ALERT_LIMITS; at most ${defaults.limits.M} tasks`} />
          <Field label="b — certificates an adversary collapses" value={b} onChange={setB}
                 hint="optional; the worst case collapses the b agents with the smallest ρ" />
          <Field label="policy proposal (optional): task index per agent, −1 = idle"
                 value={proposal} onChange={setProposal}
                 hint="when given, the lexicographic projection keeps as much of it as full coverage allows" />
          <Button label="certify" onPress={() => runCertify()} busy={certBusy} />
          {certState.error ? <Text style={s.err}>{certState.error}</Text> : null}
          {certState.unavailable ? <Unavailable message={certState.unavailable} /> : null}
        </Panel>
      ) : null}

      {r ? (
        <Panel title="Coverage" accent={r.deficiency === 0 ? t.ok : t.danger}>
          <KV k="agents N · tasks M" v={`${r.N} · ${r.M}`} />
          <KV k="Ore deficiency d" v={r.deficiency} tone={r.deficiency === 0 ? t.ok : t.danger} />
          <KV k="maximum coverage M − d" v={`${r.max_coverage} of ${r.M}`} />
          <KV k="coverage margin (collapses survived)"
              v={r.coverage_margin < 0 ? 'full coverage already fails' : r.coverage_margin}
              tone={r.coverage_margin < 0 ? t.danger : t.ok} />
          {r.b != null ? (
            <KV k={`worst-case deficiency after b = ${r.b} collapses`} v={r.worst_case_deficiency}
                tone={r.worst_case_deficiency === 0 ? t.ok : t.danger} />
          ) : null}
          <KV k="greedy (nested_greedy_fast) covers" v={r.greedy_covered} />
          {r.projection ? (
            <>
              <KV k="projection covers" v={r.projection.covered} />
              <KV k="proposal pairs kept" v={r.projection.kept_from_proposal} />
              <KV k="proposed pairs that were ineligible"
                  v={r.projection.proposal_ineligible_agents.length
                    ? r.projection.proposal_ineligible_agents.join(', ') : 'none'} />
            </>
          ) : null}

          <Text style={s.sub}>Worst-case deficiency against b</Text>
          <View nativeID="paper3-worst-case">
            <LineChart width={w} height={w < 420 ? 180 : 210}
              xLabel="b" yLabel="deficiency" yMin={0}
              yMax={Math.max(1, ...r.worst_case_curve.map((p) => p.deficiency)) + 0.5}
              series={[{ key: 'wc', label: 'worst case', color: t.accent,
                points: r.worst_case_curve.map((p) => ({ x: p.b, y: p.deficiency })) }]} />
          </View>

          <Text style={s.sub}>Count profile (tasks by α ascending)</Text>
          <DataTable rows={profileRows} max={50} />
          <Text style={s.sub}>Assignment per agent</Text>
          <DataTable rows={agentRows} max={50} />
          <Text style={s.source}>source: {r.source}</Text>
          <View style={s.exportRow}>
            <ExportMenu title="Paper III certificate computation" data={cert}
                        csv={agentRows} sources={r.source} svgId="paper3-worst-case" />
          </View>
        </Panel>
      ) : null}

      {defaults ? (
        <Panel title="Population lift"
               subtitle="P(full coverage) for N agents that fall into alert-limit levels independently with probabilities q">
          <Field label={`N — fleet size (≤ ${defaults.limits.lift_N})`} value={liftN}
                 onChange={setLiftN} />
          <Field label="alert limits α per task, m" value={liftAlpha} onChange={setLiftAlpha}
                 multiline />
          {levelLabels(defaults.alert_limits_m).map((lab, i) => (
            <Field key={lab} label={`q · ${lab}`} value={q[i] ?? ''}
                   onChange={(v) => setQ((qq) => qq.map((x, j) => (j === i ? v : x)))} />
          ))}
          <Text style={s.hint}>
            Prefilled from e2_lift.csv's independent row. That file stores q
            cumulatively (q_le2, q_le10, q_le20) only, so the mass between 2 and
            10 m is placed in the (5, 10] level and (2, 5] starts at 0 — edit
            freely. q must sum to 1.
          </Text>
          <Button label="predict" onPress={runLift} busy={liftBusy} />
          {liftState.error ? <Text style={s.err}>{liftState.error}</Text> : null}
          {liftState.unavailable ? <Unavailable message={liftState.unavailable} /> : null}
          {lift ? (
            <View style={{ marginTop: 10 }}>
              <KV k="P(full coverage), i.i.d. lift" v={fmt(lift.p_full)} tone={t.accent} />
              <Text style={s.hint}>{lift.assumption}</Text>
              <View style={s.exportRow}>
                <ExportMenu title="Paper III lift computation" data={lift}
                            csv={[{ N: lift.N, M: lift.M, alpha: lift.alpha.join(' '),
                                    ...Object.fromEntries(lift.q_levels.map((l, i) => [`q ${l}`, lift.q[i]])),
                                    p_full: lift.p_full }]}
                            sources={lift.source} />
              </View>
            </View>
          ) : null}
          {defaults.lift_reference.length ? (
            <>
              <Text style={s.sub}>The paper's check: lift prediction against simulation</Text>
              <DataTable rows={defaults.lift_reference}
                         columns={LIFT_COLUMNS.filter((c) => c in defaults.lift_reference[0])} />
              {defaults.lift_reference.map((row) => {
                const inside = Number(row.p_sim_lo) <= Number(row.p_iid_exact)
                  && Number(row.p_iid_exact) <= Number(row.p_sim_hi);
                return (
                  <KV key={row.dependence}
                      k={`${row.dependence}: lift prediction inside the simulated 95% interval?`}
                      v={inside ? 'yes' : 'no'} tone={inside ? t.ok : t.danger} />
                );
              })}
              <Text style={s.hint}>
                The lift assumes agents degrade independently. Where the
                prediction falls outside the simulated interval, that
                assumption, not the combinatorics, is what failed.
              </Text>
            </>
          ) : null}
        </Panel>
      ) : null}

      <Panel title="MARL results by run directory"
             subtitle="e6_main.csv (the e5_marl run) and every e6_main_<dir>.csv; interquartile means with intervals">
        {marlState.unavailable ? <Unavailable message={marlState.unavailable} /> : null}
        {marlState.error ? <Text style={s.err}>{marlState.error}</Text> : null}
        {marl ? (
          <>
            <Pills options={marl.dirs} value={dir} onChange={setDir} />
            <DataTable rows={marlRows}
                       columns={MARL_COLUMNS.filter((c) => marlRows?.length && c in marlRows[0])}
                       colWidth={96} />
            <Text style={s.source}>source: {marl.sources[dir]}</Text>
            <View style={s.exportRow}>
              <ExportMenu title={`Paper III MARL ${dir}`} data={marlRows} csv={marlRows}
                          sources={marl.sources[dir]} />
            </View>
          </>
        ) : null}
        {!marl && !marlState.unavailable && !marlState.error
          ? <Text style={s.hint}>loading…</Text> : null}
      </Panel>

      <ResultsBrowser pid="III" />
    </ScrollView>
  );
}

/** One label per level of the lift: rho at or under each alert limit, then above all. */
function levelLabels(lv) {
  return [
    `ρ ≤ ${lv[0]}`,
    ...lv.slice(1).map((hi, i) => `${lv[i]} < ρ ≤ ${hi}`),
    `ρ > ${lv[lv.length - 1]}`,
  ];
}

const styles = (t) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 48 },
  label: {
    color: t.muted, fontSize: 9.5, fontWeight: '700', letterSpacing: 0.5,
    textTransform: 'uppercase', marginBottom: 4, marginTop: 6,
  },
  sub: {
    color: t.text, fontSize: 12, fontWeight: '700', marginTop: 14, marginBottom: 4,
    fontFamily: fonts.display,
  },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 4 },
  err: { color: t.danger, fontSize: 11.5, marginTop: 8 },
  source: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, marginTop: 8 },
  exportRow: { flexDirection: 'row', justifyContent: 'flex-end', marginTop: 10 },
});
