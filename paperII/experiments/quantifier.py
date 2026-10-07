#!/usr/bin/env python3
"""Quantifier types, the lift graph, and transfer soundness (Paper II, Sec. III).

A guarantee or an assurance objective is typed by a *state* (scope, modality):

  scope    in   : all perturbations of one input (or one input region)
           tr   : all disturbances along trajectories over a bounded horizon
           op   : one complete operation / every execution
           popd : a distribution of demands (inputs, environments, operations)
           poph : a rate per flight hour
  modality A    : for-all, deterministic and sound
           Ac   : for-all with confidence 1-alpha over the certifier's own coins
           P    : probability bound over the environment / data distribution
           E    : bound on an expectation (average)
           X    : existential (counterexample / falsification): refutes only

A *lift* is a typed edge between states.  Every edge emits obligations, and each
obligation has an evidence kind.  Transfer from a guarantee class to an
objective is computed as a least-obligation path (Dijkstra with unit weights).
Nothing in this file is data: it is the calculus.  The data are the codings in
../corpus and the objective corpus.

Stdlib only.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

SCOPES = ["in", "tr", "op", "popd", "poph"]
MODALITIES = ["A", "Ac", "P", "E", "X"]

# --------------------------------------------------------------------------
# Obligations: what a lift asks the assurance case to evidence.
#   kind: 'proof'        -- discharged by a sound argument on the artefact
#         'model'        -- a modelling claim about the plant/estimator
#         'statistical'  -- needs samples from the deployment distribution
#         'operational'  -- needs operational data (exposure, profile)
#         'architectural'-- needs a design/independence argument
# --------------------------------------------------------------------------
OBLIGATIONS = {
    "O_alpha": ("accept the certifier's failure probability alpha", "proof"),
    "O_lip":   ("Lipschitz constant / plant-model error bound over the operating region", "model"),
    "O_hor":   ("horizon or re-anchoring covers the whole operation", "model"),
    "O_cov":   ("surrogate (generator, abstraction, contract) covers the real sensor", "statistical"),
    "O_prof":  ("operational profile of inputs and per-cell robustness over the ODD", "statistical"),
    "O_iid":   ("samples exchangeable with deployment, or a bounded shift", "statistical"),
    "O_odd":   ("deployment stays inside the certified set (ODD containment)", "statistical"),
    "O_dep":   ("temporal dependence and exposure model (per demand -> per hour)", "statistical"),
    "O_mcov":  ("monitor coverage (recall) on hazardous inputs", "statistical"),
    "O_lat":   ("switching latency keeps the state recoverable", "model"),
    "O_rec":   ("recovery controller verified on the recoverable set", "proof"),
    "O_ind":   ("monitor independent of the monitored channel", "architectural"),
    "O_thr":   ("perturbation model covers the objective's hazard", "architectural"),
}
STATISTICAL = {k for k, (_, kind) in OBLIGATIONS.items() if kind in ("statistical",)}

# lift -> obligations it implies when a *paper* uses it (for intrinsic deficits)
LIFT_OBLIGATIONS = {
    "L_dyn": ["O_lip"], "L_hor": ["O_hor"], "L_gen": ["O_cov"], "L_op": ["O_prof"],
    "L_rate": ["O_dep"], "L_conc": ["O_iid"], "L_sup": ["O_odd"],
    "L_mon": ["O_mcov", "O_lat", "O_rec", "O_ind"],
}


@dataclass(frozen=True)
class Edge:
    src: tuple
    dst: tuple
    lift: str
    obligations: tuple


def _edges() -> list[Edge]:
    E = []
    add = lambda s, d, l, o: E.append(Edge(s, d, l, tuple(o)))
    for s in ("in", "tr", "op"):
        add((s, "Ac"), (s, "A"), "L_alpha", ["O_alpha"])
    add(("in", "A"), ("tr", "A"), "L_dyn", ["O_lip"])
    add(("tr", "A"), ("op", "A"), "L_hor", ["O_hor"])
    add(("tr", "P"), ("op", "P"), "L_hor", ["O_hor"])
    add(("in", "A"), ("popd", "P"), "L_op", ["O_prof"])
    add(("in", "P"), ("popd", "P"), "L_op", ["O_prof"])
    add(("op", "A"), ("popd", "P"), "L_sup", ["O_odd"])
    add(("op", "P"), ("popd", "P"), "L_id", [])          # P per operation is a popd statement
    add(("popd", "P"), ("poph", "P"), "L_rate", ["O_dep"])
    for s in ("popd", "poph"):
        add((s, "P"), (s, "E"), "L_weak", [])           # tail bound on failure -> mean
    for m in ("A", "P"):
        add(("in", m), ("op", "P"), "L_mon", ["O_mcov", "O_lat", "O_rec", "O_ind"])
    return E


EDGES = _edges()

# --------------------------------------------------------------------------
# Hazard coverage: which perturbation models cover which objective hazards.
#   N = natural variation and failures, Adv = adversarial, B = both
# --------------------------------------------------------------------------
COVERS = {"norm": {"Adv"}, "patch": {"Adv"}, "semantic": {"Adv"}, "poisoning": {"Adv"},
          "disturbance": {"N"}, "distribution": {"N"}, "none": set()}


def hazard_covered(perturbation: str, hazard: str) -> bool:
    need = {"N"} if hazard == "N" else {"Adv"} if hazard == "Adv" else {"N", "Adv"}
    return need <= COVERS.get(perturbation, set())


@dataclass
class Transfer:
    verdict: str                     # 'D' discharge, 'L' lift needed, 'X' category error
    lifts: list = field(default_factory=list)
    obligations: list = field(default_factory=list)

    @property
    def k(self) -> int:
        return len(self.obligations)


def shortest_path(src: tuple, dst: tuple):
    """Least-obligation path from state src to state dst; None if unreachable."""
    if src == dst:
        return [], []
    dist = {src: 0}
    prev = {}
    pq = [(0, SCOPES.index(src[0]), src)]
    while pq:
        d, _, u = heapq.heappop(pq)
        if u == dst:
            break
        if d > dist.get(u, 1 << 30):
            continue
        for e in EDGES:
            if e.src != u:
                continue
            nd = d + len(e.obligations) + 1e-3      # tie-break: fewer hops
            if nd < dist.get(e.dst, 1 << 30):
                dist[e.dst] = nd
                prev[e.dst] = e
                heapq.heappush(pq, (nd, SCOPES.index(e.dst[0]), e.dst))
    if dst not in prev:
        return None
    path, u = [], dst
    while u != src:
        e = prev[u]
        path.append(e)
        u = e.src
    path.reverse()
    return [e.lift for e in path], [o for e in path for o in e.obligations]


def transfer(g_state: tuple, g_pert: str, o_state: tuple, o_hazard: str) -> Transfer:
    p = shortest_path(g_state, o_state)
    if p is None:
        return Transfer("X")
    lifts, obl = p
    obl = list(dict.fromkeys(obl))
    if not hazard_covered(g_pert, o_hazard):
        obl.append("O_thr")
    lifts = [l for l in lifts if l not in ("L_id", "L_weak")]
    return Transfer("D" if not obl else "L", lifts, obl)


def check_no_free_modality() -> list:
    """Proposition 2 (no modality for free), checked exhaustively on the graph:
    every reachable path from a non-P state to a P state carries at least one
    statistical obligation.  Returns the list of violating (src,dst) pairs."""
    bad = []
    states = [(s, m) for s in SCOPES for m in MODALITIES]
    for src in states:
        if src[1] in ("P", "E"):
            continue
        for dst in states:
            if dst[1] != "P":
                continue
            p = shortest_path(src, dst)
            if p is None:
                continue
            if not (set(p[1]) & STATISTICAL):
                bad.append((src, dst))
    return bad


def check_monotone_scope() -> list:
    """No edge lowers the scope: lifts move guarantees towards larger objects."""
    return [e for e in EDGES if SCOPES.index(e.dst[0]) < SCOPES.index(e.src[0])]


if __name__ == "__main__":
    assert not check_monotone_scope()
    assert not check_no_free_modality(), check_no_free_modality()
    print("edges:", len(EDGES))
    for src in [("in", "Ac"), ("tr", "A"), ("op", "A"), ("popd", "P"), ("op", "X"), ("popd", "E")]:
        for dst in [("op", "A"), ("popd", "P"), ("poph", "P")]:
            print(src, "->", dst, shortest_path(src, dst))
    print("no-free-modality: OK; scope monotone: OK")
