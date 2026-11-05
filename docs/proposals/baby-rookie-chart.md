# Baby II → Rookie chart proposal

Proposal only, with **NEW DIGIMON on**. Baseline: `31d992c9`.
No species, requirements, evolution tables, patches or story scripts change here.

Recommend six ordinary Rookie targets for each of the eight In-Trainings,
retaining every original-disc route and putting the familiar canon route first
in the presentation. All 45 raisable Rookies remain reachable: 44 by ordinary
evolution and Kunemon by its existing special route. This reduces 56 ordinary
edges to 48, chiefly by removing duplicate added routes.

One prerequisite needs a separate design decision before implementation:
Tsunomon → Gabumon has no shared specialty today. The recommendation includes
adding Battle to Tsunomon's empty third specialty slot, retaining Air and Ice.
That is a proposed exception to the existing policy of preserving original
battle specialties, not an already permitted change. Without either this
identity adjustment or a new canon-link specialty exception, the canon request
and the current hard specialty filter cannot both be satisfied.

## Current chart and the six-slot distinction

Sources: [curated topology](../../content/tables/evolution-tree.json),
[species rows](../../content/species/), and the
[added-species evolution rules](../reference/partner.md#evolution-rules-for-the-added-species).
The lists below follow the current source-model picker order: stored `to` rows,
then reciprocal record links in species-id order. They count ordinary targets,
not special transformations. Kunemon is discussed separately below.

| In-Training | Current ordinary Rookies, in order | Count | Beyond the first six / absent from the old fixed chart |
|---|---|---:|---|
| Koromon | Agumon, Gabumon, Goblimon, ToyAgumon, Veemon, RedOtamamon, Candlemon, Solarmon, Kotemon, Renamon, Guilmon | 11 | Candlemon, Solarmon, Kotemon, Renamon, Guilmon |
| Tsunomon | Elecmon, Penguinmon, SnowAgumon, Muchomon, Gizamon, VioletElecmon, Bearmon | 7 | Bearmon |
| Tokomon | Patamon, Biyomon, Gotsumon, Psychemon, Tsukaimon, Hagurumon, Hawkmon, DemiDevimon, Tapirmon, Monmon | 10 | Hawkmon, DemiDevimon, Tapirmon, Monmon |
| Tanemon | Palmon, Betamon, Dokunemon, Otamamon, Tentomon, Wormmon, Armadillomon, Mushroomon, Floramon, Gazimon | 10 | Armadillomon, Mushroomon, Floramon, Gazimon |
| Motimon | Tentomon, Kokuwamon, Wormmon, Hagurumon, Vemmon | 5 | None |
| Bukamon | Gomamon, Otamamon, Gizamon, Syakomon, Crabmon | 5 | None |
| Nyaromon | Salamon, Tsukaimon, DemiDevimon, Bearmon | 4 | None |
| Yokomon | Biyomon, Floramon, Hawkmon, Mushroomon | 4 | None |
| **Total ordinary edges** | **44 distinct Rookies; 12 repeat-parent edges** | **56** | **14 beyond six** |

**Current code can show all of these ordinary routes.** The chart fix formerly
numbered 0340 is in the patch series as
[`Show-every-evolution-route-in-the-chart-s-detail-vie.patch`](../../mods/patches/Show-every-evolution-route-in-the-chart-s-detail-vie.patch).
It collects extra targets and pages the outgoing list six boxes at a time.
[`tools/evo_chart.py`](../../tools/evo_chart.py) models 24 outgoing entries,
12 incoming entries, six outgoing boxes per page and five incoming boxes per
page. Thus the last column describes the historical omission and today's
second page, not a current inability to display those species. The old renderer
also had an odd/even layout issue; none of these populated source rows loses
an additional sixth box to that issue.

The picker and the display have different limits: an original Baby II has six
stored targets plus up to 12 extra Rookie targets (patch 0111). The proposed
six-per-baby layout fits one outgoing page and one stored row, without needing
either extra-list capacity or an increased chart limit. Six is a presentation
goal, not the current picker's maximum. Current compiled-disc layout has not
been re-audited for this documentation-only proposal.

## Canon anchors

These are familiar Adventure lines, not a claim that each species has only one
canon evolution across the franchise. English project names are used; reference
pages also use Tunomon, Pyocomon, Mochimon, Pukamon and Plotmon.

| Canon anchor | Current status | Proposal |
|---|---|---|
| Koromon → Agumon | Present; original-disc route | Keep |
| Tsunomon → Gabumon | Missing; Gabumon currently comes only from Koromon | Add alongside Koromon, subject to the specialty prerequisite |
| Tokomon → Patamon | Present; original-disc route | Keep |
| Tanemon → Palmon | Present; original-disc route | Keep |
| Yokomon → Biyomon | Already present, alongside Tokomon | Keep both; feature Yokomon's canon anchor |
| Motimon → Tentomon | Already present, alongside Tanemon | Keep Motimon; remove the added Tanemon duplicate |
| Bukamon → Gomamon | Present | Keep |
| Nyaromon → Salamon | Present | Keep |

Canon references: [Tsunomon's Adventure evolution](https://wikimon.net/Tunomon),
[Biyomon's forms](https://wikimon.net/Piyomon_(Adventure)),
[Tentomon's forms](https://wikimon.net/Tentomon_(Adventure)),
[Gomamon's forms](https://wikimon.net/Gomamon_(Adventure)), and
[Nyaromon → Salamon in Gatomon's history](https://wikimon.net/Tailmon_(Adventure)).
These support the anchor identities; the balancing assignments below are
project design choices rather than additional canon claims.

## Recommended complete ordinary lists

The first entry is the featured canon anchor, not a promise that it wins every
picker tie. Preserve original route ordering wherever necessary to protect
original outcomes. Presentation order and picker priority must be reviewed
separately during implementation.

| In-Training | Proposed ordinary Rookies | Before | After | Change |
|---|---|---:|---:|---:|
| Koromon | Agumon, Gabumon, Goblimon, ToyAgumon, Candlemon, Guilmon | 11 | 6 | −5 |
| Tsunomon | Gabumon, Elecmon, Penguinmon, SnowAgumon, Muchomon, VioletElecmon | 7 | 6 | −1 |
| Tokomon | Patamon, Biyomon, Gotsumon, Psychemon, Tsukaimon, Hagurumon | 10 | 6 | −4 |
| Tanemon | Palmon, Betamon, Dokunemon, Otamamon, Armadillomon, Gazimon | 10 | 6 | −4 |
| Motimon | Tentomon, Kokuwamon, Wormmon, Hagurumon, Vemmon, Solarmon | 5 | 6 | +1 |
| Bukamon | Gomamon, Otamamon, Gizamon, Syakomon, Crabmon, RedOtamamon | 5 | 6 | +1 |
| Nyaromon | Salamon, DemiDevimon, Bearmon, Renamon, Kotemon, Veemon | 4 | 6 | +2 |
| Yokomon | Biyomon, Floramon, Hawkmon, Mushroomon, Monmon, Tapirmon | 4 | 6 | +2 |
| **Total ordinary edges** | **44 distinct Rookies; four repeat-parent edges** | **56** | **48** | **−8** |

The range falls from **4–11** to **6–6**; mean targets per baby falls from
7 to 6. Gabumon, Biyomon, Hagurumon and Otamamon have two parents each;
the other 40 ordinary Rookies have one. No Rookie needs more than two incoming
ordinary parents, comfortably within the five stored parent slots.

The following explains the new allocations and makes every removed route
explicit:

| Operation | Routes | Reason |
|---|---|---|
| Add a second canon parent | Tsunomon → Gabumon | Canon anchor; keep Koromon's original route |
| Move from Koromon | Solarmon → Motimon; RedOtamamon → Bukamon; Kotemon, Renamon, Veemon → Nyaromon | Machine, aquatic variant, and Battle-linked creature/weapon families respectively |
| Consolidate Tsunomon duplicates | Drop Tsunomon → Gizamon and Bearmon; retain Bukamon → Gizamon and Nyaromon → Bearmon | Strengthen the marine and mammal lines without losing either Rookie |
| Consolidate Tokomon duplicates | Drop Tokomon → Hawkmon and DemiDevimon; retain Yokomon → Hawkmon and Nyaromon → DemiDevimon | Bird and dark counterpart families |
| Move from Tokomon | Tapirmon, Monmon → Yokomon | Air links; flying dream spirit and tree-dwelling creature are secondary family choices |
| Consolidate Tanemon duplicates | Drop Tanemon → Tentomon, Wormmon, Mushroomon, Floramon; retain the first two under Motimon and the latter two under Yokomon | Give the added babies clearer insect and plant identities |
| Consolidate Nyaromon duplicate | Drop Nyaromon → Tsukaimon; keep Tokomon → Tsukaimon | Dark counterpart of Patamon; free Nyaromon capacity |

“Move” means replace the named parent only; the proposed complete lists are
authoritative. No other stage or special evolution changes.

## Specialty audit and its one prerequisite

| Parent | Specialty coverage of its proposed targets |
|---|---|
| Koromon | Fire and/or Battle for all six |
| Tsunomon | Air or Ice for the five existing targets; **Gabumon requires the proposed third specialty Battle** |
| Tokomon | Air and/or Battle for all six, including Air with Hagurumon |
| Tanemon | Nature for Palmon, Dokunemon, Armadillomon and Gazimon; Ice for Betamon and Otamamon |
| Motimon | Nature for Tentomon and Wormmon; Mech for Kokuwamon, Hagurumon, Vemmon and Solarmon |
| Bukamon | Ice and/or Battle for all six; RedOtamamon shares Battle |
| Nyaromon | Battle for all six; Salamon and DemiDevimon also share Air |
| Yokomon | Air for Biyomon, Hawkmon, Monmon and Tapirmon; Nature for Floramon and Mushroomon |

With current identities, 47 of the 48 proposed edges pass the specialty filter.
With Tsunomon's proposed Battle slot, all 48 pass. This preserves its existing
Air/Ice specialties but changes identity and potentially technique-learning
behavior; it is not a neutral topology edit. Implementation must explicitly
review that effect and preserve NEW DIGIMON off behavior. Do not silently
rewrite Gabumon's Battle/Fire identity or pretend the new link qualifies for
the original-disc exemption. An alternative is a documented canon exception
for this single link, leaving all specialties unchanged, but that would relax
the hard shared-specialty requirement instead. Neither policy change is made
by this proposal.

## Original-route and reachability safeguards

Keep all eight original ordinary edges: Koromon → Agumon/Gabumon;
Tsunomon → Elecmon/Penguinmon; Tokomon → Patamon/Biyomon;
Tanemon → Palmon/Betamon. Canon additions complement these routes.
Removing an added duplicate to an original species, such as Tanemon → Tentomon,
does not remove an original-disc route.

**Kunemon is the 45th Rookie, not a missing ordinary chart target.** Preserve
its original Kunemon's Bed waking transformation from Koromon, Tsunomon,
Tokomon or Tanemon. It does not occupy an ordinary outgoing box. The added
babies need no new Kunemon special: all eight egg lines still have their listed
ordinary Rookies, while the four original babies retain access to Kunemon.
Do not invent an ordinary Kunemon requirement row just to equalize counts.

Keep all eight Fresh → Baby II pairs, original special/item routes, Rookie →
Champion and later routes, recruitment conditions and services. No recruit may
be gated by an egg choice or by a new parent assignment. In particular, leave
Kunemon's original encounter/recruitment script intact. Every original route
must still win its original qualifying state, rather than merely exist in JSON.

The lists establish topological coverage, **not proven picker reachability**.
The picker needs three of four points and resolves Rookie ties by list order;
one requirement row serves every parent of a Rookie. Keep the disc Rookies'
normal weight bands and canonical outcomes. Added Rookies currently use
underweight/overweight bands (4/26 rather than 15). Reassigning siblings requires
rechecking those bands, highest-stat choices and `requirements.digimon` bonuses;
do not assume every six-way list can be reached with today's requirements.

## Validation required before adopting the design

The proposal was checked against the committed topology and species identities:
all eight counts are six, all 44 ordinary Rookies survive, all eight original
ordinary edges survive, only the Tsunomon/Gabumon identity conflict remains with
current specialties, and the Kunemon special is retained separately. The
historical overflow lists were checked using source row order and reciprocal
links, rather than treating a child's JSON parents as a display-order guarantee.

An implementation must synchronize the curated tree, forward/reverse species
links and primary-parent bonuses; settle the Tsunomon policy prerequisite;
then run `tools/test_evo_tree.py`, `tools/evo_check.py`, `tools/evo_graph.py`
and the built-disc `tools/evo_chart.py` audit. Require a picker witness for each
of the 48 ordinary edges, protected original qualifying states, and all 45
Rookies reachable from rebirth including Kunemon's special. Verify all six
boxes in every Baby II detail view, canon incoming links, NEW DIGIMON off,
and original recruitment access. Any later C patch needs patch-series apply
validation, a full build, `main_BSS_END` comparison and heapcheck on original
2 MB hardware limits. No build, emulator run or heap measurement is needed
for this documentation-only commit; none was performed.
