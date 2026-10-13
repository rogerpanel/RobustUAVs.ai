#!/usr/bin/env python3
"""E5 -- compact MARL study (RQ1, RQ3).

Parameter-shared actor (decentralised execution, one categorical over
{IDLE, task_1..task_M} per agent) and a centralised critic (own observation
plus the fleet mean), trained with PPO (MAPPO-style). Methods:

  ours        projection layer in the ENVIRONMENT (SE placement); the policy is
              trained on its proposal; reward = certified coverage - lam_dev*deviation
  ours_nodev  same, lam_dev = 0 (ablation of the deviation penalty)
  mask        invalid-action masking per agent (rho_i <= alpha_j), conflicts by
              first claimant; no fleet-level projection
  lagrangian  certificate observed, no projection; reward = nominal coverage -
              lambda * violations, lambda by dual ascent (in-expectation limit)
  blind       certificate NOT observed, no projection, nominal reward
Learned policies are also evaluated with the projection added at deployment
("+proj"). Non-learned references: heuristic+proj, gnp (tightest fit,
re-solved every epoch), fixed_margin (design-time 1 s dead-reckoning budget).

Usage: python3 e5_marl.py --method ours --seed 0 [--updates 150]
       python3 e5_marl.py --references
Outputs: results/e5_marl/<method>_s<seed>_{train,eval}.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from certcmdp.certificate import OUT, KAPPA, THETA_BENIGN  # noqa: E402
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
}
COST_LIMIT = 0.005       # violations per agent-step allowed in expectation (Lagrangian)
FIXED_MARGIN_RHO = KAPPA * (THETA_BENIGN + 1.0)   # design-time: benign + 1 s dead reckoning


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


class Critic(nn.Module):
    def __init__(self, d):
        super().__init__()
        self.f = nn.Sequential(nn.Linear(2 * d, 128), nn.Tanh(), nn.Linear(128, 128), nn.Tanh(),
                               nn.Linear(128, 1))

    def forward(self, x):            # x: (..., N, d)
        g = x.mean(-2, keepdim=True).expand_as(x)
        return self.f(torch.cat([x, g], -1)).squeeze(-1)


N_SPECIAL = 2            # action 0 = KEEP current task, 1 = IDLE, 2+j = task j


def action_mask(env):
    """(B,N,M+2) eligibility mask. IDLE always allowed; KEEP allowed iff the
    agent holds a task it is still eligible for (or holds none: KEEP = IDLE)."""
    el = env.rho[:, :, None] <= env.alpha[:, None, :]
    held = env.assign >= 0
    bidx = np.arange(env.B)[:, None]
    keep_ok = ~held | (env.rho <= np.where(held, env.alpha[bidx, np.maximum(env.assign, 0)], np.inf))
    el = np.take_along_axis(el, env.order, axis=2)          # slot order (k-th nearest)
    return np.concatenate([keep_ok[..., None], np.ones(el.shape[:2] + (1,), bool), el], -1)


def to_task(a, env):
    """Action 2+k means the k-th nearest task in the agent's own ordering
    (env.order is refreshed by every env.obs() call, which precedes acting)."""
    a = np.asarray(a)
    slot = np.clip(a - N_SPECIAL, 0, env.cfg.M - 1)
    task = np.take_along_axis(env.order, slot[..., None], axis=2)[..., 0]
    return np.where(a == 0, env.assign, np.where(a == 1, IDLE, task))


def run_policy_episode(env, actor, cfg, alloc, greedy=True):
    obs = env.reset()
    S = {k: [] for k in ("r_cert", "r_nom", "viol", "exposure", "switches", "cov_ratio")}
    for t in range(env.cfg.horizon):
        with torch.no_grad():
            lg = actor(torch.as_tensor(env.obs(blind=cfg["blind"])))
            if cfg["mask"]:
                lg = lg.masked_fill(~torch.as_tensor(action_mask(env)), -1e9)
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


def train(method, seed, updates=150, B=16, rollout=150):
    cfg = METHODS[method]
    torch.manual_seed(seed)
    np.random.seed(seed)
    env = CertSwarm(B, EnvConfig(), seed=1000 + seed)
    N, M = env.cfg.N, env.cfg.M
    actor, critic = Actor(env.obs_dim, M + N_SPECIAL), Critic(env.obs_dim)
    opt = torch.optim.Adam(list(actor.parameters()) + list(critic.parameters()), lr=3e-4)
    lam, lam_lr = 0.0, 1.0
    gamma, gae_l, clip, ent_c = 0.995, 0.95, 0.2, 0.003
    obs = env.reset()
    t_in_ep = 0
    log = []
    cum_viol = 0
    t0 = time.time()
    for u in range(updates):
        buf = {k: [] for k in ("obs", "act", "logp", "val", "rew", "mask", "done")}
        Sm = {k: [] for k in ("r_cert", "r_nom", "viol", "exposure", "switches", "cov_ratio")}
        costs = []
        for t in range(rollout):
            o = torch.as_tensor(env.obs(blind=cfg["blind"]))
            mk = torch.as_tensor(action_mask(env)) if cfg["mask"] else None
            with torch.no_grad():
                lg = actor(o)
                if mk is not None:
                    lg = lg.masked_fill(~mk, -1e9)
                dist = torch.distributions.Categorical(logits=lg)
                a = dist.sample()
                lp = dist.log_prob(a)
                v = critic(o)
            prop = to_task(a.numpy(), env)
            ex = env.allocate(prop, cfg["alloc"])
            dev = ((ex != prop) & (prop >= 0)).mean(1) if cfg["alloc"] == "project" else 0.0
            _, info, done = env.step(ex)
            record(Sm, info, N)
            cum_viol += int(info["viol"].sum())
            base = info["r_cert"] if cfg["reward"] == "cert" else info["r_nom"]
            r = base - cfg["lam_dev"] * dev
            if cfg["lag"]:
                r = r - lam * info["cost"]
                costs.append(info["cost"].mean())
            buf["obs"].append(o); buf["act"].append(a); buf["logp"].append(lp); buf["val"].append(v)
            buf["rew"].append(torch.as_tensor(r, dtype=torch.float32))
            buf["mask"].append(mk if mk is not None else torch.ones(B, N, M + N_SPECIAL, dtype=torch.bool))
            t_in_ep += 1
            d = t_in_ep >= env.cfg.horizon
            buf["done"].append(torch.full((B,), float(d)))
            if d:
                env.reset(); t_in_ep = 0
        with torch.no_grad():
            last_v = critic(torch.as_tensor(env.obs(blind=cfg["blind"])))
        # GAE with a team reward broadcast to agents
        T = rollout
        adv = torch.zeros(T, B, N)
        lastgae = torch.zeros(B, N)
        for t in reversed(range(T)):
            nv = last_v if t == T - 1 else buf["val"][t + 1]
            nd = 1.0 - buf["done"][t][:, None]
            delta = buf["rew"][t][:, None] + gamma * nv * nd - buf["val"][t]
            lastgae = delta + gamma * gae_l * nd * lastgae
            adv[t] = lastgae
        ret = adv + torch.stack(buf["val"])
        O = torch.stack(buf["obs"]).reshape(T * B, N, -1)
        A = torch.stack(buf["act"]).reshape(T * B, N)
        LP = torch.stack(buf["logp"]).reshape(T * B, N)
        MK = torch.stack(buf["mask"]).reshape(T * B, N, M + N_SPECIAL)
        ADV = adv.reshape(T * B, N)
        RET = ret.reshape(T * B, N)
        ADV = (ADV - ADV.mean()) / (ADV.std() + 1e-8)
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
                ent = dist.entropy().mean()
                loss = pl + 0.5 * vl - ent_c * ent
                opt.zero_grad(); loss.backward()
                nn.utils.clip_grad_norm_(list(actor.parameters()) + list(critic.parameters()), 0.5)
                opt.step()
        if cfg["lag"]:
            lam = max(0.0, lam + lam_lr * (float(np.mean(costs)) - COST_LIMIT))
        row = {"update": u + 1, "env_steps": (u + 1) * rollout * B,
               **{k: float(np.mean(v)) for k, v in Sm.items()},
               "cum_violations": cum_viol, "lambda": lam, "wall_s": time.time() - t0}
        log.append(row)
        if (u + 1) % 25 == 0:
            print(method, seed, {k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()},
                  flush=True)
    with (RES / f"{method}_s{seed}_train.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(log[0])); w.writeheader(); w.writerows(log)
    # evaluation on held-out seeds, with and without the projection at deployment
    rows = []
    allocs = [(cfg["alloc"], method)]
    if cfg["alloc"] != "project":
        allocs.append(("project", method + "+proj"))
    for alloc, name in allocs:
        for es in range(3):
            ee = CertSwarm(16, EnvConfig(), seed=50000 + 97 * es)
            r = run_policy_episode(ee, actor, cfg, alloc)
            rows.append({"method": name, "train_seed": seed, "eval_seed": es, **r})
    with (RES / f"{method}_s{seed}_eval.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    torch.save(actor.state_dict(), RES / f"{method}_s{seed}_actor.pt")


def references():
    rows = []
    for es in range(3):
        for name in ("heuristic+proj", "gnp", "fixed_margin", "heuristic_none"):
            env = CertSwarm(16, EnvConfig(), seed=50000 + 97 * es)
            env.reset()
            S = {k: [] for k in ("r_cert", "r_nom", "viol", "exposure", "switches", "cov_ratio")}
            for t in range(env.cfg.horizon):
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
    with (RES / "references_eval.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=list(METHODS))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--updates", type=int, default=150)
    ap.add_argument("--references", action="store_true")
    a = ap.parse_args()
    if a.references:
        references()
    else:
        train(a.method, a.seed, a.updates)
