# Unique finishers: decisions to make

Every imported Digimon (179, MetalGreymonVaccine included) now has its own finisher in
`content/finishers/imports.json`: own name, behaviour, element, status and look, from its
signature attack in its source game, with DW1 power. `docs/mods/unique-finishers.md` explains
the data and the engine change; `python3 -m tools.finisher_balance` checks it (0 problems).

What is settled: behaviour and look follow the source attack; power sits inside the DW1 band
of the level; no economy effect; support moves become buffs with a damaging fallback; the
finisher keeps its id, so saves do not change; natives keep their finishers.

| | |
|---|---|
| Source decoded from the disc | 145 (79 Card Battle, 43 DW2, 23 DW2003) |
| Canon attack from the series | 17 |
| Proposed (no canon attack found) | 17 |
| Effect from source files / still to decode / to build from DW1 effects | 122 / 23 / 34 |

## Decisions

1. **Rookie imports drop to Rookie power (85..101).** On 2026-11-03 they kept their Champion
   finishers until an effect fits the model. Each now has its own effect, so this design puts
   them in the Rookie band. Alternative: keep their current power until each effect ships.
2. **One Ultimate band, 196..260.** The 180..195 class for Air and Battle Ultimates goes away;
   the check compares with every native Ultimate instead.
3. **Mega stays at 250..260.** A narrow band: Megas differ by element and kind, not power.
4. **Area attacks.** 21 finishers hit every enemy (DW2 "all enemies" and canon area attacks).
   They take the band floor. SkullMeramon's Metal Fireball is one of them. Card Battle attacks
   are single target (the card game has one opponent).
5. **Statuses.** 8 finishers carry one, at most 20 % and capped at the band middle. Four are
   proxies for DW2 effects DW1 lacks: ExTyrannomon (seals techniques: confusion), Clockmon
   (delays: stun), MarineDevimon (slows: stun), BlackGatomon Cat's Eyes (confusion, no source
   status). Keep or drop each.
6. **Raremon's Buffalo Breath** turns its Death Claw melee into a short-range breath with
   confusion.
7. **Buffs need engine code.** Baihumon (Kongou), Mushroomon (Fungus Cruncher) and Tinmon
   (Recovery Power) become buffs only with a small engine change; until then their damaging
   fallback ships. Build it, or ship the fallbacks for good.
8. **Names to confirm.** Romaji and odd spellings were made readable: Amethyst Mandala
   (KongouKaimandara), Mugen Hadou (or "Infinite Wave"), Talisman of Light (Bonhitsusen),
   Corona Blaster for Beelzemon's "Blast Mode" (or Double Impact), Thorny Whipping, Duo Scissor
   Claw, Dynamo Cannon, Gate of Destiny, Shell Attack, Needle Squall, Pearl Shot. Imperialdramon's
   Mega Fire is close to DW1's Mega Flame: keep or use "Positron Laser". Kongou
   could read "Diamond Guard". DarkTyrannomon's Fire Blast and MetalTyrannomon's Fire Blast II
   (both DW2 names) read alike: keep, or use the canon "Nuclear Laser" for the second.
9. **17 proposed names** for DW2003 Digimon with no known attack (Ebidramon, BlackKingNumemon,
   Bulbmon, Fujinmon, Pharaohmon, Lynxmon, Maildramon, Musyamon, Gargoylemon, Ghoulmon,
   Vemmon, Roachmon, Raijinmon, Raidenmon, Suijinmon, Zanbamon, Bastemon). Change any you dislike.
10. **Natives keep their shared finishers** (28 shared ids, listed in the format doc). The same
    override could give a native its own later.

## Follow-ups after the decisions

Engine: record bytes, `modSpeciesMove` override and the battle read sites, names at battle load
(about 300 bytes of main executable, to be measured). Text: the 179 names in all eight
languages, width-checked. Effects: the per-species effect ports, dash finishers through the
Buster Dive pass.
