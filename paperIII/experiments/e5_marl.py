#!/usr/bin/env python3
"""E5 -- MARL study (RQ1, RQ3), with the R1 (scale), R2 (baselines) and
R9 (sensitivity) extensions of the runbook.

Parameter-shared actor (decentralised execution, one categorical over
{KEEP, IDLE, k-th nearest task} per agent) and a centralised critic (own
observation plus the fleet mean), trained with PPO (MAPPO-style). Methods:

  ours        projection layer in the ENVIRONMENT (SE placement); the policy is
              trained on its proposal; reward = certified coverage - lam_dev*deviation
  ours_nodev  same, lam_dev = 0 (ablation of the deviation penalty)
  mask        invalid-action masking per agent (rho_i <= alpha_j), conflicts by
              first claimant; no fleet-level projection. This is the factored
              shield of ElSayed-Aly et al. 2021 trained with PPO.
  lagrangian  certificate observed, no projection; reward = nominal coverage -
              lambda * violations, lambda by dual ascent (in-expectation limit)
  blind       certificate NOT observed, no projection, nominal reward
R2 baselines (same environment, same budget of environment steps):
  pid_lag     PID-Lagrangian PPO (Stooke et al. 2020), parameter shared
  mappo_lag   MAPPO-Lagrangian with a separate cost critic and cost advantage
              (the SafePO formulation), cost limit 0.005 per agent-step
  mappo_lag0  the same with cost limit 0
  qmix        QMIX (Rashid et al. 2018): shared agent Q-network, monotonic
              hypernetwork mixer, double-Q targets, certified-coverage reward
  qmix_mask   QMIX with the per-agent eligibility mask in acting and in targets
Learned policies are also evaluated with the projection added at deployment
("+proj"). Non-learned references: heuristic+proj, gnp (tightest fit,
re-solved every epoch), fixed_margin (design-time 1 s dead-reckoning budget),
cbba (consensus-based auction, bundle length 1, feasibility in the bundle).

Usage: python3 e5_marl.py --method ours --seed 0 [--updates 150]
       python3 e5_marl.py --references
R1:    python3 e5_marl.py --method ours --seed 0 --N 48 --B 4 --outdir e5_marl_N48
R9:    python3 e5_marl.py --method ours --seed 0 --lam-dev 0.1 --tag ldev0.1 --outdir r9
R3:    python3 e5_marl.py --method ours --seed 0 --process trace --outdir e5_marl_trace
Outputs: results/<outdir>/<method>[-<tag>]_s<seed>_{train,eval}.csv
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from certcmdp.certificate import OUT, KAPPA, THETA_BENIGN, ThreatProfile  # noqa: E402
from certcmdp.env import CertSwarm, EnvConfig, IDLE  # noqa: E402

RES = OUT / "e5_marl"
RES.mkdir(parents=True, exist_ok=True)
torch.set_num_threads(1)

METHODS = {
    "ours":       dict(blind=False, alloc="project", reward="cert", lam_dev=0.05, mask=False, lag=False),
    "ours_nodev": dict(blind=False, alloc="project", reward="cert", lam_dev=0.0, mask=False, lag=False),
    "mask":       dict(blind=False, alloc="mask", reward="cert", lam_dev=0.0, mask=True, lag=False),
    "lagrangian": dict(blind=False, alloc="none", reward="nom", lam_dev=0.0, mask=False, lag=True),
    "blind":      dict(blind=True, alloc="none", reward="nom", lam_dev=0.0, mask=False, lag=False),
    # R2
    "pid_lag":    dict(blind=False, alloc="none", reward="nom", lam_dev=0.0, mask=False, lag="pid"),
    "mappo_lag":  dict(blind=False, alloc="none", reward="nom", lam_dev=0.0, mask=False, lag="critic"),
    "mappo_lag0": dict(blind=False, alloc="none", reward="nom", lam_dev=0.0, mask=False, lag="critic",
                       cost_limit=0.0),
    "qmix":       dict(blind=False, alloc="none", reward="cert", lam_dev=0.0, mask=False, lag=False,
                       learner="qmix"),
    "qmix_mask":  dict(blind=False, alloc="mask", reward="cert", lam_dev=0.0, mask=True, lag=False,
                       learner="qmix"),
}
COST_LIMIT = 0.005       # violations per agent-step allowed in expectation (Lagrangian)
FIXED_MARGIN_RHO = KAPPA * (THETA_BENIGN + 1.0)   # design-time: benign + 1 s dead reckoning
PID_GAINS = (10.0, 1.0, 10.0)   # Kp, Ki, Kd for pid_lag            [assumption]
CBBA_DIST_W = 1.0 / 500.0       # CBBA score = value - w * distance [assumption]
K_ATTN = 16                     # tasks visible to the attention actor
J_ATTN = 4                      # nearest jammers visible to the attention actor


class Actor(nn.Module):
    def __init__(self, d, a, keep_bias=3.0):
        super().__init__()
        self.f = nn.Sequential(nn.Linear(d, 128), nn.Tanh(), nn.Linear(128, 128), nn.Tanh(),
                               nn.Linear(128, a))
        # sticky prior: an untrained allocator should mostly keep its task
        with torch.no_grad():
            self.f[-1].bias.zero_()
            self.f[-1].bias[0] = keep_bias

    def forward(self, x):
        return self.f(x)


class AttnActor(nn.Module):
    """Permutation-invariant pointer actor for large fleets (R1, N >= 48).

    Input: compact observation (own state, K nearest task slots of 8 features,
    J nearest jammers, count profile). The context attends over the task slots;
    each slot gets a logit from [slot embedding, attended context], and KEEP /
    IDLE get logits from the context. Input size is independent of M."""

    def __init__(self, k=K_ATTN, ctx_dim=5 + 2 * J_ATTN + 4, keep_bias=3.0, h=64):
        super().__init__()
        self.k, self.ctx_dim = k, ctx_dim
        self.slot = nn.Sequential(nn.Linear(8, h), nn.Tanh(), nn.Linear(h, h))
        self.ctx = nn.Sequential(nn.Linear(ctx_dim, h), nn.Tanh(), nn.Linear(h, h))
        self.att = nn.MultiheadAttention(h, 4, batch_first=True)
        self.ptr = nn.Sequential(nn.Linear(2 * h, h), nn.Tanh(), nn.Linear(h, 1))
        self.spec = nn.Sequential(nn.Linear(h, h), nn.Tanh(), nn.Linear(h, 2))
        with torch.no_grad():
            self.spec[-1].bias.zero_()
            self.spec[-1].bias[0] = keep_bias

    def forward(self, x):
        sh = x.shape[:-1]
        x = x.reshape(-1, x.shape[-1])
        own, slots, rest = x[:, :5], x[:, 5:5 + 8 * self.k], x[:, 5 + 8 * self.k:]
        s = self.slot(slots.reshape(-1, self.k, 8))
        c = self.ctx(torch.cat([own, rest], -1))
        a, _ = self.att(c[:, None, :], s, s)
        c2 = c + a[:, 0]
        lp = self.ptr(torch.cat([s, c2[:, None, :].expand_as(s)], -1)).squeeze(-1)
        out = torch.cat([self.spec(c2), lp], -1)
        return out.reshape(*sh, -1)


class Critic(nn.Module):
    def __init__(self, d):
        super().__init__()
        self.f = nn.Sequential(nn.Linear(2 * d, 128), nn.Tanh(), nn.Linear(128, 128), nn.Tanh(),
                               nn.Linear(128, 1))

    def forward(self, x):            # x: (..., N, d)
        g = x.mean(-2, keepdim=True).expand_as(x)
        return self.f(torch.cat([x, g], -1)).squeeze(-1)


class QNet(nn.Module):
    """Shared per-agent utility network for QMIX (no keep prior: epsilon-greedy)."""

    def __init__(self, d, a):
        super().__init__()
        self.f = nn.Sequential(nn.Linear(d, 128), nn.ReLU(), nn.Linear(128, 128), nn.ReLU(),
                               nn.Linear(128, a))

    def forward(self, x):
        return self.f(x)


class Mixer(nn.Module):
    """QMIX monotonic mixer; state = fleet mean and max of agent observations."""

    def __init__(self, n, sd, e=32):
        super().__init__()
        self.n, self.e = n, e
        self.w1 = nn.Sequential(nn.Linear(sd, 64), nn.ReLU(), nn.Linear(64, n * e))
        self.b1 = nn.Linear(sd, e)
        self.w2 = nn.Sequential(nn.Linear(sd, 64), nn.ReLU(), nn.Linear(64, e))
        self.v = nn.Sequential(nn.Linear(sd, e), nn.ReLU(), nn.Linear(e, 1))

    def forward(self, q, s):         # q: (B, N), s: (B, sd)
        w1 = torch.abs(self.w1(s)).view(-1, self.n, self.e)
        h = torch.relu(torch.bmm(q[:, None, :], w1)[:, 0] + self.b1(s))
        w2 = torch.abs(self.w2(s))
        return (h * w2).sum(-1) + self.v(s)[:, 0]


def mix_state(o):
    return torch.cat([o.mean(-2), o.max(-2).values], -1)


N_SPECIAL = 2            # action 0 = KEEP current task, 1 = IDLE, 2+j = task j


def compact_obs(o, cfg):
    """(B,N,D) full observation -> (B,N,5+8K+2J+4) for the attention actor."""
    M, J = cfg.M, cfg.n_jammers
    own = o[..., :5]
    slots = o[..., 5:5 + 8 * M].reshape(*o.shape[:-1], M, 8)[..., :K_ATTN, :]
    jr = o[..., 5 + 8 * M:5 + 8 * M + 2 * J].reshape(*o.shape[:-1], J, 2)
    order = np.argsort(np.linalg.norm(jr, axis=-1), axis=-1, kind="stable")[..., :J_ATTN]
    jr = np.take_along_axis(jr, order[..., None], axis=-2)
    if jr.shape[-2] < J_ATTN:
        pad = np.full(jr.shape[:-2] + (J_ATTN - jr.shape[-2], 2), 2.0, np.float32)
        jr = np.concatenate([jr, pad], -2)
    prof = o[..., -4:]
    return np.concatenate([own, slots.reshape(*o.shape[:-1], -1),
                           jr.reshape(*o.shape[:-1], -1), prof], -1).astype(np.float32)


def action_mask(env, n_slots=None):
    """(B,N,n_slots+2) eligibility mask. IDLE always allowed; KEEP allowed iff the
    agent holds a task it is still eligible for (or holds none: KEEP = IDLE)."""
    el = env.rho[:, :, None] <= env.alpha[:, None, :]
    held = env.assign >= 0
    bidx = np.arange(env.B)[:, None]
    keep_ok = ~held | (env.rho <= np.where(held, env.alpha[bidx, np.maximum(env.assign, 0)], np.inf))
    el = np.take_along_axis(el, env.order, axis=2)          # slot order (k-th nearest)
    if n_slots is not None:
        el = el[..., :n_slots]
    return np.concatenate([keep_ok[..., None], np.ones(el.shape[:2] + (1,), bool), el], -1)


def to_task(a, env):
    """Action 2+k means the k-th nearest task in the agent's own ordering
    (env.order is refreshed by every env.obs() call, which precedes acting)."""
    a = np.asarray(a)
    slot = np.clip(a - N_SPECIAL, 0, env.cfg.M - 1)
    task = np.take_along_axis(env.order, slot[..., None], axis=2)[..., 0]
    return np.where(a == 0, env.assign, np.where(a == 1, IDLE, task))


class Obs:
    """Observation pipeline shared by training and evaluation."""

    def __init__(self, cfg, env_cfg, actor_kind):
        self.blind, self.mask, self.kind, self.ec = cfg["blind"], cfg["mask"], actor_kind, env_cfg
        self.n_slots = K_ATTN if actor_kind == "attn" else env_cfg.M

    def __call__(self, env):
        o = env.obs(blind=self.blind)
        return compact_obs(o, self.ec) if self.kind == "attn" else o

    def dim(self, env):
        if self.kind == "attn":
            return 5 + 8 * K_ATTN + 2 * J_ATTN + 4
        return env.obs_dim

    def amask(self, env):
        return action_mask(env, self.n_slots if self.kind == "attn" else None)


def run_policy_episode(env, actor, cfg, alloc, ob, greedy=True):
    env.reset()
    S = {k: [] for k in ("r_cert", "r_nom", "viol", "exposure", "switches", "cov_ratio")}
    for t in range(env.cfg.horizon):
        with torch.no_grad():
            lg = actor(torch.as_tensor(ob(env)))
            if cfg["mask"]:
                lg = lg.masked_fill(~torch.as_tensor(ob.amask(env)), -1e9)
            a = lg.argmax(-1) if greedy else torch.distributions.Categorical(logits=lg).sample()
        prop = to_task(a.numpy(), env)
        ex = env.allocate(prop, alloc)
        _, info, _ = env.step(ex)
        record(S, info, env.cfg.N)
    return {k: float(np.mean(v)) for k, v in S.items()}


def record(S, info, N):
    S["r_cert"].append(info["r_cert"].mean())
    S["r_nom"].append(info["r_nom"].mean())
    S["viol"].append(info["viol"].mean() / N)
    S["exposure"].append(info["exposure"].mean() / N)
    S["switches"].append(info["switches"].mean() / N)
    S["cov_ratio"].append(np.mean(info["assigned_feasible"] / np.maximum(info["bound"], 1)))


def make_env_cfg(a):
    """EnvConfig from the CLI. Defaults reproduce the compact E5 study."""
    N = a.N
    M = a.M if a.M is not None else math.ceil(2 * N / 3)
    L = a.arena if a.arena is not None else 1000.0 * math.sqrt(N / 12)
    J = a.jammers if a.jammers is not None else max(2, round(2 * N / 12))
    tp = ThreatProfile()
    s = a.threat_scale
    tp = replace(tp, jam_rate=tp.jam_rate * s, relay_rate=tp.relay_rate * s,
                 fault_rate=tp.fault_rate * s)
    return EnvConfig(N=N, M=M, L=L, n_jammers=J, threat=tp, process=a.process)


def hp_from(a):
    return dict(lam_dev=getattr(a, "lam_dev", None), keep_bias=getattr(a, "keep_bias", None),
                cost_limit=getattr(a, "cost_limit", None), dual_step=getattr(a, "dual_step", None))


def write_csv(path, rows):
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def evaluate(method, name, seed, actor, cfg, ec, ob, eval_B, res, extra):
    rows = []
    allocs = [(cfg["alloc"], name)]
    if cfg["alloc"] != "project":
        allocs.append(("project", name + "+proj"))
    for alloc, nm in allocs:
        for es in range(3):
            ee = CertSwarm(eval_B, ec, seed=50000 + 97 * es)
            r = run_policy_episode(ee, actor, cfg, alloc, ob)
            rows.append({"method": nm, "train_seed": seed, "eval_seed": es, **r, **extra})
    write_csv(res / f"{name}_s{seed}_eval.csv", rows)
    torch.save(actor.state_dict(), res / f"{name}_s{seed}_actor.pt")


def train(method, seed, updates=150, B=16, rollout=150, env_cfg=None, res=RES, tag="",
          actor_kind="mlp", eval_B=16, hp=None):
    cfg = dict(METHODS[method])
    hp = {k: v for k, v in (hp or {}).items() if v is not None}
    if "lam_dev" in hp:
        cfg["lam_dev"] = hp["lam_dev"]
    if cfg.get("learner") == "qmix":
        return train_qmix(method, seed, updates, B, rollout, env_cfg, res, tag, eval_B)
    name = method + (f"-{tag}" if tag else "")
    torch.manual_seed(seed)
    np.random.seed(seed)
    ec = env_cfg or EnvConfig()
    env = CertSwarm(B, ec, seed=1000 + seed)
    N, M = env.cfg.N, env.cfg.M
    ob = Obs(cfg, ec, actor_kind)
    d = ob.dim(env)
    kb = hp.get("keep_bias", 3.0)
    if actor_kind == "attn":
        actor = AttnActor(keep_bias=kb)
        n_act = K_ATTN + N_SPECIAL
    else:
        actor = Actor(d, M + N_SPECIAL, keep_bias=kb)
        n_act = M + N_SPECIAL
    critic = Critic(d)
    params = list(actor.parameters()) + list(critic.parameters())
    ccritic = None
    if cfg["lag"] == "critic":
        ccritic = Critic(d)
        params += list(ccritic.parameters())
    opt = torch.optim.Adam(params, lr=3e-4)
    lam, lam_lr = 0.0, hp.get("dual_step", 1.0)
    cost_limit = hp.get("cost_limit", cfg.get("cost_limit", COST_LIMIT))
    pid_i, pid_prev = 0.0, None
    gamma, gae_l, clip, ent_c = 0.995, 0.95, 0.2, 0.003
    obs = env.reset()
    t_in_ep = 0
    log = []
    cum_viol = 0
    t0 = time.time()
    for u in range(updates):
        buf = {k: [] for k in ("obs", "act", "logp", "val", "rew", "mask", "done", "cost", "cval")}
        Sm = {k: [] for k in ("r_cert", "r_nom", "viol", "exposure", "switches", "cov_ratio")}
        costs = []
        for t in range(rollout):
            o = torch.as_tensor(ob(env))
            mk = torch.as_tensor(ob.amask(env)) if cfg["mask"] else None
            with torch.no_grad():
                lg = actor(o)
                if mk is not None:
                    lg = lg.masked_fill(~mk, -1e9)
                dist = torch.distributions.Categorical(logits=lg)
                a = dist.sample()
                lp = dist.log_prob(a)
                v = critic(o)
                cv = ccritic(o) if ccritic is not None else None
            prop = to_task(a.numpy(), env)
            ex = env.allocate(prop, cfg["alloc"])
            dev = ((ex != prop) & (prop >= 0)).mean(1) if cfg["alloc"] == "project" else 0.0
            _, info, done = env.step(ex)
            record(Sm, info, N)
            cum_viol += int(info["viol"].sum())
            base = info["r_cert"] if cfg["reward"] == "cert" else info["r_nom"]
            r = base - cfg["lam_dev"] * dev
            if cfg["lag"] in (True, "pid"):
                r = r - lam * info["cost"]
            if cfg["lag"]:
                costs.append(info["cost"].mean())
            buf["obs"].append(o); buf["act"].append(a); buf["logp"].append(lp); buf["val"].append(v)
            buf["rew"].append(torch.as_tensor(r, dtype=torch.float32))
            buf["cost"].append(torch.as_tensor(info["cost"], dtype=torch.float32))
            buf["cval"].append(cv)
            buf["mask"].append(mk if mk is not None else torch.ones(B, N, n_act, dtype=torch.bool))
            t_in_ep += 1
            dn = t_in_ep >= env.cfg.horizon
            buf["done"].append(torch.full((B,), float(dn)))
            if dn:
                env.reset(); t_in_ep = 0
        with torch.no_grad():
            o_last = torch.as_tensor(ob(env))
            last_v = critic(o_last)
            last_c = ccritic(o_last) if ccritic is not None else None
        T = rollout

        def gae(rews, vals, last):
            adv = torch.zeros(T, B, N)
            lastgae = torch.zeros(B, N)
            for t in reversed(range(T)):
                nv = last if t == T - 1 else vals[t + 1]
                nd = 1.0 - buf["done"][t][:, None]
                delta = rews[t][:, None] + gamma * nv * nd - vals[t]
                lastgae = delta + gamma * gae_l * nd * lastgae
                adv[t] = lastgae
            return adv, adv + torch.stack(vals)

        # GAE with a team reward broadcast to agents
        adv, ret = gae(buf["rew"], buf["val"], last_v)
        O = torch.stack(buf["obs"]).reshape(T * B, N, -1)
        A = torch.stack(buf["act"]).reshape(T * B, N)
        LP = torch.stack(buf["logp"]).reshape(T * B, N)
        MK = torch.stack(buf["mask"]).reshape(T * B, N, n_act)
        ADV = adv.reshape(T * B, N)
        RET = ret.reshape(T * B, N)
        ADV = (ADV - ADV.mean()) / (ADV.std() + 1e-8)
        if ccritic is not None:
            cadv, cret = gae(buf["cost"], buf["cval"], last_c)
            CADV = cadv.reshape(T * B, N)
            CADV = CADV - CADV.mean()          # centred, not scaled (SafePO)
            CRET = cret.reshape(T * B, N)
            ADV = (ADV - lam * CADV) / (1.0 + lam)
        idx = np.arange(T * B)
        for _ in range(4):
            np.random.shuffle(idx)
            for mb in np.array_split(idx, 4):
                lg = actor(O[mb]).masked_fill(~MK[mb], -1e9)
                dist = torch.distributions.Categorical(logits=lg)
                nlp = dist.log_prob(A[mb])
                ratio = torch.exp(nlp - LP[mb])
                s1 = ratio * ADV[mb]
                s2 = torch.clamp(ratio, 1 - clip, 1 + clip) * ADV[mb]
                pl = -torch.min(s1, s2).mean()
                vl = ((critic(O[mb]) - RET[mb]) ** 2).mean()
                if ccritic is not None:
                    vl = vl + ((ccritic(O[mb]) - CRET[mb]) ** 2).mean()
                ent = dist.entropy().mean()
                loss = pl + 0.5 * vl - ent_c * ent
                opt.zero_grad(); loss.backward()
                nn.utils.clip_grad_norm_(params, 0.5)
                opt.step()
        if cfg["lag"] in (True, "critic"):
            lam = max(0.0, lam + lam_lr * (float(np.mean(costs)) - cost_limit))
        elif cfg["lag"] == "pid":
            kp, ki, kd = PID_GAINS
            jc = float(np.mean(costs))
            e = jc - cost_limit
            pid_i = max(0.0, pid_i + ki * e)
            dterm = max(0.0, jc - pid_prev) if pid_prev is not None else 0.0
            pid_prev = jc
            lam = max(0.0, kp * e + pid_i + kd * dterm)
        row = {"update": u + 1, "env_steps": (u + 1) * rollout * B,
               **{k: float(np.mean(v)) for k, v in Sm.items()},
               "cum_violations": cum_viol, "lambda": lam, "wall_s": time.time() - t0}
        if env_cfg is not None:
            row["N"] = N
        log.append(row)
        if (u + 1) % 25 == 0:
            print(name, seed, {k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()},
                  flush=True)
    write_csv(res / f"{name}_s{seed}_train.csv", log)
    extra = {} if env_cfg is None else {"N": N, "eval_B": eval_B}
    evaluate(method, name, seed, actor, cfg, ec, ob, eval_B, res, extra)


def train_qmix(method, seed, updates, B, rollout, env_cfg, res, tag, eval_B):
    """QMIX with the same environment-step budget as the PPO methods."""
    cfg = METHODS[method]
    name = method + (f"-{tag}" if tag else "")
    torch.manual_seed(seed)
    np.random.seed(seed)
    rng = np.random.default_rng(seed)
    ec = env_cfg or EnvConfig()
    env = CertSwarm(B, ec, seed=1000 + seed)
    N, M = ec.N, ec.M
    ob = Obs(cfg, ec, "mlp")
    d, nA = ob.dim(env), M + N_SPECIAL
    q, qt = QNet(d, nA), QNet(d, nA)
    mix, mixt = Mixer(N, 2 * d), Mixer(N, 2 * d)
    qt.load_state_dict(q.state_dict()); mixt.load_state_dict(mix.state_dict())
    params = list(q.parameters()) + list(mix.parameters())
    opt = torch.optim.Adam(params, lr=5e-4)
    cap = 20000                              # fleet-transitions in the replay buffer
    RO = np.zeros((cap, N, d), np.float32); RO2 = np.zeros_like(RO)
    RA = np.zeros((cap, N), np.int64); RR = np.zeros(cap, np.float32)
    RM2 = np.ones((cap, N, nA), bool); RD = np.zeros(cap, np.float32)
    ptr, size = 0, 0
    gamma, batch, grad_steps, eps_end = 0.99, 128, 40, 0.05
    env.reset()
    t_in_ep, cum_viol, log, t0 = 0, 0, [], time.time()
    total = updates * rollout
    o = ob(env)
    mk = ob.amask(env) if cfg["mask"] else np.ones((B, N, nA), bool)
    for u in range(updates):
        Sm = {k: [] for k in ("r_cert", "r_nom", "viol", "exposure", "switches", "cov_ratio")}
        for t in range(rollout):
            step = u * rollout + t
            eps = max(eps_end, 1.0 - step / (0.5 * total) * (1.0 - eps_end))
            with torch.no_grad():
                qv = q(torch.as_tensor(o)).masked_fill(~torch.as_tensor(mk), -1e9)
            a = qv.argmax(-1).numpy()
            rnd = rng.random((B, N)) < eps
            if rnd.any():
                g = rng.random((B, N, nA)) * mk
                a = np.where(rnd, g.argmax(-1), a)
            prop = to_task(a, env)
            ex = env.allocate(prop, cfg["alloc"])
            _, info, _ = env.step(ex)
            record(Sm, info, N)
            cum_viol += int(info["viol"].sum())
            r = info["r_cert"] if cfg["reward"] == "cert" else info["r_nom"]
            t_in_ep += 1
            dn = t_in_ep >= ec.horizon
            o2 = ob(env)
            mk2 = ob.amask(env) if cfg["mask"] else np.ones((B, N, nA), bool)
            for b in range(B):
                RO[ptr], RO2[ptr], RA[ptr], RR[ptr] = o[b], o2[b], a[b], r[b]
                RM2[ptr], RD[ptr] = mk2[b], float(dn)
                ptr = (ptr + 1) % cap; size = min(size + 1, cap)
            if dn:
                env.reset(); t_in_ep = 0
                o2 = ob(env)
                mk2 = ob.amask(env) if cfg["mask"] else np.ones((B, N, nA), bool)
            o, mk = o2, mk2
        for _ in range(grad_steps):
            ix = rng.integers(0, size, batch)
            Ob, Ob2 = torch.as_tensor(RO[ix]), torch.as_tensor(RO2[ix])
            qa = q(Ob).gather(-1, torch.as_tensor(RA[ix])[..., None])[..., 0]
            with torch.no_grad():
                m2 = torch.as_tensor(RM2[ix])
                a2 = q(Ob2).masked_fill(~m2, -1e9).argmax(-1, keepdim=True)   # double Q
                q2 = qt(Ob2).gather(-1, a2)[..., 0]
                y = torch.as_tensor(RR[ix]) + gamma * (1 - torch.as_tensor(RD[ix])) * \
                    mixt(q2, mix_state(Ob2))
            loss = ((mix(qa, mix_state(Ob)) - y) ** 2).mean()
            opt.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(params, 10.0)
            opt.step()
        if (u + 1) % 2 == 0:
            qt.load_state_dict(q.state_dict()); mixt.load_state_dict(mix.state_dict())
        row = {"update": u + 1, "env_steps": (u + 1) * rollout * B,
               **{k: float(np.mean(v)) for k, v in Sm.items()},
               "cum_violations": cum_viol, "lambda": 0.0, "wall_s": time.time() - t0}
        if env_cfg is not None:
            row["N"] = N
        log.append(row)
        if (u + 1) % 25 == 0:
            print(name, seed, {k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()},
                  flush=True)
    write_csv(res / f"{name}_s{seed}_train.csv", log)
    extra = {} if env_cfg is None else {"N": N, "eval_B": eval_B}
    evaluate(method, name, seed, q, cfg, ec, ob, eval_B, res, extra)


def cbba_assign(env, b):
    """Consensus-based bundle algorithm, bundle length 1 (Choi, Brunet & How
    2009). On a connected network its consensus phase converges to the
    sequential greedy auction, which is what we compute: repeatedly award the
    highest-scoring feasible (agent, task) bid. Feasibility rho_i <= alpha_j is
    enforced inside the bundle, so no infeasible pair is ever bid."""
    rho, alpha, val = env.rho[b], env.alpha[b], env.value[b]
    d = np.linalg.norm(env.site[b][None, :, :] - env.pos[b][:, None, :], axis=-1)
    score = val[None, :] - CBBA_DIST_W * d
    keep = env.assign[b]
    ok = keep >= 0
    score[np.flatnonzero(ok), keep[ok]] += 0.25          # incumbent bonus [assumption]
    score = np.where(rho[:, None] <= alpha[None, :], score, -np.inf)
    out = np.full(env.cfg.N, IDLE, dtype=int)
    while np.isfinite(score).any():
        i, j = np.unravel_index(np.argmax(score), score.shape)
        out[i] = j
        score[i, :] = -np.inf
        score[:, j] = -np.inf
    return out


def references(ec=None, res=RES, eval_B=16):
    ec = ec or EnvConfig()
    rows = []
    names = ("heuristic+proj", "gnp", "fixed_margin", "heuristic_none", "cbba")
    for es in range(3):
        for name in names:
            env = CertSwarm(eval_B, ec, seed=50000 + 97 * es)
            env.reset()
            S = {k: [] for k in ("r_cert", "r_nom", "viol", "exposure", "switches", "cov_ratio")}
            for t in range(env.cfg.horizon):
                if name == "cbba":
                    ex = np.stack([cbba_assign(env, b) for b in range(env.B)])
                else:
                    d = np.linalg.norm(env.site[:, None] - env.pos[:, :, None], axis=-1)
                    if name == "fixed_margin":
                        d = np.where((FIXED_MARGIN_RHO <= env.alpha)[:, None, :], d, np.inf)
                    near = d.argmin(-1)
                    if name == "fixed_margin":
                        near = np.where(np.isfinite(d.min(-1)), near, IDLE)
                    prop = np.where(env.assign >= 0, env.assign, near)
                    mode = {"heuristic+proj": "project", "gnp": "gnp",
                            "fixed_margin": "fixed_margin", "heuristic_none": "none"}[name]
                    ex = env.allocate(prop, mode, design_rho=FIXED_MARGIN_RHO)
                _, info, _ = env.step(ex)
                record(S, info, env.cfg.N)
            rows.append({"method": name, "train_seed": -1, "eval_seed": es,
                         **{k: float(np.mean(v)) for k, v in S.items()}})
            print(rows[-1])
    if ec.N != 12 or eval_B != 16:
        for r in rows:
            r.update(N=ec.N, eval_B=eval_B)
    write_csv(res / "references_eval.csv", rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=list(METHODS))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--updates", type=int, default=150)
    ap.add_argument("--references", action="store_true")
    # R1 scale
    ap.add_argument("--N", type=int, default=12)
    ap.add_argument("--M", type=int, default=None, help="default ceil(2N/3)")
    ap.add_argument("--arena", type=float, default=None, help="default 1000*sqrt(N/12) m")
    ap.add_argument("--jammers", type=int, default=None, help="default max(2, round(2N/12))")
    ap.add_argument("--B", type=int, default=16, help="parallel fleets in training")
    ap.add_argument("--eval-B", type=int, default=16)
    ap.add_argument("--actor", choices=("mlp", "attn"), default="mlp")
    ap.add_argument("--outdir", default="e5_marl")
    ap.add_argument("--tag", default="")
    # R9 sensitivity
    ap.add_argument("--lam-dev", type=float, default=None)
    ap.add_argument("--keep-bias", type=float, default=None)
    ap.add_argument("--cost-limit", type=float, default=None)
    ap.add_argument("--dual-step", type=float, default=None)
    ap.add_argument("--threat-scale", type=float, default=1.0)
    # R3 measured-trace replay
    ap.add_argument("--process", choices=("synthetic", "trace"), default="synthetic")
    a = ap.parse_args()
    res = OUT / a.outdir
    res.mkdir(parents=True, exist_ok=True)
    default_env = (a.N == 12 and a.M is None and a.arena is None and a.jammers is None
                   and a.threat_scale == 1.0 and a.process == "synthetic")
    ec = None if default_env else make_env_cfg(a)
    if a.references:
        references(ec, res, a.eval_B)
    else:
        train(a.method, a.seed, a.updates, B=a.B, env_cfg=ec, res=res, tag=a.tag,
              actor_kind=a.actor, eval_B=a.eval_B, hp=hp_from(a))
