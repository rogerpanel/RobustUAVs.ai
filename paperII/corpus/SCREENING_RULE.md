# Title/abstract screening rule (Paper II, S2)

Copied verbatim from the manuscript, Sec. IV-A ("Inclusion" and "Two tiers"),
so that every screener -- the two humans and the LLM third screener -- reads
the same rule. This file adds no criteria of its own; if the manuscript's rule
changes, this file must be re-copied and the change logged.

## Inclusion (Sec. IV-A, verbatim)

We include a paper if it states a formal, statistical or architectural
guarantee about a learned component, or about a system containing one, and if
the object its guarantee quantifies over can be identified. We exclude
empirical attack studies without a guarantee, guarantees about non-learned
components, and theses that duplicate a journal version.

## Two tiers (Sec. IV-A, verbatim)

The inclusion rule in our proposal required evaluation on an autonomous
vehicle. Applied literally, it would exclude the canonical verifiers that
define the guarantee classes, which are evaluated on image benchmarks. We
therefore code two tiers. Tier A contains guarantees evaluated on a vehicle
task, including standard vehicle benchmarks such as ACAS Xu, TaxiNet, adaptive
cruise control and quadrotors. Tier B contains method anchors evaluated only
on generic benchmarks. Both tiers are included.

## Screening convention

At the title/abstract stage, a record that might meet the rule is included
for full-text reading; uncertainty is resolved at full text, not here. A
record with no abstract is judged on its title and the same convention.
