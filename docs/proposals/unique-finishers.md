# Unique finishers: decisions (decided 2026-11-15)

Every imported Digimon (179, MetalGreymonVaccine included) now has its own finisher in
`content/finishers/imports.json`: own name, behaviour, element, status and look, from its
signature attack in its source game, with DW1 power. `docs/mods/unique-finishers.md` explains
the data and the engine change; `python3 -m tools.finisher_balance` checks it (0 problems).

Every question below is decided, and the designed numbers play (`"neutral": false`). Behaviour
and look follow the source attack. Power sits inside the DW1 band of the level. There is no
economy effect. Support moves ship as damaging attacks. The finisher keeps its id, so saves do
not change. Natives keep their finishers.

| | |
|---|---|
| Source decoded from the disc | 145 (79 Card Battle, 43 DW2, 23 DW2003) |
| Canon attack from the series | 17 |
| Proposed (no canon attack found) | 17 |
| Effect from source files / still to decode / to build from DW1 effects | 122 / 23 / 34 |

## Decisions

1. **Rookie imports use Rookie power (85..101).** This replaces the 2026-11-03 entry that kept
   their Champion finishers until an effect fit the model: each now has its own effect.
2. **One Ultimate band, 196..260.** The 180..195 class for Air and Battle Ultimates is gone;
   the check compares with every native Ultimate.
3. **Mega stays at 250..260.** Megas differ by element and kind, not power.
4. **Area attacks take the band floor.** 21 finishers hit every enemy (DW2 "all enemies" and
   canon area attacks), SkullMeramon's Metal Fireball among them. Card Battle attacks stay
   single target.
5. **Statuses.** Kept: ExTyrannomon (seals techniques: confusion), Clockmon (delays: stun),
   MarineDevimon (slows: stun). Dropped: BlackGatomon's Cat's Eyes, which has no source status.
   A status comes only from a decoded source or a name that implies one.
6. **Raremon's Buffalo Breath** stays as designed: a short-range breath with confusion.
7. **No buffs.** Baihumon (Kongou), Mushroomon (Fungus Cruncher) and Tinmon (Recovery Power)
   keep their damaging attacks for good. A buff would need engine code, and the heap is tight.
8. **Names.** The official English name is used when one exists, otherwise the readable form:
   - Imperialdramon: "Positron Laser".
   - MetalTyrannomon: "Nuclear Laser".
   - Beelzemon: "Corona Blaster".
   - SkullMeramon: "Metal Fireball".
   - The rest as proposed: Amethyst Mandala, Mugen Hadou, Talisman of Light, Thorny Whipping,
     Duo Scissor Claw, Dynamo Cannon, Gate of Destiny, Shell Attack, Needle Squall, Pearl Shot,
     Kongou.
9. **The 17 proposed names** for DW2003 Digimon with no known attack stay as proposed.
10. **Natives keep their shared finishers** (28 shared ids, listed in the format doc).

## Done

The engine work (record bytes, `modSpeciesMove`, names at battle load), the 179 names in all
eight languages and the per-species effects with their source sounds are built; see
`docs/mods/unique-finishers.md`.
