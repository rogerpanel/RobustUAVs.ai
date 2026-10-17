# Paper II codebook (v1.0, frozen 2026-10-07)

The unit of coding is a **guarantee**, which is the main formal or statistical claim a paper proves, certifies or estimates about a learned component, or about a system that contains one. Code one row per paper, for its headline guarantee. If a paper has two independent headline guarantees, code the one in its abstract.

Every field is a closed vocabulary. Write exactly one value unless the field says "list".

| Field | Values | Rule |
|---|---|---|
| `tier` | `A` / `B` | **A**: the paper evaluates its guarantee on a perception, estimation, navigation, planning or control task of an autonomous vehicle (air, ground, sea, or a standard vehicle benchmark such as ACC, quadrotor, ACAS Xu, TaxiNet, Cityscapes, F1/10, Highway-env). **B**: a method anchor evaluated only on generic benchmarks (MNIST, CIFAR, ImageNet, ModelNet, gridworld, Atari, pendulum without a vehicle). |
| `component` | `perception` / `estimation` / `control` / `planning` / `end2end` | The learned component the guarantee is about. Image classifiers, detectors and segmenters count as `perception`. A closed loop whose learned part is a vision network counts as `perception`. A closed loop whose learned part maps state to action counts as `control`. |
| `scope` | `in` / `tr` / `op` / `pop` | What the guarantee quantifies over. **in**: inputs in a neighbourhood or input set of one point, or one input region; includes per-step action certificates. **tr**: trajectories over a bounded horizon from an initial set, under disturbance; includes reach-sets and Lyapunov/barrier certificates over a domain. **op**: one complete operation or mission, or a runtime property enforced on every execution (Simplex, shields, runtime verification of a mission spec). **pop**: a distribution of inputs, environments or operations (generalisation, failure probability, reliability per demand or per hour). |
| `modality` | `A` / `Ac` / `P` / `E` / `X` | **A**: ∀, deterministic and sound. **Ac**: ∀, but with confidence 1−α over the *certifier's own* randomness (randomized smoothing, Monte Carlo certification). **P**: probability bound over the *environment or data* distribution (PAC, conformal, statistical model checking, scenario). **E**: bound on an expectation or average. **X**: ∃, meaning counterexamples or falsification, which can refute only. |
| `perturbation` | `norm` / `semantic` / `patch` / `disturbance` / `distribution` / `poisoning` / `none` | The threat or uncertainty model the guarantee is robust to. `disturbance` is a bounded additive process or sensor disturbance in the dynamics. `distribution` is natural sampling variation or shift. |
| `lifts` | list from `L_dyn` `L_hor` `L_gen` `L_op` `L_rate` `L_conc` `L_sup` `L_mon` `none` | Arguments the paper itself uses to carry a guarantee to a larger scope or a different modality. **L_dyn**: Lipschitz, Grönwall, contraction or reachability through a plant model. **L_hor**: horizon or re-anchoring to cover a whole operation. **L_gen**: generative, abstraction or contract surrogate standing in for the real sensor. **L_op**: operational profile weighting of per-input robustness. **L_rate**: per-input or per-demand probability converted to a rate per hour or per operation. **L_conc**: concentration, PAC, conformal or scenario argument from samples. **L_sup**: support or ODD containment, meaning "the deployment stays inside the certified set". **L_mon**: runtime monitor with switching to a fallback. |
| `assumption` | `U` / `S` / `SE` / `SEC` | The status of the assumption that the paper's main lift needs. **U**: not stated. **S**: stated. **SE**: stated, and evidence is supplied for it in the paper (a measurement, a validation set, a test). **SEC**: stated, evidenced, and the evidence carries a confidence level that enters the final guarantee. If `lifts=none`, code the status of the paper's main modelling assumption (for example, the plant model). |
| `evidence` | `proof` / `measured` / `simulated` / `modelled` | The strongest evidence class behind the headline number. `proof` means a sound certificate computed on the actual model. `measured` means real-world data. `simulated` means a simulator or benchmark environment. `modelled` means an analytical model only. |

**Decision rules**

1. Randomized-smoothing confidence is `Ac`, never `P`.
2. Falsification and counterexample search are `X`, even when they use sampling. A zero-failure sampling campaign whose confidence enters the claim is `P`.
3. If a certificate over a domain is checked by sampling, and the sampling enters the claim, add `L_conc`.
4. A competition report inherits the scope of its benchmark category.
5. For a runtime-assurance architecture, use `scope=op` and `modality=A` when the paper proves a safety theorem conditional on the monitor, and list `L_mon`.
6. When in doubt between two scopes, choose the smaller one and flag it in `note`.

**v1.1 additions (after the pilot; frozen before the full study)**

7. *Rule CLR-1.* If a closed-loop reachability result is computed only from an initial-state set, with no disturbance or noise input, code `perturbation=none`. Use `disturbance` only when the dynamics carry an explicit bounded disturbance or noise term.
8. *Rule PIL-1.* If a perception-in-the-loop result ranges over a generator's latent space, code `perturbation=semantic`. If it ranges over a perception error set that is estimated from data, code `distribution`.
9. *Rule COMP-1.* A learned trajectory or intent predictor counts as `estimation`.
