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

`max(sheet x (100 + sheetPercent) / 100, partner x (100 + partnerPercent) / 100)`, at most 9999

where *sheet* is the species' `wild` stats in `content/species/` (copied into the table by `tools/city_residents.py`).
The stats are set before the battle records its initial stats, so its rewards and stat gains follow them.
`noItems` opens the battle bag empty (it comes back whole); `noLateStep` gives the fight none of
`battle-formulas.json` NORMAL's late-game step (HP and attack ramp, damage floor), on any difficulty, and puts it back
after the battle whatever its outcome. HARD keeps its own factors and floor.

## Save state

| What | Where |
|---|---|
| today's challenger (row + 1, 0 = nobody) | saved pstat `challengerVar` (story `challenger`) |
| the bag: rows 1-8, 9-16 | saved pstats `bagVars` (story `challenge_bag`, `challenge_bag2`, executable only) |
| won today / fought today | flags `wonFlag`, `triedFlag` |

All are pinned in the story's `save.lock`; `tools/test_resident_challenges.py` checks that the table, the lock and the
story agree.

## Adding a resident

A row (16 at most) names the species, its story file, home file, site (screen and `at`), the exit path it runs after a
win, the item, the bits and its five named lines. The story side is the row's constant `CH_<NAME>` in
`state.py` (its 1-based row), the site file's presence (`not recruited(...) or trigger(50)`), `on_enter` and challenge
talk, the home's `on_enter`, and the lines in `text/en.json` and every translation. The site must keep the hang rules:
the exit on walkable ground in a straight line, `run` only for models with a run clip (slot 4).
