# Resident challenges

A postgame feature of the extended story. Once the game is beaten, every in-game day one resident of
`content/tables/resident-challenges.json` leaves its home in the city and waits at the spot where the tamer first
met it, much stronger than then. Talking to it offers a fight with no running away.

- **Won:** a line of its own, the row's item and bits (on top of the battle's usual bits and technique chance), and it
  runs off back to the city. Nobody else goes out that day.
- **Lost:** the usual defeat (Jijimon's house, the items lost, a life). It waits there the rest of the day, and the
  next talk opens with its retry line. Retries are unlimited.
- **Midnight:** whoever was out is home again and the next one goes out (none before the first midnight after the
  ending).

## Who goes out

At midnight `modChallengeDaily` (patch "Resident challenges", `src/main/script_common.c`) picks from the rows whose
species is recruited, with the table's stage rule:

- `same-or-lower`: only residents whose stage is the partner's at that midnight or lower. A shuffle bag: one not sent
  out yet in this cycle, of the partner's own stage if any is left, else of the next stage down, and so on. When all
  that can go have gone, the bag empties and a new cycle starts. A Baby or In-Training partner sends nobody.
- `any`: every stage, the same bag without the stage order.

Never the resident of the day before, even across a new cycle: if yesterday's is the only one that could go, nobody goes.

## The fight

The talk sets scratch pstat `armedPstat` to 1 before the fight; the battle start clears it and gives every foe of the
row's species, for each of HP, MP, Offense, Defense, Speed and Brain:

`max(floor x (100 + sheetPercent) / 100, partner x (100 + partnerPercent) / 100)`, at most 9999

(`sheetPercent` is 0 by default, so the floor itself is the minimum; it may not be negative) where *floor* is the
species' `wild` stats in `content/species/` or, for a species with none (most of the game's own residents), the row's
`base` (its `_base` says where the numbers come from: its fight in the original game, else the sheets of the rows of
its stage). `tools/city_residents.py` copies them into the table and refuses a row with both or neither.
The stats are set before the battle records its initial stats, so its rewards and stat gains follow them.
`noItems` opens the battle bag empty (it comes back whole); `noLateStep` gives the fight none of
`battle-formulas.json` NORMAL's late-game step (HP and attack ramp, damage floor), on any difficulty, and puts it back
after the battle whatever its outcome. HARD keeps its own factors and floor.

## Save state

| What | Where |
|---|---|
| today's challenger (row + 1, 0 = nobody) | saved pstat `challengerVar` (story `challenger`) |
| the bag: one bit a row, 16 rows a register | saved wide registers from `bagWreg` (w10-w14; executable only) |
| won today / fought today | flags `wonFlag`, `triedFlag` |

The vars and flags are pinned in the story's `save.lock`; the bag's registers are saved with the others (save tag `WREGS`,
w0-w15) and no script uses them; `tools/test_resident_challenges.py` checks that the table, the lock and the
story agree.

## Adding a resident

The roster is every visible city resident (`content/tables/city-residents.json`), the game's own and ours, each at the
spot where it was recruited; the rows come in batches. Rows are numbered in the save (the challenger var and the bag
bits), so a released row is never moved or removed: new ones are appended. The bag holds 80 rows (five saved 16-bit
wide registers); the table has room for 72 (`MOD_CHALLENGE_MAX`).

A row (72 at most) names the species, its story file, home file, site (screen and `at`), the exit path it runs after a
win, the item, the bits, its `base` when its species has no `wild` sheet, and its five named lines. The story side is the row's constant `CH_<NAME>` in
`state.py` (its 1-based row), the site file's presence (`not recruited(...) or trigger(50)` for a Digimon of ours; for one of the game's own,
whose original NPC leaves once recruited, a file in `arcs/challenges/` with a new NPC of the species, `when=recruited(...)`
on the same spot, that leaves from `on_enter` unless the game is beaten and it is today's challenger: the shorter
condition keeps MAPHEAD inside its buffer), `on_enter` and challenge talk, the home's `on_enter`, and the lines in `text/en.json` and every translation. The site must keep the hang rules:
the exit on walkable ground in a straight line, `run` only for models with a run clip (slot 4).
The challenger must take an NPC slot 0-7 (`python3 tools/dws.py slots SCREEN`): slots 8-15 of the story-state engine
never fight, so a site whose eight slots are taken (Coela Point, Misty Trees 117, Path Thru Mt. Panorama 18) moves to a
screen next to it.
A resident whose home NPC shares its slot layout with other screens of the same script (the arena lobby), or is a
clerk or a slot the script spawns, has no home file (`home: null`): it only appears at its site.
