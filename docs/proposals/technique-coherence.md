# Proposal: technique coherence of the added species

**A implemented, 2026-11-08. B and C remain proposals:** correct conspicuous attack identities in eleven species, then decide whether to commission B's broader role rebalance. Gargoylemon's vines/swarm are a real presentation problem; Nature itself is not synonymous with plants. Existing techniques already offer substantial room for differentiation. New learnable techniques require engine work, not just extra JSON records.

The audit covers **226 added partners**, excluding all **65 originals**. Of the 218 non-babies, **91 (41.7%) share their complete compatible ordinary move set** with another added species, across 31 duplicate groups. Current averages rise from 7.06 moves per Rookie to 13.57 per Mega. A improves coherence but only reduces duplicate-set membership to 86 species in 30 groups; it does not deliver the player's larger differentiation request. B would cap choices at 6/8/10/10 by stage, with deliberate roles and exceptions. C would add three new attack identities after a separate engine/assets budget.

The original audit was documentation-only. Option A now changes species data, save loading and enemy selections; the historical CSV current columns retain the audit baseline, and its option_a columns are the implemented choices. No Identity-sheet or released v0.0.7 wiki snapshot is changed. The companion [CSV](technique-coherence.csv) has one reviewed row per added partner, current/proposed slot arrays, named identity findings, mechanical flags, learning counts, duplicate peers and overlap measurements. The eleven concrete A rows appear below; every other row's proposed data is identical to its current data.

## Scope, evidence and interpretation

Snapshot: `a8505228` on `technique-coherence-audit`, NEW DIGIMON on. Scope is exactly `partner` present and `vanilla` absent/false in `content/species/*.json`: 291 partners minus 65 originals = 226. This includes restored enemy/NPC partners, native recolors made raisable and eight added babies; it excludes enemy-only records, NPC twins and placeholders. WereGarurumon, IceLeomon, Gigadramon and MetalEtemon are among the 65 excluded originals. The [2026-11-05 audit](../reference/new-digimon-technique-audit.md) included these four, hence its 230 rather than 226. IceLeomon's Ice Statue and second-slot Ice decision still constrain how we assess learning.

Read together: [decisions](../decisions.md), [import identity rules](../reference/imported-species.md#identity-and-data-of-an-imported-species), [partner learning](../reference/partner.md#learning-techniques), [combat elements](../reference/combat.md#techniques), [species format](../mods/species.md), [Brains pool/weights](../../content/tables/brain-training.json), [evolution topology](../../content/tables/evolution-tree.json), [backlog](../ideas.md) and [wiki model](../wiki.md). The imports' donor filler was discarded; committed specialties and canon-selected attacks represent approved Identity decisions. A suspicious move is a proposal to revisit that decision, **not evidence that the importer accidentally retained filler**. The historical read-only Identity sheet was not available through a connected source in this task; this audit uses its committed results and documented constraints, not a claimed fresh sheet comparison.

Every CSV row screens appearance/attack-family identity against the committed specialties and named move list. Eighteen rows additionally cite an independently checked official species profile; the CSV labels that evidence separately. Other rows are a curated-baseline/lore screening, not independently verified encyclopedic canon. Uncertain energy, sound, holy, dark and source-game mappings remain review findings. Specifically, ChaosLord is not assumed to be Chaosdramon, NeoCrimson is not assumed to be a similarly named new species, and the original DW1 Rockmon/Golemon is not assigned the different [Reference Book Golemon's](https://digimon.net/reference_en/detail.php?directory_name=golemon) poison-gas lore.

DW1 has seven elements. Ice includes water; Air includes electricity and is often used for sound/light/dark magic; Nature includes insects, venom and Earth's proxy as well as plants. Battle covers blows, blades and Tremar's quake. Mech can represent metal, guns and beams without claiming a species is a robot: [Baihumon](https://digimon.net/reference_en/detail.php?directory_name=baihumon), for example, has a steel/metalizing identity. These mappings are editorial interpretations of canon, not new canon facts. Wings alone do not mandate Air, and Vaccine/Virus are attributes, not holy/dark attack elements.

Attribute was screened separately from element. The CSV records every current attribute and labels independently checked canon attributes. Native species keep DW1's attribute by project policy: Tentomon's Data versus the [official Vaccine](https://digimon.net/reference_en/detail.php?directory_name=tentomon) is not automatically a defect. For imports the documented Free → Data fallback conflicts with the committed non-Data attributes of the checked Veemon, Wormmon, Stingmon, ExVeemon, Armadillomon, Ankylomon, Digmon and Gargoylemon. Resolve that policy/approved-Identity discrepancy separately; A proposes no attribute changes. Free is visible in their linked official profiles, including [Veemon](https://digimon.net/reference_en/detail.php?directory_name=v-mon), [Wormmon](https://digimon.net/reference_en/detail.php?directory_name=wormmon), [Stingmon](https://digimon.net/reference_en/detail.php?directory_name=stingmon) and [ExVeemon](https://digimon.net/reference_en/detail.php?directory_name=xv-mon). No exhaustive independent attribute reconciliation is claimed for the other imports.

## Priorities and every-species disposition

CSV `severity` ranks conspicuous identity problems P1, debatable mappings/mechanical issues P2, retained baselines P3 and babies P4, independently of whether a prior decision blocks an immediate fix. `priority_rank` sorts severity first, then quiz starters, direct Champion children of quiz starters and later forms; ties use species ID. This is a reproducible exposure proxy from `new-game.json` and the tree, **not measured partner popularity**. The player's named Gargoylemon complaint also deserves immediate attention regardless of its numerical rank.

| Priority | Finding and response |
|---|---|
| Starter identities | Tentomon lacks an ordinary electrical attack despite its signature static discharge; Armadillomon's swarm/venom quota and Bearmon's water/ice attacks obscure physical identities. Address in A. Kotemon/Veemon/Renamon's shared list is a B role problem; do not infer their optimal elements from a shared quota. |
| First-evolution visibility | Gargoylemon's Battle/Nature list contains Green Trap, Mass Morph, Insect Plague and Poison Claw. Its [official profile](https://digimon.net/reference_en/detail.php?directory_name=gargomon) describes a restrained winged dark beast whose White Statue summons a demon statue. Poisonous swarms/vines are weak matches; Battle/Air with wind, a spinning projectile and confusion is the proposed approximation. White Statue is **not** Ice Statue just because the names overlap. Ankylomon and Dinohyumon have similarly conspicuous plant/swarm quotas. |
| Later clear mismatches | Shakkoumon's bombs/eye lasers are obscured by eight Nature options. Triceramon's horns are obscured by the insect/plant pool. Minotarumon's existing Tremar quake is diluted by insect and poison options. Address in A without inventing new effects. |
| Strong but constrained concerns | Golemon's ice-heavy native set needs the correct identity source. Grizzlymon's ice package conflicts with its [martial profile](https://digimon.net/reference_en/detail.php?directory_name=gryzmon), but Giga Freeze was explicitly approved on November 5. MarineAngemon's six heavy physical moves obscure its [peaceful Ocean Love](https://digimon.net/reference_en/detail.php?directory_name=marinangemon) role. Review these in B; do not silently reverse approved rows. |
| Mechanical cleanup | BlackKingNumemon lists Buster Dive outside Filth/Ice; propose an empty slot. Machinedramon's Aurora Freeze is also off-specialty, but its exact boss/NPC set is protected pending coordinated review. |

Disposition totals: **11 A candidates, 49 further reviews, 34 explicit-decision holds, 124 retained identities and 8 babies = 226**. “Retain” means no clear specialty/identity contradiction in this screening, not that every pool move is a signature attack. “Protected” can include a concern; it means the named prior decision controls until reviewed. All counts and individual reasons are in the CSV.

Do not automatically rewrite Mummymon's intentionally empty Air slot, the machine bug line's poison/insect identity, the newly differentiated Filth partners, the recent aquatic Rookie edits, SaberLeomon's thunder identity, or the ten species expanded by the earlier depth audit. Zudomon's electric hammer/finisher request already exists in `ideas.md`; it belongs in a coordinated role/finisher review. Adding free access to previously missable Machine attacks would also decide a separate backlog request, so none is promised here.

## What the measurements count

A **listed normal** is a distinct ID 0–57 in the species array. A **compatible ordinary** also matches one of the three specialties. This measures the form's potential usable arsenal once the move is known, not lifetime acquisition probability. A **positive battle** move has a nonzero `learnChances[specialty slot]`; the enemy must use it, and only one successful candidate is awarded after battle. Brains does not improve that roll.

A **positive Brains-pool** count intersects the eight ordered moves per element with positive weights at that position and specialty slot. It is potential pool eligibility, not guaranteed acquisition: the first unknown compatible move controls the candidate, other specialties compete, awards need a successful roll and only threshold crossings trigger attempts. The table's first main-specialty pool weight is zero; do not substitute a hand-waved descending weight sequence. Evolution separately teaches the weakest nonzero-power move of the main specialty. Babies use intrinsic Bubble IDs ≥113 and correctly have zero ordinary moves.

Compatible moves with neither a positive battle chance nor positive Brains weight are labeled `inheritance_only`: Tekkamon and Diaboromon's Buster Dive; Myotismon's Aurora Freeze; Icemon's Tremar/Buster Dive; Armageddemon's Bug; Suijinmon's Thunder Justice. Previously learned moves or a prior form/life can supply them; this is not a missing-element error. The CSV does not promise encounter availability for every positive battle candidate. Machinedramon has six listed normals but five compatible; BlackKingNumemon has fifteen listed but fourteen compatible.

Overlap is **Jaccard = shared compatible IDs / union of compatible IDs**, ignoring slot order, finishers and intrinsic moves. IDs 44/48 and 55/57 stay distinct even when display names overlap. Identical-set groups express equal available choices, not identical power/MP, equipped loadouts, animation timing, stats or finishers. Empty baby sets are excluded from duplicate warnings and overlap averages. “Sibling” means same level and at least one shared direct parent in the committed tree, including timed Ultimate routes; it is not an invented franchise family label. Per-row sibling overlap fractions and nearest same-level peers are in the CSV.

| Level | Added species | Compatible moves min–max (mean) | Same-level pairs / mean overlap | Sibling pairs / mean overlap |
|---|---:|---|---|---|
| fresh | 4 | 0–0 (0.00) | 0 / n/a | 0 / n/a |
| in-training | 4 | 0–0 (0.00) | 0 / n/a | 0 / n/a |
| rookie | 36 | 5–9 (7.06) | 630 / 23.9% | 76 / 34.1% |
| champion | 74 | 7–13 (10.05) | 2701 / 23.8% | 266 / 43.2% |
| ultimate | 57 | 6–14 (12.40) | 1596 / 23.1% | 90 / 42.6% |
| mega | 51 | 5–15 (13.57) | 1275 / 27.3% | 85 / 41.6% |

Adjacent-form examples use actual directed evolution links and allow an original endpoint when its child/parent is added. They show why inheritance should remain while siblings acquire different roles.

| Adjacent forms | Shared / union | Overlap |
|---|---:|---:|
| Tentomon → Kabuterimon | 5 / 13 | 38.5% |
| Wormmon → Stingmon | 8 / 12 | 66.7% |
| Bearmon → Grizzlymon | 7 / 11 | 63.6% |
| Gekomon → ShogunGekomon | 8 / 8 | 100.0% |
| Guilmon → Growlmon | 7 / 10 | 70.0% |
| Growlmon → WarGrowlmon | 5 / 18 | 27.8% |
| WarGrowlmon → Gallantmon | 7 / 20 | 35.0% |
| MetalGreymonVaccine → WarGreymon | 7 / 20 | 35.0% |
| Mammothmon → SkullMammothmon | 13 / 14 | 92.9% |
| Kurisarimon → Infermon | 10 / 13 | 76.9% |
| Infermon → Diaboromon | 11 / 16 | 68.8% |

Across all added non-babies there are **158 distinct compatible sets**. Including the eight identical empty baby sets gives 159 sets for all 226 partners. If order is also required to match, only **8 nonempty groups / 19 species** share the same ordered ordinary list; slot order affects animations and saves, while the 31 unordered groups measure the player’s available choices. The complete nonempty choice-set duplicates are:

| Compatible moves | Species sharing exactly this set |
|---:|---|
| 10 | Flamedramon, Starmon, Shadramon, Lynxmon, Kyubimon |
| 10 | Ankylomon, Digmon, Tortomon, Dinohyumon, Gargoylemon |
| 13 | Brachiomon, Kimeramon, SuperStarmon, SkullMeramon |
| 14 | Creepymon, WarGreymon, BlackWarGreymon, MaloMyotismon |
| 13 | Angewomon, MagnaAngemon, Silphymon, Kyukimon |
| 14 | Piedmon, SaberLeomon, SlashAngemon, Zanbamon |
| 14 | Vikemon, MarineAngemon, SkullMammothmon, Pukumon |
| 13 | Mammothmon, MarineDevimon, Dragomon, Divermon |
| 14 | PrinceMamemon, Baihumon, Boltmon, Beelzemon |
| 13 | Lillymon, Blossomon, Deramon, Arukenimon |
| 10 | Apemon, Tuskmon, Deltamon |
| 7 | RedOtamamon, Candlemon, Guilmon |
| 7 | Veemon, Kotemon, Renamon |
| 10 | Aquilamon, Pegasusmon, Lighdramon |
| 10 | BlackGatomon, Vilemon, Musyamon |
| 7 | Salamon, DemiDevimon, Monmon |
| 14 | ChaosLord, HiAndromon, MegaGargomon |
| 10 | DarkTyrannomon, Cyclonemon |
| 13 | ExTyrannomon, SkullSatamon |
| 14 | Seraphimon, Sakuyamon |
| 13 | MetalGreymonVaccine, MetalTyrannomon |
| 14 | Fujinmon, Raijinmon |
| 13 | LadyDevimon, GrapLeomon |
| 10 | Halsemon, Wizardmon |
| 10 | Devidramon, Maildramon |
| 8 | Gekomon, ShogunGekomon |
| 10 | Tylomon, Octomon |
| 10 | Ikkakumon, Ebidramon |
| 13 | Knightmon, Mummymon |
| 13 | Magnamon, Paildramon |
| 13 | Triceramon, Bastemon |

## Options and trade-offs

| Option | Proposal | Benefit | Cost / limitation |
|---|---|---|---|
| **A — clear coherence fixes** | The eleven rows below; reuse existing normal IDs, preserve finishers/retained slot indices and avoid global technique balance changes. | Removes the most conspicuous wrong-looking attacks and restores Tentomon's electrical signature. Total compatible memberships fall from 2,397 to 2,381. | Some beam/wind techniques remain approximations. Only five fewer species belong to duplicated sets (91 → 86); specialties affect defense, learning and AI too. Needs alias/effect checks and save-equipment remapping. |
| **B — A plus roles and smaller lists** | Working maximums: Rookie **6**, Champion **8**, Ultimate **10**, Mega **10** ordinary compatible moves; babies 0. Do not pad sparse or mono-element lists to meet a quota. For each species choose 2–3 identity-defining attacks, an affordable move and a deliberate support/control choice, then complementary options. | Gives each form a meaningful role rather than every physical attack plus most of an element. Preserve shared core attacks along a line while differentiating siblings; separate wind birds from electric beasts, sword users from gunners and water bruisers from fairies. | Applying caps mechanically after A would touch **196** species and remove at least **522** memberships (before exceptions). That is a large rebalance, not a small patch. Choose actual cuts individually; preserve costly top-tier choices and avoid leaving only dominant moves. Mono-element limits, protected decisions and special bosses need explicit exceptions. No automatic power buffs are included. |
| **C — B plus three attack identities** | Prototype a low/mid-tier **Rock Shot** for rocky/Earth forms, a non-poison **Blade Wave** for sword/sickle users, and a **Sonic Pulse** for musical/sonic forms. These are roles, not final names/IDs/power/MP. | Covers real gaps that currently force rock creatures into vines, sword users into punches and singers into lightning. | Every ID below 58 is already occupied. IDs ≥58 are not made ordinary learnable moves by adding JSON. Requires an explicit slot-reuse/migration design or learner/table/save/menu expansion, plus effects, names/translations, model events and performance proof. Highest cost and risk; no promise of a drop-in addition. |

For B, compare sibling overlap before/after, not only counts. Randomly cutting each shared pool can preserve or worsen duplication. An initial review target is no unexplained exact duplicate across unrelated non-babies and sibling Jaccard below about 70%, with documented canon-line exceptions; neither is a substitute for play balance. Check damage/MP, range, status, animation time and affordable access together. The recent poison cost, bounded high-stat damage curve and existing technique power must not be casually undone. No evolution currently requires a learned-technique count, so trimming does not need a new technique-count evolution gate.

C's limits need a separate technical proposal. Current battle learning enumerates **0–57**, finisher semantics occupy **58–112**, and **113–120** are intrinsic baby bubbles; higher records are not evidence of a usable learning slot. Reusing duplicate-name IDs 48 or 57 would still change real data, models and existing saves; they are not free IDs. Extending beyond the current range must audit learning chances, enemy `usedMoves` recording, every learned-bit consumer and save layout, Brains order/weights, technique menus and names, compatibility/effect tables and BTL/STD/VS paths. The partner reference exposes a two-word learned set while some save code walks a wider area: prove the actual layout rather than assuming capacity. Do not repurpose a finisher or bubble and call it a new normal move.

A/B move-list edits fit the existing **16 total species slots**, normally at most 15 ordinary plus one finisher. Null holes also consume slots. Alias pointers can reuse existing programs but still need table space, suitable cast range and correct hit/projectile events. Actual new motion/effect programs consume model/battle heap and resident effect space; names, translations, menus and learning UI consume resident/MENU budget. Measure linked MENU size, minimum heap margin, model sizes, effect loading and worst map/tournament/VS combinations on 2 MB before accepting C; also test supported Chinese/8 MB configurations. No byte-cost estimate is claimed without an implementation/build. See [effect requirements](../reference/imported-species.md#technique-effects), [model constraints](../mods/species.md) and [existing heap-sensitive attack work](../mods/buster-dive.md).

## Option A: exact choices for review

Each cell below lists compatible ordinary moves with IDs; the CSV also preserves **all sixteen-capacity slot positions**, nulls, finishers and any off-specialty entries. “—” is an empty specialty slot. All eleven retain their current finisher ID and index. For BlackKingNumemon, current/proposed compatible lists are intentionally identical: only the unusable Buster Dive entry becomes null.

These are proposed choices, not mechanically derived canon truth. In particular, wind/beam proxies need a visual preview before implementation. Recent explicit decisions are left outside A.

| Species | Current specialties / compatible ordinary moves | Proposed specialties / compatible ordinary moves | Reason |
|---|---|---|---|
| 111 Tentomon | Nature/—/—: Poison Powder (32), Bug (33), Mass Morph (34), Insect Plague (35), Charm Perfume (36), Poison Claw (37), Danger Sting (38) | Nature/Air/—: Electric Cloud (10), Megalo Spark (11), Static Elect (12), Bug (33), Mass Morph (34), Insect Plague (35), Poison Claw (37), Danger Sting (38) | Mono-Nature omits its signature element; plant perfume/powder are less direct than electric moves. [profile](https://digimon.net/reference_en/detail.php?directory_name=tentomon) |
| 185 Armadillomon | Battle/Nature/—: Mass Morph (34), Insect Plague (35), Poison Claw (37), Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43) | Battle/Nature/—: Mass Morph (34), Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43) | Insect Plague and Poison Claw imply unsupported swarm/venom; retain Mass Morph as shell defense. [profile](https://digimon.net/reference_en/detail.php?directory_name=armadimon) |
| 353 Bearmon | Battle/Ice/—: Ice Needle (19), Aqua Magic (21), Tear Drop (23), Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43) | Battle/—/—: Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43), Dynamite Kick (44), Counter (45) | Ice Needle, Aqua Magic and Tear Drop have no direct martial-bear rationale. [profile](https://digimon.net/reference_en/detail.php?directory_name=bearmon) |
| 189 Ankylomon | Battle/Nature/—: Mass Morph (34), Insect Plague (35), Poison Claw (37), Green Trap (39), Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43), Dynamite Kick (44), Megaton Punch (46) | Battle/Nature/—: Mass Morph (34), Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43), Dynamite Kick (44), Megaton Punch (46) | Green Trap, Insect Plague and Poison Claw are poor proxies for armor and blunt impact; Nature may retain defensive Mass Morph. [profile](https://digimon.net/reference_en/detail.php?directory_name=ankylomon) |
| 308 Dinohyumon | Battle/Nature/—: Mass Morph (34), Insect Plague (35), Poison Claw (37), Green Trap (39), Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43), Dynamite Kick (44), Megaton Punch (46) | Battle/Air/—: Spinning Shot (9), Wind Cutter (13), Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43), Dynamite Kick (44), Counter (45), Megaton Punch (46) | Green Trap, Insect Plague and Poison Claw do not express its sword techniques; replace plant quota with blade/wind proxies. [profile](https://digimon.net/reference_en/detail.php?directory_name=dinohumon) |
| 327 Gargoylemon | Battle/Nature/—: Mass Morph (34), Insect Plague (35), Poison Claw (37), Green Trap (39), Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43), Dynamite Kick (44), Megaton Punch (46) | Battle/Air/—: Spinning Shot (9), Wind Cutter (13), Confused Storm (14), Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43), Dynamite Kick (44), Counter (45), Megaton Punch (46) | Green Trap, Insect Plague, Mass Morph and Poison Claw obscure its winged/dark identity; Air wind/control is a DW1 approximation. [profile](https://digimon.net/reference_en/detail.php?directory_name=gargomon) |
| 330 Minotarumon | Battle/Nature/—: Poison Powder (32), Mass Morph (34), Insect Plague (35), Poison Claw (37), Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43), Counter (45), Megaton Punch (46) | Battle/Nature/—: Mass Morph (34), Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43), Counter (45), Megaton Punch (46) | Insect Plague, Poison Claw and Poison Powder are unsupported; Tremar directly represents quake. [profile](https://digimon.net/reference_en/detail.php?directory_name=minotaurmon) |
| 93 Muchomon | Ice/Air/—: Megalo Spark (11), Static Elect (12), Giga Freeze (16), Winter Blast (18), Ice Needle (19), Water Blit (20), Aqua Magic (21) | Battle/Air/Ice: Wind Cutter (13), Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43), Dynamite Kick (44), Counter (45) | Giga Freeze, Ice Needle, Winter Blast and other water/cold moves dominate without cold identity. [profile](https://digimon.net/reference_en/detail.php?directory_name=muchomon) |
| 214 Shakkoumon | Nature/Mech/—: All Range Beam (25), Pulse Laser (27), Delete Program (28), DG Dimension (29), Reverse Prog (31), Poison Powder (32), Bug (33), Mass Morph (34), Insect Plague (35), Charm Perfume (36), Poison Claw (37), Danger Sting (38), Green Trap (39) | Mech/Air/Nature: Electric Cloud (10), Megalo Spark (11), Static Elect (12), Power Crane (24), All Range Beam (25), Metal Sprinter (26), Pulse Laser (27), Delete Program (28), DG Dimension (29), Full Potential (30), Reverse Prog (31) | Eight Nature poison/swarm/plant moves overwhelm beam identity; Mech/Air is a clearer projectile/holy proxy. [profile](https://digimon.net/reference_en/detail.php?directory_name=shakkoumon) |
| 257 Triceramon | Battle/Nature/—: Poison Powder (32), Bug (33), Charm Perfume (36), Danger Sting (38), Green Trap (39), Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43), Dynamite Kick (44), Counter (45), Megaton Punch (46), Buster Dive (47) | Battle/Nature/—: Tremar (40), Muscle Charge (41), War Cry (42), Sonic Jab (43), Dynamite Kick (44), Counter (45), Megaton Punch (46), Buster Dive (47) | Bug, Green Trap, Charm Perfume and Poison Powder do not express horns; Danger Sting is a horn-projectile approximation only. [profile](https://digimon.net/reference_en/detail.php?directory_name=triceramon) |
| 307 BlackKingNumemon | Filth/Ice/—: Giga Freeze (16), Winter Blast (18), Ice Needle (19), Water Blit (20), Aqua Magic (21), Tear Drop (23), Odor Spray (49), Poop Spd Toss (50), Big Poop Toss (51), Big Rnd Toss (52), Poop Rnd Toss (53), Rnd Spd Toss (54), Horizontal Kick (55), Ult Poop Hell (56) | Filth/Ice/—: Giga Freeze (16), Winter Blast (18), Ice Needle (19), Water Blit (20), Aqua Magic (21), Tear Drop (23), Odor Spray (49), Poop Spd Toss (50), Big Poop Toss (51), Big Rnd Toss (52), Poop Rnd Toss (53), Rnd Spd Toss (54), Horizontal Kick (55), Ult Poop Hell (56) | Buster Dive is a listed Battle move outside specialties; mark its slot empty rather than advertise it as learnable. [record](../../content/species/307-blackkingnumemon.json) |

**Route-only specialties are explicit compromises.** Muchomon retains Air and third-slot Ice while Battle becomes main; its new Wind Cutter is a sonic/air-cut approximation, not a claim that a flightless bird flies. Its ordinary cold/water attacks are removed, but Ice remains for the existing Tsunomon, Soulmon, Sorcermon and Quetzalmon links. Shakkoumon keeps tertiary Nature for the Ankylomon and Pharaohmon links; its new main Mech expresses bombs/eye lasers, secondary Air is a holy-energy proxy, and no plant/insect normal attack remains. Removing those bridge specialties would leave six current edges without a shared element. A instead follows the existing Mummymon precedent, retains every edge's existing shared-specialty validity, and documents the remaining canon compromise. A future removal needs a separate route exception/topology decision, not a quiet evolution change. Triceramon likewise keeps Nature as its approved Earth/line bridge with no ordinary Nature attack; its physical list is already the complete eight-move Battle pool. Armadillomon and Ankylomon retain Mass Morph as an armor-defense approximation.

Gargoylemon's complete ordinary proposal is the six existing Battle moves plus Counter, Wind Cutter, Confused Storm and Spinning Shot. Air is secondary so all four selected Air/Battle additions have positive battle chances; no Ice Statue is smuggled in as White Statue. Moving Shakkoumon's Mech to main changes its evolution award to the weakest eligible Mech attack. Tentomon's added Air moves all have positive secondary battle chances. Neither new specialty order automatically teaches every added move to an existing partner.

In the slot proposal, removals become null, additions occupy vacated ordinary slots first, and extra additions append after existing entries. No retained attack or finisher is shifted. This preserves enemy indices for retained attacks but **does not make replacements save-safe automatically**: a saved animation slot can refer to a newly substituted technique. Implement the migration below before shipping any such edit.

## Saves, enemies, Brains training and wiki

**Option A saves use the required technique-layout record (0x8003, byte 1).** Unmarked saves migrate equipped selections before absent-content cleanup and mode conversion; marked saves already use the new slots. The globally learned library is unchanged. A removed selection falls back to an already-known compatible ordinary move, preferring the old element then closest power, with species slot order breaking ties and no duplicate fallback selection; otherwise it becomes empty. Finishers keep their slot. Unknown layout versions are refused. Older Continue loaders refuse this required record rather than silently reinterpret the new slots.

The following paragraphs describe the original migration requirements. For an implementation of A or B, preserve species IDs and learned technique bits. Already learned moves remain known globally across forms/lives; removing one from this form's eligibility does not justify erasing it from the save. The partner can use it again in another compatible form. Newly added moves are still unknown unless the save already knows their IDs; do not grant an entire new list on Continue. Battle/Brains gates use the current species data, and list trimming restricts future availability even in a save that knows everything.

Equipped moves are saved as **animation slot indices**, not a safe species-local technique identity. Before replacing or clearing a slot, resolve old equipped slots to old technique IDs, match surviving IDs into the new list, clear removed/incompatible selections and choose a valid already-known fallback. Keep the finisher's index. Because a trimmed move is absent from the new list, a generic “known bit set” check alone cannot migrate this safely. A data-only list swap cannot be promised as a complete save migration. Test a Continue save with each changed slot equipped, a removed move still learned, a surviving move equipped, no surviving normal selection, evolution, rebirth and a mode toggle. Never clear the whole library to force differentiation. For C, repurposed IDs need versioned learned-bit interpretation or an explicit incompatible-save policy; a larger ID range needs proven serialization/migration for every reader. Memory-card saves are the upgrade path; save states retain old code/data and are not a migration test.

Specialties also determine incoming element multipliers averaged across three slots, first-specialty AI weighting and learning-chance columns. A main-slot change is therefore a balance change even if every technique's global power stays fixed. Verify NEW DIGIMON off fallback behavior, shared native/record-original data and per-species mode scalars; no excluded original's curated identity is permission to edit its row. The retained Ice/Nature bridge slots still affect defense despite having no attacks.

Brains training must use the new lists and exact positional weights. Do not reorder the global eight-move pools to compensate for individual trims; doing so affects all species. A move with zero tertiary battle chance and zero Brains weight needs inheritance or a different slot, as IceLeomon's November 5 decision demonstrated. B should preserve a reachable cheap attack and at least one meaningful in-form learning path; C needs new pool/order/weight design and teacher availability, not just new record IDs.

A species list is also used by wild/boss/arena/VS models and enemy animation-slot selections. Audit `content/battle/enemy-movesets.json`, map placements, named DWS selections and finisher aliases for every removed/replaced slot. A retained enemy slot keeps its old meaning; a replaced one may acquire a different move and an emptied one may become idle. Decide replacements deliberately rather than inheriting accidental difficulty changes. Playtest effects and collision origin, not merely successful JSON lint.

The [wiki](../wiki.md) reads species, learning tables and encounters from the selected **release snapshot**. Once a future implementation is released, regenerate species pages, technique-compatible-partner tables, actual enemy-teacher sources, effective battle percentages and learning guidance from that tag. Review all nine languages and runtime technique-name IDs. Existing released wiki snapshots stay pinned; do not publish this proposal as current gameplay or hand-edit generated movesets. New source encounters/training opportunities must be real, and protected boss-only Machine teaching must not silently become ordinary access.

## Original audit validation and implementation acceptance

The proposal audit checks all 226 CSV rows against the snapshot; resolves every move name/duplicate-name ID; checks counts, specialties, positive battle/Brains membership and exact duplicate peer sets; checks all A proposal arrays against the 16-slot limit and finisher indices; and finds no newly lost shared-specialty edge, including timed Ultimate routes. Documentary metrics are projections, not measured combat results. No models, extracted disc, game build or live combat validation were available/needed for this documentation-only change.

For implementation, require species/model/alias lint, the evolution topology and practical-chain checks, mode-balance checks, save migration tests, enemy selection review and live normal/finisher/effect validation. For B additionally publish each species' chosen role/cuts, resulting overlap and damage/MP examples. For C additionally supply an ID/storage/MENU/heap budget and prove learning in battle and Brains training, persistence and localized menu/effect behavior. Keep the backlog's unique finishers and broader acquisition/economy changes as separate decisions.

To independently check the implemented A arrays and duplicate totals without running a game build, from the repository root:

```python
import csv, json, pathlib, re
from collections import defaultdict
root = pathlib.Path('.')
species = [json.loads(p.read_text()) for p in (root/'content/species').glob('*.json')]
techs = [json.loads(p.read_text()) for p in (root/'content/techniques').glob('*.json')]
by_id = {t['id']: t for t in techs}
by_name = defaultdict(list)
for t in techs:
    by_name[t['name']].append(t['id'])
def move_id(value):
    if isinstance(value, int):
        return value
    suffix = re.search(r' \((\d+)\)$', value)
    if suffix:
        return int(suffix[1])
    assert len(by_name[value]) == 1
    return by_name[value][0]
added = {s['id']: s for s in species if 'partner' in s and not s.get('vanilla')}
rows = list(csv.DictReader(open('docs/proposals/technique-coherence.csv')))
assert len(rows) == len(added) == 226
assert {int(r['id']) for r in rows} == set(added)
groups = defaultdict(list)
for row in rows:
    s = added[int(row['id'])]
    slots = [None if x is None else move_id(x) for x in s['techniques']]
    assert json.loads(row['option_a_slots_json']) == slots
    assert json.loads(row['option_a_specialties_json']) == s['specialties']
    normal = {i for i in slots if i is not None and i < 58}
    compatible = {i for i in normal if by_id[i]['element'] in s['specialties']}
    assert len(compatible) == int(row['option_a_compatible_count'])
    groups[tuple(sorted(compatible))].append(s['id'])
duplicates = [ids for moves, ids in groups.items() if moves and len(ids) > 1]
assert len(duplicates) == 30 and sum(map(len, duplicates)) == 86
print('226 added partners; 30 duplicate compatible sets involving 86 non-babies after A')
```

## Implementation notes (A)

All eleven specialty/slot arrays match the CSV option_a columns exactly. Tentomon extends its model table for appended Megalo Spark using its existing casting animation. Native Tentomon encounters replace the former Charm Perfume selection with Electric Cloud; wild Gargoylemon replaces Insect Plague with Wind Cutter at the same AI weight. Muchomon encounter choices now resolve to its physical list; GCAN11 formerly selected three slots beyond its eight-entry list and now explicitly selects Sonic Jab, Dynamite Kick and Wind Cutter (50/30/20). No evolution edge or global technique power/MP changes.

Brains keeps the exact global pool order and positional weights; regression tests compare each implemented species with the CSV projected positive-pool counts. The wiki model supports an explicit `working` review snapshot, while the public wiki builder continues to require a release tag. Release v0.0.7 remains pinned. See [balance](../mods/balance.md#technique-coherence-option-a) and [save format](../reference/save-format.md#technique-layout-a).

Registered VS fighters also save animation slots. Continue migrates their equipment before a new save receives the layout marker; the direct VS card loader applies the same migration to legacy entries. Because registrations contain no learned library, removed or incompatible selections become empty and surviving selections retain their identity. Older direct VS loaders did not honor required extension tags; do not use A registrations with an older engine.

BlackKingNumemon has one unavoidable legacy exception. Released v0.0.7 used Battle IDs in indices 8 and 10–13 and no index 15; the unversioned audit baseline had Ice IDs there. Neither format identifies that data revision, and a complete learned library cannot distinguish them. Unmarked saves therefore clear those six ambiguous equipped indices (8, 10, 11, 12, 13, 15), including registrations, instead of guessing. Common Filth selections and finisher index 14 survive; every learned bit remains. The JSON arrays still match A exactly. Once a save has layout 1, its current Ice selections survive later Continues. Host tests cover both historical arrays with a full 128-bit library.
