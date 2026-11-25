# Resident challenges

A postgame feature of the extended story. Once the game is beaten, every in-game day a resident of
`content/tables/resident-challenges.json` leaves its home in the city and waits at the spot where the tamer first
met it, much stronger than then. Talking to it offers a fight with no running away.

The rows form two pools (each row's `pool`), and each open pool sends one challenger a day:

- `original`: the game's own residents (species below 112). Open once the game is beaten.
- `new`: Horizon's residents (species 112 and up). Closed until every one of the pool's residents is recruited; then
  it works like the first. So one challenger a day until the last new resident is recruited, then two.

The two challenges are independent: each pool has its own challenger var and tried flag, and winning one leaves the
other where it is.

- **Won:** a line of its own, the row's item and bits (on top of the battle's usual bits and technique chance), and it
  runs off back to the city. Nobody else of its pool goes out that day.
- **Lost:** the usual defeat (Jijimon's house, the items lost, a life). It waits there the rest of the day, and the
  next talk opens with its retry line. Retries are unlimited.
- **Midnight:** whoever was out is home again and each open pool sends its next one (none before the first midnight
  after the ending).

While a challenger waits, its screen has no wild Digimon: the NPC is placed with `alone=` (its presence condition),
and the compiler (`tools/dws/recruit_screens.py`) wraps every ordinary wild of the screen's setup (`LOAD_DIGIMON` /
`SET_DIGIMON` of a base NPC whose talk is `recruitable()`) in the opposite test, so the slot is never set up: no
wild battle, and no empty spawn. Story encounters of the screen stay. Once the challenger is beaten (or at midnight)
the next load of the screen places its wilds again.

## Who goes out

At midnight `modChallengeDaily` (patch "Resident challenges", `src/main/script_common.c`) picks, for each open pool, from
that pool's rows whose species is recruited, with the table's stage rule (each pool has its own cycle):

- `same-or-lower`: only residents whose stage is the partner's at that midnight or lower. A shuffle bag: one not sent
  out yet in this cycle, of the partner's own stage if any is left, else of the next stage down, and so on. When all
  of a pool that can go have gone, that pool's bits of the bag empty and a new cycle starts. A Baby or In-Training partner sends nobody.
- `any`: every stage, the same bag without the stage order.

Never the pool's resident of the day before, even across a new cycle: if yesterday's is the only one that could go,
nobody of that pool goes.

## The fight

The talk sets scratch pstat `armedPstat` to 1 (`original` pool) or 2 (`new`) before the fight; the battle start clears it and gives every foe of the
row's species, for each of HP, MP, Offense, Defense, Speed and Brain:

`max(its own stat, partner x (100 + partnerPercent) / 100)`, at most 9999

Its own stats are the ones the site NPC declares, the challenge's floor: the species' `wild` stats in
`content/species/` or, for a species with none (most of the game's own residents), the row's `base` (its `_base` says
where the numbers come from: its fight in the original game, else the sheets of the rows of its stage), times
(100 + `sheetPercent`) / 100 (`sheetPercent` is 0 by default and may not be negative). The residents fought by the very
NPC of their recruit fight (`CHALLENGE_RECRUIT_STATS` in `tools/city_residents.py`: Armadillomon, Candlemon, Datamon,
Digmon, Knightmon, Kotemon, Mammothmon, Mushroomon, Phantomon, Pumpkinmon, Starmon, Triceramon) keep that fight's stats
as their floor. `tools/city_residents.py` refuses a row with both or neither of `wild` and `base`, and
`tools/test_resident_challenges.py` checks every site NPC against `challenge_site_stats`. The table itself holds only
the rule, the save numbers and each row's species with its level in the high bits, so the daily pick reads no species sheet (164 bytes of the executable).
The stats are set before the battle records its initial stats, so its rewards and stat gains follow them.
`noItems` opens the battle bag empty (it comes back whole); `noLateStep` gives the fight none of
`battle-formulas.json` NORMAL's late-game step (HP and attack ramp, damage floor), on any difficulty, and puts it back
after the battle whatever its outcome. HARD keeps its own factors and floor.

## Save state

| What | Where |
|---|---|
| today's challenger (row + 1, 0 = nobody; + 128 once beaten) | saved pstat `challengerVar` (story `challenger`), `newChallengerVar` (`new_challenger`) |
| fought today | flags `triedFlag` (`challenge_tried`), `newTriedFlag` (`new_challenge_tried`) |
| the bag: one bit a row, 16 rows a register | saved wide registers from `bagWreg` (w10-w14; executable only) |
| which rows are the new pool | the species: `MOD_CHALLENGE_NEW_FIRST` (112) and up, as each row's `pool` must say |

A win adds `CHALLENGE_BEATEN` (128) to its pool's var: the site's NPC (`when=challenger == CH_X`) and its `alone=` stop
holding together, so it is gone and the wilds are back, and its home shows it again. The vars and flags are pinned in
the story's `save.lock`; the bag's registers are saved with the others (save tag `WREGS`,
w0-w15) and no script uses them; `tools/test_resident_challenges.py` checks that the table, the lock and the
story agree.

**New Game Plus** rebuilds the default save (`modNewGamePlusReset`): the wide registers (the bag), the vars and the
flags start empty, so nobody goes out until the new run's ending, and the new pool stays closed until every new
resident is recruited again.

## Yuramon's rumours

Many challengers' absence shows on a walk through the city: their home is empty. The rows marked `"hint": true` are
the ones it does not show: residents out at that hour or by chance anyway (the Restaurant, the item shop, the secret
shop, the lower city, the top map), under a story condition (Coelamon, Myotismon), or with no city home after the ending
(Seadramon, SkullGreymon, MetalMamemon, Etemon, Penguinmon, WaruMonzaemon, Kotemon). After the ending, Yuramon on
File City's top map (`arcs/rumours/yuramon.py`) tells the day:

- a hinted challenger out today and not beaten: its riddle, `<name>.rumour.who` (who, by trade, habit or character,
  never the name) and `<name>.rumour.where` (where, as a picture of the site's landscape, never its name). One for each
  pool's challenger when both are hinted.
- otherwise, someone out or beaten today: `rumour.unheard` ("take a walk around the city").
- nobody out (both vars 0): `rumour.quiet`.

Before the ending the talk is the game's own. On the days Andromon stands in Yuramon's place there is no rumour. A new
hinted row needs its two lines in every language and its branch in `yuramon-riddles.py` (`tools/test_resident_challenges.py`
checks that the riddles are exactly the hinted rows).

The riddles do not fit in script 162 (File City's top map) with the rest of that screen's talk: the script buffer holds
16 KB. Yuramon's talk jumps to section 1 of the library script 210 (Jijimon's news, `yuramon-riddles.py`), read from the
disc only when the talk jumps, so they cost no memory while the city runs. With all 34 riddles as full sentences, 210 is
at 6.5-10.8 KB depending on the language and 162 at 9.8-12.6 KB.

## Adding a resident

The roster is every visible city resident (`content/tables/city-residents.json`), the game's own and ours, each at the
spot where it was recruited; the rows come in batches. Rows are numbered in the save (the challenger vars and the bag
bits), so a released row is never moved, removed or given another pool: new ones are appended. The bag holds 80 rows (five saved 16-bit
wide registers); the table has room for 72 (`MOD_CHALLENGE_MAX`).

A row (72 at most) names the species, its story file, home file, site (screen and `at`), the exit path it runs after a
win, the item, the bits, its `base` when its species has no `wild` sheet, and its five named lines. The story side is the row's constant `CH_<NAME>` in
`state.py` (its 1-based row), the site file's presence (for a Digimon of ours, its recruit NPC with
`when=not recruited(...) or new_challenger == CH_X`; for one of the game's own, whose original NPC leaves once
recruited, a file in `arcs/challenges/` with a new NPC of the species on the same spot, `when=challenger == CH_X`),
`alone=` with the pool's var `== CH_X` (no wilds while it waits), the challenge talk (`CHALLENGE_ARMED` 1 or 2, the
pool's tried flag, the pool's var `.add(CHALLENGE_BEATEN)` on a win), the home's `on_enter`, and the lines in
`text/en.json` and every translation. A few keep their own presence and leave from `on_enter` unless they are today's
challenger (Kotemon, Phantomon, Pumpkinmon, the caged Bearmon). The site must keep the hang rules:
the exit on walkable ground in a straight line, `run` only for models with a run clip (slot 4).
The challenger must take an NPC slot 0-7 (`python3 tools/dws.py slots SCREEN`): slots 8-15 of the story-state engine
never fight, so a site whose eight slots are taken (Coela Point, Misty Trees 117, Path Thru Mt. Panorama 18) moves to a
screen next to it. So does one whose screen has no heap left for it (Native Forest 2 beside the night hunter: Palmon
waits on Native Forest 4; Misty Trees 118: Kokatorimon on 119). The heap check follows the setup's paths and knows
that a challenger's `alone=` and the wilds it hides are never set up together.
A resident whose home NPC shares its slot layout with other screens of the same script (the arena lobby), or is a
clerk or a slot the script spawns, has no home file (`home: null`): it only appears at its site.
