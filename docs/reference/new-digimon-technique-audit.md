# Imported and newly raisable partner technique audit

Baseline: `f49be887^` (parent of the separate IceLeomon change). Audit date: 2026-11-05. NEW DIGIMON on, committed species levels. Sources: [partner learning rules](docs/reference/partner.md#learning-techniques), [techniques](content/techniques), [species](content/species), [Brains training order/weights](content/tables/brain-training.json), and the read-only Identity sheet retrieved on the audit date. No external species lore was needed: identity and canon attack descriptions come from those approved rows.

Scope: **230** newly raisable partners (all species with a partner block and id ≥62), including record originals, WereGarurumon’s imported replacement, and eight new babies. Native comparison: ids 1–61 with partner blocks; enemy-only records, NPC twins and unused placeholders are excluded. This deliberately includes the restored secret/NPC partners so none falls between the native and imported groups.

“Ordinary” means technique id <58 whose element matches one of the three specialties. Finishers, baby bubbles, null slots and off-element moves are excluded from counts and power maxima. Matching moves can be equipped once known; battle learning also depends on the specialty slot’s learn chance, and Brains training follows its own order/weights. The table does not promise every move can be learned from battle in one lifetime: some tertiary high-tier moves have a zero battle chance and must come from a prior form. See the learning reference. Counts include support moves with zero damage; elemental maxima exclude finishers. MP below is the normal displayed cost (`mpCost × 3`), before Brains discounts or condition surcharges. Raw power is a screening metric, not damage or a full DPS ranking; poison, range, accuracy and animation timing also matter.

Identity handling: existing approved elements, canon-selected techniques, list order and finishers are retained. The older generated quota lists receive additive options only. Explicit “keep this set” NPC rationale and recent curated identities are treated as constraints: conflicts are listed below rather than silently changed. No sheet was edited. IceLeomon’s ice addition is directly specified by the feedback.

## Findings and proposed fixes

Eleven species receive additions (IceLeomon separately, ten in the batch). Four sparse but already powerful NPC partners remain flagged for coordinated identity/model follow-up. Mummymon’s unused Air slot is intentional. No other partner clearly combines inadequate breadth or element power with a lack of suitable late-tier attacks.

| Species | Finding | Proposal and disposition |
|---|---|---|
| 63 IceLeomon | Element gap | Ice Needle/Winter Blast peak at 126 despite Ultimate tier. Add Ice Statue (424/186 MP), using the existing ranged clip; move Ice ahead of Air so its 8% battle chance and positive Brains weight allow learning in this form. Retain the finisher and off-mode move list; Air learning priority also changes off because the specialty order is shared. Applied. |
| 183 Wormmon | Low power | Seven ordinary techniques, peak 117; native Nature Rookies Palmon/Kunemon reach 180/157. Add Danger Sting (157/102 MP) for the larva’s stinging insect attack. Applied. |
| 263 Mushroomon | Low power | Seven ordinary techniques, peak 117 against Palmon’s 180. Add Charm Perfume (180/210 MP) as a mushroom spore cloud; existing poison and finisher remain. Applied. |
| 187 Stingmon | Low power | Ten techniques but peak 193, below native Nature/Battle Champions Kabuterimon/Kuwagamon (310) and Ogremon (500). Add Bug (500/354 MP), an expensive insect attack, and Megaton Punch (320/186 MP), an arm strike. Applied. |
| 225 Shurimon | Low power | Ten techniques but peak 193 versus Ninjamon’s 285. Add Spinning Shot (389/150 MP) for thrown shurikens and the stronger Dynamite Kick variant (255/99 MP); the original kick remains in its slot. Applied. |
| 328 Snimon | Low power | Ten techniques but peak 193 versus Kuwagamon’s 310. Add Spinning Shot (389/150 MP) for flying sickles and Counter (285/165 MP) for reactive blade combat. Applied. |
| 262 Flymon | Low power | Ten techniques but peak 225 versus native Nature/Air Champions at 310–389. Add Bug (500/354 MP) for the insect swarm and Spinning Shot (389/150 MP) for its fired stinger. Applied. |
| 332 Roachmon | Low power | Ten techniques but peak 193; native filth users retain 211–333 and Kabuterimon reaches 310. Add Bug (500/354 MP), Big Poop Toss (211/192 MP) for thrown refuse, and Megaton Punch (320/186 MP) for its Boxing Step identity. Applied. |
| 208 Togemon | Main-element gap | Nature peaks at 180 while the native Nature-main Champions Vegiemon/Kabuterimon/Kuwagamon reach 310. Existing Megaton Punch already provides 320 Battle power. Add Green Trap (310/147 MP), a cactus/root snare. Applied. |
| 296 Grizzlymon | Secondary-element gap | Battle already reaches 320, but four Ice techniques peak at 126, below even Penguinmon (264). Add Giga Freeze (264/120 MP) using its existing cold casting clip; retain the physical bear identity. Applied. |
| 123 Tinmon | Tier and breadth gap | Seven ordinary moves, peak 264; native Ice Ultimate MegaSeadramon has eleven ordinary moves and 430 Ice power. Add Ice Statue (424/186 MP), Aurora Freeze (430/258 MP), Green Trap (310/147 MP), and Poison Powder (117/171 MP). Ice/Nature magical control follows the existing approved element pair. Applied. |
| 66 Myotismon | Sparse; identity constraint | Six ordinary moves versus native Ultimates’ 10–15, but already 586 Air/430 Ice power. Proposed breadth: Megalo Spark, Wind Cutter, Confused Storm, Counter, Muscle Charge (eleven total). Defer: the approved sheet rationale explicitly retains this exact NPC-partner set and its model constraints. The current record now supports aliases, so a separate identity review could enable the proposal.  |
| 115 Machinedramon | Sparse; identity constraint | Only five specialty-matching ordinary moves; Aurora Freeze is listed but cannot be learned/equipped with Mech/Air/Battle. Already has 573 Mech and 586 Air power. Proposed: Pulse Laser, Delete Program, Power Crane, Metal Sprinter, DG Dimension, retaining the finisher. Defer: approved rationale keeps the native boss set and partner model; both wild/boss and partner animation slots must be supported before expanding it.  |
| 116 Analogman | Sparse; identity constraint | Seven ordinary moves versus the native late-tier 13–14, but 722 Mech power is already top-tier. Proposed: Power Crane, All Range Beam, Metal Sprinter, Thunder Justice (eleven total). Defer: approved rationale explicitly retains the NPC-partner set; new partner and wild animation slots need a coordinated identity/model change.  |
| 117 Jijimon | Sparse; identity constraint | Six ordinary moves, already 500 power. Proposed: Counter and Muscle Charge to complete all eight Brains-training Battle techniques without adding an element. Defer: approved rationale explicitly retains the NPC-partner set and model constraints; preserve its staff/elder identity pending that review.  |
| 334 Mummymon | Intentional empty specialty | Air has zero ordinary moves. The recent curated row explicitly retains Air only for the Bakemon evolution link and specifies gun/bandage attacks in Battle/Mech. No fix: adding Air attacks would conflict with that validated identity.  |

## Balance limits

All additions use existing technique records at their existing power, MP cost, accuracy, status and learning chances. No evolution, stats, finisher, economy or off-mode row changes. IceLeomon swaps its Ice/Air learning priority; all other specialty orders remain intact. Rookie additions reach 157–180 power within native Nature-Rookie coverage. New Champion peaks of 389–500 fit the native Champion overall range (up to 586); Bug’s 500 power costs 354 MP, compared with Megaton Punch’s 320/186 and Green Trap’s 310/147. This is an expensive insect option rather than a cheap replacement for every attack. Tinmon reaches the native Ice-Ultimate ceiling of 430. Species retain at most 15 ordinary slots plus one finisher. Existing move and finisher indices stay stable, with new techniques appended after the finisher.

Imported attack aliases are applied after field overlays and Buster Dive processing; additional slots share the existing suitable cast, projectile or melee animation and events. IceLeomon and Tinmon use record-original slot aliases. These add table pointers rather than new animation programs. No C or patch-series changes are required. Build/model checks verify slot presence and storage; live combat/effect alignment is a separate validation limit.

## Native comparison by level and specialty

Each row lists the number of matching native partners, ordinary total-count range, ordinary total-power range, and ordinary count/power range within that specialty. Megas have only Phoenixmon and HerculesKabuterimon in the native comparison; Mech/Ice/Filth have no native Mega peer, so Ultimate values are the stated fallback in the full table. Mono-element partners can legitimately have only eight ordinary techniques: the Brains-training pool has eight entries per element, with additional duplicate attack variants outside that pool. Babies correctly have no ordinary techniques.

| Level | Specialty | Native partners | Total count | Best overall power | Specialty count | Specialty best power |
|---|---|---:|---:|---:|---:|---:|
| rookie | fire | 3 | 7 | 279–389 | 2–5 | 84–279 |
| rookie | battle | 4 | 7 | 279–500 | 2–5 | 52–500 |
| rookie | air | 5 | 7 | 264–500 | 2–5 | 120–389 |
| rookie | nature | 3 | 7 | 211–382 | 2–4 | 157–180 |
| rookie | ice | 3 | 7 | 211–264 | 3–5 | 211–264 |
| champion | fire | 12 | 10–12 | 279–500 | 2–7 | 279–488 |
| champion | battle | 18 | 10–12 | 285–586 | 2–8 | 52–500 |
| champion | air | 12 | 8–12 | 389–586 | 0–7 | 0–586 |
| champion | nature | 10 | 8–11 | 279–500 | 2–6 | 62–310 |
| champion | ice | 9 | 8–12 | 279–586 | 2–8 | 211–430 |
| champion | filth | 3 | 8–10 | 320–333 | 7–8 | 211–333 |
| ultimate | fire | 2 | 14–15 | 586–722 | 3–8 | 488 |
| ultimate | battle | 9 | 13–14 | 500–722 | 2–8 | 320–500 |
| ultimate | air | 7 | 11–15 | 430–722 | 2–5 | 366–586 |
| ultimate | nature | 3 | 10–12 | 430–722 | 2–8 | 180–500 |
| ultimate | ice | 5 | 10–15 | 430–722 | 2–8 | 60–430 |
| ultimate | mech | 8 | 11–14 | 500–722 | 2–8 | 389–722 |
| ultimate | filth | 1 | 13 | 586 | 2 | 333 |
| mega | fire | 2 | 13–14 | 500–586 | 2–5 | 444–488 |
| mega | battle | 1 | 14 | 500 | 4 | 500 |
| mega | air | 1 | 13 | 586 | 8 | 586 |
| mega | nature | 1 | 14 | 500 | 8 | 500 |

## Every imported or newly raisable partner

Cells show **before → after** only when changed. Each specialty cell is **ordinary count / best power**. The next column counts self-learnable moves and their elemental maxima, considering a positive battle chance or Brains weight in this form. Moves with neither require inheritance from an earlier life/form; evolution alone teaches only a weak main-specialty move. “Best” names one highest-power ordinary option at that species’ current level, with power and normal MP. Peer selection prefers native partners of the same level and main specialty, then shared specialties; ties favor the closest specialty set. A dagger marks an Ultimate fallback where no same-level native shares its main specialty. Babies have no ordinary comparator. “OK” means no clear equipment gap in this audit, not equal damage in every matchup.

| ID / species | Level | Ordinary total | Specialties: count / best power | Self-learnable by specialty: count / power | Best ordinary: power / MP | Native peer: count / best power | Result |
|---|---|---:|---|---|---|---|---|
| 62 WereGarurumon | ultimate | 13 | battle 6/500; fire 4/488; ice 3/264 | battle 6/500; fire 4/488; ice 3/264 | Buster Dive: 500/258 | SkullGreymon: 13/573 | OK |
| 63 IceLeomon | ultimate | 12 → 13 | battle 8/500; ice 2/126 → 3/424; air 2/382 | battle 8/500; ice 2/126 → 3/424; air 2/382 | Buster Dive: 500/258 | SkullGreymon: 13/573 | added |
| 64 Gigadramon | ultimate | 13 | mech 8/722; ice 3/424; battle 2/320 | mech 8/722; ice 3/424; battle 2/320 | DG Dimension: 722/420 | Megadramon: 13/722 | OK |
| 65 MetalEtemon | mega | 13 | battle 8/500; air 3/586; filth 2/333 | battle 8/500; air 3/586; filth 1/53 | Thunder Justice: 586/330 | HerculesKabuterimon: 14/500 | OK |
| 66 Myotismon | ultimate | 6 | air 2/586; battle 2/320; ice 2/430 | air 2/586; battle 2/320; ice 1/264 | Thunder Justice: 586/330 | Andromon: 14/722 | deferred identity |
| 67 Yanmamon | champion | 7 | air 4/389; nature 3/157 | air 4/389; nature 3/157 | Spinning Shot: 389/150 | Airdramon: 10/444 | OK |
| 68 Gotsumon | rookie | 7 | battle 7/500 | battle 7/500 | Buster Dive: 500/258 | Gabumon: 7/320 | OK |
| 69 Flarerizamon | champion | 7 | fire 7/444 | fire 7/444 | Prominence Beam: 444/183 | Meramon: 10/488 | OK |
| 70 WaruMonzaemon | ultimate | 13 | battle 8/500; air 5/586 | battle 8/500; air 5/586 | Thunder Justice: 586/330 | Monzaemon: 13/586 | OK |
| 71 SnowAgumon | rookie | 7 | ice 4/424; battle 3/52 | ice 4/424; battle 3/52 | Ice Statue: 424/186 | Betamon: 7/264 | OK |
| 72 Hyogamon | champion | 10 | ice 4/430; battle 6/500 | ice 4/430; battle 6/500 | Buster Dive: 500/258 | Frigimon: 10/430 | OK |
| 74 Dokunemon | rookie | 7 | nature 4/157; air 3/225 | nature 4/157; air 3/225 | Confused Storm: 225/216 | Kunemon: 7/382 | OK |
| 76 Tankmon | champion | 8 | fire 6/444; mech 2/430 | fire 6/444; mech 2/430 | Prominence Beam: 444/183 | Meramon: 10/488 | OK |
| 80 Goblimon | rookie | 7 | battle 4/320; fire 3/279 | battle 4/320; fire 3/279 | Megaton Punch: 320/186 | Gabumon: 7/320 | OK |
| 82 Psychemon | rookie | 7 | battle 7/320 | battle 7/320 | Megaton Punch: 320/186 | Gabumon: 7/320 | OK |
| 84 ToyAgumon | rookie | 7 | fire 5/279; battle 2/52 | fire 5/279; battle 2/52 | Magma Bomb: 279/132 | Agumon: 7/279 | OK |
| 85 Piddomon | champion | 10 | air 6/389; battle 4/320 | air 6/389; battle 4/320 | Spinning Shot: 389/150 | Angemon: 10/389 | OK |
| 87 Geremon | champion | 8 | filth 8/333 | filth 8/333 | Ult Poop Hell: 333/333 | Numemon: 8/333 | OK |
| 88 Vermilimon | ultimate | 10 | fire 6/444; battle 4/320 | fire 6/444; battle 4/320 | Prominence Beam: 444/183 | Digitamamon: 15/586 | OK |
| 89 Fugamon | champion | 10 | air 4/366; battle 4/320; fire 2/279 | air 4/366; battle 4/320; fire 2/279 | Hurricane: 366/255 | Airdramon: 10/444 | OK |
| 90 Tekkamon | ultimate | 13 | mech 8/722; battle 5/500 | mech 8/722; battle 4/320 | DG Dimension: 722/420 | MetalGreymonVirus: 14/722 | OK |
| 91 MoriShellmon | champion | 10 | nature 2/180; ice 8/430 | nature 2/180; ice 8/430 | Aurora Freeze: 430/258 | Vegiemon: 8/310 | OK |
| 92 Guardromon | champion | 10 | mech 5/573; battle 3/320; fire 2/444 | mech 5/573; battle 3/320; fire 2/444 | All Range Beam: 573/330 | baby: not applicable | OK |
| 93 Muchomon | rookie | 7 | ice 5/264; air 2/382 | ice 5/264; air 2/382 | Megalo Spark: 382/174 | Betamon: 7/264 | OK |
| 94 Icemon | champion | 8 | ice 4/424; battle 4/500 | ice 4/424; battle 2/320 | Buster Dive: 500/258 | Frigimon: 10/430 | OK |
| 96 Tsukaimon | rookie | 7 | battle 4/500; air 3/389 | battle 4/500; air 3/389 | Buster Dive: 500/258 | Patamon: 7/500 | OK |
| 100 IceDevimon | champion | 10 | ice 4/424; battle 6/320 | ice 4/424; battle 6/320 | Ice Statue: 424/186 | Frigimon: 10/430 | OK |
| 104 BlueMeramon | ultimate | 10 | ice 4/424; fire 6/444 | ice 4/424; fire 6/444 | Prominence Beam: 444/183 | Whamon: 10/430 | OK |
| 105 Gururumon | champion | 10 | battle 6/500; ice 4/424 | battle 6/500; ice 4/424 | Buster Dive: 500/258 | Devimon: 12/586 | OK |
| 106 Saberdramon | champion | 10 | fire 6/444; air 4/389 | fire 6/444; air 4/389 | Prominence Beam: 444/183 | Birdramon: 10/444 | OK |
| 107 Soulmon | champion | 10 | air 6/586; ice 4/264 | air 6/586; ice 4/264 | Thunder Justice: 586/330 | Bakemon: 10/586 | OK |
| 108 Golemon | champion | 10 | ice 8/430; battle 2/52 | ice 8/430; battle 2/52 | Aurora Freeze: 430/258 | Frigimon: 10/430 | OK |
| 109 Otamamon | rookie | 7 | ice 7/424 | ice 7/424 | Ice Statue: 424/186 | Betamon: 7/264 | OK |
| 110 Gekomon | champion | 8 | ice 8/430 | ice 8/430 | Aurora Freeze: 430/258 | Frigimon: 10/430 | OK |
| 111 Tentomon | rookie | 7 | nature 7/500 | nature 7/500 | Bug: 500/354 | Kunemon: 7/382 | OK |
| 112 WaruSeadramon | ultimate | 13 | ice 8/430; air 5/586 | ice 8/430; air 5/586 | Thunder Justice: 586/330 | MegaSeadramon: 11/430 | OK |
| 113 Meteormon | ultimate | 9 | fire 6/444; battle 3/500 | fire 6/444; battle 3/500 | Buster Dive: 500/258 | Digitamamon: 15/586 | OK |
| 115 Machinedramon | mega | 5 | mech 2/573; air 2/586; battle 1/320 | mech 2/573; air 2/586; battle 1/320 | Thunder Justice: 586/330 | Andromon †: 14/722 | deferred identity |
| 116 Analogman | mega | 7 | mech 5/722; air 2/382 | mech 5/722; air 2/382 | DG Dimension: 722/420 | Andromon †: 14/722 | deferred identity |
| 117 Jijimon | mega | 6 | battle 6/500 | battle 6/500 | Buster Dive: 500/258 | HerculesKabuterimon: 14/500 | deferred identity |
| 119 ShogunGekomon | ultimate | 8 | ice 8/430 | ice 8/430 | Aurora Freeze: 430/258 | Whamon: 10/430 | OK |
| 120 KingSukamon | ultimate | 8 | filth 8/333 | filth 8/333 | Ult Poop Hell: 333/333 | Etemon: 13/586 | OK |
| 121 Cherrymon | ultimate | 8 | nature 8/500 | nature 8/500 | Bug: 500/354 | Piximon: 12/500 | OK |
| 122 Hagurumon | rookie | 5 | mech 3/256; air 2/120 | mech 3/256; air 2/120 | Reverse Prog: 256/297 | baby: not applicable | OK |
| 123 Tinmon | ultimate | 7 → 11 | ice 5/264 → 7/430; nature 2/180 → 4/310 | ice 5/264 → 7/430; nature 2/180 → 4/310 | Aurora Freeze: 430/258 | Whamon: 10/430 | added |
| 124 MasterTyrannomon | ultimate | 10 | battle 7/500; fire 3/444 | battle 7/500; fire 3/444 | Buster Dive: 500/258 | Mamemon: 13/500 | OK |
| 126 Brachiomon | ultimate | 13 | fire 8/488; battle 5/500 | fire 8/488; battle 5/500 | Buster Dive: 500/258 | Digitamamon: 15/586 | OK |
| 180 Veemon | rookie | 7 | battle 4/193; fire 3/155 | battle 4/193; fire 3/155 | Dynamite Kick: 193/99 | Gabumon: 7/320 | OK |
| 181 Puppetmon | mega | 14 | nature 6/500; battle 4/500; mech 4/430 | nature 6/500; battle 4/500; mech 4/430 | Bug: 500/354 | HerculesKabuterimon: 14/500 | OK |
| 182 Kimeramon | ultimate | 13 | fire 8/488; battle 5/500 | fire 8/488; battle 5/500 | Buster Dive: 500/258 | Digitamamon: 15/586 | OK |
| 183 Wormmon | rookie | 7 → 8 | nature 4/117 → 5/157; battle 3/52 | nature 4/117 → 5/157; battle 3/52 | Danger Sting: 157/102 | Kunemon: 7/382 | added |
| 184 Hawkmon | rookie | 7 | air 4/225; battle 3/52 | air 4/225; battle 3/52 | Confused Storm: 225/216 | Elecmon: 7/382 | OK |
| 185 Armadillomon | rookie | 7 | battle 4/178; nature 3/62 | battle 4/178; nature 3/62 | Tremar: 178/168 | Gabumon: 7/320 | OK |
| 187 Stingmon | champion | 10 → 12 | nature 6/180 → 7/500; battle 4/193 → 5/320 | nature 6/180 → 7/500; battle 4/193 → 5/320 | Bug: 500/354 | Kuwagamon: 10/389 | added |
| 188 Aquilamon | champion | 10 | air 6/382; battle 4/193 | air 6/382; battle 4/193 | Megalo Spark: 382/174 | Angemon: 10/389 | OK |
| 189 Ankylomon | champion | 10 | battle 6/320; nature 4/310 | battle 6/320; nature 4/310 | Megaton Punch: 320/186 | Drimogemon: 10/500 | OK |
| 190 Angewomon | ultimate | 13 | air 8/586; battle 5/500 | air 8/586; battle 5/500 | Thunder Justice: 586/330 | Monzaemon: 13/586 | OK |
| 191 MetalGarurumon | mega | 14 | ice 6/430; mech 4/722; battle 4/320 | ice 6/430; mech 4/722; battle 4/320 | DG Dimension: 722/420 | Whamon †: 10/430 | OK |
| 192 Imperialdramon | mega | 14 | mech 6/722; fire 4/488; battle 4/320 | mech 6/722; fire 4/488; battle 4/320 | DG Dimension: 722/420 | MetalGreymonVirus †: 14/722 | OK |
| 193 Digmon | champion | 10 | battle 6/320; nature 4/310 | battle 6/320; nature 4/310 | Megaton Punch: 320/186 | Drimogemon: 10/500 | OK |
| 194 ExVeemon | champion | 10 | battle 6/285; fire 4/210 | battle 6/285; fire 4/210 | Counter: 285/165 | Tyrannomon: 10/500 | OK |
| 195 Flamedramon | champion | 10 | fire 6/400; battle 4/193 | fire 6/400; battle 4/193 | Meltdown: 400/318 | Meramon: 10/488 | OK |
| 196 Halsemon | champion | 10 | air 6/382; battle 4/178 | air 6/382; battle 4/178 | Megalo Spark: 382/174 | Angemon: 10/389 | OK |
| 197 Magnamon | ultimate | 13 | battle 8/500; mech 5/722 | battle 8/500; mech 5/722 | DG Dimension: 722/420 | Mamemon: 13/500 | OK |
| 198 Nefertimon | champion | 10 | air 6/389; fire 4/210 | air 6/389; fire 4/210 | Spinning Shot: 389/150 | Airdramon: 10/444 | OK |
| 199 Paildramon | ultimate | 13 | battle 8/500; mech 5/722 | battle 8/500; mech 5/722 | DG Dimension: 722/420 | Mamemon: 13/500 | OK |
| 200 Pegasusmon | champion | 10 | air 6/382; battle 4/193 | air 6/382; battle 4/193 | Megalo Spark: 382/174 | Angemon: 10/389 | OK |
| 201 Lighdramon | champion | 10 | air 6/382; battle 4/193 | air 6/382; battle 4/193 | Megalo Spark: 382/174 | Angemon: 10/389 | OK |
| 202 Submarimon | champion | 10 | ice 6/264; battle 4/500 | ice 6/264; battle 4/500 | Buster Dive: 500/258 | Frigimon: 10/430 | OK |
| 203 Veedramon | champion | 10 | fire 6/400; battle 4/320 | fire 6/400; battle 4/320 | Meltdown: 400/318 | Meramon: 10/488 | OK |
| 205 MegaKabuterimon | ultimate | 13 | nature 6/500; fire 4/488; air 3/389 | nature 6/500; fire 4/488; air 3/389 | Bug: 500/354 | Piximon: 12/500 | OK |
| 206 MagnaAngemon | ultimate | 13 | air 8/586; battle 5/500 | air 8/586; battle 5/500 | Thunder Justice: 586/330 | Monzaemon: 13/586 | OK |
| 207 Seraphimon | mega | 14 | air 6/586; fire 4/488; battle 4/320 | air 6/586; fire 4/488; battle 4/320 | Thunder Justice: 586/330 | Phoenixmon: 13/586 | OK |
| 208 Togemon | champion | 10 → 11 | nature 6/180 → 7/310; battle 4/320 | nature 6/180 → 7/310; battle 4/320 | Megaton Punch: 320/186 | Kuwagamon: 10/389 | added |
| 209 Lillymon | ultimate | 13 | nature 8/500; battle 5/500 | nature 8/500; battle 5/500 | Bug: 500/354 | Piximon: 12/500 | OK |
| 210 GranKuwagamon | mega | 14 | nature 6/500; battle 4/500; air 4/389 | nature 6/500; battle 4/500; air 4/389 | Bug: 500/354 | HerculesKabuterimon: 14/500 | OK |
| 211 MetalSeadramon | mega | 14 | ice 8/430; mech 6/722 | ice 8/430; mech 6/722 | DG Dimension: 722/420 | Whamon †: 10/430 | OK |
| 212 VenomMyotismon | mega | 14 | fire 8/488; battle 6/500 | fire 8/488; battle 6/500 | Buster Dive: 500/258 | HerculesKabuterimon: 14/500 | OK |
| 213 AeroVeedramon | ultimate | 13 | air 6/586; battle 4/500; fire 3/444 | air 6/586; battle 4/500; fire 3/444 | Thunder Justice: 586/330 | Andromon: 14/722 | OK |
| 214 Shakkoumon | ultimate | 13 | nature 8/500; mech 5/722 | nature 8/500; mech 5/722 | DG Dimension: 722/420 | Piximon: 12/500 | OK |
| 215 Magnadramon | mega | 14 | fire 8/488; air 6/586 | fire 8/488; air 6/586 | Thunder Justice: 586/330 | Phoenixmon: 13/586 | OK |
| 216 Devidramon | champion | 10 | battle 6/320; air 4/225 | battle 6/320; air 4/225 | Megaton Punch: 320/186 | Leomon: 10/500 | OK |
| 217 Gomamon | rookie | 7 | ice 4/211; battle 3/52 | ice 4/211; battle 3/52 | Water Blit: 211/102 | Betamon: 7/264 | OK |
| 218 Ikkakumon | champion | 10 | ice 6/264; battle 4/193 | ice 6/264; battle 4/193 | Giga Freeze: 264/120 | Frigimon: 10/430 | OK |
| 219 Zudomon | ultimate | 13 | battle 8/500; ice 5/430 | battle 8/500; ice 5/430 | Buster Dive: 500/258 | SkullGreymon: 13/573 | OK |
| 220 Vikemon | mega | 14 | ice 8/430; battle 6/500 | ice 8/430; battle 6/500 | Buster Dive: 500/258 | Whamon †: 10/430 | OK |
| 221 Salamon | rookie | 7 | battle 4/193; air 3/178 | battle 4/193; air 3/178 | Dynamite Kick: 193/99 | Patamon: 7/500 | OK |
| 222 BlackGatomon | champion | 10 | battle 6/285; air 4/225 | battle 6/285; air 4/225 | Counter: 285/165 | Leomon: 10/500 | OK |
| 223 LadyDevimon | ultimate | 13 | battle 8/500; air 5/586 | battle 8/500; air 5/586 | Thunder Justice: 586/330 | Monzaemon: 13/586 | OK |
| 224 MetalGreymonVaccine | ultimate | 13 | mech 6/722; fire 4/488; battle 3/320 | mech 6/722; fire 4/488; battle 3/320 | DG Dimension: 722/420 | MetalGreymonVirus: 14/722 | OK |
| 225 Shurimon | champion | 10 → 12 | battle 5/193 → 6/255; air 3/178 → 4/389; nature 2/62 | battle 5/193 → 6/255; air 3/178 → 4/389; nature 2/62 | Spinning Shot: 389/150 | Devimon: 12/586 | added |
| 226 Silphymon | ultimate | 13 | air 8/586; battle 5/500 | air 8/586; battle 5/500 | Thunder Justice: 586/330 | Monzaemon: 13/586 | OK |
| 227 Apemon | champion | 10 | battle 6/320; fire 4/210 | battle 6/320; fire 4/210 | Megaton Punch: 320/186 | Tyrannomon: 10/500 | OK |
| 228 Baronmon | champion | 10 | fire 6/400; battle 4/178 | fire 6/400; battle 4/178 | Meltdown: 400/318 | Meramon: 10/488 | OK |
| 229 Phantomon | ultimate | 13 | air 6/586; ice 4/430; battle 3/320 | air 6/586; ice 4/430; battle 3/320 | Thunder Justice: 586/330 | Andromon: 14/722 | OK |
| 230 Rosemon | mega | 14 | nature 8/500; air 6/586 | nature 8/500; air 6/586 | Thunder Justice: 586/330 | HerculesKabuterimon: 14/500 | OK |
| 231 ShellNumemon | champion | 10 | filth 6/211; battle 4/193 | filth 6/211; battle 4/193 | Big Poop Toss: 211/192 | Nanimon: 10/320 | OK |
| 232 BomberNanimon | champion | 10 | battle 6/320; mech 4/256 | battle 6/320; mech 4/256 | Megaton Punch: 320/186 | Tyrannomon: 10/500 | OK |
| 233 RedOtamamon | rookie | 7 | fire 4/210; battle 3/52 | fire 4/210; battle 3/52 | Red Inferno: 210/171 | Agumon: 7/279 | OK |
| 234 Gatomon | champion | 10 | battle 6/285; air 4/382 | battle 6/285; air 4/382 | Megalo Spark: 382/174 | Leomon: 10/500 | OK |
| 235 Candlemon | rookie | 7 | fire 4/210; battle 3/52 | fire 4/210; battle 3/52 | Red Inferno: 210/171 | Agumon: 7/279 | OK |
| 236 DemiDevimon | rookie | 7 | battle 4/193; air 3/178 | battle 4/193; air 3/178 | Dynamite Kick: 193/99 | Patamon: 7/500 | OK |
| 237 Diaboromon | mega | 14 | mech 8/722; nature 3/500; battle 3/500 | mech 8/722; nature 3/500; battle 2/320 | DG Dimension: 722/420 | MetalGreymonVirus †: 14/722 | OK |
| 238 Dolphmon | champion | 12 | ice 8/430; air 4/225 | ice 8/430; air 4/225 | Aurora Freeze: 430/258 | Shellmon: 8/430 | OK |
| 239 Gizamon | rookie | 7 | ice 4/211; battle 3/52 | ice 4/211; battle 3/52 | Water Blit: 211/102 | Betamon: 7/264 | OK |
| 240 Gesomon | champion | 10 | ice 6/264; battle 4/320 | ice 6/264; battle 4/320 | Megaton Punch: 320/186 | Frigimon: 10/430 | OK |
| 241 Wizardmon | champion | 10 | air 6/382; battle 4/178 | air 6/382; battle 4/178 | Megalo Spark: 382/174 | Angemon: 10/389 | OK |
| 242 Sorcermon | champion | 10 | ice 6/424; air 4/225 | ice 6/424; air 4/225 | Ice Statue: 424/186 | Shellmon: 8/430 | OK |
| 243 Starmon | champion | 10 | fire 6/400; battle 4/193 | fire 6/400; battle 4/193 | Meltdown: 400/318 | Meramon: 10/488 | OK |
| 244 SuperStarmon | ultimate | 13 | fire 8/488; battle 5/500 | fire 8/488; battle 5/500 | Buster Dive: 500/258 | Digitamamon: 15/586 | OK |
| 245 Piedmon | mega | 14 | battle 8/500; air 6/586 | battle 8/500; air 6/586 | Thunder Justice: 586/330 | HerculesKabuterimon: 14/500 | OK |
| 246 Infermon | ultimate | 13 | mech 8/722; nature 5/500 | mech 8/722; nature 5/500 | DG Dimension: 722/420 | Vademon: 11/722 | OK |
| 247 Kokuwamon | rookie | 7 | air 4/225; mech 3/226 | air 4/225; mech 3/226 | Power Crane: 226/126 | Elecmon: 7/382 | OK |
| 248 MarineAngemon | mega | 14 | ice 8/430; battle 6/500 | ice 8/430; battle 6/500 | Buster Dive: 500/258 | Whamon †: 10/430 | OK |
| 249 Quetzalmon | champion | 10 | air 6/382; ice 4/264 | air 6/382; ice 4/264 | Megalo Spark: 382/174 | Bakemon: 10/586 | OK |
| 250 Shadramon | champion | 10 | fire 6/400; battle 4/193 | fire 6/400; battle 4/193 | Meltdown: 400/318 | Meramon: 10/488 | OK |
| 251 Solarmon | rookie | 7 | fire 4/210; mech 3/226 | fire 4/210; mech 3/226 | Power Crane: 226/126 | Agumon: 7/279 | OK |
| 252 Thundermon | champion | 10 | air 6/382; battle 4/320 | air 6/382; battle 4/320 | Megalo Spark: 382/174 | Angemon: 10/389 | OK |
| 253 Tuskmon | champion | 10 | battle 6/320; fire 4/210 | battle 6/320; fire 4/210 | Megaton Punch: 320/186 | Tyrannomon: 10/500 | OK |
| 254 Tylomon | champion | 10 | ice 6/264; battle 4/178 | ice 6/264; battle 4/178 | Giga Freeze: 264/120 | Frigimon: 10/430 | OK |
| 255 Valkyrimon | mega | 14 | air 6/586; battle 4/500; ice 4/264 | air 6/586; battle 4/500; ice 4/264 | Thunder Justice: 586/330 | Phoenixmon: 13/586 | OK |
| 256 VioletElecmon | rookie | 7 | air 4/382; battle 3/52 | air 4/382; battle 3/52 | Megalo Spark: 382/174 | Elecmon: 7/382 | OK |
| 257 Triceramon | ultimate | 13 | battle 8/500; nature 5/500 | battle 8/500; nature 5/500 | Buster Dive: 500/258 | Mamemon: 13/500 | OK |
| 258 SaberLeomon | mega | 14 | battle 8/500; air 6/586 | battle 8/500; air 6/586 | Thunder Justice: 586/330 | HerculesKabuterimon: 14/500 | OK |
| 259 Okuwamon | ultimate | 13 | nature 6/500; battle 4/500; air 3/389 | nature 6/500; battle 4/500; air 3/389 | Bug: 500/354 | Piximon: 12/500 | OK |
| 260 MetalTyrannomon | ultimate | 13 | mech 6/722; fire 4/488; battle 3/320 | mech 6/722; fire 4/488; battle 3/320 | DG Dimension: 722/420 | MetalGreymonVirus: 14/722 | OK |
| 261 Tortomon | champion | 10 | battle 6/320; nature 4/310 | battle 6/320; nature 4/310 | Megaton Punch: 320/186 | Drimogemon: 10/500 | OK |
| 262 Flymon | champion | 10 → 12 | nature 6/180 → 7/500; air 4/225 → 5/389 | nature 6/180 → 7/500; air 4/225 → 5/389 | Bug: 500/354 | Kabuterimon: 11/444 | added |
| 263 Mushroomon | rookie | 7 → 8 | nature 4/117 → 5/180; battle 3/52 | nature 4/117 → 5/180; battle 3/52 | Charm Perfume: 180/210 | Kunemon: 7/382 | added |
| 264 Raremon | champion | 10 | filth 6/211; battle 4/193 | filth 6/211; battle 4/193 | Big Poop Toss: 211/192 | Nanimon: 10/320 | OK |
| 265 DarkTyrannomon | champion | 10 | fire 6/444; battle 4/320 | fire 6/444; battle 4/320 | Prominence Beam: 444/183 | Meramon: 10/488 | OK |
| 266 ExTyrannomon | ultimate | 13 | battle 8/500; fire 5/488 | battle 8/500; fire 5/488 | Buster Dive: 500/258 | Mamemon: 13/500 | OK |
| 267 Mammothmon | ultimate | 13 | ice 8/430; battle 5/500 | ice 8/430; battle 5/500 | Buster Dive: 500/258 | Whamon: 10/430 | OK |
| 268 SkullMammothmon | mega | 14 | ice 8/430; battle 6/500 | ice 8/430; battle 6/500 | Buster Dive: 500/258 | Whamon †: 10/430 | OK |
| 269 Garbagemon | ultimate | 13 | filth 8/333; mech 5/722 | filth 8/333; mech 5/722 | DG Dimension: 722/420 | Etemon: 13/586 | OK |
| 270 PrinceMamemon | mega | 14 | battle 8/500; mech 6/722 | battle 8/500; mech 6/722 | DG Dimension: 722/420 | HerculesKabuterimon: 14/500 | OK |
| 271 Plesiomon | mega | 14 | ice 8/430; air 6/586 | ice 8/430; air 6/586 | Thunder Justice: 586/330 | MegaSeadramon †: 11/430 | OK |
| 272 Woodmon | champion | 10 | nature 6/310; battle 4/320 | nature 6/310; battle 4/320 | Megaton Punch: 320/186 | Kuwagamon: 10/389 | OK |
| 273 Floramon | rookie | 7 | nature 4/180; ice 3/120 | nature 4/180; ice 3/120 | Charm Perfume: 180/210 | Palmon: 7/211 | OK |
| 274 Blossomon | ultimate | 13 | nature 8/500; battle 5/500 | nature 8/500; battle 5/500 | Bug: 500/354 | Piximon: 12/500 | OK |
| 275 Scorpiomon | ultimate | 13 | ice 6/430; battle 4/500; nature 3/180 | ice 6/430; battle 4/500; nature 3/180 | Buster Dive: 500/258 | Whamon: 10/430 | OK |
| 276 Baihumon | mega | 14 | battle 8/500; mech 6/722 | battle 8/500; mech 6/722 | DG Dimension: 722/420 | HerculesKabuterimon: 14/500 | OK |
| 277 SkullMeramon | ultimate | 13 | fire 8/488; battle 5/500 | fire 8/488; battle 5/500 | Buster Dive: 500/258 | Digitamamon: 15/586 | OK |
| 278 Octomon | champion | 10 | ice 6/264; battle 4/178 | ice 6/264; battle 4/178 | Giga Freeze: 264/120 | Frigimon: 10/430 | OK |
| 279 MarineDevimon | ultimate | 13 | ice 8/430; battle 5/500 | ice 8/430; battle 5/500 | Buster Dive: 500/258 | Whamon: 10/430 | OK |
| 280 Pumpkinmon | ultimate | 13 | battle 8/500; fire 5/488 | battle 8/500; fire 5/488 | Buster Dive: 500/258 | Mamemon: 13/500 | OK |
| 281 Cyclonemon | champion | 10 | fire 6/444; battle 4/320 | fire 6/444; battle 4/320 | Prominence Beam: 444/183 | Meramon: 10/488 | OK |
| 282 Kiwimon | champion | 10 | nature 6/310; battle 4/193 | nature 6/310; battle 4/193 | Green Trap: 310/147 | Kuwagamon: 10/389 | OK |
| 283 Syakomon | rookie | 7 | ice 4/211; battle 3/52 | ice 4/211; battle 3/52 | Water Blit: 211/102 | Betamon: 7/264 | OK |
| 284 Crabmon | rookie | 7 | ice 4/211; battle 3/52 | ice 4/211; battle 3/52 | Water Blit: 211/102 | Betamon: 7/264 | OK |
| 285 Gazimon | rookie | 7 | battle 4/178; nature 3/117 | battle 4/178; nature 3/117 | Tremar: 178/168 | Gabumon: 7/320 | OK |
| 286 Deramon | ultimate | 13 | nature 8/500; battle 5/500 | nature 8/500; battle 5/500 | Bug: 500/354 | Piximon: 12/500 | OK |
| 287 Tapirmon | rookie | 7 | battle 4/178; air 3/178 | battle 4/178; air 3/178 | Tremar: 178/168 | Patamon: 7/500 | OK |
| 288 Boltmon | mega | 14 | battle 8/500; mech 6/722 | battle 8/500; mech 6/722 | DG Dimension: 722/420 | HerculesKabuterimon: 14/500 | OK |
| 289 ChaosLord | mega | 14 | mech 8/722; battle 6/500 | mech 8/722; battle 6/500 | DG Dimension: 722/420 | MetalGreymonVirus †: 14/722 | OK |
| 290 Clockmon | champion | 10 | mech 6/430; battle 4/193 | mech 6/430; battle 4/193 | Delete Program: 430/219 | baby: not applicable | OK |
| 291 Dragomon | ultimate | 13 | ice 8/430; battle 5/500 | ice 8/430; battle 5/500 | Buster Dive: 500/258 | Whamon: 10/430 | OK |
| 292 Deltamon | champion | 10 | battle 6/320; fire 4/210 | battle 6/320; fire 4/210 | Megaton Punch: 320/186 | Tyrannomon: 10/500 | OK |
| 293 Gryphonmon | mega | 14 | air 8/586; battle 6/500 | air 8/586; battle 6/500 | Thunder Justice: 586/330 | Phoenixmon: 13/586 | OK |
| 294 Datamon | ultimate | 13 | mech 8/722; air 3/382; fire 2/444 | mech 8/722; air 3/382; fire 2/444 | DG Dimension: 722/420 | MetalGreymonVirus: 14/722 | OK |
| 295 Vilemon | champion | 10 | battle 6/285; air 4/225 | battle 6/285; air 4/225 | Counter: 285/165 | Leomon: 10/500 | OK |
| 296 Grizzlymon | champion | 10 → 11 | battle 6/320; ice 4/126 → 5/264 | battle 6/320; ice 4/126 → 5/264 | Megaton Punch: 320/186 | Devimon: 12/586 | added |
| 297 Marsmon | mega | 14 | battle 8/500; fire 6/488 | battle 8/500; fire 6/488 | Buster Dive: 500/258 | HerculesKabuterimon: 14/500 | OK |
| 298 Dokugumon | champion | 10 | nature 6/310; battle 4/178 | nature 6/310; battle 4/178 | Green Trap: 310/147 | Kuwagamon: 10/389 | OK |
| 299 Hookmon | champion | 10 | battle 6/320; mech 4/389 | battle 6/320; mech 4/389 | Pulse Laser: 389/168 | Tyrannomon: 10/500 | OK |
| 300 SlashAngemon | mega | 14 | battle 8/500; air 6/586 | battle 8/500; air 6/586 | Thunder Justice: 586/330 | HerculesKabuterimon: 14/500 | OK |
| 302 HiAndromon | mega | 14 | mech 8/722; battle 6/500 | mech 8/722; battle 6/500 | DG Dimension: 722/420 | MetalGreymonVirus †: 14/722 | OK |
| 303 KingEtemon | mega | 14 | battle 6/500; air 4/586; filth 4/211 | battle 6/500; air 4/586; filth 4/211 | Thunder Justice: 586/330 | HerculesKabuterimon: 14/500 | OK |
| 304 Divermon | ultimate | 13 | ice 8/430; battle 5/500 | ice 8/430; battle 5/500 | Buster Dive: 500/258 | Whamon: 10/430 | OK |
| 305 Ebidramon | champion | 10 | ice 6/264; battle 4/193 | ice 6/264; battle 4/193 | Giga Freeze: 264/120 | Frigimon: 10/430 | OK |
| 306 GrapLeomon | ultimate | 13 | battle 8/500; air 5/586 | battle 8/500; air 5/586 | Thunder Justice: 586/330 | Monzaemon: 13/586 | OK |
| 307 BlackKingNumemon | mega | 14 | filth 8/333; battle 6/500 | filth 8/333; battle 6/500 | Buster Dive: 500/258 | Etemon †: 13/586 | OK |
| 308 Dinohyumon | champion | 10 | battle 6/320; nature 4/310 | battle 6/320; nature 4/310 | Megaton Punch: 320/186 | Drimogemon: 10/500 | OK |
| 309 Antylamon | ultimate | 13 | battle 8/500; air 5/586 | battle 8/500; air 5/586 | Thunder Justice: 586/330 | Monzaemon: 13/586 | OK |
| 310 Assaultmon | ultimate | 13 | mech 8/722; battle 5/500 | mech 8/722; battle 5/500 | DG Dimension: 722/420 | MetalGreymonVirus: 14/722 | OK |
| 311 Arukenimon | ultimate | 13 | nature 8/500; battle 5/500 | nature 8/500; battle 5/500 | Bug: 500/354 | Piximon: 12/500 | OK |
| 312 Creepymon | mega | 14 | fire 6/488; battle 4/500; air 4/389 | fire 6/488; battle 4/500; air 4/389 | Buster Dive: 500/258 | HerculesKabuterimon: 14/500 | OK |
| 313 Bulbmon | ultimate | 13 | mech 8/722; ice 5/430 | mech 8/722; ice 5/430 | DG Dimension: 722/420 | Megadramon: 13/722 | OK |
| 314 SkullSatamon | ultimate | 13 | battle 8/500; fire 5/488 | battle 8/500; fire 5/488 | Buster Dive: 500/258 | Mamemon: 13/500 | OK |
| 315 Taomon | ultimate | 13 | fire 6/488; air 4/586; battle 3/320 | fire 6/488; air 4/586; battle 3/320 | Thunder Justice: 586/330 | Digitamamon: 15/586 | OK |
| 316 Sakuyamon | mega | 14 | air 6/586; fire 4/488; battle 4/320 | air 6/586; fire 4/488; battle 4/320 | Thunder Justice: 586/330 | Phoenixmon: 13/586 | OK |
| 317 Fujinmon | mega | 14 | air 6/586; mech 4/722; battle 4/320 | air 6/586; mech 4/722; battle 4/320 | DG Dimension: 722/420 | Phoenixmon: 13/586 | OK |
| 318 Gallantmon | mega | 14 | battle 6/500; mech 4/722; air 4/389 | battle 6/500; mech 4/722; air 4/389 | DG Dimension: 722/420 | HerculesKabuterimon: 14/500 | OK |
| 319 Pharaohmon | mega | 14 | nature 8/500; battle 6/500 | nature 8/500; battle 6/500 | Bug: 500/354 | HerculesKabuterimon: 14/500 | OK |
| 320 Growlmon | champion | 10 | fire 6/444; battle 4/193 | fire 6/444; battle 4/193 | Prominence Beam: 444/183 | Meramon: 10/488 | OK |
| 321 Knightmon | ultimate | 13 | battle 8/500; mech 5/722 | battle 8/500; mech 5/722 | DG Dimension: 722/420 | Mamemon: 13/500 | OK |
| 322 Kyukimon | ultimate | 13 | air 8/586; battle 5/500 | air 8/586; battle 5/500 | Thunder Justice: 586/330 | Monzaemon: 13/586 | OK |
| 323 Lynxmon | champion | 10 | fire 6/400; battle 4/193 | fire 6/400; battle 4/193 | Meltdown: 400/318 | Meramon: 10/488 | OK |
| 324 Maildramon | champion | 10 | battle 6/320; air 4/225 | battle 6/320; air 4/225 | Megaton Punch: 320/186 | Leomon: 10/500 | OK |
| 325 Musyamon | champion | 10 | battle 6/285; air 4/225 | battle 6/285; air 4/225 | Counter: 285/165 | Leomon: 10/500 | OK |
| 326 WarGrowlmon | ultimate | 13 | fire 6/488; mech 4/722; battle 3/320 | fire 6/488; mech 4/722; battle 3/320 | DG Dimension: 722/420 | Digitamamon: 15/586 | OK |
| 327 Gargoylemon | champion | 10 | battle 6/320; nature 4/310 | battle 6/320; nature 4/310 | Megaton Punch: 320/186 | Drimogemon: 10/500 | OK |
| 328 Snimon | champion | 10 → 12 | battle 5/193 → 6/285; air 3/178 → 4/389; nature 2/62 | battle 5/193 → 6/285; air 3/178 → 4/389; nature 2/62 | Spinning Shot: 389/150 | Devimon: 12/586 | added |
| 329 Ghoulmon | mega | 14 | mech 6/722; battle 4/500; air 4/389 | mech 6/722; battle 4/500; air 4/389 | DG Dimension: 722/420 | Andromon †: 14/722 | OK |
| 330 Minotarumon | champion | 10 | battle 6/320; nature 4/117 | battle 6/320; nature 4/117 | Megaton Punch: 320/186 | Drimogemon: 10/500 | OK |
| 331 Vemmon | rookie | 7 | battle 4/193; mech 3/226 | battle 4/193; mech 3/226 | Power Crane: 226/126 | Gabumon: 7/320 | OK |
| 332 Roachmon | champion | 10 → 13 | nature 5/157 → 6/500; filth 3/88 → 4/211; battle 2/193 → 3/320 | nature 5/157 → 6/500; filth 3/88 → 4/211; battle 2/193 → 3/320 | Bug: 500/354 | Kuwagamon: 10/389 | added |
| 333 Raijinmon | mega | 14 | air 6/586; mech 4/722; battle 4/320 | air 6/586; mech 4/722; battle 4/320 | DG Dimension: 722/420 | Phoenixmon: 13/586 | OK |
| 334 Mummymon | ultimate | 13 | battle 8/500; mech 5/722; air 0/0 | battle 8/500; mech 5/722; air 0/0 | DG Dimension: 722/420 | SkullGreymon: 13/573 | intentional Air gap |
| 335 MegaGargomon | mega | 14 | mech 8/722; battle 6/500 | mech 8/722; battle 6/500 | DG Dimension: 722/420 | MetalGreymonVirus †: 14/722 | OK |
| 336 Raidenmon | mega | 14 | air 6/586; fire 4/488; mech 4/430 | air 6/586; fire 4/488; mech 4/430 | Thunder Justice: 586/330 | Phoenixmon: 13/586 | OK |
| 351 Kotemon | rookie | 7 | battle 4/193; fire 3/155 | battle 4/193; fire 3/155 | Dynamite Kick: 193/99 | Gabumon: 7/320 | OK |
| 352 Monmon | rookie | 7 | battle 4/193; air 3/178 | battle 4/193; air 3/178 | Dynamite Kick: 193/99 | Patamon: 7/500 | OK |
| 353 Bearmon | rookie | 7 | battle 4/178; ice 3/126 | battle 4/178; ice 3/126 | Tremar: 178/168 | Gabumon: 7/320 | OK |
| 354 Renamon | rookie | 7 | battle 4/193; fire 3/155 | battle 4/193; fire 3/155 | Dynamite Kick: 193/99 | Gabumon: 7/320 | OK |
| 373 WarGreymon | mega | 14 | fire 6/488; battle 4/500; air 4/389 | fire 6/488; battle 4/500; air 4/389 | Buster Dive: 500/258 | HerculesKabuterimon: 14/500 | OK |
| 400 Apocalymon | mega | 14 | mech 6/722; battle 4/500; ice 4/264 | mech 6/722; battle 4/500; ice 4/264 | DG Dimension: 722/420 | Megadramon †: 13/722 | OK |
| 401 Pukumon | mega | 14 | ice 8/430; battle 6/500 | ice 8/430; battle 6/500 | Buster Dive: 500/258 | Whamon †: 10/430 | OK |
| 402 NeoCrimson | mega | 14 | fire 8/488; battle 6/500 | fire 8/488; battle 6/500 | Buster Dive: 500/258 | HerculesKabuterimon: 14/500 | OK |
| 403 Beelzemon | mega | 14 | battle 8/500; mech 6/722 | battle 8/500; mech 6/722 | DG Dimension: 722/420 | HerculesKabuterimon: 14/500 | OK |
| 404 BlackWarGreymon | mega | 14 | fire 6/488; battle 4/500; air 4/389 | fire 6/488; battle 4/500; air 4/389 | Buster Dive: 500/258 | HerculesKabuterimon: 14/500 | OK |
| 405 Cannondramon | mega | 14 | mech 8/722; fire 6/488 | mech 8/722; fire 6/488 | DG Dimension: 722/420 | MetalGreymonVirus †: 14/722 | OK |
| 406 MaloMyotismon | mega | 14 | fire 6/488; battle 4/500; air 4/389 | fire 6/488; battle 4/500; air 4/389 | Buster Dive: 500/258 | HerculesKabuterimon: 14/500 | OK |
| 407 Armageddemon | mega | 14 | fire 6/488; battle 4/500; mech 4/430 | fire 6/488; battle 4/500; mech 4/430 | Buster Dive: 500/258 | HerculesKabuterimon: 14/500 | OK |
| 408 Suijinmon | mega | 14 | ice 8/430; mech 6/722 | ice 8/430; mech 6/722 | DG Dimension: 722/420 | Whamon †: 10/430 | OK |
| 409 Kyubimon | champion | 10 | fire 6/400; battle 4/193 | fire 6/400; battle 4/193 | Meltdown: 400/318 | Meramon: 10/488 | OK |
| 430 Zanbamon | mega | 14 | battle 8/500; air 6/586 | battle 8/500; air 6/586 | Thunder Justice: 586/330 | HerculesKabuterimon: 14/500 | OK |
| 431 Kurisarimon | champion | 10 | mech 6/430; nature 4/117 | mech 6/430; nature 4/117 | Delete Program: 430/219 | baby: not applicable | OK |
| 432 Bastemon | ultimate | 13 | battle 8/500; nature 5/500 | battle 8/500; nature 5/500 | Buster Dive: 500/258 | Mamemon: 13/500 | OK |
| 433 Guilmon | rookie | 7 | fire 4/210; battle 3/52 | fire 4/210; battle 3/52 | Red Inferno: 210/171 | Agumon: 7/279 | OK |
| 460 Garudamon | ultimate | 13 | fire 6/488; air 4/586; battle 3/320 | fire 6/488; air 4/586; battle 3/320 | Thunder Justice: 586/330 | Digitamamon: 15/586 | OK |
| 461 Omnimon | mega | 14 | battle 6/500; ice 4/430; fire 4/444 | battle 6/500; ice 4/430; fire 4/444 | Buster Dive: 500/258 | HerculesKabuterimon: 14/500 | OK |
| 470 Pabumon | fresh | 0 | nature 0/0 | nature 0/0 | baby bubble only | Yuramon: 0/0 | baby: expected |
| 471 Pichimon | fresh | 0 | ice 0/0 | ice 0/0 | baby bubble only | baby: not applicable | baby: expected |
| 472 YukimiBotamon | fresh | 0 | air 0/0 | air 0/0 | baby bubble only | Punimon: 0/0 | baby: expected |
| 473 Nyokimon | fresh | 0 | nature 0/0 | nature 0/0 | baby bubble only | Yuramon: 0/0 | baby: expected |
| 474 Motimon | in-training | 0 | nature 0/0; mech 0/0 | nature 0/0; mech 0/0 | baby bubble only | Tanemon: 0/0 | baby: expected |
| 475 Bukamon | in-training | 0 | ice 0/0; battle 0/0 | ice 0/0; battle 0/0 | baby bubble only | Tsunomon: 0/0 | baby: expected |
| 476 Nyaromon | in-training | 0 | battle 0/0; air 0/0 | battle 0/0; air 0/0 | baby bubble only | Tokomon: 0/0 | baby: expected |
| 477 Yokomon | in-training | 0 | air 0/0; nature 0/0 | air 0/0; nature 0/0 | baby bubble only | Tsunomon: 0/0 | baby: expected |

## Coverage notes

Lower secondary power alone is not a reason to give every partner every ultimate spell: native Agumon has only 52 Battle power, Shellmon no Air move, and Digitamamon only 60 Ice power. Secondary element slots also preserve evolution links. Main-element power, usable alternatives, support/status identity, tier and total coverage were considered together. ShellNumemon/Raremon retain the deliberate Filth disadvantage; their 211-power attacks match native Nanimon, and their missing 333-power Ult Poop Hell is not an automatic defect. Submarimon, Ikkakumon, Gesomon, Tylomon, Octomon and Ebidramon reach the native Seadramon Ice ceiling of 264; they are not classified as weak merely because Frigimon has Aurora Freeze. Imported Rookies with 178–226 peaks remain within the native range rather than being uniformly promoted to Megaton Punch.

Original NPC partners with few moves are flagged for breadth without claiming that 500–722 power is weak. Their exact constraints and proposed follow-up moves appear above. The four recently differentiated Machine species and the Mummymon/SkullSatamon identity pair remain intact. All new babies retain their sole bubble; they are not candidates for ordinary attacks.
