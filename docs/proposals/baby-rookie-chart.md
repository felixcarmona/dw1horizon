# Baby II → Rookie chart — implemented

**Implemented, 2026-11-05**, with **NEW DIGIMON on only**. Comparison baseline: `31d992c9`.
The before/after tables below retain the design evidence. The approved implementation
uses a canon-link exception instead of the initially proposed Battle specialty.

The implementation provides six ordinary Rookie targets for each of the eight In-Trainings,
retaining every original-disc route and putting the familiar canon route first
in the presentation. All 45 raisable Rookies remain reachable: 44 by ordinary
evolution and Kunemon by its existing special route. This reduces 56 ordinary
edges to 48, chiefly by removing duplicate added routes.

Tsunomon keeps Air/Ice and Gabumon keeps Battle/Fire. The explicit
`canon_link_exceptions` allow-list in the evolution data contains only
Tsunomon → Gabumon, with its canon reason. The separate existing Otamamon →
Geremon specialty exception remains unchanged. This exemption concerns
specialty matching only; it grants no level skip, automatic evolution or
relaxation for other links.

Gabumon uses weight 26 specifically from Tsunomon; its original weight 15
and requirements from Koromon stay unchanged. A configured parent/target weight
row supplies the same value to the picker and chart requirements popup.
Tsunomon's original Elecmon/Penguinmon candidates keep priority. Explicit
on/off paths omit the new Tsunomon/Gabumon edge in both directions with
NEW DIGIMON off.

## Baseline chart and the six-slot distinction

Sources: [curated topology](../../content/tables/evolution-tree.json),
[species rows](../../content/species/), and the
[added-species evolution rules](../reference/partner.md#evolution-rules-for-the-added-species).
The lists below follow the baseline source-model picker order: stored `to` rows,
then reciprocal record links in species-id order. They count ordinary targets,
not special transformations. Kunemon is discussed separately below.

| In-Training | Baseline ordinary Rookies, in order | Count | Beyond the first six / absent from the old fixed chart |
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

**The baseline chart already could show all of these ordinary routes.** The chart fix formerly
numbered 0340 is in the patch series as
[`Show-every-evolution-route-in-the-chart-s-detail-vie.patch`](../../mods/patches/Show-every-evolution-route-in-the-chart-s-detail-vie.patch).
It collects extra targets and pages the outgoing list six boxes at a time.
[`tools/evo_chart.py`](../../tools/evo_chart.py) models 24 outgoing entries,
12 incoming entries, six outgoing boxes per page and five incoming boxes per
page. Thus the last column describes the historical omission and the baseline's
second page at the baseline, not a current display limitation. The old renderer
also had an odd/even layout issue; none of these populated source rows loses
an additional sixth box to that issue.

The picker and the display have different limits: an original Baby II has six
stored targets plus up to 12 extra Rookie targets (patch 0111). The proposed
six-per-baby layout fits one outgoing page and one stored row, without needing
either extra-list capacity or an increased chart limit. Six is a presentation
goal, not the current picker's maximum. The implemented layout is audited from the compiled disc as described below.

## Canon anchors

These are familiar Adventure lines, not a claim that each species has only one
canon evolution across the franchise. English project names are used; reference
pages also use Tunomon, Pyocomon, Mochimon, Pukamon and Plotmon.

| Canon anchor | Baseline status | Implemented action |
|---|---|---|
| Koromon → Agumon | Present; original-disc route | Keep |
| Tsunomon → Gabumon | Missing; Gabumon currently comes only from Koromon | Added alongside Koromon, with the documented canon-link exception |
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

## Implemented complete ordinary lists

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

## Specialty audit and canon exception

| Parent | Specialty coverage of its proposed targets |
|---|---|
| Koromon | Fire and/or Battle for all six |
| Tsunomon | Air or Ice for the five existing targets; **Gabumon uses the documented canon-link exception** |
| Tokomon | Air and/or Battle for all six, including Air with Hagurumon |
| Tanemon | Nature for Palmon, Dokunemon, Armadillomon and Gazimon; Ice for Betamon and Otamamon |
| Motimon | Nature for Tentomon and Wormmon; Mech for Kokuwamon, Hagurumon, Vemmon and Solarmon |
| Bukamon | Ice and/or Battle for all six; RedOtamamon shares Battle |
| Nyaromon | Battle for all six; Salamon and DemiDevimon also share Air |
| Yokomon | Air for Biyomon, Hawkmon, Monmon and Tapirmon; Nature for Floramon and Mushroomon |

All 47 other edges share a specialty. The single canon-link exception permits
the remaining edge while preserving Tsunomon's identity. Requirements remain
fully scored, including the route-specific overfed band for Gabumon. This
supersedes the original proposal to add Battle to Tsunomon; no specialty changes
were implemented.

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

The lists establish topological coverage; practical picker witnesses are additionally
required and checked by `tools/test_evo_tree.py --practical`.
The picker needs three of four points and resolves Rookie ties by list order;
one base requirement row serves every parent of a Rookie, with the documented
Tsunomon/Gabumon weight override. Keep the disc Rookies'
normal weight bands and canonical outcomes. Added Rookies currently use
underweight/overweight bands (4/26 rather than 15). The moved siblings were checked against those bands, highest-stat choices and
`requirements.digimon` bonuses; topology alone does not establish picker
reachability.

## Implementation and validation

The curated tree, forward/reverse links and changed primary-parent bonuses
implement the complete lists above. Added Rookie requirements are resolved
against all siblings and parents, with witnesses using at most nine ordinary
training sessions during Baby II, no inheritance, zero battles and zero or one
care mistake. Witness weight assumes deliberate feeding; this is not a complete
care simulation. Original target requirement rows remain unchanged.

Regression checks cover six children per baby, the single canon-link allow-list,
unchanged Tsunomon identity, normal-weight original winning states across all
six highest-stat choices, and mode-specific route weights and paths. The
compiled chart audit checks all outgoing/incoming links. The runtime weight helper is exported as an unnumbered patch; full-build,
original-2-MB heap and emulator results are recorded below. Follow-up changes must retain
these checks and original recruitment access; no story script was changed.

The broader `evo_check.py` audit retains three baseline failures outside Baby II:
Wormmon → Dokugumon and Gomamon → Tylomon have no picker witness, and
Seadramon's original Megadramon canonical state selects WaruSeadramon.
For each case, the starting revision and this implementation have identical
candidate order, sibling requirements and levels; the baseline model reproduces
the same failure. Those later-stage rules are outside this chart change. The
built archive passes all 48 Baby II practical witnesses and has all 45 Rookies
reachable, with Kunemon counted through its existing special route.


The full nine-language build passes. The corrected native image is byte-identical
to the measured preflight: `main_BSS_END` moves from `0x801cebd0` to
`0x801cec58` (+136 bytes), aligned usable heap from 185,120 to 184,992 bytes
(−128 bytes), and MENU from 53,796 to 53,828 bytes (+32 bytes, below 55,296).
No allocation is added. All 320 archive-backed screen setups fit on 2 MB,
with a minimum margin of 272 bytes. The final compiled chart audit reports
655 routes, 655 outgoing boxes, zero omissions and zero missing game routes.


On the full disc in an original-2-MB PCSX-Redux, the Koromon and Nyaromon
detail views each display all six outgoing targets on one page. The
Tsunomon → Gabumon popup displays weight 21–31, the configured 26 ± 5 band.
A controlled Nyaromon fixture with weight 26, zero mistakes/battles and MP
as its highest stat selects Veemon in the real picker, then naturally evolves
to Veemon through the field tick; that tested target/state is not forced.
Runtime on/off checks confirm weight 26/15 and removal/restoration of the
native canon edge in both directions. The repeatable harness is
[`baby_rookie_chart.py`](../../tools/dev/playtest/baby_rookie_chart.py).
Physical console testing and full real-time care simulation remain untested.
