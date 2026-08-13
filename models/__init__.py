"""Navigation-defense models for the composed guarantee.

Two subpackages:

- `uav_defense/` — the AUTHORITATIVE Phase-A reference implementation, ported
  verbatim from the dissertation code (github.com/rogerpanel/cv, branch
  prior report branch, package `uav_defense`). This is the code
  behind the robustidps.ai /uav/certification dashboard and the Ch.6
  `run_phase_a.sh` pipeline. Contains the real CT-TGNN on the GNSS graph
  (models/ct_tgnn_gnss.py), MambaShield, the CAF-CNN + Seq2Seq-Transformer
  baselines, the attack suite, and the Gronwall and randomised-smoothing
  certificates (defenses/lipschitz.py, defenses/smoothing.py) that
  certificates/engine.py wires into the composition.

- `legacy_ridps_demo/` — the earlier robustidps.ai *network-IDS demo* modules,
  kept only for provenance. These operate on flow features, NOT the UAV
  autonomy graph; do not use them for navigation certification. File names here
  use the CORRECTED method mapping (see below).

Method mapping (dissertation Ch.6 Table tab:uav_mapping, AUTHORITATIVE — it
differs from the robustidps.ai demo README, whose M-numbers were stale):

    M1  CT-TGNN      multiscale swarm dynamics on A(t)      Lipschitz (Thm 6.1)
    M1b SDE-TGNN     EW/wind/sensor stochastics            Fokker-Planck
    M2  FedLLM-API   dronehub federation, 30% Byzantine    (eps,delta)-DP (Thm 6.2)
    M3  TripleE      mission/waypoint/component graphs     EWC
    M4  MambaShield  long telemetry streams, onboard SoC   PAC-Bayes (Thm 6.3)
    M5  S-Trans.     Bayesian visual attention             ELBO
    M6  UC-HGP       go/no-go gate under OOD sensor modes  ECE 0.078
    M7  FedGTD       Stackelberg game vs adaptive jammer   MWU regret (Thm 6.4)

Phase-A headline stack = M1 + M4 + M6 + M7 (CT-TGNN + MambaShield + UC-HGP +
FedGTD). This resolves the earlier open question: M7 is FedGTD (Stackelberg/MWU
policy-mixing defender). The four defended-stack certificates are Gronwall (M1),
PAC-Bayes (M4), the go/no-go ECE gate (M6), and MWU regret (M7), plus randomised
smoothing as the statistical complement.
"""
