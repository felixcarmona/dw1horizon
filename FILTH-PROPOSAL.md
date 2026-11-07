# Filth line proposal for v0.0.8

Status: **proposal only, pending approval**. No specialties, arsenals, evolution routes, requirements or icons change on this branch. The implemented changes repair BlackKingNumemon's field/care/victory animation and select native movement sounds for four imported species.

The baseline includes PR #297: KingSukamon already has Filth / Ice / Nature, Water Blit and Poison Powder, plus the lower toss release. Ice is the engine's Water/Ice category; Nature is Plant. Keep those changes. This review uses partner species, not the preserved NPC duplicates (for example Etemon 42, not 162; KingSukamon 120, not 463).

## Decision table

| Suggestion | Current | Proposed by the feedback | Recommendation and reason |
| --- | --- | --- | --- |
| Geremon identity | Native recolor; Filth; eight ordinary Filth moves and Party Time | Remove it, or make it normally raisable with a distinct arsenal | **Reject removal; accept differentiation.** It is already normally raisable from Otamamon, unlike the failure evolutions. Preserve that useful route and its native art. |
| Geremon Plant | Filth only | Filth/Plant; Charm Perfume and Poison Powder | **Accept as Filth/Nature/—.** Odor attacks suit its canon Hyper Smell. Plant is a gameplay interpretation of noxious clouds, not a botanical canon claim. Both proposed moves are modest direct damage with strong status utility. Keep all existing moves and finisher (11 total slots). |
| Geremon → Monzaemon | Natural children Garbagemon and Etemon; X Bandage already permits Monzaemon | Add the Monzaemon route | **Reject a new natural route for this pass.** Geremon already qualifies as a Champion for X Bandage (item 107, target 14). Nature still shares no specialty with Monzaemon's Battle/Air, so an added natural route needs another topology exception and a designed requirement row. Preserve existing children and the item route. |
| ShellNumemon specialties | Filth/Battle/— | Filth/Water, remove Battle | **Modify to Filth/Ice/Battle.** Water identity is plausible, though its official profile describes a defensive shell rather than an aquatic attack. Battle in slot three preserves ToyAgumon → ShellNumemon. Gizamon shares Ice. |
| ShellNumemon moves | Six ordinary Filth moves; Dynamite Kick, Muscle Charge, War Cry, Sonic Jab; Iga School Knife Throw finisher | Replace Battle moves with Water Blit, Aqua Magic, Tear Drop | **Modify:** replace the four Battle moves with those three Water moves plus Counter. Counter gives the third specialty a real move and represents the protective shell. Keep all six Filth moves and the finisher: 11 slots. Counter remains a conditional reaction, not an ordinary 285-power guaranteed hit. |
| Raremon third specialty | Filth/Battle/— | Add Machine | **Accept Filth/Battle/Mech.** Its official profile explicitly describes life sustained by machine parts. This is stronger canon support than interpreting its rotten body as a powerful martial artist. |
| Raremon move replacements | Dynamite Kick among four Battle moves | Remove Dynamite Kick; add Metal Sprinter, Power Crane, Megaton Punch | **Modify:** remove Dynamite Kick; add Metal Sprinter and Power Crane; defer Megaton Punch. Scrap attacks fit the machine remains. The profile emphasizes weak rotten muscles, and a convincing punch clip is unproved. Keep Muscle Charge, War Cry, Sonic Jab and Death Claw finisher: 12 slots. |
| Garbagemon | Filth/Mech; 13 ordinary moves plus Energy Bomb | Add Metal Sprinter | **Accept.** Its canon empty-can bazooka supports junk projectiles. Fits slot 15, shares its existing second specialty, and is weaker direct damage than Power Crane or DG Dimension. |
| Etemon | Battle/Air/Filth, includes Thunder Justice | Remove Thunder Justice to distinguish MetalEtemon | **Accept the removal**, retain the other 12 ordinary moves and finisher. Its next strongest Air move remains Spinning Shot (389 versus 586 power). Dark sphere/song identity does not require the strongest thunder spell. No global Thunder Justice nerf. |
| MetalEtemon | Already has Thunder Justice, identical move names and specialty order to Etemon | Add the Thunder Justice removed from Etemon; other suggestions welcome | **Accept the intended distinction; no addition needed.** Keep its current arsenal while removing Thunder Justice only from Etemon. Canon supports its mechanized fighting strength, but changing Air to Mech would remove the specialty needed to learn its three Air moves; do not bundle that redesign. |
| KingSukamon icon | Authored icon in `content/icons/120.txt`; card artwork is a different presentation | Reuse the better card-menu image in the chart | **Modify:** use the card pose as the reference for a chart-specific redraw or a masked, disc-derived conversion. The reviewed source is CARD.ALL entry 21, 150×180 at 8 bpp; the chart needs 16×16 with at most 15 opaque colors. Whole-art and face-crop previews lose the silhouette against the stage background. A direct resize is not ready to replace the current tile. No icon swap is implemented here. |
| KingSukamon Battle expansion | Already Filth/Ice/Nature with Water Blit and Poison Powder | Add Battle, Tremar, War Cry, Megaton Punch | **Reject for this pass.** All three specialty slots are occupied. Replacing either recent specialty would undo PR #297; the existing new moves already give it a distinct ranged/status role. |
| KingSukamon Machine expansion | Same current three specialties | Machine and Metal Sprinter | **Reject.** A crown is insufficient reason for mechanization, and this conflicts with the three-slot specialty budget. |
| KingSukamon Fire expansion | Same current three specialties | Fire, Magma Bomb, Red Inferno, Spit Fire, Fire Tower | **Reject.** Thematic joke rather than canon support; duplicates the new ranged role and would displace Water or Plant. Preserve its corrected toss and existing new clips. |
| BlackKingNumemon specialties | Filth/Battle/—; eight Filth moves, six Battle moves, Death Claw finisher | Filth/Water; remove Battle | **Accept Filth/Ice/— as a gameplay identity.** Its canon poisonous mucus supports liquid attacks better than boxing. Canon does not establish cryokinesis, so avoid giving it every freezing spell merely because they share the engine category. |
| BlackKingNumemon moves | 14 ordinary moves plus Death Claw | Replace all six Battle moves with all eight Water/Ice moves | **Modify:** remove all six Battle moves; add Water Blit, Aqua Magic, Tear Drop, Ice Needle, Winter Blast and Giga Freeze. Retain eight Filth moves and finisher: 15 slots. All eight Ice moves would produce 17 slots, exceeding the engine's 16 including the finisher. Defer Ice Statue/Aurora Freeze as unnecessary high-tier freezing coverage. |
| ShellNumemon → BlackKingNumemon | Champion → Mega is not a direct route; ShellNumemon → Garbagemon/Etemon → BlackKingNumemon | A visual continuation | **Accept the family concept through the existing Ultimate bridge.** Do not add a direct Champion → Mega shortcut. Both bridges retain Filth. KingSukamon's timed Mega route also retains Filth. |
| KingEtemon, Numemon, Sukamon, Nanimon, Roachmon | Existing identities and arsenals | Keep them | **Accept no change.** The proposal should diversify the named imports without a global Filth buff or unrelated route redesign. |

## Canon and interpretation

Geremon is a ferocious but weak Numemon relative with a stench attack: [official profile](https://digimon.net/reference_en/detail.php?directory_name=geremon). ShellNumemon is a skittish shell-protected relative: [official profile](https://digimon.net/reference_en/detail.php?directory_name=karatukinumemon). Raremon's machine parts sustain its rotting body: [official profile](https://digimon.net/reference_en/detail.php?directory_name=raremon). These support odor, defensive shell and scrap-machine roles respectively; they do not prove every suggested technique.

Garbagemon's trash can and empty-can bazooka support scrap projectiles: [official profile](https://digimon.net/reference_en/detail.php?directory_name=gerbemon). Etemon's signature attacks are a song and dark sphere: [official profile](https://digimon.net/reference_en/detail.php?directory_name=etemon). MetalEtemon is a fully mechanized fighter: [official profile](https://digimon.net/reference_en/detail.php?directory_name=metaletemon).

BlackKingNumemon carries a found crown like a shell; its attacks are an eye beam and poisonous mucus: [official Japanese profile](https://digimon.net/reference/detail.php?directory_name=blackkingnumemon). That profile currently calls it Ultimate; Horizon's existing identity/tree deliberately stores it as Mega. This proposal preserves the project's current stage. It neither treats the mollusk shape as proof of ice magic nor silently changes its level or finisher.

## Clips and effect integration

These are implementation candidates, **not new battle clips verified by this branch**. A shared animation reference alone does not prove effect timing, origin, collision or status application.

| Species | Existing usable performance | Candidate reuse after approval | What still needs proof |
| --- | --- | --- | --- |
| Geremon | Native Numemon-derived odor spray and toss; native hierarchy | Spray for both Nature clouds | Nature effect origins, cast timing, status collision; retain native original-option behavior |
| ShellNumemon | Native imported slug attacks and filth toss; existing defend/react performance | Toss for Water Blit; held cast for Aqua Magic; short spit for Tear Drop; shell reaction for Counter | Shell must remain aligned; water origins and buff effect; actual Counter response. Do not treat an Etemon kick as the final shell animation |
| Raremon | Imported stench/toss and existing attacks | Scrap spray for Metal Sprinter; thrown projectile for Power Crane | Mech effect binding and hit tick; Power Crane must not imply an absent crane limb; reject if the effect reads poorly |
| Garbagemon | Existing Mech casts and bazooka posture | Existing projectile cast for Metal Sprinter | Junk release point, full multi-projectile effect and actual hit |
| Etemon / MetalEtemon | Existing native Thunder Justice and Air attacks | Remove only Etemon's ordinary availability; retain MetalEtemon's existing clip | Wild slots explicitly indexed by animation must still address the intended move after any reorder |
| KingSukamon | PR #297's toss/spray aliases, two new effects and charged finisher already tested | Preserve them | No proposed new attack here; icon preview remains separate |
| BlackKingNumemon | Existing spit/filth toss and DW3 attack clips, with a separate field animation repair | Toss/spit for Water Blit/Tear Drop, held cast for Aqua Magic and freeze effects | Six separate effect/slot audits, including close and distant targets; retain Death Claw's final slot and battle reach |

The KingSukamon icon review compares the existing 16×16 idle tile against whole-card-art and head-crop reductions at 15 colors, at actual size and enlarged with nearest-neighbor sampling. The card offers a clearer frontal face as a drawing reference, but cropping and quantization alone leave stage colors around the outline; a silhouette mask and a matching highlight frame are still required. This is why the recommendation modifies direct reuse instead of accepting an unreviewed resize.

No moveset change may silently shift a finisher into an ordinary slot. Append/rebuild explicit aliases, update effect origins and inspect every referenced wild animation index. Arsenals have a hard 16-entry budget including the finisher.

## Evolution and learning consequences

Specialty order matters twice: it changes incoming element sums and chooses one of three learning chances. It does not automatically rewrite numerical evolution requirements: those are committed rows with picker competition and topology guards. Adding moves without matching specialties leaves them unlearnable in combat. Care 3 is a minimum for these three Champions (flags 0); BlackKingNumemon's care 10 is a maximum (flags 16). Weight checks allow ±5 around the listed target. HP/MP thresholds below use displayed stats; their committed requirement fields store one tenth of those values. These are individual criteria, not a claim that the picker requires every listed criterion simultaneously.

- **Geremon:** Otamamon → Geremon is already an explicit canon exception to shared specialties; Nature does not remove the need for that exception. Preserve current HP 1000, MP 1000, care 3, weight 10 row. Both Ultimate children keep Filth. No added natural Monzaemon route: the existing X Bandage item already works at Champion level (`content/items/107-x-bandage.json`, `handleEvoItems`). This is verified from data/code, not an item-use playtest.
- **ShellNumemon:** pure Filth/Ice loses ToyAgumon's Fire/Battle connection. Retaining Battle in slot three avoids removing an established parent; Counter then learns at 8%, rather than Battle slot two's 11%. Preserve current MP 1000 / Brain 100, care 3, weight 20 row and existing Ultimate targets. No direct Mega link.
- **Raremon:** adding third-slot Mech preserves Goblimon/Monmon and Garbagemon/WaruMonzaemon links through Filth/Battle. Preserve HP 1000 / Offense 100 / Speed 100, care 3, weight 20. Metal Sprinter and Power Crane learn at 18% and 22%, below the 27%/30% they would get as secondary Mech.
- **BlackKingNumemon:** Filth keeps both ordinary Ultimate parents and KingSukamon's timed route valid. Preserve HP 5000 / Offense 500, care 10, weight 20, flags 16. MP-based requirements could match its new role, but that would need a separate picker-resolved proposal; do not infer one from a specialty edit.
- **Etemon/MetalEtemon:** specialties stay Battle/Air/Filth. Thunder Justice remains 9% for MetalEtemon's second-slot Air and becomes unavailable to learn while Etemon if removed. Previously learned techniques remain in the global learned collection but cannot be equipped by a species that lacks them. Preserve current evolution requirements, timed Mega rules and NEW DIGIMON-off arsenals.
- **KingSukamon:** preserve Water Blit's 10% (second-slot Ice) and Poison Powder's 14% (third-slot Nature). Preserve its current HP 3000 / MP 2000 / Offense 300 / Defense 300 / Brain 200 criteria, care 10 minimum, weight 40 target and 30-battle bonus. The active topology lists Numemon/Sukamon parents and timed Mega children, all retaining Filth. The `special_routes` description still says laboratory-only, but conflicts with those path records and the guard tests; that label is not evidence of a runtime gate. This proposal does not change its availability.

Before implementing approval, run the evolution picker/practical-chain guard against the proposed JSON, compare on/off records, audit all changed wild loadouts, and test battle learning from a save without those techniques. No numerical requirement or technique learning chance edit is recommended in this first pass.

## Quantitative audit

Reproduce the following appendix with `python3 -m tools.filth_audit`. The broader progression comparison is produced by `python3 tools/battle_audit.py --out build/filth-audit`.

These are deterministic formula scenarios, not measured DPS. Accuracy, range, cast length, poison duration and AI choices matter. In particular, adding Poison Powder is chiefly a status option; a low-power Metal Sprinter does not raise Garbagemon's existing 722-power ceiling. Removing Thunder Justice lowers Etemon's available Air ceiling from 586 to 389 while leaving MetalEtemon's at 586.

Arsenal ceilings make the tradeoffs clearer:

| Species | Current → recommended highest ordinary power | Practical effect |
| --- | --- | --- |
| Geremon | 333 → 333 | Adds confusion/poison coverage, not a stronger maximum attack. |
| ShellNumemon | 211 → 211 (Counter is conditional) | Water Blit matches Big Poop Toss's power at 102 rather than 192 MP and 74 rather than 49 accuracy. Counter's 285 power cannot be counted as routine ranged output. |
| Raremon | 211 → 226 | Power Crane raises the ceiling by 7.1%; compared with the removed 193-power Dynamite Kick, it costs 126 versus 99 MP and has 53 versus 62 accuracy. Metal Sprinter is a 150-power alternative, not an efficient damage upgrade. |
| Garbagemon | 722 → 722 | Metal Sprinter adds a low-power junk option without increasing its peak. |
| Etemon | 586 → 500 | Highest Air power falls to 389; Buster Dive still supplies 500 Battle power. This is an availability nerf, not merely a cosmetic distinction. |
| MetalEtemon | 586 → 586 | Existing high-power Air coverage remains exclusive relative to Etemon. |
| KingSukamon | 333 → 333 | Keep the recent Water Blit/Poison Powder alternatives and their cheaper/status roles. |
| BlackKingNumemon | 500 → 333 | Removing Buster Dive reduces maximum ordinary power by 33.4%. The recommendation deliberately favors cheap liquid attacks and retained Ult Poop Hell's status utility over a new high-power freezer. It is a substantial role change, not a blanket buff; this tradeoff needs approval. |

Ult Poop Hell is 333 power, 333 MP, 100 accuracy and 83% status chance; the retained Filth option does not make cheap Water Blit redundant. These values still do not account for attack timing or target resistances, and should not be read as DPS.

### Technique numbers

NORMAL; neutral element sum 30; 100% damage roll; no buffs or block. Damage columns are Offense minus Defense −500 / 0 / +500. Support effects are not direct damage: Aqua Magic and War Cry must not use the damage minimum as their effect value. MP is the runtime cost, three times stored `mpCost`. Learning rates require an unknown observed move, a matching specialty and inclusion in the current arsenal; they are per eligible roll, not guaranteed acquisition.

| Move | Power | MP/cast | Accuracy | Direct damage −500 / 0 / +500 | Learn rate at proposed position |
| --- | --- | --- | --- | --- | --- |
| Charm Perfume | 180 | 210 | 75 | 1/180/360 | 12% (slot 2) |
| Poison Powder | 117 | 171 | 77 | 1/117/234 | 19% (slot 2) |
| Water Blit | 211 | 102 | 74 | 1/211/422 | 10% (slot 2) |
| Aqua Magic | 0 | 36 | 100 | support | 14% (slot 2) |
| Tear Drop | 60 | 42 | 44 | 1/60/120 | 22% (slot 2) |
| Metal Sprinter | 150 | 165 | 78 | 1/150/300 | 18% (slot 3) |
| Power Crane | 226 | 126 | 53 | 1/226/452 | 22% (slot 3) |
| Megaton Punch | 320 | 186 | 70 | 1/320/640 | 13% (slot 2) |
| Tremar | 178 | 168 | 60 | 1/178/356 | 8% (slot 2) |
| War Cry | 0 | 42 | 100 | support | 15% (slot 2) |
| Magma Bomb | 279 | 132 | 50 | 1/279/558 | 14% (slot 2) |
| Red Inferno | 210 | 171 | 72 | 1/210/420 | 12% (slot 2) |
| Spit Fire | 66 | 30 | 43 | 1/66/132 | 22% (slot 2) |
| Fire Tower | 155 | 81 | 55 | 1/155/310 | 16% (slot 2) |
| Giga Freeze | 264 | 120 | 65 | 1/264/528 | 10% (slot 2) |
| Ice Statue | 424 | 186 | 79 | 1/424/848 | 8% (slot 2) |
| Winter Blast | 120 | 165 | 90 | 1/120/240 | 12% (slot 2) |
| Ice Needle | 126 | 78 | 50 | 1/126/252 | 15% (slot 2) |
| Aurora Freeze | 430 | 258 | 81 | 1/430/860 | 6% (slot 2) |
| Thunder Justice | 586 | 330 | 85 | 1/586/1172 | 9% (slot 2) |

### Incoming specialty sums

Columns follow Fire / Battle / Air / Nature / Ice / Mech / Filth. Each sum enters damage with divisor 30. A null specialty contributes 10. Adding a specialty changes defense even without a new damaging move.

| Species | Current | Recommended |
| --- | --- | --- |
| Geremon | 40 / 40 / 40 / 40 / 40 / 40 / 30 | 50 / 40 / 32 / 40 / 32 / 50 / 30 |
| ShellNumemon | 40 / 40 / 40 / 40 / 40 / 40 / 30 | 32 / 40 / 50 / 50 / 40 / 32 / 30 |
| Raremon | 40 / 40 / 40 / 40 / 40 / 40 / 30 | 50 / 40 / 32 / 32 / 50 / 40 / 40 |
| BlackKingNumemon | 40 / 40 / 40 / 40 / 40 / 40 / 30 | 32 / 40 / 50 / 50 / 40 / 32 / 30 |

### Current partner arsenals

- **Geremon (87)**: filth / — / —; Horizontal Kick (57), Odor Spray, Poop Spd Toss, Poop Rnd Toss, Rnd Spd Toss, Big Poop Toss, Big Rnd Toss, Ult Poop Hell, Party time (65).
- **ShellNumemon (231)**: filth / battle / —; Odor Spray, Big Poop Toss, Horizontal Kick (55), Poop Rnd Toss, Poop Spd Toss, Rnd Spd Toss, Dynamite Kick (44), Muscle Charge, War Cry, Sonic Jab, Iga School Knife Throw.
- **Raremon (264)**: filth / battle / —; Odor Spray, Poop Rnd Toss, Horizontal Kick (55), Poop Spd Toss, Rnd Spd Toss, Big Poop Toss, Dynamite Kick (44), Muscle Charge, War Cry, Sonic Jab, Death Claw.
- **KingSukamon (120)**: filth / ice / nature; Horizontal Kick (55), Odor Spray, Poop Spd Toss, Big Poop Toss, Poop Rnd Toss, Rnd Spd Toss, Big Rnd Toss, Ult Poop Hell, Party time (65), Water Blit, Poison Powder.
- **Garbagemon (269)**: filth / mech / —; Big Poop Toss, Ult Poop Hell, Big Rnd Toss, Poop Spd Toss, Rnd Spd Toss, Odor Spray, Poop Rnd Toss, Horizontal Kick (55), Power Crane, DG Dimension, All Range Beam, Delete Program, Pulse Laser, Energy Bomb.
- **Etemon (42)**: battle / air / filth; Sonic Jab, Dynamite Kick (44), Megaton Punch, Counter, Buster Dive, Tremar, War Cry, Muscle Charge, Megalo Spark, Spinning Shot, Thunder Justice, Horizontal Kick (55), Ult Poop Hell, Dark Network & Concert Crush.
- **MetalEtemon (65)**: battle / air / filth; Sonic Jab, Dynamite Kick (44), Megaton Punch, Counter, Buster Dive, Tremar, War Cry, Muscle Charge, Megalo Spark, Spinning Shot, Thunder Justice, Horizontal Kick (55), Ult Poop Hell, Dark Network & Concert Crush.
- **BlackKingNumemon (307)**: filth / battle / —; Ult Poop Hell, Big Rnd Toss, Big Poop Toss, Poop Spd Toss, Rnd Spd Toss, Odor Spray, Poop Rnd Toss, Horizontal Kick (55), Megaton Punch, Buster Dive, Counter, Dynamite Kick (44), Tremar, Sonic Jab, Death Claw.
- **KingEtemon (303)**: battle / air / filth; Megaton Punch, Buster Dive, Counter, Dynamite Kick (44), Tremar, Sonic Jab, Thunder Justice, Spinning Shot, Megalo Spark, Hurricane, Big Poop Toss, Poop Spd Toss, Rnd Spd Toss, Odor Spray, Dark Network & Concert Crush.
