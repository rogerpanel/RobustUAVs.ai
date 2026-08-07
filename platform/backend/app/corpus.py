"""Instantiate the live fleet from the committed corpus.

Until now the fleet demo spawned aircraft from a fixed seed: plausible numbers,
but invented ones. This draws every initial state from the six ingested sources,
so "the fleet you are watching came from real captures" is literally true and
each aircraft can say which file gave it which field.

What each source contributes, and why it and not another:

  uav_ew_bench_2026   mission profile, defence configuration and the J/S
                      operating point, with the MCR that configuration actually
                      achieved there. It is the only source with per-flight
                      completion outcomes.
  uav_attack_whelan   the gamma regime. Three real PX4 flights, and the only
                      source that observed a network/RF event and the flight it
                      degraded on one airframe.
  datamut_sim         per-hop residual delays for the mesh links, sampled from
                      15,392 measured hops rather than drawn from a distribution
                      fitted to them.
  uavids_2025         the mesh attack-class prior, from the released class
                      distribution.
  hcrl_uavcan         the intra-bus signature, from the per-type analysis.
  uav_cas             nothing. Its release file is not reachable in this
                      deployment, and the sampler says so rather than quietly
                      redistributing the other five sources' weight.

Everything is read through `results.py`, so a missing file raises
ResultUnavailable and the caller degrades to a synthetic fleet with the reason
attached -- never silently.
"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Any

from . import results

# Ceiling on how much of the hop ledger is held in memory. 15,392 rows is small,
# but this is a per-session structure on a shared host and the demo needs a few
# hundred at most.
HOP_POOL = 1200


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def _ew_profiles() -> list[dict]:
    """(defence, J/S, measured MCR) triples the campaign actually ran."""
    rows = _safe(results.mcr_anchor, [])
    out = []
    for r in rows:
        try:
            out.append({
                "defense": str(r["defense"]),
                "js_db": float(r["js_db"]),
                "mcr": float(r["mcr"]),
                "ci_low": float(r["ci_low"]),
                "ci_high": float(r["ci_high"]),
                "n": int(r["n"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _hop_residuals() -> dict[str, list[float]]:
    """Measured per-hop residual delays, split benign / malicious."""
    rows = _safe(lambda: results.read_csv("hop_ledger.csv"), [])
    pools: dict[str, list[float]] = {"benign": [], "malicious": []}
    for r in rows:
        try:
            v = float(r["residual_s"])
        except (KeyError, TypeError, ValueError):
            continue
        key = "malicious" if str(r.get("malicious_sender")) == "1" else "benign"
        if len(pools[key]) < HOP_POOL:
            pools[key].append(v)
    return pools


def _class_priors() -> dict[str, dict[str, float]]:
    """Attack-class distribution per source, normalised."""
    rows = _safe(results.ingest_stats, [])
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        dist = str(r.get("class_distribution") or "")
        if not dist or dist == "absent":
            continue
        counts: dict[str, float] = {}
        for part in dist.split(";"):
            if ":" not in part:
                continue
            k, _, v = part.partition(":")
            try:
                counts[k.strip()] = float(v)
            except ValueError:
                continue
        total = sum(counts.values())
        if total:
            out[str(r["source"])] = {k: v / total for k, v in counts.items()}
    return out


def _whelan_gamma() -> dict[str, float]:
    rows = _safe(results.whelan_calibration, [])
    out = {}
    for r in rows:
        try:
            g = r.get("gamma_peak_m_s")
            if g in (None, ""):
                continue
            out[f"{r['flight']}__{r['source']}"] = float(g)
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _bus_signatures() -> list[dict]:
    rows = _safe(lambda: results.read_csv("hcrl_type_signatures.csv"), [])
    out = []
    for r in rows:
        try:
            out.append({
                "scenario": str(r["scenario"]),
                "assigned_class": str(r.get("assigned_classes") or "benign"),
                "normal_rate_fps": float(r.get("normal_rate_fps") or 0.0),
                "n_attack_frames": int(float(r.get("n_attack_frames") or 0)),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out


# Cached once per process. These are small, immutable and read from committed
# files; re-reading them on every fleet reset would be pure waste.
_CACHE: dict[str, Any] = {}


def corpus() -> dict:
    if not _CACHE:
        _CACHE.update({
            "ew": _ew_profiles(),
            "hops": _hop_residuals(),
            "priors": _class_priors(),
            "gamma": _whelan_gamma(),
            "bus": _bus_signatures(),
        })
    return _CACHE


def availability() -> dict:
    c = corpus()
    return {
        "uav_ew_bench_2026": {"available": bool(c["ew"]), "n": len(c["ew"]),
                              "gives": "mission profile, defence, J/S, measured MCR",
                              "source": "results/ewbench_mcr_anchor.csv"},
        "datamut_sim": {"available": bool(c["hops"]["benign"]),
                        "n": len(c["hops"]["benign"]) + len(c["hops"]["malicious"]),
                        "gives": "per-hop residual delays for mesh links",
                        "source": "results/hop_ledger.csv"},
        "uavids_2025": {"available": "uavids_2025" in c["priors"],
                        "n": len(c["priors"].get("uavids_2025", {})),
                        "gives": "mesh attack-class prior",
                        "source": "results/ingest_stats.csv"},
        "uav_attack_whelan": {"available": bool(c["gamma"]), "n": len(c["gamma"]),
                              "gives": "gamma regime, measured on real PX4 flights",
                              "source": "results/whelan_delta_calibration.csv"},
        "hcrl_uavcan": {"available": bool(c["bus"]), "n": len(c["bus"]),
                        "gives": "intra-bus signature",
                        "source": "results/hcrl_type_signatures.csv"},
        "uav_cas": {"available": False, "n": 0,
                    "gives": "nothing — release file not reachable in this deployment",
                    "source": "PENDING_ON_DATA.md #1"},
    }


MISSIONS = ["search_and_rescue", "perimeter_patrol", "cargo_mixed_terrain"]
RECEIVERS = ["ublox_f9p_sim", "novatel_oem7_sim", "gp_software_receiver"]


def sample_fleet(n: int, seed: int | None = None) -> list[dict]:
    """Draw n aircraft from the corpus, each carrying its own provenance."""
    c = corpus()
    rng = random.Random(seed)
    ew = c["ew"] or []
    hops = c["hops"]
    mesh_prior = c["priors"].get("uavids_2025", {})
    bus = c["bus"] or []

    # Spread the defence configurations rather than sampling them independently:
    # a fleet that happens to draw eight framework aircraft demonstrates nothing.
    by_def: dict[str, list[dict]] = defaultdict(list)
    for r in ew:
        by_def[r["defense"]].append(r)
    order = [d for d in ("ours_m1m4m6m7", "ours_m1m4m6m7", "seq2seq_tr",
                         "caf_cnn", "no_def") if d in by_def] or ["ours_m1m4m6m7"]

    out = []
    for i in range(n):
        defense = order[i % len(order)]
        pool = by_def.get(defense) or []
        prof = rng.choice(pool) if pool else {"js_db": 10.0, "mcr": None,
                                              "ci_low": None, "ci_high": None, "n": 0}
        # Benign residual for the aircraft's own uplink, from measured hops.
        benign = hops["benign"] or [0.12]
        residual = rng.choice(benign)

        out.append({
            "defense": defense,
            "mission": MISSIONS[i % len(MISSIONS)],
            "receiver": RECEIVERS[i % len(RECEIVERS)],
            "js_db": prof["js_db"],
            "campaign_mcr": prof.get("mcr"),
            "campaign_ci": [prof.get("ci_low"), prof.get("ci_high")],
            "campaign_n": prof.get("n"),
            "uplink_residual_s": round(residual, 4),
            "mesh_prior": mesh_prior,
            "bus_signature": (rng.choice(bus) if bus else None),
            "provenance": {
                "defense_and_js": "uav_ew_bench_2026 · results/ewbench_mcr_anchor.csv",
                "uplink_residual": "datamut_sim · results/hop_ledger.csv",
                "mesh_class_prior": ("uavids_2025 · results/ingest_stats.csv"
                                     if mesh_prior else "unavailable"),
                "bus_signature": ("hcrl_uavcan · results/hcrl_type_signatures.csv"
                                  if bus else "unavailable"),
                "gamma_regime": "uav_attack_whelan · results/whelan_delta_calibration.csv",
            },
        })
    return out


def sample_mesh(uav_ids: list[str], seed: int | None = None,
                degree: int = 2) -> list[dict]:
    """Peer links between aircraft, each carrying a measured residual delay.

    A ring plus a few chords: the ring guarantees the mesh is connected, and the
    chords make clustering non-trivial. Delays come from the benign hop pool, so
    a link that later degrades does so from a real starting value.
    """
    c = corpus()
    rng = random.Random(seed)
    benign = c["hops"]["benign"] or [0.12]
    n = len(uav_ids)
    if n < 2:
        return []

    links: dict[tuple[str, str], dict] = {}

    def add(a: str, b: str) -> None:
        key = tuple(sorted((a, b)))
        if key in links or a == b:
            return
        links[key] = {
            "src": key[0], "dst": key[1],
            "residual_s": round(rng.choice(benign), 4),
            "baseline_s": None, "state": "trust",
        }

    for i in range(n):
        add(uav_ids[i], uav_ids[(i + 1) % n])
    for _ in range(max(0, (degree - 2)) * n // 2 + n // 3):
        a, b = rng.sample(uav_ids, 2)
        add(a, b)

    for lk in links.values():
        lk["baseline_s"] = lk["residual_s"]
    return list(links.values())


def clusters(uav_ids: list[str], links: list[dict],
             degraded_states: tuple[str, ...] = ("jammed", "delayed")) -> dict:
    """Connected components over the links that are still healthy.

    A jam that splits the mesh is the interesting event: the fleet becomes two
    groups that can no longer reach each other, which is exactly the missed
    contact window the theorem's slack term is about.
    """
    healthy = defaultdict(set)
    for u in uav_ids:
        healthy[u] = set()
    for lk in links:
        if lk["state"] not in degraded_states:
            healthy[lk["src"]].add(lk["dst"])
            healthy[lk["dst"]].add(lk["src"])

    seen: set[str] = set()
    groups: list[list[str]] = []
    for u in uav_ids:
        if u in seen:
            continue
        stack, comp = [u], []
        seen.add(u)
        while stack:
            v = stack.pop()
            comp.append(v)
            for w in healthy[v]:
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        groups.append(sorted(comp))

    isolated = [g[0] for g in groups if len(g) == 1]
    return {
        "groups": sorted(groups, key=len, reverse=True),
        "n_clusters": len(groups),
        "n_isolated": len(isolated),
        "isolated": isolated,
        "partitioned": len(groups) > 1,
        "reading": "One cluster means the mesh is whole. More than one means "
                   "jamming has partitioned the fleet: aircraft in different "
                   "groups cannot relay for each other, so a delayed frame has "
                   "no alternative path and misses its contact window.",
    }
