# Response to Prof. Conti's assessment of Paper D

Source: assessment relayed via Federico Corò on the `paperD_v4_conti_corrected.tex`
draft. Result: `paper/paperD_v5.tex`, compiling with 0 errors and 0 undefined
references.

Every comment is answered below. The comments were about presentation, and the
revision is a presentation revision: no result, number, or claim changed.

---

## The comments, and what was done

### 1. *"'UAV security is studied as two disjoint problems.' I feel like this sentence reads poorly... I would rather say something like X is approached from two different points of view."*

Adopted verbatim in substance. The abstract now opens:

> The security of an unmanned aerial vehicle (UAV) is presently approached from
> two different points of view.

The Conclusion carried the same construction ("studied as two separate
problems") and has been rewritten to match.

### 2. *"'Network intrusion detection bounds what reaches the aircraft but says nothing about the flight;' ... it's not very clear what we are talking about ... as well as 'certified robustness' ... when we use a concept, it is good practice to make it clear to the reader before using it."*

This was the central failure and drove most of the rewrite. Both concepts are now
defined, in plain words, at the point of first use in the abstract:

> *Network intrusion detection* inspects the traffic carried by the aircraft's
> radio links and on-board buses and raises an alarm when that traffic looks
> malicious. *Certified robustness* proves that a navigation model's output
> cannot move by more than a fixed amount when its sensor input is perturbed by
> no more than a given magnitude.

Only after both are defined does the abstract say what each fails to do. The
same discipline was applied throughout: `operating point` is now defined at its
first appearance (in the contributions list) as "the threshold at which the
detector decides to raise an alarm", rather than several pages later.

### 3. *"Please check if 'airworthiness' is a good term to use here."*

**Prof. Conti's instinct was right, and this was a genuine misuse.**
Airworthiness is a specific term of art: the fitness of an aircraft type or
individual aircraft for safe flight, established through a certification
process. It is not a synonym for "the mission succeeded". The abstract used it
to mean the latter:

> ~~Neither answers the question that determines airworthiness: whether an
> attack that evades the detector still lets the mission complete.~~

That sentence is gone; the abstract now asks whether "the mission can still be
completed". A second loose use in the Discussion ("connect that choice to
airworthiness") is likewise replaced with "connect that choice to whether the
fleet completes its missions".

Two uses remain and are **correct**: both refer to DO-326A/ED-202A, whose actual
title is *Airworthiness Security Process Specification*. Naming the standard is
not the same as claiming the property, and those should stay.

### 4. *"'A two-layer schema promotes'... if the two-layer schema is a contribution of our paper... let's make it clearer... in this paper we propose a novel two-layer blabla."*

Adopted. The abstract now reads "We propose a two-layer schema whose unit of
analysis is the *cross-layer pairing*", with the contribution attributed
explicitly.

### 5. *"The rest of the abstract doesn't seem to read very well either... many concepts used in the sentences and taken for granted... what is a 'time-delay forwarding attack evading a detector at a given operating point'? And also a 'delay-to-position interface'?"*

The abstract was rewritten end to end. Both offending phrases are gone, replaced
by what they actually mean:

| Was | Now |
|---|---|
| "any time-delay forwarding attack evading a detector at a given operating point" | "an attacker who delays relayed messages by just less than the detector's threshold" |
| "the delay-to-position interface, calibrated on real GPS-spoofing and jamming flights, is an order of magnitude tighter than the kinematic worst case" | "one second of delayed navigation input costs about 1.4 m of position error, an order of magnitude less than a worst-case kinematic argument assumes" |
| "the residual attack budget saturates at the network's contact-window slack" | "the delay an attacker can hide does not grow without limit: it saturates at 4.84 s" |

The abstract is now two paragraphs: what the two viewpoints are and what neither
answers, then what we do about it.

### 6. *"'A modern autonomous UAV is a stack of trust boundaries.' ?"*

Replaced. The introduction now opens by naming the four interfaces concretely
and saying what each carries, rather than asserting a metaphor:

> An autonomous UAV is exposed to an adversary at four distinct interfaces.
> Commands reach it from a ground station over a command-and-control (C2) radio
> link. Peer aircraft in a swarm exchange position and status reports over a
> multi-hop mesh, in which each aircraft relays traffic for its neighbours. [...]

### 7. *"'What it has not produced is a way to reason across them.' very vague."*

Replaced with the specific question the paper answers:

> Our concern is a question that none of those defences is posed to answer:
> given that some attacks will get through, *what happens to the flight
> afterwards?*

### 8. *"'This gap is not academic.' ? especially placed like this at the beginning of a new paragraph."*

Removed. The paragraph now opens by stating why the question is not rhetorical
and immediately gives two concrete attack mechanisms, rather than announcing its
own importance.

### 9. *"'A two-layer schema and six validated adapters (§IV, §V)' what are the adapters?"*

An adapter is now defined where the term first appears, in the contribution
itself:

> An *adapter* is the program that reads one dataset in its native release
> format and emits records in that representation; we write one per dataset and
> verify that no source column is discarded.

### 10. *"Using colors for the text seems very unusual to me."*

Removed entirely from running text. `\layernet` and `\layerauto` were expanding
to bold coloured words in every paragraph and table cell that mentioned a layer;
they now expand to plain "network" and "autonomy". Colour survives only inside
the figures, where it distinguishes the two layers visually and is doing work.
Verified: zero `\textcolor` occurrences remain in body prose.

### 11. *"In Section IV, it's impossible to grasp a high-level description of the proposed schema."*

Section IV was reorganised into three subsections and given an **Overview** that
states the problem the schema solves before any record type appears, then
presents the three record kinds as a hierarchy of increasing interpretation:

> An **Event** is a single observation as its source recorded it [...] This
> layer is deliberately dumb: it asserts nothing beyond what the source file
> said. An **AttackWindow** is an interval of time during which one named attack
> was active [...] A **CrossLayerPairing** joins one network window to one
> autonomy window and asserts that the first *caused* the second. This is the
> only place in the schema where a causal claim is made [...]

The overview ends by naming the single idea to carry forward, so a reader who
stops there still has the design.

### 12. *"Figure 2, and figures in general, should be explicitly cited in the paper."*

Audited every float. Two figures were never referenced: `fig:schema` (Figure 2,
the one named) and `fig:chain` (the composition-chain diagram). Both now have
explicit in-text references that say what the reader should take from them.
**All 8 figures and all 9 tables are now cited at least once.**

### 13. *"The rest of the paper also seems to need improvement, primarily in its presentation."*

A pass over the whole manuscript for the classes of problem above:

- **Four sections opened directly into a subsection** with no orienting
  sentence, which is the same "cannot grasp the high level" problem as §IV.
  §II, §VIII and §X now open with a short roadmap naming what each subsection
  settles.
- **Rhetorical flourishes replaced with statements.** "the schema's conscience"
  → what the field actually records; "is the headline result, and it is
  deliberately parametric" → what the figure plots and why it is plotted twice;
  "the tell was recall rising" → "the symptom was recall increasing"; "The
  schema in one picture" → "Structure of the two-layer schema".
- **Self-referential process narrative removed.** A Discussion paragraph
  recounting two of our own measurement errors has been cut; the substance
  survives as one sentence in the Open Science section, where it belongs.

---

## What did not change

No result, number, figure, or claim. This revision is entirely about how the
work is presented.

## Page budget

The body (§I–§XIII) ends on page 14, essentially where the v4 draft ended: the
added definitions and roadmaps were paid for by cutting process narrative and
compressing the four-certificate walkthrough. That is still marginally over
NDSS's 13 pages excluding Ethics, references and appendices. Two levers remain,
neither of which costs clarity: switch to the official `ndss.cls`, which is more
compact than the IEEEtran configuration currently emulating it, or move the
worked end-to-end example in §X-C to the appendix.

## The judgement that is not mine to make

Prof. Conti's closing point is not a comment to be fixed:

> *"All in all, it seems to me that we are very far from an acceptable quality
> of presentation, particularly for NDSS. If we cannot improve it significantly
> [...] I would not submit it to NDSS."*

Every concrete comment above is addressed, and the abstract, introduction and
§IV are substantially different documents. Whether that clears his bar is his
call and Federico's, not something this revision can assert. The option he
raised — postponing to a later deadline and using the time for another
presentation pass — remains open on the merits, and the paper would not be worse
for it.
