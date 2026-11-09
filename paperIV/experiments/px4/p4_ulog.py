"""Offline detectors and mission metrics from one PX4 ULog (Paper IV SITL study).

Everything is computed on the mission clock t = (time since arming) - BEN_TOFF,
over the window [0, BEN_T_END]. The attacker does not react to alarms, so an
alarm computed offline from the log equals the alarm an online monitor would
raise; "detected late counts as detected" carries over from the paper.

Statistics (one per mission; a detector alarms iff its statistic > threshold):
  S1   D1 jump rule: largest horizontal jump between consecutive valid fixes,
       after removing the motion predicted by the reported GNSS velocity.
  S2   D2 (PX4's own chi-square gate): EKF2's GNSS horizontal-position test
       ratio (estimator_aid_src_gnss_pos, max over N/E), taken as the minimum
       over 3 consecutive fusion attempts, maximised over the mission.
  S3   D3 SAVIOR-style CUSUM: observer driven by the commanded acceleration
       (vehicle_local_position_setpoint), no wind model, corrected by GNSS with
       the gains of the reduced-order model; max over N/E.
  S4   D4 IMU-GNSS invariant: specific force rotated to NED with the attitude,
       gravity added, double integrated; quadratic-fit curvature of GNSS minus
       the integral over 4 s; minimum over 5 consecutive fixes; max over N/E.
  SA   anchor gate: largest normalised innovation (chi-square, 2 dof) of the
       trusted fixes (estimator_aid_src_ev_pos).
  Ssat D_sat: longest run (s) with any rotor at its upper or lower limit.
  Sstk PX4 stock: number of EKF2 GNSS rejections, position resets to GNSS and
       GNSS fusion timeouts in the window (alarm iff > 0 is reported as well).
Metrics:
  e(t)    true cross-track error: east ground-truth position minus the line
          (north axis through the take-off point), 20 Hz on [0, T_END].
  maxdev  sup |e| over the window; maxdev_after: sup |e| after attack onset.
  d(t)    the offset the attacker applied (logged by the patched GPS module).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

R_E = 6371000.0
DTG = 0.1                   # GNSS period (10 Hz)
CONSEC_CHI2, CONSEC_INV, INV_WINDOW_S, CUSUM_KAPPA = 3, 5, 4.0, 1.0
OBS_DRAG = 0.0              # PX4's setpoint is a kinematic acceleration: the observer has no drag term
GRID_DT = 0.05


def _inv_weights(n, dt_g):
    t = (np.arange(n) - (n - 1) / 2.0) * dt_g
    X = np.stack([np.ones(n), t, 0.5 * t * t], 1)
    return np.linalg.pinv(X)[2]


def _topic(ul, name, multi=0):
    for d in ul.data_list:
        if d.name == name and d.multi_id == multi:
            return d.data
    return None


def _param(ul, name, default=None):
    return ul.initial_parameters.get(name, default)


def _quat_rot(q, v):
    """Rotate body vectors v (n,3) by unit quaternions q (n,4) [w,x,y,z] (body -> NED)."""
    w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    R = np.empty((len(q), 3, 3))
    R[:, 0, 0] = 1 - 2 * (y * y + z * z); R[:, 0, 1] = 2 * (x * y - w * z); R[:, 0, 2] = 2 * (x * z + w * y)
    R[:, 1, 0] = 2 * (x * y + w * z); R[:, 1, 1] = 1 - 2 * (x * x + z * z); R[:, 1, 2] = 2 * (y * z - w * x)
    R[:, 2, 0] = 2 * (x * z - w * y); R[:, 2, 1] = 2 * (y * z + w * x); R[:, 2, 2] = 1 - 2 * (x * x + y * y)
    return np.einsum("nij,nj->ni", R, v)


def extract(path, keep_series=True):
    """path: a .ulg file, or an object with data_list / initial_parameters (tests)."""
    if hasattr(path, "data_list"):
        ul, name = path, "synthetic"
    else:
        from pyulog import ULog
        ul, name = ULog(str(path)), Path(path).name
    out = {"ulog": name, "ok": False, "why": ""}
    vs = _topic(ul, "vehicle_status")
    if vs is None:
        out["why"] = "no vehicle_status"; return out, None
    armed_times = vs["armed_time"][vs["armed_time"] > 0]
    if not len(armed_times):
        out["why"] = "never armed"; return out, None
    t_arm = int(armed_times[0])
    toff = float(_param(ul, "BEN_TOFF", 15.0)); tend = float(_param(ul, "BEN_T_END", 60.0))
    mt = lambda ts: (np.asarray(ts, float) - t_arm) * 1e-6 - toff
    out.update(t_arm_us=t_arm, toff=toff, tend=tend)

    # ---------------- ground truth and the line
    gt = _topic(ul, "vehicle_local_position_groundtruth")
    if gt is None:
        out["why"] = "no ground truth"; return out, None
    tg = mt(gt["timestamp"]); xg, yg = gt["x"].astype(float), gt["y"].astype(float)
    pre = tg <= -toff + 0.5                                   # at arming: take-off point
    x0 = float(np.median(xg[pre])) if pre.any() else float(xg[0])
    y0 = float(np.median(yg[pre])) if pre.any() else float(yg[0])
    grid = np.arange(0.0, tend + 1e-9, GRID_DT)
    if tg.max() < tend - 0.5:
        out["why"] = f"log ends at mission time {tg.max():.1f} s"
    e = np.interp(grid, tg, yg - y0)                          # line = north axis through take-off point
    along = np.interp(grid, tg, xg - x0)
    out["maxdev"] = float(np.max(np.abs(e)))
    out["along_m_end"] = float(along[-1])
    cr = (grid >= 10.0) & (grid <= 50.0)
    out["along_speed_mps"] = float(np.polyfit(grid[cr], along[cr], 1)[0])

    # ---------------- attack offset (patched GPS module) and anchors
    dv = _topic(ul, "debug_vect")
    d_grid = np.zeros_like(grid); t0_att = math.inf; n_anchor_pub = 0
    if dv is not None:
        names = ["".join(chr(int(dv[f"name[{i}]"][k])) for i in range(10) if int(dv[f"name[{i}]"][k]) > 0)
                 for k in range(len(dv["timestamp"]))]
        names = np.array(names)
        a = names == "p4atk"
        if a.any():
            ta = mt(dv["timestamp"][a]); da = dv["x"][a].astype(float)
            d_grid = np.interp(grid, ta, da, left=0.0, right=da[-1])
            nz = np.nonzero(np.abs(da) > 1e-6)[0]
            t0_att = float(ta[nz[0]]) if len(nz) else math.inf
        n_anchor_pub = int((names == "p4anc").sum())
    t0_param = float(_param(ul, "ATK_T0", 1e6)) if int(_param(ul, "ATK_EN", 0)) == 1 else math.inf
    t_on = min(t0_param, t0_att) if math.isfinite(t0_param) else t0_att
    out["attack_t0"] = t0_param if math.isfinite(t0_param) else None
    out["dmax_applied"] = float(np.max(np.abs(d_grid)))
    after = grid >= (t_on if math.isfinite(t_on) else np.inf)
    out["maxdev_after"] = float(np.max(np.abs(e[after]))) if after.any() else 0.0
    out["n_anchor_pub"] = n_anchor_pub

    # ---------------- GNSS fixes (vehicle_gps_position, full rate under the replay profile)
    gp = _topic(ul, "vehicle_gps_position")
    if gp is None:
        gp = _topic(ul, "sensor_gps")
    lat0 = float(_param(ul, "SIH_LOC_LAT0", 0)) * 1e-7; lon0 = float(_param(ul, "SIH_LOC_LON0", 0)) * 1e-7
    tz = mt(gp["timestamp"])
    lat = gp["lat"].astype(float) * (1e-7 if np.abs(gp["lat"]).max() > 1e3 else 1.0)
    lon = gp["lon"].astype(float) * (1e-7 if np.abs(gp["lon"]).max() > 1e3 else 1.0)
    zn = np.radians(lat - lat0) * R_E - x0
    ze = np.radians(lon - lon0) * R_E * math.cos(math.radians(lat0)) - y0
    vn, ve = gp["vel_n_m_s"].astype(float), gp["vel_e_m_s"].astype(float)
    valid = gp["fix_type"] >= 3
    w = (tz >= 0) & (tz <= tend)
    # D1: velocity-compensated jump between consecutive valid fixes
    idx = np.nonzero(valid)[0]
    S1 = 0.0
    if len(idx) > 1:
        i0, i1 = idx[:-1], idx[1:]
        dt = tz[i1] - tz[i0]
        jn = (zn[i1] - zn[i0]) - 0.5 * (vn[i1] + vn[i0]) * dt
        je = (ze[i1] - ze[i0]) - 0.5 * (ve[i1] + ve[i0]) * dt
        jj = np.hypot(jn, je)
        sel = (tz[i1] >= 0) & (tz[i1] <= tend) & (dt < 0.5)    # consecutive fixes only (not across outages)
        S1 = float(jj[sel].max()) if sel.any() else 0.0
    out["S1"] = S1

    # ---------------- D2: EKF2's own GNSS position gate
    ag = _topic(ul, "estimator_aid_src_gnss_pos")
    S2, n_rej = 0.0, 0
    if ag is not None:
        ta2 = mt(ag["timestamp_sample"])
        tr = np.maximum(ag["test_ratio[0]"], ag["test_ratio[1]"]).astype(float)
        m2 = (ta2 >= 0) & (ta2 <= tend) & (ag["fusion_enabled"] > 0)
        trw = tr[m2]
        if len(trw) >= CONSEC_CHI2:
            run = np.lib.stride_tricks.sliding_window_view(trw, CONSEC_CHI2).min(1)
            S2 = float(run.max())
        n_rej = int((ag["innovation_rejected"][m2] > 0).sum())
    out["S2"] = S2

    # ---------------- PX4 stock alarms
    # position resets: increments of EKF2's horizontal reset counter (vehicle_local_position.xy_reset_counter);
    # GNSS fusion stops: cs_gps going from true to false (estimator_status_flags)
    lp = _topic(ul, "vehicle_local_position")
    n_reset = 0
    if lp is not None and "xy_reset_counter" in lp:
        tl = mt(lp["timestamp"]); c = lp["xy_reset_counter"].astype(int)
        inc = np.diff(c) % 256
        ml = (tl[1:] >= 0) & (tl[1:] <= tend)
        n_reset = int((inc[ml] > 0).sum())
    sf = _topic(ul, "estimator_status_flags")
    n_stop = 0
    if sf is not None and "cs_gps" in sf:
        tf = mt(sf["timestamp"]); g = sf["cs_gps"].astype(int)
        mf = (tf[1:] >= 0) & (tf[1:] <= tend)
        n_stop = int(((g[:-1] == 1) & (g[1:] == 0))[mf].sum())
    out["n_gnss_rejected"] = n_rej
    out["n_pos_reset"] = n_reset
    out["n_gnss_fusion_stops"] = n_stop
    out["Sstk"] = float(n_rej + n_reset)

    # ---------------- D3: commanded-acceleration observer + CUSUM (N and E)
    sp = _topic(ul, "vehicle_local_position_setpoint")
    S3 = 0.0
    if sp is not None:
        ts = mt(sp["timestamp"])
        S3 = 0.0
        for ax, z in ((0, zn), (1, ze)):
            acc = np.nan_to_num(sp[f"acceleration[{ax}]"].astype(float))
            vel0 = np.interp(0.0, tz, vn if ax == 0 else ve)
            pos0 = np.interp(0.0, tz, z)
            po, vo, g3, s3 = pos0, vel0, 0.0, 0.0
            k_fix = np.nonzero(valid & w)[0]
            t_prev = 0.0
            for k in k_fix:
                tk = tz[k]
                # propagate on the setpoint samples between fixes
                seg = (ts > t_prev) & (ts <= tk)
                tt = np.concatenate([[t_prev], ts[seg], [tk]])
                aa = np.concatenate([[np.interp(t_prev, ts, acc)], acc[seg]])
                for j in range(len(aa)):
                    h = tt[j + 1] - tt[j]
                    vo = vo + (aa[j] - OBS_DRAG * vo) * h
                    po = po + vo * h
                t_prev = tk
                r3 = z[k] - po
                g3 = max(0.0, g3 + r3 * r3 - (1.0 + CUSUM_KAPPA))
                s3 = max(s3, g3)
                po = po + 0.3 * r3
                vo = vo + 0.2 * r3 / DTG
            S3 = max(S3, s3)
    out["S3"] = float(S3)

    # ---------------- D4: IMU-GNSS kinematic invariant (N and E)
    sc = _topic(ul, "sensor_combined"); att = _topic(ul, "vehicle_attitude")
    S4 = 0.0
    if sc is not None and att is not None:
        tsc = mt(sc["timestamp"])
        m4 = (tsc >= -1.0) & (tsc <= tend + 0.1)
        tsc = tsc[m4]
        f_b = np.stack([sc[f"accelerometer_m_s2[{i}]"][m4] for i in range(3)], 1).astype(float)
        tq = mt(att["timestamp"])
        q = np.stack([np.interp(tsc, tq, att[f"q[{i}]"].astype(float)) for i in range(4)], 1)
        q /= np.linalg.norm(q, axis=1, keepdims=True)
        a_ned = _quat_rot(q, f_b) + np.array([0.0, 0.0, 9.80665])
        # average onto the 20 Hz grid, then integrate
        g20 = np.arange(-1.0, tend + 0.1, GRID_DT)
        a20 = np.stack([np.interp(g20, tsc, a_ned[:, i]) for i in range(2)], 1)
        n_inv = int(round(INV_WINDOW_S / DTG)); w_inv = _inv_weights(n_inv, DTG)
        for ax, z in ((0, zn), (1, ze)):
            vi = np.cumsum(a20[:, ax]) * GRID_DT
            pi = np.cumsum(vi) * GRID_DT
            k_fix = np.nonzero(valid & (tz >= -1.0) & (tz <= tend))[0]
            rho = z[k_fix] - np.interp(tz[k_fix], g20, pi)
            tk = tz[k_fix]
            # windows of n_inv consecutive fixes without a gap (an outage restarts the window)
            gap = np.concatenate([[True], np.diff(tk) > 0.5])
            seg_id = np.cumsum(gap)
            c2 = np.zeros(len(rho))
            for sgi in np.unique(seg_id):
                ii = np.nonzero(seg_id == sgi)[0]
                if len(ii) >= n_inv:
                    win = np.lib.stride_tricks.sliding_window_view(rho[ii], n_inv)
                    c2[ii[n_inv - 1:]] = np.abs(win @ w_inv)
            inwin = tk >= 0
            c2w = c2[inwin]
            if len(c2w) >= CONSEC_INV:
                S4 = max(S4, float(np.lib.stride_tricks.sliding_window_view(c2w, CONSEC_INV).min(1).max()))
    out["S4"] = float(S4)

    # ---------------- anchor gate
    ae = _topic(ul, "estimator_aid_src_ev_pos")
    SA, n_anchor_fused = 0.0, 0
    if ae is not None:
        tae = mt(ae["timestamp_sample"])
        fused = (ae["fused"] > 0) & (tae >= 0) & (tae <= tend + 0.5)
        if fused.any():
            nis = (ae["innovation[0]"] ** 2 / ae["innovation_variance[0]"]
                   + ae["innovation[1]"] ** 2 / ae["innovation_variance[1]"]).astype(float)
            SA = float(nis[fused].max())
            n_anchor_fused = int(fused.sum())
    out["SA"] = SA
    out["n_anchor_fused"] = n_anchor_fused

    # ---------------- saturation
    ca = _topic(ul, "control_allocator_status")
    Ssat = 0.0
    if ca is not None:
        tca = mt(ca["timestamp"]); mca = (tca >= 0) & (tca <= tend)
        sat = np.zeros(mca.sum(), bool)
        for i in range(4):
            col = f"actuator_saturation[{i}]"
            if col in ca:
                sat |= np.abs(ca[col][mca]) >= 2
        tt = tca[mca]
        best = run_start = None
        longest = 0.0
        for k in range(len(sat)):
            if sat[k] and run_start is None:
                run_start = tt[k]
            if (not sat[k] or k == len(sat) - 1) and run_start is not None:
                longest = max(longest, tt[k] - run_start); run_start = None
        Ssat = float(longest)
    out["Ssat"] = Ssat

    # ---------------- navigation state: failsafes, landing, disarm inside the window
    tvs = mt(vs["timestamp"])
    inw = (tvs >= 0) & (tvs <= tend)
    out["failsafe"] = bool((vs["failsafe"][inw] > 0).any()) if "failsafe" in vs else False
    out["disarmed_in_window"] = bool((vs["arming_state"][inw] != 2).any())
    out["nav_states"] = sorted(set(int(x) for x in vs["nav_state"][inw]))
    out["ok"] = out["why"] == ""
    series = None
    if keep_series:
        series = {"t": grid.astype(np.float32), "e": e.astype(np.float32), "d": d_grid.astype(np.float32),
                  "along": along.astype(np.float32)}
    return out, series


if __name__ == "__main__":
    import json
    for p in sys.argv[1:]:
        o, _ = extract(p)
        print(json.dumps(o, indent=1, default=str))
