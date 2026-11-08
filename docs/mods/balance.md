# Balance as JSON

Looking for why something changed? See the [gameplay and design decision log](../decisions.md).

Every number that balances a Digimon (techniques, evolution requirements and
paths, stat gains, raise data, learning chances, drops, wild enemies,
tournaments) can be changed by editing JSON. `tools/balance.py extract` can import numerical values for authoring. Builds clear numeric domains and apply committed JSON to the executable, its overlays and the `.MAP` files; they never inherit a player-disc balance floor.

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
| Evolution timers (`evolution-rules.json`), lifetime (`new-game.json`), care rules, training gains (`trn_reward.c`), battle stat-gain formula, special evolutions, rival stat spread | C code constants | | | not covered: C (the `caps` patch shows the way) |

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

No **uncapped** conversion may turn bits into more bits. Every unlimited item/card conversion is valued at its
best unlimited exit: shop sale, merit, uncapped trades and NPC card conversions. An uncapped Mojyamon output must
not exceed the input's sale value; card-pack and machine expected returns must stay below their purchase price.

There is a precise exception for reviewed Mojyamon rows limited to **one item per in-game day**, persisted in the
save. Those rows may exceed the input's sale value. The five approved daily gain pairs and the separately approved
**once-per-save** Dolph Fin pair are pinned by row, input, output and limit in `tools/economy_audit.py`'s
`MOJYAMON_GAIN_EXCEPTIONS`. An unreviewed gain, including a changed profitable pair or missing required cap, fails the audit. Dolph Fin must not be
classified as daily. Capped edges are excluded from unlimited trade-chain/vending valuations; their finite gains
are reported separately. The existing daily card shop is likewise bounded by six cards, one copy each.

| What | Disc | Now | Why |
|---|---|---|---|
| Mojyamon's exchanges (`shops.json`) | unlimited rewards, including Medium Recovery → S.Def.disk | eight daily exchanges and one once-per-save exchange (table below) | explicit bounded gains; amount box caps at 1; Dolph Fin cannot be farmed by delaying recruitment |
| sup.recovery / Sup.restore merit | 20 / 100 | 60 / 250 | merit sold through them made a 500-bit card pack worth about 1090 bits |
| Card machine odds (`economy.json` `cardMachine`, in its script `libraries/s219` before patch 0237), rarity 2 / 4 | 7 / 70 % | 5 / 72 % | the cards' own sale price plus DemiMeramon and ClearAgumon gave back 103 bits a 100-bit card (the price is in its text) |
| Tekkamon's drop (`90-tekkamon.json`) | S.Def.disk 100 % | 15 % | a wild fight of the Back Dimension, about 4900 bits each, without limit |
| Ground items (patch 0230) | rolled again on every entry | a spot gives its item once a day | Amida Forest's road gave about 1260 bits an entry |
| New screens' ground items (`content/ground-items.json` `"off"`) | — | 3 of the 7 mushrooms of Native Forest's script they share, on reachable floor | all 7 on 34 screens was about 240 free daily pickups |
| Battle bits (patch 0235, `economy.json` `battle.bitsPercent`) | the enemies' bits | 150 % | money earned by playing: a fight paid one or two days of upkeep, and nothing was worth saving for |
| Secret shop chips (`secret-item-shop/s177`, Devimon's hours) | DVChipA / D / E only | DVChipA / D / E only; plain chips stay at 800 merit in the merit shop and in chests | selling the six plain chips beside the Devil Chips undermined them; the merit shop keeps the plain chips |
| Meat price (`content/items/38-meat.json`) | 50 | 30 | upkeep while training (no fights, no income): a day of food was about 500 bits for Agumon, 1100 for Numemon, 1400 for Tyrannomon; 40 % less for all |
| New game start kit (`file-city/s193-238` section 55, after the intro wipes the debug save) | 0 bits, no items | 20 Meat, 1000 bits | the first days had only the farm's 3 Meat a day; once per game, no loop |
| Meat farm big harvest (`libraries/s207`, `file-city/s164-204` section 11) | 1 day in 10 | 1 day in 4 | 5 instead of 3 Meat / Giant Meat / Sirloin; a day's share, no loop |
| Psychemon / Gururumon wild bits (story mod) | 200 / 200 | 300 / 400 | the pay of the original's wild Digimon of their offense (330-420: about 300) |

The executable reads the player's input from `shops.json`'s `mojyamonGives` and the reward from `mojyamonTakes`.
Freezeland scripts 128/129 retain three groups. Group 3 alone recruits after all nine historical rows are complete;
return to it if another group completed the final row. Previously recruited saves keep their departure flags.

| Group | Player gives | Mojyamon gives | Limit | Input sale | Reward sale | Sale-value gain |
|---|---|---|---|---:|---:|---:|
| 1 | Happy Mushroom | Deluxe Mushroom | 1/day | 500 | 2500 | +2000 |
| 1 | Digiseabass | Chain Melon | 1/day | 4000 | 2500 | -1500 |
| 1 | Digisnapper | Digipine | 1/day | 50 | 500 | +450 |
| 2 | Supercarrot | Large MP | 1/day | 250 | 1000 | +750 |
| 2 | Hawk Radish | Large Recovery | 1/day | 250 | 500 | +250 |
| 2 | Blue Apple | Double Floppy | 1/day | 500 | 750 | +250 |
| 3 | Digimushroom | Auto Pilot | 1/day | 50 | 150 | +100 |
| 3 | Giant Meat | DigiTrout | 1/day | 250 | 150 | -100 |
| 3 | Small Recovery | Dolph Fin | **1/save** | 50 | 2500 | +2450, once only |

The six positive daily sale-value exceptions total **3800 bits/day** above selling those inputs directly. Taking
all eight daily rows, including the two that lose sale value, adds **2200 bits/day** over selling all eight inputs.
Mammothmon already sells Ice Mushrooms, so the first reward is now Deluxe Mushroom. It grants +100 HP,
+100 MP and +10 to each of the four other stats: about 240 points spread, versus about 900 from a training day.
Happy Mushrooms are scarce: one per day from Dragon Eye Lake vending for 1500 bits, plus rare ground rolls.
Buying that input and selling the reward nets at most **1000 bits/day**, below the 1500-bit Birdramon trip.
With an already-owned input, the gain over selling it is **2000 bits/day** (2500 minus 500); these baselines
must remain distinct.

These are finite allowances, not unlimited conversion exits. Item 70 (Chain Melon) is displayed as Overripe Melon
in the English item-name bank. Double Floppy is item 7, not Restore.

Every amount box caps at one. Daily bits 789–796 gate the eight daily rows; the former ninth daily bit 797 stays
reserved/cleared for compatibility. Dolph Fin checks historical completion flag **13**, which is never cleared
at midnight. Its first successful exchange sets that flag, even if recruitment is postponed. Cancellation and
full-bag failures spend neither type of allowance. Saving/loading retains the flags. Existing saves that already
completed the old ninth row keep it spent rather than resetting recruitment progress.

### Daily gain ceilings

A ceiling means **additional gain**, not the gross sale value of the rewards. With inputs already owned, the
baseline is selling them directly. Doing all eight rows adds **2200 bits/day**; choosing only the six positive
rows adds at most **3800 bits/day**, or **2300 after a 1500-bit Birdramon trip**. Doing all eight after that trip
gains 700 relative to selling the inputs. A free pickup or fish still has its sale value as an opportunity cost.
The audit prints both all-row and positive-row totals. After group 3 recruits, the remaining six rows still add
2200 together, with a positive-row ceiling of 3700 (2200 after the trip).

Purchase gains subtract the cheapest actual fixed offers below. Digiseabass has **no shop offer**, so no purely
shop-funded eight-row calculation exists. Digisnapper is sold at the Cold Store for 100 (90 with a baby).

| Daily input | Cheapest normal / baby purchase | Source | Reward sale |
|---|---:|---|---:|
| Happy Mushroom | 1500 / 1500 | Dragon Eye Lake vending, one/day | 2500 |
| Digiseabass | not sold | fishing | 2500 |
| Digisnapper | 100 / 90 | Cold Store | 500 |
| Supercarrot | 500 / 450 | city stalls; Vegiemon is fixed at 500 | 1000 |
| Hawk Radish | 500 / 450 | city stalls; Vegiemon is fixed at 500 | 500 |
| Blue Apple | 1000 / 900 | Tapirmon's Market Shed | 750 |
| Digimushroom | 51 / 51 | Dragon Eye Lake vending | 150 |
| Giant Meat | 300 / 300 | Ancient Glacial Region vending | 150 |
| **All eight daily rows** | **3951 / 3741**, plus free Digiseabass | | **8050** |

| Gain baseline and choice | Normal | Baby discounts | After 1500 trip, normal / baby |
|---|---:|---:|---:|
| Own all inputs: trade all eight instead of selling them | 2200 | 2200 | 700 / 700 |
| Own inputs: choose only positive sale-value rows | **3800** | **3800** | **2300 / 2300** |
| Buy inputs: trade all seven purchasable rows | 1599 | 1809 | 99 / 309 |
| Buy inputs: choose only profitable purchasable rows | **1999** | **2109** | **499 / 609** |
| Buy seven inputs + free Digiseabass: all eight cash net | 4099 | 4309 | 2599 / 2809 |
| Buy inputs + free Digiseabass: choose positive cash-net rows | 4499 | 4609 | 2999 / 3109 |

The purchase-only ceiling uses Happy Mushroom → Deluxe Mushroom, Digisnapper → Digipine,
Supercarrot → Large MP and Digimushroom → Auto Pilot;
Hawk Radish → Large Recovery also profits with baby discounts (normal price breaks even). The mixed cash-net
scenarios add the fished Digiseabass reward while counting no fishing/bait expense. They do **not** count its
4000-bit sale value as a cost; that trade actually loses 1500 versus selling the fish. Return travel and paid bait
are excluded. The outputs' gross 8050 is a receipt total, never the incremental daily-gain ceiling. All eight
owned inputs sell for 5850 before any exchange. Free inputs can come from pickups, fishing, farm stock and drops;
Supercarrot/Hawk Radish drop from RedVegiemon/Weedmon at 10% each.

Group 2 adds 1250 over selling its three inputs; buying all three nets 250/450. Dolph Fin adds **2450 once per
save** over selling Small Recovery, or **2400/2410 once-only purchase net** at a 100/90 input price. It never enters
recurring daily gains.

Tapirmon keeps Hawk Radish and Supercarrot at their global value 500 (450 baby purchase); Vegiemon remains fixed
at 500. Generic shops read `ITEM_PARA[item].value` for display and charge, and the story `shop(...)` API takes stock
only. There is no per-shop price override, so a Tapirmon-only 700-bit price is skipped rather than changing global
values or Vegiemon's prices.

North Star (92) remains **Whamon (24)**'s arena cup-14 reward, with its original descriptions in all eight languages.
Whamon is an Ultimate with NEW DIGIMON on, so a Champion can use North Star. With the option off Whamon is a
Champion and a Rookie can use it. The native target-stage reader follows current stages: Mega items require an Ultimate, including Red Ruby and Beetlepearl. No story Whamon (146), tournament reward, merit or North Star value changes.

**Dolph Fin (124)** is a separate 5000-value evolution item, sold for 2500, with meritValue 0. The otherwise-unused
AS Decoder slot has no stock, drop or story use in this branch or current main; the real fridge key remains item
123. Its existing AS Decoder sprite uses an existing blue palette. The existing fourth `evolutionItemRules` slot
maps it to Dolphmon (238) for a Rookie (level 3), and its handler/refusal range now includes 124. NEW DIGIMON off
refuses the unavailable import without consuming it. No item table, name/description count, icon atlas, custom
rule array or save field is enlarged. All nine localized names fit 11 characters. Simplified Chinese includes the item name/description and both
daily/permanent trade-limit messages, with the 鳍 glyph in both fonts; Chinese requires 8 MB. Existing ninth-row completion flag 13 remains spent in old saves,
including saves that received the earlier North Star reward; no progress is reset or item silently exchanged.

The money analysis behind it: upkeep is about 300-1500 bits a game day, nothing on the story path costs
bits, and bits bought little power (DV chips about 40 stat points a 1000 bits, restaurants 1-4, the gym 80-100 a day for
free). Drimogemon's plans are checked by the audit: their tables must sell for less than their price.

Daily ground finds use an 8% per-entry floor for ordinary food and utility items. The five 1% single-stat
food spots (Power Ice, Sage Fruit twice, Muscle Yam and Calm berry) use 3%. Deluxe mushroom, Chain melon
and Gold Acorn keep their existing odds to protect permanent stats, lifetime and jackpot rewards. The
one-pickup-per-spot-per-day cap is unchanged: unsuccessful entries can reroll, but collection consumes
the spot until midnight. Rare useful finds were too rare once this daily cap existed.

Amida Forest keeps Orange banana / Happymushrm / Auto Pilot at 8% / 12% / 20%, preserving that rarity
order; Omni Disk / Medium MP use 8% / 25%. The added probability comes from the empty outcome, keeping
companion odds intact. These rolls still stop after Centarumon is recruited. New story screens keep
their current mushroom odds, including Deluxe mushroom at 2%.

## 6.2 The care and reward pass

Changes taken from a tester's balance document. They are the rules of the game for everybody: there are no modes.
Requirement tests: `tools/test_evo_tree.py --practical`, `tools/economy_audit.py`.

| What | Disc | Now | Why |
|---|---|---|---|
| Lifetime, Champion wait, Numemon fallback | 360, 144, 96 h | 408, 168, 120 h | a day more as a Champion to reach a target; the Rookie keeps the disc's 72 h wait; the time as an Ultimate does not change |
| Digiseabass, Chain melon, DV chips (lifetime) | +3, +20, -24 h | +6, +24, -6 h | worth using to stay longer in a form |
| File City gym base gain | 8 (HP, MP 80) | 10 (100) | less grind; the secondary gains stay |
| Tiredness of a gym session | HP 10, Off and Def 9, Spd 8, MP 7, Brain 6 | 8 in every gym | no stat is harder to train for its tiredness: about 9 sessions before 70, the same average |
| The training type's favoured stat | x1.1 | x1.2 | the type matters; x0.9 stays |
| Leomon's and the Ice Sanctuary's gyms | 8 and 12, with a secondary stat | 15 (HP 150), no secondary stat | a reason to walk there; Beetle Land stays at 12, Trash Mountain and Cherrymon already gave this |
| A won battle | the disc's formula | also at least 1 % of the strongest enemy's stat, 1.2 % and 1.6 % against two and three (patch 0322) | a stronger partner still gains; about one gym session of points a fight, so the gym stays the way to train |
| Favoured / hated map, an hour | happiness +1 / -1, tiredness -2 / +1 | +3 / -3, -3 / +2 | the favoured place matters, with no bar filled in a day |
| Element chart (`type-factors.json`) | uneven, 2.0 to 0.2 | 2.0 strong, 1.0 neutral, 0.2 weak, in cycles; all hit Filth for 2.0, Filth hits Mech for 2.0 | a chart a player can learn |
| Restaurants (`libraries/s217`, `s218`) | 300-9000 bits, 1-5 points | 400-1500 bits, 8-42 points, 35 energy | a meal was not worth buying. DV chips still give more points a bit, at a lifetime cost |
| Digitamamon's roll | one in three each | 30 / 30 / 40 %, all stats | a late recruit's meal should please |
| Drimogemon's plans | 3 days 1000 bits, 10 days 5000 bits | 1 day 2000 bits, 3 days 5000 bits, new tables; with Gabumon 5 % roll another item | the price is what stops a daily profit: the 1000 bits a day table would sell for 1545 |
| Underground Pond dirt hauling (`underground-pond/s029-28`, `file-city/s162`) | 10 round trips, each 500 bits, Off and Def +5, HP +50, tiredness +10 | 5 round trips, each 1000 bits, Off and Def +10, HP +100, tiredness +20; the pile shrinks two steps a trip and stays gone once the tunnel opens, a box carried home counts as a trip | the same totals (5000 bits once, the tunnel's work done) in half the walking; the five-day wait still finishes it |
| Poison Claw (`content/techniques/37-poison-claw.json`) | 17 MP (51 shown) | 22 (66 shown) | 44 partners can learn it (10 on the disc), and its poison takes 1-3 % of the foe's max HP every 5 s: cheap enough to spam on every boss |
| Death evolutions (`libraries/s212`) | 10 % | 30 %; Devimon stays at 50 % | a player should see them without resetting |
| Evolution items (patch 0323) | no gains, lifetime or tamer level | as any evolution | they are rare, they should not punish |
| Evolution rows `techs` | a bonus for 21-49 techniques | gone; Gigadramon asks 100 battles instead | the bonus could stand in for the stats, so a raised partner took another route |
| Grey Lord's Mansion, Ice Sanctuary | a Virus, a Vaccine partner | also any partner once Myotismon, Angemon joined | the partner does not lock a place already opened |
| Monzaemon's costume | gone after the toy story | a Numemon can always wear it | a late route to Monzaemon |
| Sukamon, Andromon in File City (`city/file-city-services.py`) | one line each | Sukamon clears the island's poop for 1000 bits (patch 0324); Andromon remodels a Mamemon as Guardromon does, who keeps doing it; other partners receive his usual city greeting | Andromon stands there on about one daytime visit in four: the service cannot depend on him alone |

The first partner and partners born later both start with **408 hours** of remaining
lifetime (`new-game.json`: `firstPartner.lifetimeHours`, `partnerBirth.lifetimeHours`).
Care and training can reduce that budget. The Chart requirements popup shows time
in the current form against the selected target’s wait, and warns in red when the
remaining lifetime counter is shorter than the wait still needed. “Ready” requires
the score, model fit and time; competing targets and special routes still follow
the game’s selection rules.

## 6.3 Monochromon recruitment

Each shift serves exactly twenty visits from a shuffled deck of **8 Meat / 9
Portable Potty / 3 Medicine**. Draw the item first, then independently draw
Goblimon/Gotsumon/Weedmon/Muchomon with weights 3/3/2/1. This removes the
Medicine-count lottery. Every visit counts once, including an offended departure.

A customer draws one hidden maximum markup, uniformly in 10-percentage-point
steps: Goblimon **+30…+50 %**, Gotsumon **0…+30 %**, Weedmon **−10…+20 %**,
Muchomon **−20…+50 %**. The player selects −30…+50 % in ten-point steps. An offer
at or below the maximum sells immediately. Overshooting by ten or twenty points
allows one retry, after reducing the maximum by ten points. An overshoot of
thirty points, or any second overshoot, ends the visit without a sale. Offers,
purchases and departures have no additional random rolls or Rethink loop.

The engine's ordinary selection window renders four rows; custom-sized text
windows have no selection handler. The menu therefore uses existing translated
Raise / Keep / Lower strings. Raise opens +10/+20/+30 and another Raise entry
for +40/+50; Lower opens −30/−20/−10. Selecting Keep immediately offers list
price. All nine prices remain available with no random offer draw.

Arrival bubbles hint at the budget. Goblimon shows annoyed at +30, happy at
+50, and either face with equal probability at +40. Gotsumon's lower half
(0/+10) shows annoyed 75 % of the time; the upper half (+20/+30) shows happy
75 % of the time. Weedmon and Muchomon show annoyed in the lower half and
happy in the upper half. Each face therefore leaves at least two possible
budgets. A rejection changes the bubble to angry; an offended departure shows
furious. These hints improve results while leaving profitable offers at risk.

Recruitment requires **2560 profit**, the top halfway comment starts at **1280**,
and the 1500-bit consolation tier starts at **1792** (70 % of the goal). These
thresholds match the existing profit plate and the engine's whole 256-bit
`shop_hi` comparisons. Original per-sale profits and 500/1500/2000-bit payouts
remain: Meat earns 0…40, Portable Potty 0…240 and Medicine 0…800 over the nine
prices. Failed shifts still consume eight hours and pay at most 1500; success
pays 2000 once and disables further shifts. Tuskmon's later shop is unchanged.

`tools/monochromon_shop.py` exhausts every undominated fixed species table,
then solves the exact Bellman recurrence over remaining deck, running profit,
species and face. Both searches maximize recruitment probability rather than
expected profit. The retry pair uses only information available after a rejection.
Monte Carlo independently shuffles the deck and draws each visit, with 200,000
shifts per policy and seed 49:

| Policy | Simulated recruit | Exact recruit | Mean profit |
|---|---:|---:|---:|
| List price on both offers | 0.00 % | 0.00 % | 1677 |
| +20 %, then list price for everyone | 16.65 % | 16.67 % | 2144 |
| Best fixed species table, ignoring faces | 49.59 % | 49.67 % | 2542 |
| Best play reading face, remaining deck and total | 74.70 % | 74.67 % | 2738 |

As an information check, the same goal-aware solver without arrival faces reaches
58.13 % exactly (58.06 % across another 200,000 shifts, seed 49), versus 74.67 %
with faces. The benefit therefore persists when both policies track the total
and remaining deck.

The best fixed table is Goblimon +40→+20, Gotsumon +20→−10, Weedmon +10→−10,
and Muchomon +30→0. Goal-aware play uses first offers from −20 through +50,
with different choices by species, face and progress; no one price dominates.
Its customers still leave without buying 1.61 % of the time. Profit shares are
6.62 % Meat, 44.56 % Portable Potty and 48.82 % Medicine, so Meat remains useful.
The Monte Carlo sampling error near 50 % is about ±0.22 percentage points at
95 % confidence. Reproduce with `python3 tools/monochromon_shop.py --shifts 200000`
(NumPy required); boundary and small-deck oracle tests are in
`tools/test_monochromon_shop.py`.

## 7. Related sources

Runtime rules and their numeric data are mapped in [data sources](data-sources.md).
Species records, including imported evolution data, are described in
[species](species.md). Story-owned cup tables and events go through the story
compiler; translated names belong to the text bank. Model and sound formats
have their own authoring tools. Rebuild through derive and the integrated builder
so these sources remain consistent.

## Jijimon's starter quiz

`content/tables/new-game.json` owns the 38-entry starter list (37 expanded results plus Kunemon for NEW DIGIMON off), seven questions' weights and two 45-cell grids.
Six partner Rookie recolours stay evolution-only: SnowAgumon, Psychemon, Muchomon, Tsukaimon, RedOtamamon and VioletElecmon. Vemmon also uses Baby II evolution. Mushroomon, Dokunemon and Syakomon join the expanded quiz; Kunemon stays out because of its special evolution route. Crabmon and Tapirmon replace Flarerizamon and Yanmamon, which are now Champions.
All seven answers count. Each axis chooses its highest score, breaking a tie by the most recent answer that
supported it. If that answer supported both tied choices, the earlier axis wins: battle/fire/ice/nature/air,
vaccine/data/virus, bold/calm/cunning. Mech shares air. There is no random draw.
`tools/starter_quiz.py` enumerates all 2187 paths: minimum 32/2187 (1.4632%), maximum 126/2187 (5.7613%). NEW DIGIMON off remains byte-for-byte identical. Agumon and Gabumon keep their fixed cells. Cells favor attribute, then shared specialty; the scarce fire/virus and air/virus combinations require a few cross-attribute or cross-element choices.

| element / attribute | bold | calm | cunning |
|---|---|---|---|
| battle / vaccine | Salamon | Veemon | Tapirmon |
| battle / data | Patamon | Gabumon | Gotsumon |
| battle / virus | Gazimon | Crabmon | Guilmon |
| fire / vaccine | Agumon | Solarmon | Biyomon |
| fire / data | Renamon | ToyAgumon | Candlemon |
| fire / virus | Guilmon | Goblimon | Kotemon |
| ice / vaccine | Bearmon | Gomamon | Bearmon |
| ice / data | Crabmon | Penguinmon | Otamamon |
| ice / virus | Betamon | Gizamon | Syakomon |
| nature / vaccine | Palmon | Armadillomon | Palmon |
| nature / data | Tentomon | Floramon | Penguinmon |
| nature / virus | Mushroomon | Wormmon | Dokunemon |
| air / vaccine | Tapirmon | Hagurumon | Salamon |
| air / data | Elecmon | Hawkmon | Kokuwamon |
| air / virus | DemiDevimon | Monmon | DemiDevimon |


With NEW DIGIMON off the same answers read `quiz.vanillaCells`, a second 45-cell grid holding only the nine rookies of
the original game, so the partner never starts as a species that option forbids. `modQuizResult` picks the grid once;
the announced name, default partner name and partner all read the same p254. Each of the nine lands between 10.3% and
11.9% of the paths, checked in `tools/starter_quiz.py` (9%..13%).

The self-test rejects missing pool species, invalid cells/weights and frequencies outside 0.5%..6% (9%..13% with NEW DIGIMON off).
`tools/test_starter_quiz.py` also compares the production C result function with the model on every path when
a prepared tree and host compiler are available. This host comparison does not verify emulator dialogue or input.

Every partner Rookie has at least four distinct Champion targets in the final tree. These replace the earlier additions wherever a species changed tier.

| Rookie | Champions |
|---|---|
| Agumon | Greymon, Meramon, Birdramon, Centarumon, Monochromon, Tyrannomon |
| Armadillomon | Ankylomon, Digmon, Submarimon, Tortomon, Dinohyumon |
| Bearmon | Gururumon, Golemon, Ikkakumon, Grizzlymon, Leomon |
| Betamon | Seadramon, Dolphmon, Shellmon, Coelamon |
| Biyomon | Birdramon, Airdramon, Kokatorimon, Unimon, Kabuterimon, Saberdramon |
| Candlemon | Baronmon, Wizardmon, Shadramon, Flarerizamon, Lynxmon |
| Crabmon | Ebidramon, Coelamon, Shellmon, Tylomon, Gesomon |
| DemiDevimon | IceDevimon, Devidramon, Vilemon, BlackGatomon, Devimon |
| Dokunemon | Flymon, Dokugumon, Roachmon, Kurisarimon |
| Elecmon | Leomon, Angemon, Bakemon, Kokatorimon, Thundermon |
| Floramon | MoriShellmon, Woodmon, Kiwimon, Snimon, Vegiemon |
| Gabumon | Centarumon, Monochromon, Drimogemon, Tyrannomon, Ogremon, Garurumon |
| Gazimon | Gururumon, Dinohyumon, Gargoylemon, Minotarumon, Grizzlymon |
| Gizamon | Hyogamon, Gesomon, Tylomon, Octomon, ShellNumemon |
| Goblimon | Fugamon, Tuskmon, Flarerizamon, Raremon, Cyclonemon, Ogremon |
| Gomamon | Submarimon, Ikkakumon, Dolphmon, Gesomon, Tylomon, Octomon |
| Gotsumon | Guardromon, Golemon, Tortomon, Gargoylemon, Minotarumon, Monochromon |
| Guilmon | Flamedramon, Veedramon, Tuskmon, Growlmon |
| Hagurumon | Tankmon, Guardromon, Hookmon, Clockmon |
| Hawkmon | Saberdramon, Aquilamon, Halsemon, Shurimon, Quetzalmon |
| Kokuwamon | Thundermon, Flymon, Clockmon, Guardromon |
| Kotemon | Flamedramon, Apemon, Baronmon, Tuskmon, DarkTyrannomon, Musyamon |
| Kunemon | Bakemon, Kabuterimon, Kuwagamon, Vegiemon, Flymon |
| Monmon | Golemon, Apemon, Hookmon, Raremon, Musyamon, Ninjamon |
| Muchomon | Soulmon, Aquilamon, Sorcermon, Quetzalmon |
| Mushroomon | Woodmon, Kiwimon, Snimon, Vegiemon |
| Otamamon | Geremon, MoriShellmon, Gekomon, Ebidramon |
| Palmon | Kuwagamon, Vegiemon, Ninjamon, Dolphmon, Coelamon, Togemon |
| Patamon | Drimogemon, Tyrannomon, Ogremon, Leomon, Angemon, Unimon |
| Penguinmon | Dolphmon, Shellmon, Garurumon, Frigimon, Mojyamon, Sorcermon |
| Psychemon | Ankylomon, Lighdramon, Minotarumon, Gururumon |
| RedOtamamon | Shadramon, Growlmon, Maildramon, Flarerizamon, Meramon |
| Renamon | Baronmon, Gatomon, Wizardmon, Kyubimon |
| Salamon | Nefertimon, Pegasusmon, Gatomon, BlackGatomon, Piddomon |
| SnowAgumon | Hyogamon, Gururumon, Ikkakumon, Ebidramon, Icemon, Frigimon |
| Solarmon | Guardromon, BomberNanimon, Starmon, Cyclonemon, Lynxmon |
| Syakomon | Ebidramon, Octomon, Coelamon, Icemon, Shellmon |
| Tapirmon | Wizardmon, Bakemon, Apemon, Aquilamon |
| Tentomon | Stingmon, Woodmon, Roachmon, Snimon, Yanmamon, Kabuterimon |
| ToyAgumon | Tankmon, Digmon, Starmon, DarkTyrannomon, Deltamon, ShellNumemon |
| Tsukaimon | Piddomon, Soulmon, Devidramon, Wizardmon, Devimon |
| Veemon | ExVeemon, Flamedramon, Lighdramon, Veedramon, Maildramon |
| Vemmon | Tyrannomon, Hookmon, Tankmon, BomberNanimon |
| VioletElecmon | Aquilamon, Pegasusmon, Lighdramon, Thundermon |
| Wormmon | Stingmon, Shurimon, Dokugumon, Kurisarimon, Snimon, Yanmamon |

The later curated evolution tree is data in `content/tables/evolution-tree.json`, applied by `tools/evo_tree.py`. Canon main lines come first, then family/shared specialty; imported canon Megas follow Perfects. The revised tier table includes Rookie and Champion changes; the quiz keeps 35 entries, all seven questions and its unchanged NEW DIGIMON off grid. Up to five parents and six children fit the existing species rows. Requirements are resolved against sibling competition and disc canonical states, then checked with conservative File City training gains and the natural evolution gains. Timing and lifetime tables are unchanged: Champion 144 h, Mega 120 h; entering Ultimate from another level adds 96 h and entering Mega adds 120 h. Same-level Ultimate evolution adds no lifetime. Original-disc paths are exempt from the shared-specialty rule. The sole mod-route exception is the documented canon Otamamon → Geremon link; original specialties are unchanged.

A record original inside ids 1–62 still uses the resident `EVOLUTION_PATHS` row. The balance layer therefore writes its species file’s padded `from`/`to` lists there, while its other rows retain the existing record-original behavior. This makes WereGarurumon’s three curated parents fit without counting unused reverse entries from the disc placeholder. Native partners 63, 66, 121 and 124 carry cached records for their onward evolution paths; the moved tiers use the frozen peer balance rows.

Placed enemies whose species changed tier retain their previous zone stats and bits through explicit map overrides (45 slots), including the deliberately weaker Gear Savanna Vermilimon. Species defaults now fit their new tier; the area fights retain their established difficulty. General recruited-species tournament brackets include level 6; fixed named cups and story recruit triggers keep their identities.

The extended City roster has 18 Rookies, 34 Champions and 20 Ultimates, worth 143 prosperity points. Only the species in `content/tables/city-residents.json` count, including when loading older saves. The original story’s 50 recruits still total 100 points.

## 6.3 Vending machines

All listed prices are in bits. Item values use the best repeatable conversion exit, including Mojyamon chains.

| Machine | Stock | Rule |
|---|---|---|
| Dragon Eye Lake, screen 8 | Digimushroom **51**; Happy mushroom **1500**; Ice mushroom **1000** | Digimushrooms unlimited; one of each rare mushroom per day, refilled at midnight |

Digimushrooms must cost 51 rather than 20: their shop sale pays 50.
Happy and Ice mushrooms each exit at 500. Deluxe mushrooms are not sold. Original saved triggers 798/799 hold
the two stock bits, excluded from script allocation; the midnight routine clears them with ground pickups.
There is no new resident state. Buying consumes stock only after the item fits and payment succeeds. Saving
and continuing retains stock; rolling back to a save before buying has the same limits as ground pickups.

The former 200-bit surprise machine on Ancient Glacial Region screen 81 (sometimes described as Ancient Dino Region)
now sells unlimited Moldy Meat **26**, Meat **20**, Giant Meat **300**, and Sirloin **1000**. Moldy Meat must rise from
10 to 26 because it sells for 25. The others' best exits are 15, 250 and 750; Giant Meat -> Auto Pilot pays less.

Gear Savanna screen 74 sells Small Recovery **118**, Medium Recovery **318**, MP Floppy **218**, and Medium MP **500**.
Its separate MP Station (use 2) is unchanged. Each successful purchase has the original **9%** chance of one bonus
Double Floppy. The bonus sells for 750, adding **67.5** to every purchase's expected exit: the four totals are
117.5, 317.5, 217.5 and 467.5. The proposed 70/300/200 prices therefore rise to the smallest safe whole-bit prices.
A bonus that does not fit is lost; it never becomes an S.Speed Disk. Normal bag-space failures cost nothing.

Tropical Jungle does have a machine: the MP Station on screen 11. It now hosts the **1000-bit** prize draw; Gear
Savanna retains its MP Station. Each play gives Small/Medium/Large Recovery, MP Floppy/Medium/Large MP, Various
or Omnipotent at **10% each**, or Restore/Offense Disk/Defense Disk/HiSpeed Disk at **5% each**. There is no additional
bonus. All 100 random outcomes pay an item; the expected best conversion exit is **487.5 bits** per play.
Payment happens before the draw, with an explicit no-refund warning: filling the bag to reject common prizes
cannot give free rerolls until a valuable prize fits. Make space before playing; a prize that does not fit is lost.
All four machines use at most three menu rows, with More/Back paging and the game's normal cancel control.
Their prompts, choices and rewards are authored in all eight languages, using each language's item names.

`tools/economy_audit.py` exercises every vending menu purchase and all 100 random rolls from the actual Python
handlers. It values all payouts through the Mojyamon fixed-point trade graph, rejects resale and expected-value
loops (including the Gear Savanna bonus), checks failed purchases and daily stock, and rejects unreviewed script
conversions consuming vending items. The merit shop buys cards and sells items: an item's meritValue is a purchase
cost, not an additional cash-out. Card sales, card-to-merit and card NPC trades remain covered by the card audit.
Regression cases deliberately restore unsafe prices, remove the daily write, inflate a trade-chain exit, lower
the slot price, and introduce selective full-bag refunds; each must fail.

## 6.4 Level changes in both NEW DIGIMON modes

Level changes own complete targets, technique slots and finisher scalars in the species JSON. On values are `evolution.gains`, `techniques` and `finisher`; the explicit `off` block owns the other mode. No balancing value is inferred from player data. `content/tables/species-mode-balance.json` freezes the pre-change measurements and fit bands so changing the affected species cannot silently expand their own limits. All measured finisher rows store MP cost 40. Finisher execution consumes its gauge and skips MP deduction; ordinary techniques charge three times their stored cost.

The measurements include all raisable peers on, and the native raisable pool off. A moved native's missing old off targets are measured from committed original-species JSON, never an executable. Raw finisher ranges expose borrowed-technique outliers: on Rookies 85–172, Champions 100–260, Ultimates 100–260, Megas 170–777; off Rookies 85–101, Champions 100–196, Ultimates 170–260. No Mega is raisable off. The 777-power boss Infinity Cannon is not a normal Mega peer. Ordinary native Rookie finishers give 85–101; ordinary Champions give 130–196, with 100 for filth exceptions. Native Ultimate finishers cluster around 200–260; 196–260 accommodates the lower edge used by imported Ultimates. Imported Mega finishers reuse native ids and range 180–260; moved Megas use their upper 250–260 band rather than inheriting a Champion's 170 or the boss's 777. All measured costs are 40. Elements express the species' actual attack identity, not an ordering by level.

| Fit level | HP / MP targets | Other four targets | Finisher power | Stored cost |
| --- | --- | --- | --- | --- |
| Rookie | 450–1000 | 45–100 | 85–101 | 40 |
| Champion | 1000–2500 | 100–250 | 100–196 | 40 |
| Ultimate | 3000–9000 | 300–900 | 196–260 | 40 |
| Mega | 5000–8000 | 500–800 | 250–260 | 40 |

These are fit envelopes from ordinary peers, not an assertion that all existing species are already balanced. In particular, filth zero targets and borrowed finisher ids remain visible in the frozen raw measurements. The six-stat envelopes are broad enough for existing HP/MP and speed/brains specializations; they exclude missing or zero target rows for a moved partner.

| Species | Mega on targets (HP/MP/Off/Def/Speed/Brains) | Ultimate off targets | Finisher on / off; element |
| --- | --- | --- | --- |
| Phoenixmon | 7000/7000/600/550/750/750 | 6000/6000/400/400/600/600 | 250 / 213; fire |
| HerculesKabuterimon | 7500/5500/750/750/600/600 | 5000/5000/500/500/500/500 | 260 / 232; air |
| MetalEtemon | 7000/7000/800/750/800/700 | 6000/6000/600/600/600/650 | 255 / 222; battle |
| Machinedramon | 8000/7000/800/800/550/650 | 7000/6000/650/650/400/500 | 260 / 250; mech |
| Analogman | 5500/7000/550/500/600/800 | 4000/6000/400/400/450/700 | 250 / 210; mech |
| Jijimon | 6000/6500/600/650/550/800 | 4500/6000/450/500/400/700 | 250 / 220; battle |

Phoenixmon keeps speed/brains and HerculesKabuterimon keeps physical strength. Electro Shocker uses air, the engine's electrical element, rather than its inherited fire tag. Electrical attack typing does not add Air to its inherited Nature/Battle/Fire specialties. MetalEtemon's off targets lose their previous Mega-strength extremes. Machinedramon's partner finisher uses the normal band in both modes while story encounters retain their explicit stats and AI. The scalar adjustment also applies if a Machinedramon enemy casts Infinity Cannon. Analogman and Jijimon retain brains-focused profiles. Their technique identities and animation slots remain unchanged: existing Ultimates can use the same advanced ordinary techniques, while finisher power is resolved per casting species. A shared id never changes another species' global technique row.

| Other moved species | Levels on / off | Off targets (HP/MP/Off/Def/Speed/Brains) | Finisher power on / off; element |
| --- | --- | --- | --- |
| IceLeomon | Ultimate / Champion | 2500/1500/250/200/200/150 | 230 / 170; battle |
| Yanmamon | Champion / Rookie | 750/750/75/75/100/75 | 167 / 92; air |
| Flarerizamon | Champion / Rookie | 1000/750/100/75/75/75 | 155 / 90; fire |
| Vermilimon | Ultimate / Champion | 2500/2000/200/250/100/150 | 225 / 160; fire |
| Icemon | Champion / Rookie | 750/1000/75/100/50/100 | 157 / 94; ice |
| BlueMeramon | Ultimate / Champion | 2000/2500/200/150/150/200 | 220 / 162; ice |
| Meteormon | Ultimate / Rookie | 1000/750/100/100/50/50 | 230 / 90; fire |
| KingSukamon | Ultimate / Champion | 2500/1500/150/250/100/150 | 200 / 150; filth |

Their existing on targets already fit their new levels and remain. Rookie off lists retain their ordinary techniques: the measured native Rookie arsenal already spans power 0–500 (support moves through Patamon’s Buster Dive). Champion peers span 0–586 and Ultimate peers 0–722. The moved species’ ordinary lists fit those bands. Keeping slots populated also preserves the explicit move indices used by existing wild encounters. Champion/Ultimate lists retain their established breadth, which ordinary peers also have. Meteormon and Flarerizamon deliberately share Fireball's animation/effects but have different on power. KingSukamon's stronger Ultimate filth finisher does not alter Sukamon's global Party Time row. The option's existing raisability restrictions still apply to these native enemies made partners.

Whamon uses Ultimate targets 6000/4500/400/550/450/500 and 210-power Ice Blasting Spout on, Champion targets 2500/1500/100/150/100/200 and 150-power Ice Blasting Spout off. Both use stored cost 40. Its existing full Ice arsenal and Nature controls fit the Ultimate role and preserve the original Champion slots off.

Dolphmon takes the former Champion Whamon requirements exactly, including HP 100 (1000 actual HP), brains 100, at most five mistakes, weight 40 and discipline 60, with every other threshold and flag unchanged. This applies on only. Its four parents are Gomamon, Palmon, Betamon and Penguinmon, all sharing Ice; Palmon and Penguinmon had five Champion options after Whamon moved and now have six, while Betamon keeps four and Gomamon six. No suitable replacement has to be removed. `resident_target_order` retains the JSON route order in those three native path rows: Dolphmon occupies Whamon’s former position instead of being appended after every native sibling. With 1500 HP/MP, 150 other stats, weight 40, zero mistakes and the discipline bonus, all three still pick Dolphmon; unchanged formal requirements alone would not preserve those winning states. Gomamon also has a zero-training witness within the same requirement row. Its own Champion targets remain 1750/1400/140/175/135/145. It keeps Ice/Air and 150-power Ice Blasting Spout; Ice Statue and Aurora Freeze complete the former Whamon Ice repertoire in two already-aliased animation slots, while its Air moves replace Whamon's Nature controls. All earlier slots, including the finisher, stay at their indices. NEW DIGIMON off still follows Palmon/Betamon/Penguinmon → Whamon using explicit JSON; Dolphmon remains unavailable in that mode.

Radius/height and animation/effect donors describe the same physical model in both modes, not a level multiplier, so they do not change. Hunger, sleep, weight and discipline retain species identity; evolution time/lifetime use the engine's existing level rules. Runtime battle AI priorities and merit payouts belong to individual map/story encounters. Reviewed DWS authoring defaults in `content/battle/enemy-movesets.json` resolve into explicit map rows; they are separate from partner balance. Encounter stats, bits and recruit difficulty remain fixed in both modes, including intentionally weak Vermilimon encounters. Species wild defaults already fit the curated on identities; they are authoring defaults, not live partner targets. No automatic level-based size or economy multiplier is introduced. The off blocks own every balance value that actually varies with the option.

The natural evolution thresholds retain their curated JSON challenge. In particular, the legacy native Mega routes retain their strict thresholds in both modes; Whamon alone changes its incoming level and therefore has a separate off requirement row. Native enemies whose lower off tier is not raisable gain no new off evolution routes. Neither mode resets trained stats to evolution targets.

The complete runtime change, including menu readers, grows the eight-language `main_BSS_END` by 700 bytes (0x801ce4d4 → 0x801ce790). Active finisher scalars and scratch use 172 bytes; both full move lists stay on disc in owned-data output. Heap alignment costs 704 bytes overall: 186,208 bytes remain. All 320 actual archive setups fit; screen 207 is tightest with 1,488 bytes. Level/target/finisher tests cover both modes and shared-id isolation; source and archive practical tree checks also pass.

## Ordinary technique stat curve

Ordinary attacks retain the original integer formula through ±500 Offense minus
Defense. Beyond +500 they add `power × excess / (excess + 500)`, with truncation
toward zero: 2× at +500, 2.5× at +1000, 2.9× at +5000, always below 3×.
The negative side keeps the original minimum. This applies to partner and enemy
attacks in field/story, tournaments and VS; finishers are unchanged.

The knee/divisor and the new `damage.tailHalfDifference` (500) and
`damage.tailPowerDivisor` (1) belong to `content/tables/battle-formulas.json`.
A missing/nonpositive tail parameter disables the extension. Existing element,
random roll, EASY, counter and block ordering stays intact; VS retains its
separate 9999 hit limit, BTL/STD their 30000 limit. The ordinary increase beyond
the old plateau is bounded below 50%, including for enemies.

The [damage investigation](../investigations/technique-damage.md#bounded-high-stat-extension-2026-11-06)
contains the placement census, explicit partner scenarios, tournament stat
rolls, boss landed-hit/TTK budgets, finisher ratios and risks. Reproduce the
numbers with `python3 tools/battle_audit.py`; add `--charts` in an environment
with matplotlib to export the multiplier chart and boss table.

### Aquatic Rookie technique identities

Gomamon, Gizamon and Crabmon keep Water/Battle (`ice`/`battle` in JSON).
Syakomon gains Plant (`nature`) in specialty slot three, retaining its existing
Water/Battle learning ranks. Their Bukamon parent and Champion routes remain.

| Species | Technique changes |
|---|---|
| Gomamon | Water Blit → Winter Blast; Aqua Magic → Giga Freeze |
| Crabmon | Ice Needle → Tremar (Tremor); Muscle Charge → Counter |
| Gizamon | Aqua Magic → Dynamite Kick (44); keeps Muscle Charge |
| Syakomon | Adds Poison Powder and Charm Perfume after Blasting Spout |

Each replacement stays at its old animation index. Syakomon's additions use
slots 0x36/0x37; its finisher remains at 0x35. The new ordinary lists fit the
16-slot record. Technique numbers and global balance rows remain unchanged.
The imports registry aliases Dynamite Kick to Gizamon's Sonic Jab, Counter
to Crabmon's Sonic Jab, and both Plant moves to Syakomon's Winter Blast.
These choices use attack/casting clips in the reassigned slots. Scripted
2 MB battles confirmed positive HP loss from every new move, including a
reactive Counter against a melee opponent. Fresh fights isolate the Plant
attacks from lingering status effects; all tested fights return to the field.
Status-screen inspection confirms Water/Battle and Syakomon's third Plant icon. All four final
models have finite clips for every listed technique and fit the unchanged
100352-byte resident and 8192-byte streamed-animation buffers. Measured resident
sizes are Gomamon 91078, Gizamon 77730, Syakomon 30038 and Crabmon 73106 bytes;
the largest sector-aligned cold read is 6144 bytes (Gizamon).

#### Buster Dive decision

The comparison uses the owned technique JSON and `tools/battle_audit.py`'s
ordinary damage formula: NORMAL, neutral element sum 30, equal offense and
defense, 100% damage roll, no guard, buffs or status. The accuracy-weighted column
is a base-accuracy proxy, not measured DPS or an assertion that every
collision has that hit chance; speed and defender state affect the hit roll.
Positioning, cooldown and animation length also matter. Actual MP consumption is three times `mpCost`.

| Technique | Power | Base accuracy | Actual MP | Damage × accuracy | Weighted damage / MP |
|---|---:|---:|---:|---:|---:|
| Buster Dive | 500 | 80 | 258 | 400.00 | 1.550 |
| Dynamite Kick (44) | 193 | 62 | 99 | 119.66 | 1.209 |
| Counter | 285 | 100 | 165 | 285.00 | 1.727 |
| Tremar | 178 | 60 | 168 | 106.80 | 0.636 |
| Giga Freeze | 264 | 65 | 120 | 171.60 | 1.430 |
| Winter Blast | 120 | 90 | 165 | 108.00 | 0.655 |
| Poison Powder | 117 | 77 | 171 | 90.09 | 0.527 |
| Charm Perfume | 180 | 75 | 210 | 135.00 | 0.643 |

Counter's proxy uses its base power. The actual damage calculation reduces
the target's defense to 30%: at offense/defense 100/100, a neutral 100%-roll
Counter deals 324 rather than 285. It requires a reactive hit. Area techniques can
hit multiple enemies; poison and confusion have additional value beyond these
single-target numbers.

Buster Dive would raise Gizamon's ordinary peak from Water Blit's 211 to 500,
2.37× the landed damage. Its weighted damage is 3.34× Dynamite Kick's with
1.28× its MP efficiency, plus ranged dash reach. A neutral 500-HP opponent at
equal defense falls in one landed Buster Dive versus three Dynamite Kicks
at the reference roll. With both speeds 100 and a stationary, nonattacking
defender, the actual hit chances are 77% and 60%, giving 385 versus 115.8
weighted damage (3.32×). Attacking or stunned defenders are automatically hit;
these exceptions do not reduce the 500-to-193 landed-damage gap.
Although Patamon, Gotsumon and Tsukaimon already learn Buster Dive, expanding
that outlier to this Water/Battle group would overwhelm the intended modest
melee distinction. Gizamon therefore uses the lower-power fallback and keeps
Muscle Charge. The existing Buster Dive native-track repair remains necessary
for users of that move; Gizamon needs no dash recipe.

#### Learning, specialties and evolution

Battle observation chances use the matching specialty's column; the move must
also appear in the species list. New-move chances are Winter Blast 20%, Giga
Freeze 17% (Gomamon's primary Water), Tremar 8%, Counter 11% (Crabmon's second
Battle), Dynamite Kick 17% (Gizamon's second Battle), Poison Powder 14% and Charm
Perfume 9% (Syakomon's third Plant). Buster Dive would have used 7%.

Brains training also filters by the species list. The new candidates' table
weights are Winter Blast 18, Giga Freeze 15, Tremar 6, Counter 8, Dynamite Kick
13 and Poison Powder 7. Charm Perfume has third-specialty training weight zero,
so Syakomon learns it through battle observation rather than brains training. These are candidate weights, not independent chances
per training session: the training routine chooses among the earliest unlearned
candidates for each specialty. Evolution still teaches a weak primary Water
move; adding Plant does not grant a free Plant attack.

The status renderer supports all three specialty slots and the existing Plant
icon (element 3). Plant replaces Syakomon's formerly neutral third defensive
factor: incoming sums for Fire/Battle/Air/Plant/Water/Mech/Filth change from
22/30/40/40/30/22/30 to 32/30/32/40/22/32/30. Thus Fire and Mech become more
effective while Air and Water become less effective.

Evolution topology checks require a shared specialty; every affected incoming
and outgoing edge retains one. Syakomon additionally shares Plant with Coelamon.
Runtime stat, weight, care and bonus requirements are explicit rows, not
recomputed from specialties. Known-technique bonuses can count the two added
moves normally. No requirements or route order change.

## Enemy encounter move variety (2026-11-06)

Enemy difficulty belongs to encounter stats and move selections, independently
of the partner's learnable list. A species can have many techniques while a
story placement uses only its first three animation slots. That old DWS default
gave IceDevimon Sonic Jab, Counter and War Cry: one ordinary damaging technique
after support choices become unavailable. Counter has damage power but
`BTL_isMoveUsable` excludes it from the selection lottery; it is reactive.
IceLeomon (the Panjyamon model) got
only physical attacks. Current story Devimon, species 130, has Megaton Punch
rather than Sonic Jab in slot 46; its first three slots nevertheless repeat the
same attack/support/support pattern. The native Mt. Infinity encounter also
has Megalo Spark in its fourth slot at weight 10, so it already has two
proactive attacks rather than only one. The reported interruption pattern is
credible, but those names must not be used to infer the current slot contents.

`content/battle/enemy-movesets.json` owns reviewed DWS defaults. Techniques are
named and resolved to each species' existing animation slots at build time.
The defaults replace inherited template priorities as well as move selections.
Existing native encounters keep explicit `moves`/`prios` in `content/maps`;
matching reviewed rows use the same selections. No species technique list,
animation, global technique power/status chance, encounter stats, bits or drop
is changed by this pass.

| Species | Attacks | Weights, in order; idle last |
| --- | --- | --- |
| Devimon, species 6 | Megaton Punch, Spinning Shot, Giga Freeze, idle | 40 / 25 / 15 / 20 |
| Story Devimon, species 130 | Megaton Punch, Giga Freeze, Megalo Spark, idle | 40 / 25 / 15 / 20 |
| IceDevimon | Giga Freeze, Ice Statue, Megaton Punch, idle | 40 / 15 / 25 / 20 |
| IceLeomon | Megaton Punch, Buster Dive, Winter Blast, Dynamite Kick (44) | 30 / 20 / 30 / 20 |
| Sorcermon | Giga Freeze, Ice Statue, Wind Cutter, idle | 35 / 15 / 30 / 20 |
| ShimaUnimon | Dynamite Kick (48), Megalo Spark, Electric Cloud, idle | 30 / 30 / 30 / 10 |
| NiseDrimogemon | Dynamite Kick (44), Buster Dive, Tremar, idle | 35 / 25 / 30 / 10 |
| Tekkamon | Megaton Punch, Buster Dive, Pulse Laser, idle | 30 / 25 / 35 / 10 |
| DarkLizardmon | Magma Bomb, Heat Laser, Red Inferno, idle | 35 / 30 / 25 / 10 |
| Gururumon | Megaton Punch, Giga Freeze, Winter Blast, idle | 35 / 25 / 30 / 10 |
| Golemon | Ice Needle, Ice Statue, Winter Blast, idle | 35 / 15 / 30 / 20 |
| WereGarurumon | Megaton Punch, Magma Bomb, Giga Freeze, idle | 35 / 30 / 25 / 10 |
| SkullSatamon | Megaton Punch, Buster Dive, Prominence Beam, idle | 30 / 30 / 30 / 10 |
| Gargoylemon | Megaton Punch, Tremar, Insect Plague, idle | 30 / 30 / 30 / 10 |

Weights are lottery weights, not a rotation or a guaranteed maximum streak.
They are base weights: the existing AI adds a group-move bonus while another
enemy lives, suppresses unaffordable/unusable moves and favors available buffs
early in a fight. The reviewed defaults avoid support-only slots.
An empty slot with positive weight is intentional: the existing AI takes
`cooldown.noTargetMs` (4000 ms) before trying again. Completed attacks retain
`cooldown.afterAttackMs` (2000 ms), plus their existing animation, charge and
global-effect waits. Removing Sonic Jab from these selections eliminates the
weak melee fallback instead of changing it for partners everywhere. Ice Statue
has only 15% base weight in the IceDevimon/Sorcermon/Golemon sets because its
38% stun chance could otherwise replace interruption with repeated long stuns.
Devimon uses lower-stun alternatives: Spinning Shot has no status, Giga Freeze
has a 10% stun chance, and story Devimon's Megalo Spark has only 15% base weight.
IceLeomon uses Winter Blast (15% stun), whose existing global-effect lock
prevents another globally locked move from starting for 5500 ms. An initial
Ice Statue-heavy trial produced 23.1- and 30.35-second action gaps against
IceLeomon and story Devimon; those measurements prompted these selections.
IceLeomon keeps three physical attacks available with NEW DIGIMON off, when
its ice slots are disabled; its fourth slot therefore carries an attack rather
than an idle choice.

`python3 tools/moveset_audit.py --out build/moveset-audit` inventories every
owned native placement. Add `--maps build/NAME-maps/screens --maps build/NAME/story-maps --maps build/NAME/balance-maps/maps` after a full build to
replace native rows with final map data and include generated story encounters.
It reports distinct weighted ordinary damaging choices and weak melee
candidates (power 1–100, melee, weight at least 30). These are review flags,
not measured animation speed or encounter frequency. Zero chase range includes
both story fights and town actors and is listed separately. Early two-move
enemies, support specialists, babies and town residents are not automatically
rebalanced by a count threshold.
For example, the kennel's caged Bearmon has the same first-three-slot pattern
but never fights: its release/recruit scene remains unchanged. The neighboring
Overdell Pass roster does fight, so SkullSatamon, Gargoylemon and WereGarurumon
receive three proactive specialty attacks rather than two attacks plus
Counter or a buff.

The generated-map census contains 1,149 placements, including dormant actors.
The pass edits 42 native rows in 21 maps and supplies 14 DWS species defaults.
Comparing all 278 canonical map files in the two images finds 91 changed
runtime enemy rows across 43 maps; only the four move slots and four priorities
differ. Ninety rows match the reviewed profiles; the noncombat caged Bearmon
also inherits changed template priorities. Every other enemy field is identical.
The final source/map census is:

| Group | Rows | Narrow before → after | Weak melee before → after |
| --- | --- | --- | --- |
| Nonzero chase range | 709 | 278 → 219 | 226 → 197 |
| Zero chase range | 440 | 310 → 302 | 102 → 100 |

These categories overlap. Even a
nonzero chase range can survive on a noncombat template, so these totals must
not be read as numbers of broken fights.

Remaining review candidates include Goblimon, Shamamon, Psychemon, Tsukaimon,
SnowGoblimon and SnowAgumon sets with Sonic Jab weighted 30–45; early
Agumon/ModokiBetamon two-attack sets; and single-Megaton-Punch Gotsumon sets.
The last group has a strong ordinary attack rather than the reported weak-jab
pattern. Native resident variants also produce many zero/one-attack flags,
including Shellmon and Kunemon town placements. Those need scene classification
before any encounter change. The reproducible census retains every flagged
row for follow-up; this pass changes the reviewed specialty profiles rather
than automatically raising the power of the entire early-game roster.

The independent economy and ordinary-damage audits remain
`tools/economy_audit.py` and `tools/battle_audit.py`; moveset counts do not
substitute for either audit or for live battle measurements.

Reproduce the 2 MB battle measurements with
`python3 tools/dev/playtest/seam_movesets.py build/NAME.cue --exe build/NAME/exe/SLUS_010.32 --out build/NAME-battles`.
The fixture is Agumon, NORMAL, NEW DIGIMON on, 800 Offense, 500 Defense,
350 Speed, 700 Brains, 9999 HP/MP and Red Inferno under Your Call. It uses one
named opponent per fight; enemy stats, RNG, hit results and outcomes are not
injected. This isolates the move selection change; it does not reproduce
every partner, group fight or player save.
IceDevimon starts 200 units from the partner to exercise its melee loop; the
other fixtures use an offset of 300/100 units. The camera pans before staging,
and battle entry is armed while paused so field following cannot move the
partner away between staging and the start.
Add `--neutral --cases iceleomon,icedevimon,devimon` for the physical comparison: Leomon
with Megaton Punch, the same stats and no forced hits. The flag chooses this
fixture; it does not force an elemental multiplier of 1.0.

Matched 2 MB measurements (one completed unforced trial per cell):

| Encounter / partner | Outcome and battle seconds, before → after | HP lost | Partner starts / hits | Longest start gap (s) |
| --- | --- | --- | --- | --- |
| IceLeomon / Agumon / Red Inferno | win 190.35 → win 175.05 | 3826 → 4717 | 33/23 → 33/23 | 20.45 → 10.85 |
| IceDevimon / Agumon / Red Inferno | win 113.25 → win 101.65 | 821 → 2064 | 17/14 → 15/14 | 13.65 → 15.75 |
| Sorcermon / Agumon / Red Inferno | KO 150.90 → win 129.25 | 9999 → 3656 | 22/13 → 26/16 | 14.80 → 9.95 |
| IceLeomon / Leomon / Megaton Punch | win 74.40 → win 76.40 | 2229 → 2205 | 11/10 → 12/10 | 12.00 → 17.15 |
| IceDevimon / Leomon / Megaton Punch | win 270.20 → win 33.90 | 5153 → 403 | 49/7 → 8/8 | 13.65 → 4.60 |
| Story Devimon / Leomon / Megaton Punch | KO 117.95 → win 172.55 | 9999 → 7904 | 17/15 → 22/19 | 14.55 → 17.50 |

KO means the partner lost; otherwise the time is time-to-win. A start is the
ordinary attack execution hook after animation/charge waits; hits are damage
calculation events against the selected enemy. Misses and interruptions can
both prevent a hit. The longest gap is between consecutive starts, excluding
the wait before the first and after the last. Staged and entered positions are
identical in every trial and match between images. No partner self-hit was
recorded.

IceDevimon's baseline landed only Sonic Jab: 19 hits against Agumon and 69
against Leomon. In the final ranged trial it landed three Giga Freezes and one
Ice Statue, causing more damage with fewer hits. Leomon completed eight of
eight attacks instead of seven of 49; that close-melee fixture is substantially
easier after removing the jab loop. Keep encounter stats fixed and accept
this shorter close-melee fight as a consequence of removing interruption
pressure. The ranged Seam
fixtures still cost 2,064–4,717 HP, and story Devimon costs 7,904 HP. IceLeomon's
physical comparison stays close in time and HP loss. Sorcermon's reduced Ice
Statue weighting makes the previous knockout winnable. Thus challenge remains,
but it is not equal in every matchup and action gaps do not universally shrink.

These trials do not establish a maximum interruption streak or balance for
every player save. Group fights, multiple RNG seeds, original hardware and
runtime NEW DIGIMON off remain unmeasured. The off-mode move availability is
statically checked. Keep the raw starts, damage traces, samples, RAM/heap
checks and outcomes in the harness output when comparing later changes.

Both images have the same boot executable SHA-256 after disc relayout:
`aa09cfa6b7bdab95e1e2945daf4903a0895918a6f621fe2c80fabe89e39ac269`.
The native executable used for symbols/checkpoint identity is also unchanged
(`83c4340c4e8508c5d7e6a22bab23538db23f107444adabb29db4297abab9b8ba`).
`main_BSS_END` stays at `0x801cdf84`, leaving 188,272 bytes of heap.
The final archive-based heap check passes all 320 screen setups; the tightest
setup is screen 207 at 184,712 bytes, with 3,552 bytes spare. The runtime
fixtures reject expanded RAM and read exactly 2,097,152 bytes. Battle-entry
free/largest blocks are 13,392 bytes for daytime Seam, 60,824 for nighttime
IceDevimon and 129,008 for Mt. Infinity Devimon. Move selection and weights
change map data only; this pass adds no C code or runtime allocation.
