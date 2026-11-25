# Unique finishers for the imported species

Every imported species gets its own finisher: its own name, behaviour, element, status and
look, taken from its signature attack in the game it comes from. The battle still uses the
finisher id the species has today (58..112), so saves, menus and the technique tables keep
working. Only the numbers the battle reads and the name the player sees change, per species.

- Data: `content/finishers/imports.json`, one entry per imported species (179 entries: the 178
  imports plus MetalGreymonVaccine, the recoloured native that borrowed MetalGreymon's finisher).
- Check: `python3 -m tools.finisher_balance` (table and problems, exit 1 on a problem) and
  `python3 -m unittest tools.test_finisher_balance` (in `tools/selftest.sh`).
- Effects: the visual effect of each finisher is the species JSON `own_effect`
  ([the signature effects notes](signature-effects.md)): all 179 are authored, written for this game with the kit in
  `tools/technique_effects`. This file decides what the finisher does.

Status: built. `tools/species.py` writes every entry into its species record and the names into
`DIGI.DAT`; patch `Give-each-species-its-own-finisher-numbers-and-name.patch` reads them in
battle and in the menus. Every design question is decided
(`docs/proposals/unique-finishers.md`) and the designed numbers play: `"neutral": false`.

### The neutral switch

`"neutral"` at the top of `content/finishers/imports.json` is `false`: the build writes the
designed numbers of this file (power, element, status, range, iframes, accuracy, distance and
the needs-target flag) and area finishers hit every enemy. Setting it to `true` (the default
when the key is missing) is the one-line revert: the build then writes the technique and the
name reference but not the numbers, the record's present flag stays clear and every import
fights with the numbers of the DW1 finisher it replaces (`replaces`). Its own name and its own
effect (`own_effect`) still apply, as single-target chunks.

## Rules the data follows

1. **Same behaviour as the source.** Kind (shot, beam, breath, dash, melee, area...), target,
   hit pattern and status come from the source attack. Digimon World 2 entries use the decoded
   skill record (element nibble, target, cast clip, status flags). Digital Card Battle attacks
   always hit the one opponent, so they are single target. Digimon World 2003 attacks are not
   decoded yet; their kind follows the canon attack.
2. **DW1 power, not source power.** Power sits inside the DW1 finisher band of the species'
   level. Inside the band the entry's place follows its source power's rank among same-game,
   same-level signatures (middle of the band when there is no source number).
3. **Element is one of the species' specialties.** The source element is used when it is one
   of them; otherwise the closest specialty (electric and sound are Air in DW1).
4. **Area costs power.** An attack that hits every enemy takes the band floor.
5. **Status costs power.** An entry with a status is capped at the band middle, chance at most
   20 %. Statuses come only from a decoded source status or a name that clearly implies one.
6. **Support moves ship as attacks.** The engine applies buffs by technique id, and the heap
   has no room for code that reads them from data, so a source support move becomes a damaging
   attack of the species' element. The check still accepts a `buff` entry (power 0, buff total
   at most 70 %, heal at most 25 %, with a `fallback`), but none ships.
7. **Unique names.** No name repeats, and no name equals a DW1 technique name or a name players
   see in `text/ours/names.json` (`main.MOVE_NAMES.*`). Every English name fits the 136-pixel
   finisher field in all three fonts (widest: Transcendent Sword, 109 px).
8. **No economy effect.** A finisher deals damage and may apply a status. None gives bits,
   items or merit, so there is no repeatable bits-for-bits loop (`docs/mods/balance.md`, economy
   rule; `tools/economy_audit.py` is not affected).

### Bands

From `content/tables/species-mode-balance.json` (`bands.*.finisher_power`):

| Level | Finisher power | Offense used by the check |
|---|---|---|
| Rookie | 85..101 | 72.5 |
| Champion | 130..196 (100 is only the filth Party Time) | 175 |
| Ultimate | 196..260 | 600 |
| Mega | 250..260 | 650 |

The Champion-level finishers the Rookie imports carried until now (decision of 2026-11-03,
"until an effect fits the model") are replaced by Rookie-band power, because every entry here
comes with its own effect. Decided on 2026-11-15.

## The check: expected damage

`tools/finisher_balance.py` scores every finisher with the battle formula
(`docs/reference/combat.md`): `(Off + P) * m / 30`, where Off is the middle of the level's
offense band and `m` is the type factor (`content/tables/type-factors.json`) averaged over every
species' three specialties. A status multiplies by `1 + chance * weight` (poison and confusion
0.15, stun and flatten 0.25); an area hit counts 1.3 times. The score of each import must lie
inside the score range of the same-level native finishers that sit inside the band, with 10 %
slack. It also checks the band, the area floor, the status cap, the buff cap, the element,
range and distance per kind, that DW1 itself has a technique with the same range, distance and
iframes (and that only ranges whose DW1 techniques need a target set the target flag), and the names.

### Imports against same-level natives

Expected damage (min / median / max). Natives with mode scalars use their scalar power.

| Level | Natives in band | Native power | Native score | Imports | Import power | Import score |
|---|---|---|---|---|---|---|
| Rookie | 22 | 85..101 | 159 / 172 / 193 | 26 | 86..100 | 161 / 170 / 184 |
| Champion | 51 | 130..196 | 324 / 339 / 372 | 58 | 130..195 | 313 / 357 / 406 |
| Ultimate | 31 | 200..260 | 808 / 884 / 1061 | 47 | 196..258 | 814 / 899 / 1153 |
| Mega | 6 | 250..260 | 885 / 982 / 1197 | 48 | 250..260 | 889 / 981 / 1274 |

The import maxima above the native maxima are Air and Mech single-target finishers: Air hits
three of the seven specialties hard, and the natives have few Air finishers at those levels.
They stay within the 10 % slack.

Natives outside their band (left as they are, listed for reference): Goblimon and Gotsumon
Pummel Whack 170 and Psychemon Drill Spin 150 (Rookie); Guardromon Deadly Bomb 260 and the
Party Time line at 100 (Champion); MasterTyrannomon Blaze Blast 174, Myotismon Death Claw 180
and ShogunGekomon Blasting Spout 150 (Ultimate).

## Entry format

```json
{
 "species": 264, "species_name": "Raremon", "level": "champion",
 "name": "Buffalo Breath",
 "source": {"game": "dw2", "basis": "disc", "name": "Buffalo Breath", "power": 45,
            "dw2_element": "darkness", "dw2_target": "one enemy",
            "description": "Confuses foe in Counter", "cast_clip": "F0",
            "status_flags": "0x400", "voice_xa": [3230, 3]},
 "replaces": {"id": 62, "name": "Death Claw"},
 "behavior": {"kind": "breath", "target": "one", "hits": 1, "look": "A foul green breath.",
              "dash": false, "clip": "F0"},
 "effect": {"files": ["EFFECT/EFFEWA/MEWA0300.BIN", "..."], "file_ids": [967, 929, 970, 932],
            "logic": "...", "status": "authored", "template": {"id": 62, "name": "Death Claw"}},
 "move": {"power": 163, "element": "filth", "range": 2, "distance": 90000, "accuracy": 100,
          "status": 2, "statusChance": 20, "iframes": 15, "flags": ["T"], "mpCost": 40},
 "notes": "Source confuses."
}
```

| Field | Meaning |
|---|---|
| `species`, `species_name`, `level` | The species and its level (must match `content/species`). |
| `name` | The finisher name players see. Goes to the text banks as `species.<id>.finisher`. |
| `source.game` | `dcb` (Digital Card Battle), `dw2`, `dw3` (Digimon World 2003), `dw1` (recolour). |
| `source.basis` | `disc`: decoded from the source disc. `canon`: the species' attack in the series, not on these discs. `proposed`: no canon attack found; name and behaviour proposed. |
| `source.*` | The raw source data: name as the disc spells it, power, and for DW2 the decoded element, target, description, cast clip, status flags and voice. |
| `replaces` | The finisher id the species uses today. It stays the id in saves and menus. |
| `behavior.kind` | `shot`, `thrown`, `rain` (several projectiles from above or in a volley), `breath`, `beam`, `dash` (the attacker travels), `melee`, `area` (every enemy), `buff`. |
| `behavior.target` | `one`, `all`, `random` (Blind Attack, like Nightmare Syndromer), `self`. |
| `behavior.hits` | Hits the effect shows. Damage is applied once, as for every DW1 finisher. |
| `behavior.look` | What the effect shows, in words, for whoever builds it. |
| `behavior.clip` | The attack clip: DW2 cast slot (`F0`, `G0`, `H0`) or `by eye`. |
| `effect.status` | `authored` on every entry: the effect is written here from nothing (`effect.logic` names the file), its behaviour its own, and `effect.template` is the DW1 finisher it replaces. The older values `source` (the source effect files known), `source-undecoded` and `dw1-template` are no longer used by any entry. |
| `effect.files`, `file_ids`, `file`, `shared_by_cards` | Where the source effect lives; for DCB, how many other cards share the pack. |
| `move` | What the battle reads, field by field as in `content/techniques/*.json`. `range` 1 melee, 2 ranged (including dashes), 3 area, 4 buff. `distance` is squared. `flags` `T` = needs a target. Accuracy is always 100 and the stored cost 40: finishers use the gauge. |
| `buff`, `fallback` | Accepted by the check for a support move; no shipped entry has them (see below). |
| `notes` | Spelling fixes, status proxies, open questions. |

Kind decides range, distance and iframes. Every combination is one DW1's own finishers use
(Deadly Bomb, Genocide Attack, Mega Flame, Drill Spin, Death Claw, Dark Network):

| Kind | Range | Distance (squared) | Iframes |
|---|---|---|---|
| shot, thrown | 2 | 360000 (600) | 1 |
| rain | 2 | 360000 | 1 |
| breath | 2 | 90000 (300, as Mega Flame) | 15 |
| beam | 2 | 640000 (800) | 1 |
| dash | 2 | 160000 (400) | 1 |
| melee | 1 | 0 | 1 |
| area | 3 | 160000 (as Dark Network) | 1 |
| buff | 4 | 0 | 1 |

## Where the numbers come from (179 entries)

| | Count |
|---|---|
| Source decoded from the disc | 145 (79 DCB, 43 DW2, 23 DW2003) |
| Canon attack, not on the discs | 17 |
| Proposed (no canon attack found) | 17 |
| Effect written here (`authored`) | 179 |

Kinds: 45 shot, 36 beam, 31 dash, 22 area, 14 thrown, 13 rain, 12 melee, 6 breath.

The 37 species without a distinct source signature (DW2003 enemy-only species, plus
BlackGatomon, whose card shares Lightning Paw with Gatomon) have `basis` `canon` or `proposed`.
Lightning Paw stays with Gatomon; BlackGatomon takes its own card's third attack, Cat's Eyes,
with no status (the card has none).

### Support moves

These three ship the attack in the last column for good.

| Species | Source | Buff it would be | Ships |
|---|---|---|---|
| Baihumon | Kongou: unbeatable during its own turn | Defense +50 %, Offense +10 % | dash, Battle, 255 |
| Mushroomon | Fungus Cruncher: its attacks poison | Offense +10 %, Speed +10 %, its hits poison at 15 % | spore shot, Nature, 93, poison 20 % |
| Tinmon | Recovery Power: cures confusion, poison, stun | Cures them, heals 20 % of max HP, Defense +15 % | beam, Ice, 228 |

DW1 applies buffs by technique id (`BTL_applyBuffMove` switches on the id), so a buff
finisher would need engine code that reads the buff numbers from the record, and the main
executable has no heap to spare for it.

## Data model: per-species override on the existing id

Chosen with the effects work (option B): no new technique ids. Finisher ids are 58..112 and
every slot is spoken for (110 Glacial Blast is an empty entry, 107 and 108 are a duplicate
Party Time, but taking them would change what those ids mean in saves and tables). The
override lives in the species record in `DIGI.DAT` (`tools/species.py`, 0x200 bytes):

| Offset | Type | Field |
|---|---|---|
| 0x1CF | u8 | `own_effect` technique (effects work) |
| 0x1D0 | i16 | `own_effect` chunk (effects work) |
| 0x1D2 | u8 | the finisher id it overrides (`replaces.id`, also written when neutral) |
| 0x1D3 | u8 | flags: bit0 present (the numbers apply), bit1 spreads (below) |
| 0x1D4 | `Move` | the whole 16-byte `Move` the battle reads (`dw/move.h`) |
| 0x1E4 | u16 | name reference (1-based entry of this file, 0 none) |
| 0x1E6 | u16 | byte of this name in its sector |
| 0x1E8 | u32 | sector of this name in the first language |
| 0x1EC | u8 | name sectors per language |
| 0x1ED | u8 | hits (shown only) |

The `Move` is the native technique's (`content/techniques`, the source of `MOVE_DATA`) with this
file's power, element (`special`: the index in `fire, battle, air, nature, ice, mech, filth`),
status, status chance, range, iframes, accuracy and distance on top, and the needs-target flag
in `unk3` bit 0. Its cost and the other bytes stay native. The build stops if a number is out of
range or if `replaces.id` is not the finisher in the species' `techniques`. A `buff` entry would
ship its `fallback.move`. 0x1EE..0x1FF stays free.

### Reading it in battle

`modSpeciesMove(type, move)` (patch `Apply-species-mode-moves-and-finisher-scalars.patch`)
already returns a per-species copy of a move and is called by the MP check, the charge
requirement, the move setup cost, the menus, the STD damage and charge paths and VS. For a
finisher id of an imported species with the present flag, it copies the override over that
copy. The natives' mode scalars stay as they are and take precedence for natives (imports have
no scalar rows: they stop at `NUM_ORIGINAL_DIGIMON`).

Places in `battle_main.c` that still read `MOVE_DATA` directly and must go through
`modSpeciesMove` for the override to show everywhere: AI launch distance; hit chance
(accuracy); damage power and element (the patch already moves these); the particle effect
call (element, iframes); the invulnerability timer (iframes); the melee counter and block
checks (range 1); the buff path (range 4); the needs-target and lock flags; the speed buffer;
the AI scores; and `BTL_applyMoveStatus` (status, chance).

Records are read through `getSpeciesRecord`, a 16-slot cache that can miss and read a CD
sector. A fighter's record is already cached from its battle load on and is not evicted while
the species is in use, so `modSpeciesMove` answers from the cached record itself
(`modFinisherRecord`: the record's own `Move`, no copy and no table in the executable). All of
the sites above read it, `BTL_applyMoveStatus` included (the attacker is passed through a
static beside it). A native without a record original answers NULL at once, with no read.

**Area finishers.** DW1 range 3 is not an area on its own: the native area finishers hit
everything inside their effect's radius. An import whose designed range is 3 on a finisher
whose DW1 range is not gets the spreads flag from the build and spreads each landing hit
to every other living fighter of the victim's side (`BTL_spreadAreaHit`, battle overlay only),
once per hit and never back to the caster's side. A species whose finisher plays its own
effect chunk (SkullMeramon's Metal Fireball on Mega Flame) gets no spreads flag: the chunk picks
its own targets, and with the designed numbers the effects step converts it with `area` (`finisher_area_chunks` in `tools/derive/steps/effects.py`),
so Metal Fireball's chunk 122 hits every enemy itself. With `"neutral": true` nothing spreads
and no chunk is made an area one.

### Names and translations

The name is a text-bank entry, `species.<id>.finisher`, in `text/ours/names.json` and every
`text/<language>/names.json` (all 179, in every language). `tools/species.py` encodes each
one exactly as the executable compiler encodes `MOVE_NAMES` in that language (the language's
font codes, Shift-JIS otherwise; at most 27 bytes) and appends them to `DIGI.DAT`, 64 names of
32 bytes per sector, one block per language in `MOD_LANG` order. The engine keeps one name, the
partner's in the current language (28 bytes): `modMoveName(species, move)` reads it when the
partner or the language changes (outside battle, or at battle load) and otherwise returns
`MOVE_NAMES[move]`. Every place that shows a finisher name uses it: the status page, the
battle command bar and its shout, STD and VS. Script text that names a technique (`{tech}`)
keeps the shared `MOVE_NAMES` entry, to keep the executable small.
`python3 -m tools.localize.ui` measures the names against the 136-pixel finisher field.

### NEW DIGIMON off

With NEW DIGIMON off an imported species shows as its `vanilla_as` native, which has no
override: its finisher is the native one. Nothing to do.

### What the engine change touches

| Area | Effect |
|---|---|
| Saves | None. The finisher keeps its id and its slot in the move list. |
| Menus | Name and power of a finisher come from the species (status, evolution and Brains screens). |
| Origin and effect tables (`effects_like`) | Unchanged. |
| Species record | 0x1D2..0x1E9 written by `tools/species.py` from this file; the names after the records in `DIGI.DAT` (27 sectors). |
| Main executable | About 340 bytes: `modFinisherRecord` (96), `modMoveName` (216) with its 28-byte name buffer, 40 more in `modSpeciesMove`, fewer in the status page. Measured with the whole batch on origin/main 4b8a2e15 in the nine-language dev build: `main_BSS_END` 0x801ce0a0 to 0x801ce248, heap 187,984 to 187,568 B, no screen short (tightest 217, 2,568 B to spare). The battle code (spread, Move routing) lives in the BTL, STD and VS overlays. |
| Free ids | None needed. |

## How it plugs into the effects and Buster Dive

- The effect of a finisher is the species JSON `own_effect` on `replaces.id`, for example
  SkullMeramon's Metal Fireball: `own_effect` chunk 122 on Mega Flame (63); Raremon's Buffalo
  Breath on Death Claw (62). This file adds what the move does: Metal Fireball hits every enemy
  (DW2 target "all enemies"), so it becomes an area finisher at the Ultimate floor; Buffalo
  Breath turns Death Claw's melee into a 300-unit breath with confusion.
- Dash finishers (36 entries, `behavior.dash`) need the attacker to travel. The Buster Dive
  pass (`tools/models/buster_dive.py`, `docs/mods/buster-dive.md`) already copies a native dash
  root track into a technique clip when the clip's own travel is under 500. The same pass can
  run on the finisher clip (slot 0x2E plus the finisher's index) with a reviewed recipe key
  such as `finisher_clip` in the imports registry, under the same resident (100352 bytes) and
  streamed (8192 bytes) buffer checks.
- For DW2 entries, `behavior.clip` names the source attack clip (cast 0, 1, 2 = F0, G0, H0).

## Natives that share a finisher

Left as they are. Fifteen of them already differ in power through mode scalars, and changing a
native finisher would change the original game.

| Id | Finisher | Natives |
|---|---|---|
| 58 | Blaze Blast | MasterTyrannomon, Tyrannomon |
| 59 | Pepper Breath | Agumon, ClearAgumon, ToyAgumon |
| 60 | Lovely Attack | Monzaemon, WaruMonzaemon |
| 61 | Fireball | Flarerizamon, Meramon, Meteormon |
| 62 | Death Claw | Devimon, IceDevimon, Myotismon |
| 66 | Electric Shock | Betamon, ModokiBetamon |
| 71 | Boom Bubble | Patamon, Tsukaimon |
| 73 | Bit Bomb | Cherrymon, Piximon |
| 74 | Deadly Bomb | Giromon, Guardromon |
| 75 | Drill Spin | Drimogemon, MoriShellmon, Psychemon |
| 76 | Electric Thread | Dokunemon, Kunemon |
| 78 | Genocide Attack | Gigadramon, Megadramon |
| 81 | Pummel Whack | Fugamon, Goblimon, Golemon, Gotsumon, Jijimon, Ogremon |
| 82 | Hand of Fate | Angemon, Piddomon |
| 83 | Dark Claw | Bakemon, Soulmon |
| 86 | Solar Ray | Centarumon, Yanmamon |
| 87 | Hydro Pressure | Gekomon, Shellmon |
| 88 | Ice Blast | BlueMeramon, Gururumon, Seadramon |
| 90 | Blasting Spout | ShogunGekomon, Whamon |
| 92 | Love Serenade | Etemon, MetalEtemon |
| 93 | Electro Shocker | HerculesKabuterimon, Kabuterimon |
| 94 | Meteor Wing | Birdramon, Saberdramon |
| 95 | Super Slap | Muchomon, Otamamon, Penguinmon, SnowAgumon |
| 102 | Spiral Sword | Analogman, Andromon, Tekkamon |
| 104 | Volcanic Strike | Monochromon, Tankmon, Vermilimon |
| 105 | Subzero Ice Punch | Frigimon, Hyogamon, Icemon |
| 107 | Party Time | Nanimon, Numemon, Sukamon |
| 111 | Maelstrom | MegaSeadramon, WaruSeadramon |

Most pairs are canon: the series gives these species the same attack (Agumon's line, the
Gekomon line, Andromon and its kin). The same override could later give a native its own
finisher if wanted.
