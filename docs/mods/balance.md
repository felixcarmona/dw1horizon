# Balance as JSON

Every number that balances a Digimon (techniques, evolution requirements and
paths, stat gains, raise data, learning chances, drops, wild enemies,
tournaments) can be changed by editing JSON. `tools/balance.py` reads the
original values from the player's own disc into JSON, and writes JSON back into
the compiled executable, its overlays and the `.MAP` files.

**Species are not overrides.** Everything the game keeps per
species (parameters, techniques, drops, raise data, voices, training rows,
battle music, reincarnation stats…) is in the species' own file,
`content/species/<id>-<name>.json`, complete and committed (`docs/mods/species.md`):
to rebalance Greymon, edit `content/species/5-greymon.json`. `balance.py build`
writes those rows into the executable with the other tables; `DIGI.DAT`
(species ≥ 180) is built from the same files by `species.py`. Only the
originals' **evolution** rows (requirements, gains, paths) are still a balance
table (original ⊕ engine layer).

(Format, commands and examples: sections 2 to 6. This section is the inventory.)

## 1. Inventory: where every balance number lives

Addresses: *original* = `decomp/config/us/symbols*.txt` (the disc's
`SLUS_010.32` and overlays); *mod* = the integration build
(`build/decomp-int/build/us/psx/gcc/SLUS_010.32.elf`; the mod addresses below are
one such build), which moves every table. `balance.py` never uses fixed mod
addresses: it reads them from the ELF of the build it patches. File offset =
RAM − `0x80090000` in `SLUS_010.32`, RAM − `OVL_TRN_BASE` (`0x80088800`) in
`TRN_REL.BIN`/`TRN2_REL.BIN`, RAM − `OVL_BTL_BASE` (`0x80052AE0`) in
`STD_REL.BIN` (checked: the original and mod overlay tables are byte-equal at
those offsets).

### 1.1 Per species

| What | C symbol (source) | original: rows × size | mod: rows × size | ids ≥ 180 (`DIGI.DAT` record offset) | JSON |
|---|---|---|---|---|---|
| Parameters: attribute, level, elements, drop and its chance (the **drops** of wild enemies), the technique list (slot *i* plays animation 0x2E+*i*), radius, height | `DIGIMON_DATA` (`main.c`) | 180 × 52 | 180 × 52 | `+0x00` (`DigimonPara`) | `content/species`: `level`, `attribute`, `specialties`, `techniques`, `drop`, `model.radius/height` |
| Raise data (hunger hours, energy, poop, favourite food, sleep cycle, favoured region, training type, birth weight, status screen position) | `RAISE_DATA` (`partner_impl.c`) | 66 × 28 (by type) | 180 × 28 | `+0xD4` | `content/species`: `partner.*` |
| Item take distance | `ITEM_TAKE_DISTANCE` (by type − 1) | 66 × 1 | 180 × 1 (the last row, type 180, is dead: written 0) | `+0x130` | `partner.item_distance` |
| Voices (short, long), the species whose effects it borrows, the gym animation rows | `DIGIMON_VBALL_SOUND_ID`, `DIGIMON_VLALL_SOUND_ID` (`sound.c`), `ORIGINAL_DIGIMON_TYPES` (`map.c`), `TRN_`/`TRN2_TRAINING_ANIM_IDS` (overlays) | 180, 66, 180 × 2, 67 × 2 | 180 each | `+0x4E`, `+0x4F`, `+0x4C`, `+0x131` | `voice`, `partner.voice`, `effects_like`, `partner.training` |
| Battle music of a wild enemy | `SPECIES_BATTLE_MUSIC` (`btl.c`, patch 0081; was `ENEMY_MUSIC_MAPPING`, types 67..111) | 48 | 180 | `+0x52` | `battle_music` |
| Reincarnation stats (the 4 Fresh), new-game technique (Agumon, Gabumon) | `REINCARNATION_STATS`, `NEW_GAME_TECHNIQUES` (`partner_impl.c`, patch 0081; literals in the original's code) | — | 4 × 14, 2 × 4 | — | `reincarnation_stats`, `new_game_technique` |
| Evolution requirements: stats (HP/MP in tenths; for Rookies 1 = must be the highest stat), `care` (mistakes), `weight`, bonus `digimon`/`discipline`/`happiness`/`battles`/`techs`, `flags` (0x10 max mistakes, 0x01 max battles) | `EVOLUTION_REQS` (`evolution.c`) | 63 × 28 (by target type) | 180 × 28 | `+0xF0` | originals: engine layer `species.<id>.evoReqs` (not overridable); imports: `evolution.requirements` |
| Stat gains on evolving into it | `EVOLUTION_STATS_GAINS` (`evolution.c`) | 66 × 14 | 180 × 14 | `+0x10C` | engine layer `species.<id>.evoGains`; imports `evolution.gains` |
| Evolution paths: `from[5]`, `to[6]` (the targets) | `EVOLUTION_PATHS` (`evolution.c`, by type − 1) | 62 × 11 (`s8`) | 62 × 22 (`DigimonId` = `s16`) | `+0x11A` (+ the index links) | engine layer `species.<id>.evoPaths`; imports `evolution.from/to` |
| **Base stats per level** | — | **none**: the game has no per-level or per-species stat table. Stats come from training, battles, the evolution gains above, the reincarnation stats and the new-game script | | | |
| Wild enemy battle stats | the `.MAP` of each screen (`loadMapDigimon`, `overworld.c:994`), 33 × s16 per placed Digimon: `hp mp currentHP currentMP off def speed brain bits chargeMode move0..3 prio0..3` | 242 `.MAP` files, up to 8 per screen | same files | — (DWS `place` for new placements; `wild` in `content/species` is the default stats DWS gives) | DWS `place`, `dwmap.py` (whole map JSON) | `maps.<file>.<slot>` (patched in place) |

### 1.2 Techniques and learning (global)

| What | C symbol (source) | original | mod | JSON before | JSON now |
|---|---|---|---|---|---|
| Technique data: `distance` (range²), `power`, `mpCost` (÷3: the game charges 3×), `iframes`, `range` (1 melee, 2 ranged, 3 area, 4 self), `special` (element), `status` (1 poison, 2 confusion, 3 stun, 4 flatten), `accuracy`, `statusChance`, `unk3` (flags: 1 needs a target, 2 global lock) | `MOVE_DATA` (`item.c`) | `0x8012623C`, 122 × 16 | `0x80122334` | — | `techniques.<id>` |
| Learn chance in battle, per technique × the learner's main/2nd/3rd element | `MOVE_LEARN_CHANCES` (`item.c`) | `0x80125FA4`, 58 × 3 | `0x80122CBC` | — | `techniques.<id>.learnChances` |
| Learning by brains training: the 8 techniques per element offered, and the weight of each position per element rank | `TRN_D_8008F14C` [56], `TRN_D_8008F184` [8][3] (`trn_reward.c`); the TRN2 overlay has its own copy (`TRN2_D_8008DAD0`, `TRN2_D_8008DB08`) | TRN `0x8008F14C`, `0x8008F184`; TRN2 `0x8008DAD0`, `0x8008DB08` | TRN `0x8008E0BC`, `0x8008E0A4`; TRN2 `0x8008D048`, `0x8008D030` | — | `brainTraining` (written to both overlays) |
| Element effectiveness (×0.1) | `TYPE_FACTORS` [7][7] (`item.c`) | `0x80125F70` | `0x80122D6C` | — | `typeFactors` |
| Learning on evolving (weakest technique of the main element) | C code (`EVL_applyEvolution`) | | | — | not covered (C rule; it follows `techniques.*.power` and the species' `techniques`); the new-game technique is `new_game_technique` in the species file |

### 1.3 Evolution, battles, items, tournaments (global)

| What | C symbol (source) | original | mod | JSON now |
|---|---|---|---|---|
| Evolution items 0x47..0x72 → species | `EVOLUTION_ITEM_TARGET` [44] (`item.c`) | `0x80127C5C` | `0x80121088` | `evolutionItems` |
| Join chance of other wild Digimon (partner × enemy attribute) | `FLEE_CHANCES` [12] (`btl.c`, misnamed) | `0x8012BB14` | `0x80129338` | `joinChances` |
| Item price, merit, sort order, colour, droppable | `ITEM_PARA` (`item.c`), 128 × 32 (name not exported) | `0x801269DC` | `0x80121334` | `items.<id>` |
| Tournament calendar (cup per day × slot) | `TOURNAMENT_SCHEDULE` [30][6] (`script_common.c`) | `0x80130198` | `0x8012CFA8` | `tournaments.schedule` |
| Rival base stat per cup | `STD_OPPONENT_BASE_STATS` [24] (`std_setup.c`, STD overlay) | `0x800799B4` | `0x80073CF0` | `tournaments.opponentBaseStats` |
| Simulated bracket win chances by level | `STD_WIN_CHANCES` [4][3] (`std_main.c`) | `0x8007A58C` | `0x80073EB4` | `tournaments.winChances` |
| Cup eligibility, overlevel and rival lists, requirements | map script section 10 (`DG.SCN`, `getCupDataJumpTable`) | | | not covered: DWS (`docs/mods/dws.md`); the species ≥ 180 levels come from `DIGI.DAT` |
| Evolution timers (24/72/144 h …), lifetime (360 h), care rules, training gains (`trn_reward.c`), battle stat-gain formula, special evolutions, rival stat spread | C code constants | | | not covered: C (the `caps` patch shows the way) |

## 2. The three layers

| Layer | Where | In git? | What |
|---|---|---|---|
| **original** | read from the player's `extracted/` (`balance.py extract` writes it to `build/balance/original/tables.json` and `maps.json` to read) | **never** (game data) | every table of § 1 as the disc has it |
| **species** | `content/species/<id>-<name>.json` (`docs/mods/species.md`) | yes | every per-species row, original values ⊕ what the C patches change, complete; `species.py extract` makes the originals' from the player's disc |
| **engine** | `content/balance/engine/tables.json` | yes | what the C patch series (`mods/patches`) puts in the originals' **evolution** rows, as differences from the original (requirements, gains and paths of the NPC partners, the Mega paths). **Generated** by `balance.py sync` from a compiled build; never edited by hand |
| **overrides** | `content/balance/*.json` (top level only, read in name order) | yes | the balance changes: sparse, only the fields that change. A field set by two files is an error |

**Maps:** the wild Digimon's stats (and the whole placement) are `content/maps/<FILE>.json`; the `maps` layer
of this tool is retired (an override of it is an error).

**Policy.** Every numeric domain is committed JSON and the source of the build:
the species in `content/species` (the 180 originals included), techniques, items and the small tables in
`content/techniques|items|tables` (`tools/content.py`), the evolution rows of the originals in their species files
(`docs/mods/data-sources.md`). Models, textures, sounds, dialogue text and disc files are never committed. The
extractors stay, so every file can be made again from the player's own disc.

What the game gets = species files + (original ⊕ engine ⊕ overrides) for the
other tables. Evolution rows the mod's executable has and the original has not
(the 180-row tables) start as zeros, as a C array without an initializer.

## 3. The format

One document shape for the dumps and the overrides. Ids are JSON strings.
Keys that start with `_` are comments, ignored everywhere (the dumps use them
for names: `_name`, `_moves`, `_evolvesTo`, `_mp`). Field names are those of
the decompilation's structs (`include/dw/*.h`) and of `content/species`.
Values are the raw numbers the game stores (no unit conversion: `mpCost` 10
costs 30 MP; HP/MP requirements are in tenths); lists are replaced whole.

```jsonc
{
  "species": {                       // dumps and the engine layer only: the originals' evolution rows
    "<id>": {                        // (the other per-species values: content/species, docs/mods/species.md)
      "evoReqs":  { "digimon", "hp", "mp", "offense", "defense", "speed", "brain", "care", "weight",
                    "discipline", "happiness", "battles", "techs", "flags" },        // -1 = no requirement
      "evoGains": { "hp", "mp", "offense", "defense", "speed", "brains", "targetDigimon" },
      "evoPaths": { "from": [5], "to": [6] }                                         // -1 = empty slot
    }
  },
  "techniques": { "<0..121>": { "distance", "power", "mpCost", "iframes", "range", "special", "status",
                                "accuracy", "statusChance", "unk3", "learnChances": [main, second, third] } },
  "brainTraining":  { "techniques": { "fire": [8], "battle": [8], ... }, "weights": [[3] x 8] },  // TRN overlay
  "brainTraining2": { ... },                                     // TRN2 overlay, when it differs from TRN
  "typeFactors":    [[7] x 7],          // [attack element][defender element], tenths
  "evolutionItems": { "<71..114>": species },
  "joinChances":    [[3] x 4],          // FLEE_CHANCES: partner attribute x enemy attribute, %
  "items":          { "<0..127>": { "value", "meritValue", "sortingValue", "itemColor", "droppable" } },
  "tournaments":    { "schedule": [[6] x 30], "opponentBaseStats": [24], "winChances": [[3] x 4] },
  "maps":           { "MAP/MAP1/MAYO02.MAP": { "<slot>": { "hp", "mp", "currentHP", "currentMP", "off", "def",
                      "speed", "brain", "bits", "chargeMode", "moves": [4], "prios": [4] } } }
}
```

Notes:

- A species' technique list (`techniques` in its file) is in slot order: the
  model plays animation 0x2E+*i* for slot *i*, so reordering the list changes
  which animation a technique uses. On evolving the partner learns the weakest
  technique of its main element *in this list* and its finisher is the last id
  58..112 in it (`EVL_applyEvolution`).
- A wild Digimon's `moves` are **slots** 46..61 (0x2E + index in its species'
  technique list), as in the `.MAP`; the dump names them in `_moves`.
- A `species` section in `content/balance/*.json` is an error (its values are
  in `content/species`).
- A new species is linked into an original's paths through its own
  `evolution.from`/`to` (`content/species`), not by writing its id into the
  original's `evoPaths`.
- An executable with 8-bit paths (the original) refuses ids > 127 in
  `evoPaths`.

## 4. Commands

```bash
tools/balance.py extract            # build/balance/original/tables.json + maps.json from extracted/ (read them, copy fields)
tools/balance.py show 17            # one species' table rows as the game will get them (ids >= 180 too)
tools/balance.py dump               # build/balance/effective.json: every species, every table, layers merged
tools/balance.py check              # validate content/balance/*.json (below)
tools/balance.py build --exe-dir build/decomp-int/build/us/psx/gcc -o build/full/exe   # what build-full.sh runs
tools/balance.py verify             # species files + original + engine == the build's 27 tables, table by table (sha1 printed)
tools/balance.py sync               # after a C patch changes an evolution table: regenerate the engine layer
tools/species.py sync               # after a C patch changes a per-species table on purpose: the species files
BALANCE_CONTENT=dir tools/balance.py ...   # another override folder (or --content dir)
SPECIES_CONTENT=dir tools/balance.py ...   # another species folder (all 180 originals in it)
```

`--exe-dir` defaults to `build/decomp-int/build/us/psx/gcc`. A folder without
`SLUS_010.32.elf` is taken as the **original executable** (`--exe-dir extracted`):
then there is no engine layer, the species rows come from `species.py extract`
of that executable, and the overrides become a data patch of the unmodified
game.

**Which disc it reads.** `build` starts from the tables of the executable it is given (a compiled
one holds original ⊕ engine already, as the C initializes them), then the species files and the committed JSON: it
opens no executable or overlay of `extracted/`, so a European disc can be the base. `extract`, `verify`, `sync`,
`check`, `dump` and `show` read the original layer from the USA executable in `extracted/`: developer tools. A C patch
that changes a table after the last `sync` shows up in `verify`/`check` (the build keeps the C's values, as it always
did).

**How it writes.** `build` copies the executable and overlays of the build
(`SLUS_010.32`, its `.elf`/`.elf.map`, `*_REL.BIN`) into `-o`, encodes every
table of § 1 from the merged JSON and writes it at the symbol's address, taken
from the build's ELF symbol table (address and size: the row count and the
8/16-bit path width follow from the size). It does not touch the C sources:
the tables are plain non-`const` data, so a table written after linking is
what the code reads. This is chosen over a generated header in the decomp
worktree because the proof of identity is a `cmp`, the numbers never enter the
decomp sources, no recompile is needed to rebalance, and it works with any
build variant (or the original executable). `.MAP` overrides are written in
place (same size) into `-o/maps/…`, starting from the file `--file DEST=SRC`
names (a DWS output) or the original; `build` prints `FILE: DEST=SRC` lines.
`tools/build-full.sh` runs it between `make` and `build-disc.py` (step 5b) and
passes those files on.

If a C patch changed a per-species table and the species files do not say so,
`build` stops, naming each species, field, C value and JSON value (`species.py
verify`): edit the JSON, or `species.py sync` when the C change was meant. If a
C patch changed another table after the last `sync`, `build` warns and puts the
overrides on top of the executable's own values (it never reverts C); `verify`
and `check` fail until `balance.py sync` is run.

**Validation** (`check`; `build` runs it too and stops on an error):

- every key is known (a typo such as `weigth` is an error, with the list of
  valid fields), sections and ids exist;
- every value fits its C field (`s8`/`u8`/`s16`/`s32` ranges), lists have
  their length (16 moves, 3 specials, 5 `from`, 6 `to`, 8 hunger times …);
- references: technique ids exist (0..121 or 255), learn chances only for
  techniques 0..57, elements 0..6 or 255, statuses 0..4, ranges 1..4,
  percentages 0..100, species in `evolutionItems` exist (originals or
  `content/species`), wild slots exist in that `.MAP`, wild moves are slots
  46..61;
- no `species` section (species values are in `content/species`, which
  `species.py` validates: every key known, the list of keys in every error);
- the engine layer still matches the build.

```
$ tools/balance.py check
error: techniques.2.powr: unknown field (distance, power, mpCost, iframes, range, special, status, accuracy, statusChance, unk3, unk4, unk5)
error: techniques.70.learnChances: only techniques 0..57 are learnable
1 override files: 2 values for the executable tables (0 equal to the current value), 0 for wild Digimon: 2 errors
```

## 5. Examples

Raise Spit Fire's power and make it easier to learn
(a new file in `content/balance/`, e.g. `spit-fire.json`):

```json
{ "techniques": { "2": { "_name": "Spit Fire", "power": 90, "learnChances": [45, 30, 20] } } }
```

A species value (any species, original or imported): edit its file. Greymon
drops a Giant Meat at 30 %; at 60 %, in `content/species/5-greymon.json`:

```json
  "drop": {"item": "Giant Meat", "percent": 60},
```

(The originals' evolution requirements are not editable through overrides.)

A wild Digimon (slot 1 of `MAYO02.MAP`) with more HP and a bigger reward:

```json
{ "maps": { "MAP/MAP1/MAYO02.MAP": { "1": { "hp": 1200, "currentHP": 1200, "bits": 2000 } } } }
```

Then `tools/balance.py check` and `tools/build-full.sh`.

## 6. Proofs

`balance.py verify --exe-dir extracted`: the 27 tables (19 global, 8 per species) encoded from `species.py extract`'s
files and the original JSON equal the disc's bytes. `balance.py verify` on the integration build: content/species ⊕
original ⊕ engine layer (evolution rows only) equals all 27 tables. A disc built with every table written from JSON is
byte-identical to one built from the executable as linked.

In the game, the example overrides (`BALANCE_CONTENT=content/balance/examples`: Veemon's technique list without Sonic Jab
in `DIGI.DAT`, and Tremar's `mpCost` 56 → 20 in `MOVE_DATA`) change 72 bytes of the disc. With Agumon forced to evolve
into Veemon (`EVOLUTION_TARGET=180`):

| | disc A (unchanged) | disc C (JSON) |
|---|---|---|
| `MOVE_DATA[40].mpCost` in RAM | 56 | 20 |
| learned on evolving (`learnedMoves`) | Sonic Jab (bit 43) | Tremar (bit 40) |
| equipped slot `moves[0]` | 0x30 (list index 2) | 0x33 (list index 5) |
| Digimon › Tech screen | Sonic Jab, 52 power, 18 MP | Tremar, 178 power, **60 MP** |

## 6.1 The economy rule

No repeatable conversion may turn bits into more bits. Every item and card is valued at its best way out (a shop's
sell price, merit at the merit shop's best rate, Mojyamon, DemiMeramon, ClearAgumon, the Trash Mountain card swap): a
Mojyamon trade may not give more than its input sells for, and a card pack or the card machine may not give back more
than it costs; the daily card shop (6 cards, one copy each) is bounded by itself. The changes that meet it:

| What | Disc | Now | Why |
|---|---|---|---|
| Mojyamon's outputs (`shops.json` `mojyamonTakes`) | med.recovery, Omnipotent, Hair grower, Auto Pilot, Restore, Medicine, S.Off/S.Def/S.speed disk | sm.recovery, Off. Disk, Medicine, Auto Pilot, Rest pillow, Def. Disk, Large MP, MP Floppy, Meat | each output is worth no more than its input (the trades never had a limit: med.recovery bought for 500 became an S.Def.disk sold for 2000, 99 at a time since patch 0223) |
| sup.recovery / Sup.restore merit | 20 / 100 | 60 / 250 | merit sold through them made a 500-bit card pack worth about 1090 bits |
| Card machine odds (`economy.json` `cardMachine`, in its script `libraries/s219` before patch 0237), rarity 2 / 4 | 7 / 70 % | 5 / 72 % | the cards' own sale price plus DemiMeramon and ClearAgumon gave back 103 bits a 100-bit card (the price is in its text) |
| Tekkamon's drop (`90-tekkamon.json`) | S.Def.disk 100 % | 15 % | a wild fight of the Back Dimension, about 4900 bits each, without limit |
| Ground items (patch 0230) | rolled again on every entry | a spot gives its item once a day | Amida Forest's road gave about 1260 bits an entry |
| Battle bits (patch 0235, `economy.json` `battle.bitsPercent`) | the enemies' bits | 150 % | money earned by playing: a fight paid one or two days of upkeep, and nothing was worth saving for |
| Chips for bits (`secret-item-shop/s177`, Devimon's hours) | merit only (800) | the six chips at 9999 each too | a sink worth saving for on the original story too (a chip sells for 4999: no loop) |
| Meat price (`content/items/38-meat.json`) | 50 | 30 | upkeep while training (no fights, no income): a day of food was about 500 bits for Agumon, 1100 for Numemon, 1400 for Tyrannomon; 40 % less for all (Mojyamon's Digianchovy -> Meat: 25 -> 15, still under its input) |
| New game start kit (`file-city/s193-238` section 55, after the intro wipes the debug save) | 0 bits, no items | 20 Meat, 1000 bits | the first days had only the farm's 3 Meat a day; once per game, no loop |
| Meat farm big harvest (`libraries/s207`, `file-city/s164-204` section 11) | 1 day in 10 | 1 day in 4 | 5 instead of 3 Meat / Giant Meat / Sirloin; a day's share, no loop |
| Psychemon / Gururumon wild bits (story mod) | 200 / 200 | 300 / 400 | the pay of the original's wild Digimon of their offense (330-420: about 300) |

The money analysis behind it: upkeep is about 300-1500 bits a game day, nothing on the story path costs
bits, and bits bought little power (DV chips about 40 stat points a 1000 bits, restaurants 1-4, the gym 80-100 a day for
free). Drimogemon's 5000-bit dig gives one item, and no item sells for more than 4999, so it cannot pay without
changing its price, which its text says.

## 6.2 Monochromon recruitment

The shift recruit target falls from 3072 to 2560 bits of profit. Recruitment was
an approximately 1 % outcome at list prices and 13 % at a steady +10 %; simulation
at 2560 gives 8 % and 37 %, respectively. The top halfway comment moves from
1536 to 1280 bits, half the new target. The 1792-bit payout tier and the
500/1500/2000-bit payouts stay unchanged, as do prices, odds, customers and text.
The plate fills at 2560 bits, with its 1792-bit tick at 70 % of the inside width.

## 7. Related sources

Runtime rules and their numeric data are mapped in [data sources](data-sources.md).
Species records, including imported evolution data, are described in
[species](species.md). Story-owned cup tables and events go through the story
compiler; translated names belong to the text bank. Model and sound formats
have their own authoring tools. Rebuild through derive and the integrated builder
so these sources remain consistent.

## Jijimon's starter quiz

`content/tables/new-game.json` owns the 35-rookie starter list, seven questions' weights and two 45-cell grids.
The eight partner rookies that reuse another species' model (SnowAgumon, Dokunemon, Psychemon, Muchomon, Tsukaimon,
BlackGatomon, RedOtamamon, VioletElecmon; `RECOLOURS` in `tools/starter_quiz.py`) are never a quiz result. They
stay in the game through evolution.
All seven answers count. Each axis chooses its highest score, breaking a tie by the most recent answer that
supported it. If that answer supported both tied choices, the earlier axis wins: battle/fire/ice/nature/air,
vaccine/data/virus, bold/calm/cunning. Mech shares air. There is no random draw.
`tools/starter_quiz.py` enumerates all 2187 paths: minimum 32/2187 (1.4632%), maximum 103/2187 (4.7096%).
Agumon keeps fire/vaccine/bold; Gabumon keeps battle/data/calm. Ten cells are spare: Palmon, Betamon, Salamon, DemiDevimon, Guilmon, Flarerizamon,
Bearmon, Penguinmon, Kunemon and Yanmamon each hold two.

Renamon uses battle/vaccine/cunning and Candlemon uses fire/vaccine/cunning although both are Data. Two specialty exceptions fill thin cells: Monmon uses fire/virus/cunning and Kotemon uses
nature/data/cunning. Their species attributes and specialties remain unchanged. All other cells match attribute
and at least one specialty. The assignments are:

| element / attribute | bold | calm | cunning |
|---|---|---|---|
| battle / vaccine | Salamon | Veemon | Renamon |
| battle / data | Patamon | Gabumon | Gotsumon |
| battle / virus | Gazimon | DemiDevimon | Guilmon |
| fire / vaccine | Agumon | Solarmon | Candlemon |
| fire / data | Flarerizamon | ToyAgumon | Flarerizamon |
| fire / virus | Guilmon | Goblimon | Monmon |
| ice / vaccine | Bearmon | Gomamon | Bearmon |
| ice / data | Penguinmon | Penguinmon | Otamamon |
| ice / virus | Betamon | Gizamon | Betamon |
| nature / vaccine | Palmon | Armadillomon | Palmon |
| nature / data | Tentomon | Floramon | Kotemon |
| nature / virus | Kunemon | Kunemon | Wormmon |
| air / vaccine | Biyomon | Hagurumon | Salamon |
| air / data | Elecmon | Hawkmon | Kokuwamon |
| air / virus | Yanmamon | Yanmamon | DemiDevimon |

With NEW DIGIMON off the same answers read `quiz.vanillaCells`, a second 45-cell grid holding only the nine rookies of
the original game, so the partner never starts as a species that option forbids. `modQuizResult` picks the grid once;
the announced name, default partner name and partner all read the same p254. Each of the nine lands between 10.3% and
11.9% of the paths, checked in `tools/starter_quiz.py` (9%..13%).

The self-test rejects missing pool species, invalid cells/weights and frequencies outside 0.5%..6% (9%..13% with NEW DIGIMON off).
`tools/test_starter_quiz.py` also compares the production C result function with the model on every path when
a prepared tree and host compiler are available. This host comparison does not verify emulator dialogue or input.

Starter evolution coverage is counted from distinct champions' `evolution.from` and `requirements.digimon`,
not a rookie's `to` list or duplicate NPC names. Patch 0273's data companion adds the following shared-specialty
routes, keeping the existing primary-parent bonus and every disc species' own route and requirement:

| rookie | added champions |
|---|---|
| Yanmamon | Roachmon |
| VioletElecmon | Lighdramon |
| Monmon | Hookmon |
| Bearmon | Ebidramon |
| Renamon | Wizardmon |
| Psychemon | Minotarumon, Lighdramon |
| BlackGatomon | Devidramon, Vilemon |
| RedOtamamon | Shadramon, Growlmon |
| Kokuwamon | Thundermon, Snatchmon |
| Solarmon | Starmon, BomberNanimon |

A second round brings every partner rookie to at least four distinct champions:

| rookie | added champions |
|---|---|
| Guilmon | Flamedramon, Tuskmon |
| Renamon | Baronmon, Gatomon |
| Monmon | Golemon, Tapirmon |
| Bearmon | Ikkakumon, Golemon |
| SnowAgumon | Ikkakumon, Gururumon |
| Psychemon | ExVeemon, Ankylomon |
| BlackGatomon | Gatomon, Fugamon |
| RedOtamamon | Syakomon, ExVeemon |
| ToyAgumon | Magnamon, Digmon |
| Solarmon | Bulbmon, Guardromon |
| Kokuwamon | Bulbmon, Flymon |
| VioletElecmon | Pegasusmon, Aquilamon |
| Yanmamon | Stingmon, Shurimon |
| Wormmon | Shurimon, Kurisarimon |
| Dokunemon | Kurisarimon |
| Goblimon | Veedramon |
| Kotemon | Flamedramon |
| Muchomon | Aquilamon |
| Salamon | Halsemon |
| Tentomon | Stingmon |

Every added link shares a specialty, goes to an imported champion and leaves it with at most three parents.

The later curated evolution tree is data in `content/tables/evolution-tree.json`, applied by `tools/evo_tree.py`. Canon main lines come first, then family/shared specialty; imported canon Megas follow Perfects. The generator leaves the 45-cell quiz, its results and all Rookie → Champion links unchanged. Up to five parents and six children fit the existing species rows. Requirements are resolved against sibling competition and disc canonical states, then checked with conservative File City training gains and the natural evolution gains. Timing and lifetime tables are unchanged: Champion 144 h, another Ultimate 96 h, engine Mega 120 h; natural Ultimate adds 96 h. The documented specialty exceptions preserve disc/engine routes, Otamamon → Geremon and the canon Kurisarimon → Infermon line.

A record original inside ids 1–62 still uses the resident `EVOLUTION_PATHS` row. The balance layer therefore writes its species file’s padded `from`/`to` lists there, while its other rows retain the existing record-original behavior. This makes WereGarurumon’s three curated parents fit without counting unused reverse entries from the disc placeholder. Native partners 63, 66, 121 and 124 carry cached records for their onward evolution paths; requirements and gains are retained.
