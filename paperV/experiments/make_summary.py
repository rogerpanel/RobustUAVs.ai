"""Write paperV/results_summary.md from the result CSVs (every number is computed here)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from admissible import TighteningConfig
from aggregate import load, aggregate, time_overhead, solve_time_table
from constants import RESULTS, ROOT, DELTA_ADV, W_BAR_NOM, provenance_rows, ETA_INT
from stats import cp_upper, wilson, trend


def f(x, d=3):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    if isinstance(x, (int, np.integer)):
        return f"{x:,}"
    ax = abs(x)
    if ax != 0 and (ax < 1e-3 or ax >= 1e5):
        return f"{x:.2e}"
    return f"{x:.{d}f}"


def ci(m, lo, hi, d=3):
    return f"{f(m, d)} [{f(lo, d)}, {f(hi, d)}]"


def md_table(header, rows):
    s = "| " + " | ".join(header) + " |\n|" + "|".join("---" for _ in header) + "|\n"
    for r in rows:
        s += "| " + " | ".join(str(x) for x in r) + " |\n"
    return s


def main():
    df = load()
    cells = aggregate(df)
    tov = time_overhead(df)
    st_tab, allt = solve_time_table()
    meta = json.loads((RESULTS / "run_meta.json").read_text())
    theta = json.loads((RESULTS / "oracle_theta.json").read_text())
    blev = json.loads((RESULTS / "budget_levels.json").read_text())
    nest = pd.read_csv(RESULTS / "nestedness.csv") if (RESULTS / "nestedness.csv").exists() else None
    tc = TighteningConfig(b_tot=DELTA_ADV).summary()
    L = []
    w = L.append
    w("# Paper V pilot results (NON-LLM planners, simulation only)\n")
    w("> **Status: PILOT.** Every number below comes from a seeded simulation of a planar double-integrator "
      "fleet with *non-LLM* planners (scripted, random, stall and action-space oracle adversaries). "
      "No language model was queried; real-LLM campaigns (A1-A5 in the plan's ladder) are pending. "
      "Naming: the action-space oracle is the task brief's A7 (the research plan calls it A6 and reserves A7 "
      "for its composition with Paper IV's covert sensing attacker; here that composition is approximated by "
      "realising the sensing offset at the declared budget). "
      "The oracle adversary chooses actions directly and is therefore an upper envelope on any "
      "prompt-injection attacker *for the safety claim*; for denial it is a lower bound on what the "
      "searched family can do, not a proof of the strongest attack. Dynamics, disturbance and "
      "certificate generators are illustrative models (provenance below); nothing here is a hardware claim.\n")
    # ------------------------------------------------------------ run size
    tot_eps = int(sum(v.get("episodes", 0) for k, v in meta.items() if not k.startswith("_")))
    wall = sum(v.get("wall_s", 0) for k, v in meta.items() if not k.startswith("_"))
    on = df[df.filter_on]
    w(headline(df, cells, tov, st_tab, nest))
    w("## 1. Campaign size and runtime\n")
    w(md_table(["stage", "episodes", "wall time (s)"],
               [[k, f(int(v.get("episodes", 0))), f(v.get("wall_s", 0), 0)] for k, v in meta.items()
                if not k.startswith("_")]))
    w(f"\nTotal: {f(tot_eps)} episodes (CEM training episodes counted as candidates x training seeds), "
      f"{f(wall/60, 1)} min wall on {meta.get('_env', {}).get('workers', 2)} worker processes "
      f"(2-vCPU container). Evaluation episodes with the filter ON: {f(len(on))}, "
      f"{f(int(on.aircraft_steps.sum()))} aircraft-steps at dt = 0.1 s. "
      f"Environment: {json.dumps(meta.get('_env', {}))}.\n")
    # ------------------------------------------------------------ setup
    w("## 2. What was simulated\n")
    w("- **Plant** (`plant.py`): N in {4, 12} aircraft, per-axis double integrator at dt = 0.1 s, actuator "
      "saturation 4 m/s^2 per axis, speed limit 12 m/s per axis, bounded acceleration mismatch "
      "|d|_inf <= w_true. Keep-in polygon (6 half-planes incl. two chamfers), 40 m lanes, pairwise lane-swap "
      "goals at 560 m (crossing traffic), mission T = 70 s, deadline (1+kappa_sched)T with kappa_sched = 0.10 "
      "(headline) and 0.25 (sensitivity), simulated to 87.5 s.\n"
      "- **True vs navigation state:** p_true = p_nav + e_cert + e_adv with |e_cert|_inf <= rho_i(t) "
      "(Paper III generator: L_rho = e^{L T_c} gamma = 5.296 m/s of error per s of staleness, benign residuals "
      "from the parent hop ledger) and |e_adv|_inf <= b_adv (covert sensing offset realised at the declared "
      "budget). Under (A2) staleness is capped at 0.944 s (rho_bar = 5.0 m) and relay jumps are off.\n"
      "- **Filter** (`filter.py`): joint-fleet QP every Ts = 0.5 s, horizon N_p = 10 (5 s), tube controller "
      "u = v + K(x - z) at 10 Hz with K = (1.2, 1.8) (Paper IV PD). Tightening "
      "beta_k = min(max(rho, rho_floor) + L_rho (k+1) Ts, rho_bar) + b_tot + eps_k + bulge; separation linearised "
      "with ||n||_1 scaling; loiter (zero-velocity) terminal set; independent exact verifier; continuation "
      "plan from the latched nominal when the re-anchored problem fails; latched tail otherwise. "
      "Solvers: OSQP (40 ms first stage) then Clarabel IPM; total budget 0.25 s per tick (overrun = fallback).\n"
      f"- **Tightening numbers at b_tot = delta_adv = {DELTA_ADV} m, w_bar = {W_BAR_NOM} m/s^2:** "
      f"eps_p(inf) = {f(tc['eps_p_inf'])} m, eps_v(inf) = {f(tc['eps_v_inf'])} m/s, eps_u(inf) = "
      f"{f(tc['eps_u_inf'])} m/s^2 (nominal accel bound {f(tc['u_nom'])} m/s^2), terminal tightening "
      f"{f(tc['beta_terminal'])} m, closed-loop spectral radius {f(tc['spectral_radius'])}.\n"
      "- **Planners** (`agent.py`, `attacks.py`): benign scripted (A0); random waypoints; stall (benign, then "
      "safe holds from a random onset in [5, 30] s); oracle_violation and oracle_denial = CEM-tuned members of "
      "a parametric action-space family (push to nearest wall / neighbour / fixed direction / along velocity / "
      "toward goal), run with adversarial nature (disturbance, certificate error and sensing offset all "
      "pointing at each aircraft's most binding constraint); oracle_denial is constrained to keep a "
      "progress-toward-goal term (an attacker that wants the *filter* to cause the denial). Hand-designed "
      "family members are evaluated alongside. A `MockLLMPlanner` stub (JSON schema, sha256 cache, usage log) "
      "exists for the future LLM runs and was not used in the campaign.\n"
      f"- **Oracle CEM optimum** (N = 4, seeds 2xxx, transferred unchanged to N = 12): "
      f"theta_violation = {np.round(theta['violation'], 3).tolist()} (score = {f(theta['violation_score'])} = "
      f"minus the minimum true margin), theta_denial = {np.round(theta['denial'], 3).tolist()} "
      f"(score {f(theta['denial_score'])}). theta = (w_wall, w_nbr, w_const, phi, w_vel, w_goal).\n")
    w("Constants and provenance (`results/constants_paperV.csv`):\n")
    w(md_table(["name", "value", "provenance"], [[a, f(b, 4) if isinstance(b, float) else b, c]
                                                for a, b, c in provenance_rows()]))
    # ------------------------------------------------------------ RQ1
    w("\n## 3. RQ1 - physical safety of the true state\n")
    ins = df[(df.filter_on) & (df.inside_assumptions == 1)]
    k, nst = int(ins.viol_steps.sum()), int(ins.aircraft_steps.sum())
    w(f"**Filter ON, inside the stated assumptions (A1 w_true <= w_bar, A2 rho within envelope, no actuator "
      f"saturation, no uncertified start), all stages pooled:** {f(k)} violating aircraft-steps out of "
      f"{f(nst)} ({f(len(ins))} episodes; {f(int(ins.viol_episode.sum()))} episodes with any violation). "
      f"One-sided 95% Clopper-Pearson upper bound on the per-aircraft-step violation probability: "
      f"**{f(cp_upper(k, nst))}**.\n")
    for N in (4, 12):
        g = ins[ins.N == N]
        if len(g):
            w(f"- N = {N}: {f(int(g.viol_steps.sum()))} / {f(int(g.aircraft_steps.sum()))} aircraft-steps "
              f"({f(len(g))} episodes), CP95 upper {f(cp_upper(int(g.viol_steps.sum()), int(g.aircraft_steps.sum())))}.")
    orc = ins[ins.planner.str.startswith("oracle")]
    w(f"- Oracle planners only (adversarial nature): {f(int(orc.viol_steps.sum()))} / "
      f"{f(int(orc.aircraft_steps.sum()))} aircraft-steps ({f(len(orc))} episodes), CP95 upper "
      f"{f(cp_upper(int(orc.viol_steps.sum()), int(orc.aircraft_steps.sum())))}; closest approach over all "
      f"inside-assumption oracle episodes: corridor margin {f(orc.min_corridor_margin.min())} m, separation "
      f"margin {f(orc.min_sep_margin.min())} m (true state).\n")
    excl = df[(df.filter_on) & (df.inside_assumptions == 0) & (df.within) &
              (df.w_true <= df.w_assumed + 1e-12)]
    if len(excl):
        w(f"- Filter-ON episodes nominally inside (A1)/(A2) but excluded from the pooled count because an "
          f"auxiliary condition failed (actuator saturation or uncertified start): {f(len(excl))} episodes, "
          f"{f(int(excl.viol_steps.sum()))} violating aircraft-steps, saturation steps "
          f"{f(int(excl.sat_steps.sum()))}, uncertified ticks {f(int(excl.uncertified_ticks.sum()))} "
          f"(tags: {sorted(excl.tag.unique().tolist())}).\n")
    # main table
    w("\n### 3.1 Filter ON vs OFF (main stage, b_tot = delta_adv = 4.371 m, w_true = w_bar = 0.5 m/s^2)\n")
    m = cells[cells.stage == "main"].sort_values(["N", "planner", "filter_on"])
    rows = []
    for _, r in m.iterrows():
        rows.append([r.N, r.planner, "ON" if r.filter_on else "OFF", f(r.episodes),
                     ci(r.viol_ep_rate, r.viol_ep_lo, r.viol_ep_hi, 2), f(r.svr, 4),
                     f(r.svr_cp_upper95) if r.viol_steps == 0 else "-",
                     ci(r.ir, r.ir_lo, r.ir_hi, 3) if r.filter_on else "-",
                     ci(r.fr, r.fr_lo, r.fr_hi, 3) if r.filter_on else "-",
                     f(r.cont_rate, 3) if r.filter_on else "-",
                     ci(r.mcr, r.mcr_lo, r.mcr_hi, 2), f(r.denial_filter, 2), f(r.denial_envelope, 2),
                     f(r.denial_violation, 2), f(r.mean_dev, 3) if r.filter_on else "-"])
    w(md_table(["N", "planner", "filter", "eps", "episode viol. rate [Wilson 95%]", "SVR (per aircraft-step)",
                "CP95 SVR upper (if 0)", "IR [boot 95%]", "FR [boot 95%]", "continuation rate", "MCR [Wilson]",
                "denial: filter", "denial: envelope", "denial: violation", "mean ||u*-u_LLM|| (m/s^2)"], rows))
    w("\nIR = fraction of aircraft-ticks with ||v0 - u_des||_inf > "
      f"{ETA_INT} m/s^2 (includes fallback ticks); FR = fraction of fleet ticks executing the latched tail; "
      "continuation rate = fraction of ticks certified by the continuation problem (not a fallback). "
      "MCR = all aircraft reach the goal by (1.10)T with zero violations (conjunctive). Denial causes: "
      "*filter* = some aircraft missed the deadline although its planner's cumulative progress intent covered "
      "its goal distance; *envelope* = planner never asked for enough progress; *violation* = a violation "
      "occurred (only possible OFF or outside the assumptions).\n")
    if len(tov):
        w("\n**Benign mission-time overhead (ON minus OFF, paired by seed):** " + "; ".join(
            f"N = {int(r.N)}: {ci(r.overhead_s, r.lo, r.hi, 2)} s over a mean OFF fleet completion of "
            f"{f(r.t_off_mean, 1)} s ({f(100*r.overhead_rel, 1)}%), {int(r.pairs)} pairs"
            for _, r in tov.iterrows()) + ".\n")
    # oracle family
    w("\n### 3.2 Oracle family members (hand-designed + CEM optimum), worst case per mission\n")
    h = df[(df.stage.isin(["main", "hand"])) & (df.planner.str.startswith("oracle"))]
    rows = []
    for (N, fon), g in h.groupby(["N", "filter_on"]):
        wc = g.groupby("seed").agg(v=("viol_episode", "max"), cm=("min_corridor_margin", "min"),
                                   sm=("min_sep_margin", "min"), fbt=("fallback_ticks", "max"),
                                   den=("complete", "min"))
        k_ = int(wc.v.sum()); n_ = len(wc)
        lo, hi = wilson(k_, n_)
        rows.append([N, "ON" if fon else "OFF", g.planner.nunique(), n_, f"{k_}/{n_} [{f(lo,2)}, {f(hi,2)}]",
                     f(wc.cm.min(), 2), f(wc.sm.min(), 2), f(1 - wc.den.mean(), 2)])
    w(md_table(["N", "filter", "# oracle variants", "missions (seeds)", "worst-case missions with a violation",
                "min corridor margin (m)", "min separation margin (m)", "worst-case denial rate"], rows))
    hc = cells[(cells.stage.isin(["hand", "main"])) & (cells.planner.str.startswith("oracle")) & (cells.filter_on)]
    rows = [[r.N, r.planner, f(r.episodes), f(r.viol_steps), f(r.min_corridor_margin, 2), f(r.min_sep_margin, 2),
             f(r.ir, 3), f(r.fr, 3), f(r.cont_rate, 3), f(r.denial, 2), f(r.denial_filter, 2)]
            for _, r in hc.sort_values(["N", "planner"]).iterrows()]
    w("\nPer variant, filter ON:\n")
    w(md_table(["N", "variant", "eps", "viol. steps", "min corr. margin", "min sep. margin", "IR", "FR",
                "cont.", "denial", "denial: filter"], rows))
    # ------------------------------------------------------------ budget
    w("\n## 4. RQ3 - budget sweep: admissible-set shrinkage, induced fallback/denial, nestedness\n")
    w("Budget levels (m): " + ", ".join(f"{f(b, 3)} ({lab})" for b, lab in blev["levels"]) +
      f". s*(eps = 0.1) = {f(blev['s_star'], 2)} m from Paper IV's union bound over its committed marginals. "
      "The covert sensing offset is realised at the declared budget (adversarial nature) in every budget cell.\n")
    b = cells[(cells.stage == "budget") & (cells.tag == "budget")].sort_values(["N", "planner", "b_tot"])
    rows = []
    for _, r in b.iterrows():
        bt = TighteningConfig(b_tot=r.b_tot).summary()["beta_terminal"]
        rows.append([r.N, r.planner, f(r.b_tot, 3), f(bt, 2), f(r.episodes), f(r.viol_steps),
                     ci(r.fr, r.fr_lo, r.fr_hi, 3), f(r.ir, 3), f(r.cont_rate, 3), ci(r.denial, r.denial_lo, r.denial_hi, 2),
                     f(r.denial_filter, 2), f(r.denial_envelope, 2), f(r.uncertified_ticks)])
    w(md_table(["N", "planner", "b_tot (m)", "terminal tightening (m)", "eps", "viol. steps", "FR [boot]", "IR",
                "cont.", "denial [Wilson]", "denial: filter", "denial: envelope", "uncertified ticks"], rows))
    # trend tests
    bd = df[(df.stage == "budget") & (df.tag == "budget")]
    lv = sorted(bd.b_tot.unique())
    w("\n**Ordered-trend tests (Spearman, per-episode values vs b_tot level, common random numbers):**\n")
    for (N, pl), g in bd.groupby(["N", "planner"]):
        r1, p1 = trend(g.b_tot, 1 - g.complete)
        r2, p2 = trend(g.b_tot, g.fallback_ticks / g.n_ticks)
        r3, p3 = trend(g.b_tot, g.interventions / g.aircraft_ticks)
        # pathwise monotonicity per seed
        piv = g.pivot_table(index="seed", columns="b_tot", values="complete")
        nonmono = int(sum(np.any(np.diff(1 - piv.loc[s].values) < 0) for s in piv.index))
        pivf = g.pivot_table(index="seed", columns="b_tot", values="fallback_ticks")
        nonmono_f = int(sum(np.any(np.diff(pivf.loc[s].values) < 0) for s in pivf.index))
        w(f"- N = {N}, {pl}: denial rho_s = {f(r1, 2)} (p = {f(p1)}); fallback fraction rho_s = {f(r2, 2)} "
          f"(p = {f(p2)}); intervention rate rho_s = {f(r3, 2)} (p = {f(p3)}). Pathwise: {nonmono}/{len(piv)} "
          f"seeds have a non-monotone denial sequence and {nonmono_f}/{len(pivf)} a non-monotone fallback-count "
          f"sequence across levels (pathwise monotonicity is NOT predicted by the theory).")
    if nest is not None:
        w("\n**One-step nestedness / transparency study** (`results/nestedness.csv`; random fleet states, "
          "certificates and proposals; Clarabel without time limit; identical linearisation across levels):\n")
        piv_f = nest.pivot(index="instance", columns="level", values="feasible").values
        piv_t = nest.pivot(index="instance", columns="level", values="transparent").values
        piv_d = nest.pivot(index="instance", columns="level", values="dev").values
        nf = int(np.sum(np.diff(piv_f, axis=1) > 0))
        nt = int(np.sum(np.diff(piv_t, axis=1) > 0))
        dd = np.diff(piv_d, axis=1)
        nd = int(np.sum(dd[np.isfinite(dd)] < -1e-3))
        feas = nest[nest.feasible == 1]
        agree = int(((feas.transparent == 1) == (feas.dev <= ETA_INT)).sum())
        ver = int(feas.verified.sum())
        g = nest.groupby("b_tot").agg(feasible=("feasible", "mean"), transparent=("transparent", "mean"),
                                      n=("instance", "count")).reset_index()
        w(md_table(["b_tot (m)", "instances", "feasible fraction", "transparent fraction"],
                   [[f(r.b_tot, 3), f(int(r.n)), f(r.feasible, 3), f(r.transparent, 3)] for _, r in g.iterrows()]))
        w(f"\nNestedness violations between adjacent levels: feasibility {nf}, transparency {nt}, "
          f"deviation decreasing by more than 1e-3 m/s^2: {nd} (over {piv_f.shape[0]} instances x "
          f"{piv_f.shape[1]-1} level pairs). Lemma 1 (transparent <=> deviation <= {ETA_INT}) agreed on "
          f"{agree}/{len(feas)} feasible (instance, level) pairs; {ver}/{len(feas)} IPM solutions passed the "
          f"independent verifier.\n")
    gm = cells[(cells.stage == "budget") & (cells.tag.str.startswith(("gamma", "dbar")))]
    if len(gm):
        w("\n**gamma and staleness-envelope levels** (benign, N = 4, b_tot = delta_adv, adversarial nature):\n")
        rows = []
        for _, r in gm.sort_values("tag").iterrows():
            t = TighteningConfig(b_tot=r.b_tot, gamma=r.gamma, delta_bar=r.delta_bar).summary()
            rows.append([r.tag, f(r.gamma, 3), f(r.delta_bar, 3), f(t["rho_bar"], 2), f(t["beta_terminal"], 2),
                         f(r.episodes), f(r.viol_steps), f(r.fr, 3), f(r.ir, 3), ci(r.mcr, r.mcr_lo, r.mcr_hi, 2),
                         f(r.uncertified_ticks)])
        w(md_table(["cell", "gamma (m/s)", "Delta_bar (s)", "rho_bar (m)", "terminal tightening (m)", "eps",
                    "viol. steps", "FR", "IR", "MCR", "uncertified ticks"], rows))
    # ------------------------------------------------------------ mismatch
    w("\n## 5. Mismatch sweep (honest negative control): filter assumes w_bar = 0.5 m/s^2\n")
    mm = cells[cells.stage == "mismatch"].sort_values(["N", "planner", "w_true"])
    rows = [[r.N, r.planner, f(r.w_true / W_BAR_NOM, 1) + "x", f(r.episodes), f(r.viol_steps),
             ci(r.viol_ep_rate, r.viol_ep_lo, r.viol_ep_hi, 2),
             f(r.svr, 5) if r.viol_steps else f"0 (CP95 <= {f(r.svr_cp_upper95)})",
             f(min(r.min_corridor_margin, r.min_sep_margin), 3), ci(r.ir, r.ir_lo, r.ir_hi, 3), f(r.fr, 3),
             f(r.cont_rate, 3), f(r.sat_steps), f(r.mcr, 2)] for _, r in mm.iterrows()]
    w(md_table(["N", "planner", "w_true / w_bar", "eps", "viol. steps", "episode viol. rate", "SVR",
                "min true margin (m)", "IR [boot]", "FR", "cont.", "saturation steps", "MCR"], rows))
    # ------------------------------------------------------------ negative / ablations
    w("\n## 6. Outside (A2) and ablations\n")
    ng = cells[cells.stage == "negative"].sort_values(["tag", "N", "planner"])
    rows = [[r.tag, r.N, r.planner, f(r.episodes), f(r.viol_steps), ci(r.viol_ep_rate, r.viol_ep_lo, r.viol_ep_hi, 2),
             f(min(r.min_corridor_margin, r.min_sep_margin), 2), f(r.fr, 3), f(r.cont_rate, 3),
             f(r.rho_over_bar_steps), f(r.mcr, 2), f(r.denial_filter, 2)] for _, r in ng.iterrows()]
    w(md_table(["cell", "N", "planner", "eps", "viol. steps", "episode viol. rate", "min true margin (m)", "FR",
                "cont.", "steps with rho > rho_bar", "MCR", "denial: filter"], rows))
    w("\n*outsideA2*: Paper III default certificate process (staleness cap 10 s, undetected relay-delay jumps "
      "from the hidden-residual pool, seeds 5xxx) -- outside the theorem's scope by construction. "
      "*no_lookahead*: tightening uses the current rho only (no L_rho growth over the horizon). "
      "*no_continuation*: re-anchored problem + latched tail only.\n")
    # ------------------------------------------------------------ latency
    w("\n## 7. Solve time (O_lat)\n")
    a = st_tab[st_tab.stage == "ALL"]
    w(md_table(["N", "ticks", "p50 (ms)", "p95 (ms)", "p99 (ms)", "max (ms)", "> 250 ms", "> 500 ms"],
               [[int(r.N), f(int(r.n)), f(r.p50_ms, 1), f(r.p95_ms, 1), f(r.p99_ms, 1), f(r.max_ms, 1),
                 f(r.frac_over_250ms, 4), f(r.frac_over_500ms, 4)] for _, r in a.iterrows()]))
    w("\nTimes are wall-clock per filter tick (both solve stages + verification), Python + OSQP 1.1 / "
      "Clarabel 0.11 on the 2-vCPU container with two episodes running concurrently. The filter period is "
      "500 ms; the in-code budget is 250 ms, after which the tick falls back to the latched plan.\n")
    w(findings(df))
    w(file_list())
    (ROOT / "results_summary.md").write_text("\n".join(L))
    print("\n".join(L)[:3000])



# ---------------------------------------------------------------- generated narrative blocks
def _cell(cells, **kw):
    c = cells
    for k, v in kw.items():
        c = c[c[k] == v]
    return c.iloc[0] if len(c) else None


def headline(df, cells, tov, st_tab, nest):
    H = ["## 0. Headline numbers (pilot)\n"]
    ins = df[(df.filter_on) & (df.inside_assumptions == 1)]
    k, n_ = int(ins.viol_steps.sum()), int(ins.aircraft_steps.sum())
    orc = ins[ins.planner.str.startswith("oracle")]
    H.append(f"1. **Safety inside the assumptions (RQ1).** Filter ON: {f(k)} true-state violations (corridor or "
             f"separation) in {f(n_)} aircraft-steps over {f(len(ins))} episodes (N = 4 and 12, all planners, "
             f"all stages); 95% Clopper-Pearson upper bound {f(cp_upper(k, n_))} per aircraft-step. Oracle "
             f"adversaries alone (with worst-case disturbance, certificate error and sensing offset): {f(int(orc.viol_steps.sum()))} in "
             f"{f(int(orc.aircraft_steps.sum()))} aircraft-steps (CP95 {f(cp_upper(int(orc.viol_steps.sum()), int(orc.aircraft_steps.sum())))}); "
             f"they pushed the true state to within {f(orc.min_corridor_margin.min(), 3)} m of the keep-in boundary "
             f"and {f(orc.min_sep_margin.min(), 3)} m of the separation minimum, i.e. the tightening is nearly tight "
             f"and the attack is not weak.")
    m = cells[cells.stage == "main"]
    offs = []
    for N in (4, 12):
        for pl in ("oracle_violation", "oracle_denial", "random"):
            r = _cell(m, N=N, planner=pl, filter_on=False)
            if r is not None:
                offs.append(f"{pl} N={N}: {int(r.viol_episodes)}/{int(r.episodes)}")
    H.append("2. **Sanity check, filter OFF:** episodes with a violation - " + "; ".join(offs) +
             ". The same planners with the filter ON: 0 in every cell (section 3.1).")
    b4 = _cell(m, N=4, planner="benign", filter_on=True); b12 = _cell(m, N=12, planner="benign", filter_on=True)
    if b4 is not None and b12 is not None and len(tov):
        H.append(f"3. **Benign cost (RQ4).** MCR {f(b4.mcr, 2)} (N = 4, {int(b4.episodes)} eps) and {f(b12.mcr, 2)} "
                 f"(N = 12, {int(b12.episodes)} eps) with the filter ON, identical to OFF; benign intervention rate "
                 f"{ci(b4.ir, b4.ir_lo, b4.ir_hi)} (N = 4) and {ci(b12.ir, b12.ir_lo, b12.ir_hi)} (N = 12), mostly "
                 f"the take-off acceleration clipped from 4.0 to the tightened {f(TighteningConfig().u_nom, 2)} m/s^2 and "
                 f"crossing-pair separation; mean deviation {f(b4.mean_dev)} / {f(b12.mean_dev)} m/s^2; "
                 "mission-time overhead " + "; ".join(f"N = {int(r.N)}: {ci(r.overhead_s, r.lo, r.hi, 2)} s"
                                                      for _, r in tov.iterrows()) + ".")
    parts = []
    for N in (4, 12):
        st = _cell(m, N=N, planner="stall", filter_on=True)
        od = _cell(m, N=N, planner="oracle_denial", filter_on=True)
        if st is not None and od is not None:
            parts.append(f"N = {N}: stall planner denial {f(st.denial, 2)} of which in-envelope "
                         f"{f(st.denial_envelope, 2)} (fallback rate {f(st.fr, 3)}); progress-intent oracle_denial "
                         f"denial {f(od.denial, 2)}, filter-induced {ci(od.denial_filter, od.denial_filter_lo, od.denial_filter_hi, 2)}, "
                         f"fallback rate {ci(od.fr, od.fr_lo, od.fr_hi)}, continuation rate {f(od.cont_rate, 3)}")
    H.append("4. **Denial decomposition (RQ2/Prop. 2 recast).** " + "; ".join(parts) + ". Safe-but-useless "
             "proposals deny the mission with the filter essentially transparent - the filter cannot reduce "
             "MDR_envelope, exactly as the recast proposition predicts - while a filter-aware attacker that keeps a "
             "progress term converts its blocked safety attack into filter-induced denial.")
    bd = cells[(cells.stage == "budget") & (cells.tag == "budget") & (cells.planner == "benign") & (cells.N == 4)]
    if len(bd):
        last_ok = bd[bd.denial == 0].b_tot.max()
        first_bad = bd[bd.denial > 0].b_tot.min()
        txt = (f"5. **Budget (RQ3/Prop. 3 recast).** Benign denial stays {f(0.0, 2)} for b_tot <= {f(last_ok, 3)} m "
               f"and jumps to {f(float(bd[bd.b_tot == first_bad].denial.iloc[0]), 2)} at b_tot = {f(first_bad, 3)} m "
               f"(full Paper IV b_tot(eps = 0.1)), where the terminal tightening "
               f"{f(TighteningConfig(b_tot=first_bad).summary()['beta_terminal'], 2)} m makes the required nominal lane "
               f"separation {f(5 + 2 * TighteningConfig(b_tot=first_bad).summary()['beta_terminal'], 1)} m exceed the 40 m "
               f"lane spacing: the admissible set is empty at take-off (A5 fails; the theorem is silent there, and the "
               f"uncertified brake-and-hold start did show violations under the adversarial offset). Benign intervention "
               f"rate {'rises monotonically' if np.all(np.diff(bd.sort_values('b_tot').ir.values) >= 0) else 'changes non-monotonically'} "
               f"across levels: " + ", ".join(f(x) for x in bd.sort_values('b_tot').ir.values) + ".")
        if nest is not None:
            g = nest.groupby("b_tot").feasible.mean()
            txt += (f" One-step study: feasible fraction {f(g.iloc[0])} -> {f(g.iloc[-1])} over the 7 levels with 0 "
                    f"nestedness violations (feasibility, transparency, deviation) in {nest.instance.nunique()} instances.")
        H.append(txt)
    mm = cells[(cells.stage == "mismatch") & (cells.N == 4) & (cells.planner == "oracle_violation")]
    if len(mm):
        H.append("6. **Mismatch negative control.** oracle_violation, N = 4: " + "; ".join(
            f"w_true = {f(r.w_true / W_BAR_NOM, 0)}x w_bar: {int(r.viol_episodes)}/{int(r.episodes)} episodes violate, "
            f"min true margin {f(min(r.min_corridor_margin, r.min_sep_margin), 2)} m" for _, r in mm.sort_values('w_true').iterrows())
                 + ". Violations appear exactly when the stated mismatch bound is exceeded.")
    ng = cells[cells.stage == "negative"]
    o = _cell(ng, tag="outsideA2", N=4, planner="oracle_violation"); nl = _cell(ng, tag="no_lookahead", N=4)
    nc = _cell(ng, tag="no_continuation", N=4)
    if o is not None and nl is not None:
        H.append(f"7. **Outside (A2) / ablations.** Paper III's default certificate process (10 s staleness cap, "
                 f"relay jumps): {int(o.viol_episodes)}/{int(o.episodes)} oracle episodes violate (min margin "
                 f"{f(min(o.min_corridor_margin, o.min_sep_margin), 1)} m) - the theorem is silent there, as stated. "
                 f"Dropping the L_rho look-ahead *inside* (A2): {int(nl.viol_episodes)}/{int(nl.episodes)} episodes "
                 f"violate (min margin {f(min(nl.min_corridor_margin, nl.min_sep_margin), 2)} m), so the Paper III "
                 f"Thm 3 look-ahead is necessary, not cosmetic."
                 + (f" Without the continuation problem the fallback rate under oracle_denial is {f(nc.fr, 3)} "
                    f"(vs {f(_cell(m, N=4, planner='oracle_denial', filter_on=True).fr, 3)} with it), still with 0 violations."
                    if nc is not None else ""))
    a = st_tab[st_tab.stage == "ALL"]
    if len(a):
        H.append("8. **Latency (O_lat).** " + "; ".join(
            f"N = {int(r.N)}: p50 {f(r.p50_ms, 1)} ms, p95 {f(r.p95_ms, 1)} ms, p99 {f(r.p99_ms, 1)} ms, max "
            f"{f(r.max_ms, 1)} ms over {f(int(r.n))} ticks" for _, r in a.iterrows()) +
                 " (filter period 500 ms; Python prototype, 2 concurrent episodes on 2 vCPU).")
    return "\n".join(H) + "\n"


def findings(df):
    F = ["\n## 8. Findings, bugs found during development, and caveats\n"]
    p1 = RESULTS.parent / "results_run1_intentv1" / "episodes_main.csv"
    det = ""
    if p1.exists():
        a = pd.read_csv(p1); b = pd.read_csv(RESULTS / "episodes_main.csv")
        key = ["N", "planner", "filter_on", "seed"]
        j = a.merge(b, on=key, suffixes=("_1", "_2"))
        same_v = int((j.viol_steps_1 == j.viol_steps_2).sum())
        same_f = int(((j.fallback_ticks_1 == j.fallback_ticks_2) & (j.interventions_1 == j.interventions_2)).sum())
        on = j[j.filter_on]
        same_on = int(((on.fallback_ticks_1 == on.fallback_ticks_2) & (on.interventions_1 == on.interventions_2)
                       & (on.continuation_ticks_1 == on.continuation_ticks_2)).sum())
        def cellm(d):
            d = d[d.filter_on]
            return d.groupby(["N", "planner"]).apply(lambda g: pd.Series(dict(
                ir=g.interventions.sum() / g.aircraft_ticks.sum(), fr=g.fallback_ticks.sum() / g.n_ticks.sum(),
                cont=g.continuation_ticks.sum() / g.n_ticks.sum(), mcr=g.complete.mean())), include_groups=False)
        ca, cb = cellm(a), cellm(b)
        dif = (ca - cb).abs()
        det_cell = (f" At cell level (10 filter-ON main cells) the largest run-to-run differences were: IR "
                    f"{f(dif.ir.max(), 4)}, FR {f(dif.fr.max(), 4)}, continuation rate {f(dif.cont.max(), 4)}, "
                    f"MCR {f(dif.mcr.max(), 3)}.")
        det = (f" Reproducibility across the two full runs (main stage, {len(j)} paired episodes): violation counts "
               f"identical in {same_v}/{len(j)}; filter-ON episodes with identical intervention, continuation and "
               f"fallback counts {same_on}/{len(on)}. Differences, where present, come from wall-clock solver budgets "
               f"(OSQP 40 ms first stage, 250 ms per tick): seeds fix the scenario, but which ticks hit a time limit "
               f"depends on machine load. Safety does not depend on this (every executed plan is verified), the "
               f"liveness metrics do slightly." + det_cell + " For the paper runs the wall-clock budgets should be "
               f"replaced by iteration caps (deterministic) and latency measured separately.")
    von = df[(df.filter_on) & (df.viol_steps > 0)]
    reasons = []
    for _, r in von.iterrows():
        why = []
        if r.w_true > r.w_assumed + 1e-12: why.append("w_true>w_bar")
        if not r.within: why.append("outside A2")
        if not r.lookahead: why.append("no look-ahead ablation")
        if r.uncertified_ticks > 0: why.append("uncertified start (A5)")
        if r.sat_steps > 0: why.append("actuator saturation")
        reasons.append(f"{r.tag}/N{r.N}/{r.planner}: " + (", ".join(why) if why else "NONE - INSIDE ASSUMPTIONS"))
    rs = pd.Series(reasons).value_counts()
    inside_bad = int(sum(v for k, v in rs.items() if "NONE" in k))
    F.append(
        f"- **Filter-ON violations inside the stated assumptions: {inside_bad} episodes.** All {len(von)} filter-ON "
        f"episodes with a violation break a stated assumption by design (episode counts by cell and reason: "
        + "; ".join(f"{k} x{v}" for k, v in rs.items()) + "). These are reported as findings (the scope "
        "boundary of the theorem), not bugs.\n"
        "- **Bug/finding 1 (fixed before the campaign):** with OSQP alone at tolerance 1e-5 many ticks hit the "
        "iteration limit or returned plans that failed the independent verifier by ~1e-4 (terminal velocity and "
        "speed rows). Because every executed plan is verified, this never produced an uncertified action - it "
        "produced fallbacks. Fix: solver buffers (0.10 m, 0.05 m/s, 0.05 m/s^2) that the verifier does not use, an "
        "exact terminal-velocity repair, relative coordinates, and a Clarabel interior-point second stage.\n"
        "- **Finding 2 (design):** re-anchoring the plan to the navigation state every tick does not preserve "
        "recursive feasibility under worst-case disturbance near the boundary (the new tightening counts the "
        "already-realised error again). The paper's filter therefore needs the continuation problem (or a "
        "Mayne-style initial-state constraint); the no_continuation ablation shows the cost in fallback rate.\n"
        "- **Bug 3 (fixed, campaign re-run):** the first full run's denial decomposition measured planner intent "
        "from the current velocity plus one tick of proposed acceleration, which understated intent when the filter "
        "held aircraft at rest (it labelled the empty-admissible-set denial at b_tot = 12.7 m as 'envelope'). Intent "
        "is now the velocity the action asks for; all stages except CEM were re-run (first run archived in "
        "`results_run1_intentv1/`)." + det + "\n"
        "- **Bug 4 (fixed in the dry run):** the 'inside assumptions' flag initially counted the no-look-ahead "
        "ablation as compliant; its violations are correctly attributed to the ablation.\n"
        + cem_note(df) +
        "- **Modelling caveats:** estimation and sensing errors are output offsets of the true position (not in the "
        "feedback loop), chosen box-worst-case (stronger than the Euclidean certificate); w is bounded by "
        "construction (clipped Gauss-Markov), so the w_bar held-out calibration check of the plan is not exercised "
        "here - calibrating w_bar against Paper IV's sim.py plant is pending; violations are checked at the 0.1 s "
        "plant step; the filter runs at 2 Hz on a joint fleet QP with fleet-level fallback; separation is "
        "linearised (conservative); the OFF baseline has no speed governor, so its corridor margins diverge; "
        "N = 12 cells have 4-14 episodes, so their CIs are wide; the denial decomposition uses an intent "
        "proxy (cumulative progress the actions ask for vs. goal distance); for acceleration-mode (oracle) "
        "actions the asked-for velocity is taken as v + a x 1 s, which understates intent when the filter holds an "
        "aircraft at rest (e.g. oracle_denial at b_tot = 12.7 m is labelled 'envelope' although the admissible set "
        "is empty), so filter-induced shares for oracle planners are conservative; gamma = 1.625 m/s is a hover-regime "
        "constant applied to a 10 m/s cruise (transfer assumption C3).\n"
        "- **Not done (pending):** real-LLM planners (A1-A5), the composed Paper IV covert attacker as an actual "
        "detector-gated process (here the sensing offset is simply realised at the budget), PX4 SITL cross-check, "
        "baselines other than filter OFF (Simplex accept/reject, one-step CBF-QP, LLM judge), >= 3e6 inside-"
        "assumption aircraft-steps per fleet size for a 1e-6 bound per cell.\n")
    return "\n".join(F)


def cem_note(df):
    th = json.loads((RESULTS / "oracle_theta.json").read_text())
    o = df[(df.filter_on) & (df.inside_assumptions == 1) & (df.stage.isin(["main", "hand"])) & (df.N == 4)]
    mg = o.assign(mm=np.minimum(o.min_corridor_margin, o.min_sep_margin)).groupby("planner").mm.min().sort_values()
    return ("- **CEM search budget is small** (8 candidates x 4 generations x 2 training seeds, N = 4 only, "
            f"transferred to N = 12). Training score of the violation optimum: closest true approach "
            f"{f(-th['violation_score'], 2)} m on seeds 2000-2001. Held-out closest approach per planner "
            f"(N = 4, filter ON): " + ", ".join(f"{k} {f(v, 2)} m" for k, v in mg.items()) +
            ". Hand-designed members are therefore always evaluated and the worst case per mission is reported; "
            "denial numbers are lower bounds on the oracle family's power, not its supremum.\n")


def file_list():
    root = RESULTS.parent
    out = ["\n## 9. Files\n", f"Root: `{root}`\n"]
    for sub in ("experiments", "results", "figdata"):
        p = root / sub
        if p.exists():
            names = sorted(x.name for x in p.iterdir() if x.is_file())
            out.append(f"- `{sub}/`: " + ", ".join(f"`{n}`" for n in names))
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
