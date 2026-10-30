# The partner: care, stats, evolution, death and techniques

How the partner Digimon is stored and how every care value moves: hunger, sleep, poop, weight, happiness, discipline,
tiredness, sickness and lifetime; how training, evolution, death, rebirth and technique learning work. The clock that
drives all of it is in [core.md](core.md); battles in [combat.md](combat.md); item effects in
[items-and-menus.md](items-and-menus.md).

Addresses are RAM addresses of the original US executable (`decomp/config/us/symbols.txt`; `tools/dwsyms.py` resolves
names for a rebuilt executable). `file.c:line` citations point into `decomp/src/main/` unless another directory is
given. `int16` values are little-endian. `[inferred]` marks deductions.

## Summary

The partner lives in two blocks: `PARTNER_ENTITY` (species, stats, learned techniques, name, lives) and `PARTNER_PARA`
(raising values). Every frame `partnerTick` → `tickConditions` advances hunger, sleep, tiredness, sickness, unhappiness
and death with counters on `CURRENT_FRAME` (20 frames = 1 game minute, 1200 = 1 hour) and then evaluates evolution
(`evoTimer` >= 6/24/72/144 h by level, scored against `EVOLUTION_REQS`). The partner dies at lifetime 0 (360 h at birth,
minus penalties for unhappiness), after 12 h of sickness or when it loses a battle with its last life; the egg inherits
`tamerLevel` % of the stats only after a natural death.

## Source files

| File | Contents |
|---|---|
| `partner.c` | partner state machine (`PARTNER_STATE`: 1 normal, 3 sleep, 4 scold, 15 praise, 5 eat, 6 toilet, 7 wild poop, 8/14 die, 9 eat poop, 13 evolve); `callDigimonRoutine` (routines called by scripts) |
| `partner_impl.c` | `RAISE_DATA`, `SLEEP_PATTERN`, `PARTNER_PARA` initialization, all care ticks (`tickConditions` and its `tick*Mechanics`), food, poop, sleep, sickness, death, `skipHours`, `handlePostBattleTiredness` |
| `evolution.c` | `EVOLUTION_REQS`, `EVOLUTION_STATS_GAINS`, `EVOLUTION_PATHS`, target selection, special evolutions, `reincarnatePartner` |
| `evl.c` + `src/evl/evl.c` | the EVL overlay: `EVL_applyEvolution` (stats, techniques, weight, lifetime), `EVL_scaleBaseStats`, `EVL_clampBaseStats` |
| `src/murd/murd.c` | MURD overlay: iris over the partner, lives box (`LIFE.TIM`), death map; loads DOOA with 0 lives |
| `src/dooa/dooa.c`, `src/doo2/doo2.c` | body dissolving, egg box, rebirth (`REINCARNATE_BABY_TYPE`) |
| `src/trn/trn_reward.c`, `src/trn2/trn2_reward.c` | training gains, multiplier, learning through Brains (`TRN_tryLearnMove`) |
| `battle_ui.c` | `handleBattleInjury`, `battleMoveLearning` |
| `tamer.c` | `startBattle`/`advanceBattleTime` (post-battle effects), `addTamerLevel`, medals, tamer states 17/19 (life lost) |
| `item.c` | food and medicine effects, `MOVE_LEARN_CHANCES`, `EVOLUTION_ITEM_TARGET`, `handleEvoItems` |
| `utils2.c`, `script_value.c`, `script_common.c` | `hasMove`/`learnMove`/`unlearnMove`, `STATS_LIMIT_ARRAY`, `hasDigimonRaised` (trigger `0x200+id`) |
| `include/dw/params.h`, `partner.h`, `evl.h`, `entity.h` | `PartnerPara`, `RaiseData`, `EvoRequirements`/`EvoStatsGains`/`EvolutionPath`, `Stats`/`PartnerEntity` |

## State in memory

There is no `PARTNER_STATS` symbol: the stats are inside `PARTNER_ENTITY` (+0x38).

| Symbol | RAM | Type / size | Meaning |
|---|---|---|---|
| `PARTNER_PARA` | `0x80138460` | `PartnerPara`, 0x84 | raising values (table below) |
| `PARTNER_ENTITY` | `0x801557A8` | `PartnerEntity`, 0x80 | entity, stats, techniques, name, lives |
| `TAMER_ENTITY` | `0x8015576C` | `TamerEntity`, 0x3C | +0x38 `tamerLevel` (i8, 0..10, at `0x801557A4`), +0x39 `raisedCount` (u8, <= 99) |
| `DEATH_STATS` | `0x801384E4` | `Stats`, 0x20 | stats at death, basis for inheritance (the `size:0x18` in symbols.txt is wrong `[inferred]`: `WORLD_POOP` is 0x20 further) |
| `WORLD_POOP` | `0x80138504` | 100 x `{u8 map, u8 x, u8 y, i8 size}` | poop piles in the world, saved with the game; size 0 = free |
| `RAISE_DATA` | `0x801225BC` | 66 x `RaiseData` (0x1C) | per-species raising data (units below) |
| `SLEEP_PATTERN` | `0x80122CF4` | 8 x `{u8 sleepyH, sleepyM, wakeH, wakeM, awakeHours, sleepHours}` | sleep schedules |
| `EVOLUTION_REQS` | `0x8012ABEC` | 63 x `EvoRequirements` (0x1C), index = target id | requirements |
| `EVOLUTION_STATS_GAINS` | `0x8012B2D0` | 66 x `{i16 hp, mp, off, def, spd, brn, target}` (0xE) | gains and the id actually evolved into |
| `EVOLUTION_PATHS` | `0x8012B66C` | 62 x `{i8 from[5], to[6]}`, index = id - 1 | evolution candidates (0xFF empty) |
| `EVOLUTION_ITEM_TARGET` | `0x80127C5C` | 44 x u8, index = item - 0x47 | species given by each evolution item |
| `MOVE_LEARN_CHANCES` | `0x80125FA4` | 58 x `u8[3]` | % chance to learn each technique (column = specialty position) |
| `STATS_LIMIT_ARRAY` | `0x80130318` | 22 x i16 | caps for script `SET_STAT`/`ADD_STAT`, index = `SCRIPT_STAT_*` |
| `REINCARNATE_BABY_TYPE` | `0x80134BAC` | 4 x i16 = {1, 15, 29, 43} | eggs: Botamon, Punimon, Poyomon, Yuramon |
| `EVOLUTION_TARGET` | `0x80134E50` | i16 | species about to evolve into; -1 none |
| `HAS_USED_EVOITEM` | `0x80134E52` | u8 | 1 = the evolution in progress comes from an item (no gains) |
| `PARTNER_STATE` / `PARTNER_SUB_STATE` | `0x80134C5B` / `0x80134C5C` | i8 | partner state / step in it |
| `TAMER_STATE` | `0x80134C91` | i8 | 0 free; 6 still; 17/19 life lost (sickness/battle); 20 reward |
| `IS_NATURAL_DEATH` | `0x80134C4C` | i32 | 1 = died at lifetime 0 (inherits stats) |
| `NANIMON_TRIGGER` | `0x80134C64` | i32 | 1 = the next special check gives Nanimon |
| `ITEM_SCOLD_FLAG` | `0x80134C59` | i8 | 1 = refused an item or pooped: scolding gives +8 discipline; 2 = accepts the next item |
| `HAS_IMMORTAL_HOUR` / `IMMORTAL_HOUR` | `0x80134CA8` / `0x80134CA4` | i32 / i8 | the hour (the wake-up hour) during which it cannot die or lose a life |
| `CURRENT_POOP_ID` / `POOP_TO_EAT` | `0x80134C58` / `0x80134C68` | u8 | next free `WORLD_POOP` slot / pile Numemon or Sukamon is about to eat |
| `ITEM_TAKE_DISTANCE` | `0x80122D24` | 66 x i8 | distance at which it accepts items (`distance*20+160`) |
| `EVO_SEQUENCE_DATA` | `0x80154F90` | 0x34 | state of the EVL sequence |
| `DOOA_REINCARNATION_SEQ` | `0x80087868` (DOOA overlay) | 0x40 | +0x0E `eggSlot` (i16, 0..3), the chosen egg |

### `PartnerPara` (`params.h:36`), base `0x80138460`

`condition` (u32, +0x00): bit 0 SLEEPY, 1 TIRED, 2 HUNGRY, 3 POOPY, 4 UNHAPPY, 5 INJURED, 6 SICK. All other fields are
`int16`.

| Field | +off | Meaning (unit) | Range / initial |
|---|---|---|---|
| `condition` | 0x00 | state bits | 0 |
| `sleepyHour` / `sleepyMinute` | 0x04 / 0x06 | bedtime | |
| `wakeupHour` / `wakeupMinute` | 0x08 / 0x0A | wake-up time | |
| `hoursAwakeDefault` / `hoursAsleepDefault` | 0x0C / 0x0E | hours awake / asleep in the pattern | 3..15 / 1..9 |
| `timeAwakeToday` | 0x10 | remaining awake time in tenths of an hour | `hoursAwakeDefault*6` |
| `sicknessCounter` | 0x12 | hours awake while SLEEPY; >= 10 enables sickness | 0 on sleeping |
| `missedSleepHours` | 0x14 | hours of sleep missed (statistic) | |
| `tirednessSleepTimer` | 0x16 | tiredness accumulator that brings bedtime forward | |
| `poopLevel` | 0x18 | steps of 10 game minutes until it needs to go | `RaiseData.poopTimer` |
| `virusBar` | 0x1E | poop piles left on the ground; 16 → Sukamon | 0..16 |
| `poopingTimer` | 0x20 | frames it holds on while POOPY | -1 if not |
| `tiredness` | 0x22 | | 0..100 |
| `subTiredness` | 0x24 | nothing increments it in US (>= 60 would give tiredness +1) | 0 |
| `tirednessHungerTimer` | 0x26 | consecutive frames with tiredness >= 50 | |
| `discipline` | 0x28 | | 0..100, initially 50 |
| `happiness` | 0x2A | | -100..100, initially 50 |
| `timesBeingSick` / `sicknessTries` | 0x30 / 0x32 | times sick / sickness rolls made | |
| `areaEffectTimer` | 0x34 | frames on the current map (favoured/hated area) | 0 on map change, cap 28800 |
| `sicknessTimer` | 0x36 | hours sick; 12 → loses a life | |
| `injuryTimer` | 0x38 | hours injured; 12 → becomes sick | |
| `nextHungerHour` | 0x3A | next hunger hour | 0..23 |
| `energyLevel` | 0x3C | stomach | 0..`energyCap`, initially `energyThreshold` |
| `foodLevel` | 0x3E | game minutes until hungry | |
| `starvationTimer` | 0x40 | while HUNGRY: units of 10 frames until the hunger passes | 180 |
| `weight` | 0x42 | | 1..99, initially `defaultWeight` |
| `refusedFavFood` | 0x44 | 2 = just refused its favourite food | |
| `emptyStomachTimer` | 0x46 | minutes with energy 0 (statistic) | |
| `remainingLifetime` | 0x48 | hours left; 0 = death | 360 |
| `age` | 0x4A | days | 0 |
| `trainBoostFlag` / `Value` / `Timer` | 0x4C / 0x4E / 0x50 | training boost from an item (stat mask / % / frames) | |
| `careMistakes` | 0x52 | care mistakes in this form | 0 on evolving |
| `battles` | 0x54 | battles won in this form | 0 on evolving |
| `evoTimer` | 0x56 | hours at the current level | 0 on a level change |
| `fishCaught` | 0x5E | fish caught (medal at 100) | |
| `upgradeHPcounter` / `MP` / `Off` | 0x66 / 0x68 / 0x6A | sessions trained as Fresh/In-Training; >= 10 → x1.2 on that stat for good | |
| `buggedUpgradeBrainsCounter` | 0x6C | never read or written | |
| `upgradeDefenseCounter` / `Speed` / `Brain` | 0x6E / 0x70 / 0x72 | as above for Def and Spd; the Brain one rises (`trn_brain.c:44`) but is never read: Brains training uses the MP multiplier | |
| `sukaBackupHP/MP/Off/Def/Speed/Brain` | 0x76..0x80 | stats saved on turning into Sukamon | |

Offsets 0x1A, 0x1C, 0x2C, 0x2E, 0x58-0x5C, 0x60-0x64, 0x74, 0x82 are unused. `PARTNER_PARA` is only overwritten whole
when a game is loaded: the `upgrade*` counters and `fishCaught` survive evolutions and rebirths.

### `PartnerEntity` (`entity.h:111`), base `0x801557A8`

| Field | +off | RAM | Meaning |
|---|---|---|---|
| `entity.type` | 0x00 | `0x801557A8` | species id (i32), index into `DIGIMON_DATA`/`RAISE_DATA` |
| `entity.anim.animId` | 0x2E | `0x801557D6` | current animation (0/1 idle, 2/3 walk, 4 run, 0xE..0x13 state warnings) |
| `stats.base.off/def/speed/brain` | 0x38-0x3E | `0x801557E0` | base stats, cap 999 (9999 with the caps patch) |
| `stats.base.movesPrio[4]` | 0x40 | `0x801557E8` | battle usage priority |
| `stats.base.moves[4]` | 0x44 | `0x801557EC` | equipped techniques as animation ids (`0x2E + index in DigimonPara.moves`, 0xFF empty); [3] is the finisher |
| `stats.base.hp/mp` | 0x48 / 0x4A | `0x801557F0` | max HP/MP, cap 9999 (30000 with the caps patch) |
| `stats.current.currentHP/MP` | 0x4C / 0x4E | `0x801557F4` | current HP/MP |
| `stats.current.vabId` | 0x54 | `0x801557FC` | voice bank (4 = partner) |
| `learnedMoves[2]` | 0x58 | `0x80155800` | 64-bit set, bit = technique id (`utils2.c:304`); 0x2C and 0x30 share bits 12 and 16 of the second word (both are set), 0x37 and 0x39 bits 23 and 25 |
| `name[20]` | 0x68 | `0x80155810` | name given by the player |
| `lives` | 0x7C | `0x80155824` | i8, 3 at birth |

### `RaiseData` units

`hungerTimes[8]` hours of the day at which hunger sets in (-1 ends; Fresh and In-Training ignore it); `energyCap`
maximum energy; `energyThreshold` minimum energy to count as fed; `energyUsage` energy lost per hour; `poopTimer` steps
of 10 game minutes until it needs to go; `unk2` always 1200; `poopSize` (>= 11 large, >= 14 huge); `favoriteFood` item
id; `sleepCycle` row of `SLEEP_PATTERN`; `favoredRegion`; `trainingType` 0..4; `defaultWeight`. Agumon's row is
`{1,5,9,13,17,21,-1,-1}, 40, 20, 5, 24, 1200, 8, 38 (Meat), 1, 0, 0, 15`.

`SLEEP_PATTERN` (`partner_impl.c:184`): 0 = 16:00→01:00, 1 = 19:00→04:00, 2 = 22:00→07:00, 3 = 02:00→11:00,
4 = 07:00→16:00, 5 = 10:00→19:00 (all 15 h awake, 9 asleep); 6 = 4 h awake / 1 h asleep (Fresh), 7 = 8 h / 3 h
(In-Training): for these two the times count from birth.

## Time units and when care runs

`tickGameClock` adds 1 to `CURRENT_FRAME` per frame (2 at double speed, half at half speed): `% 20` = every game minute,
`% 200` = 10 min, `% 1200` = 1 h, `% 4800` = at 0/4/8/... h. A battle adds 20 min (`advanceBattleTime`), a training
session 1 h (`TRN_advanceTrainingTime`), sleeping jumps to the wake-up time (`advanceToTime`), and `skipHours`
(`partner_impl.c:1960`, used by scripts) applies the same rules in one go.

`tickConditions` (`partner_impl.c:2029`) only runs with `GAME_STATE == 0`, `PARTNER_STATE == 1`, the clock running, a
new frame and no `FADE_PROTECTION`: in menus, battles, fishing and cutscenes nothing advances.
`tickConditionBoundaries` clamps every frame: happiness ±100, discipline 0..100, tiredness 0..100, energy
0..`energyCap`, weight 1..99. In the mod most of the periods, thresholds and amounts below are data (patches 0125,
0126, 0130, 0140); the defaults are the original values given here.

## Hunger and energy (`tickHungerMechanics`, `partner_impl.c:1464`)

- `setFoodTimer`: Fresh eats every 2 h on the hour, In-Training every 3 h, the rest at the next hour in `hungerTimes`;
  `foodLevel` = minutes until then. It drops 1 per minute, 15 per battle, 60 per skipped hour; with
  `tirednessHungerTimer >= 50` (tiredness >= 50 for 50 frames) it loses 3 more per hour.
- `foodLevel <= 0` → HUNGRY, `starvationTimer = 180` (-1 every 10 frames = 1.5 h; -40 per battle, -120 per skipped
  hour). At 0 the hunger passes by itself, the next meal is scheduled and **if `energyLevel < energyThreshold` it is a
  care mistake**.
- `energyLevel -= energyUsage` every hour. With energy 0, weight -1 every 200 frames. Reaching the threshold sets
  trigger 640 (no script reads it).
- Feeding (`partnerHandleFoodFeed`): the item has already added its energy (x1.4 and +2 happiness for the favourite,
  capped at `energyCap`). If it was hungry and now has enough energy: happiness +5, discipline +1, hunger cleared, next
  meal scheduled. Food (items 0x26..0x46, 0x79, 0x7A) given when not hungry: happiness -3, discipline -2.
- Refusals (`partnerWillRefuseItem`): always refuses 0x73..0x7C except 0x79/0x7A, and items 0x21..0x25; evolution
  items for the wrong level; items 0x00..0x20 are refused if `rand(100) < 110 - (discipline + rand(10) + 10)`
  (discipline 100 never, 50 about 45 %, 0 almost always), then `ITEM_SCOLD_FLAG = 1`; when not hungry the favourite
  food is refused 20 % of the time.

## Sleep (`tickSleepMechanics`, `handleSleeping`, `sleepRegen`)

- Rookie and above: fixed schedule from `SLEEP_PATTERN[sleepCycle]`. Fresh/In-Training (`setSleepTimes`): fall asleep
  3 / 7 h after birth (`randomLimit(1)` always returns 0) and sleep 1 / 3 h, chaining from each wake-up.
- Every minute `tirednessSleepTimer += tiredness*3/10`; past 180, on each `% 200`, `timeAwakeToday--` and bedtime moves
  earlier (`sleepyHour = wakeupHour - hoursAsleepDefault - hoursLost`): the more tired, the sooner it gets sleepy.
- SLEEPY is set when `HOUR` enters [sleepyHour, wakeupHour). While SLEEPY and awake: Fresh -1 happiness and -1
  discipline every 200 frames, In-Training every 300, the rest -2/-4 every hour; every hour `sicknessCounter++` and
  `missedSleepHours++`. If the wake-up time passes without sleep: SLEEPY cleared, **care mistake**,
  `addTamerLevel(1 %, -1)`, new schedule.
- Sleeping (state 3, started from the menu): the clock jumps to the wake-up time; `evoTimer += hoursAsleepDefault`,
  `remainingLifetime -= hoursSlept`; hunger cleared and the next meal scheduled; if it needed to go it leaves a poop
  pile where it sleeps (raises `virusBar`); sick: `sicknessTimer += hours`, -20 happiness, -10 discipline, +10
  tiredness; injured: `injuryTimer += hours`, -10/-5/+5. (The "weight -1 if it sleeps hungry" branch is dead: the bit is
  cleared before.) On waking `IMMORTAL_HOUR = HOUR` (no death or life loss during that hour) and
  `handleSpecialEvolutions(2)` runs.
- Regeneration: `factor = hoursSlept*100/hoursAsleepDefault` (x1.2 with the Rest pillow 0x22, x1.2 in the favoured area,
  x0.8 in the hated one); `HP += factor% * HPmax*(70+rand(10))%`, the same for MP; `tiredness -= factor% *
  tiredness*(80+rand(20))%`; `weight -= defaultWeight/10`.

## Poop and the virus bar (`tickPoopingMechanic`, `createPoopPile`)

- Only while the tamer is free: `poopLevel` -1 every 200 frames (10 min; -2 per battle, -6 per skipped hour, -1 per
  meal). At 0 → POOPY and `poopingTimer = (discipline+20)*12` frames (discipline 0: 12 min; 50: 42 min; 100: 72 min);
  it counts down every frame (-400 per battle).
- Time runs out → state 7, wild poop (`handleWildPoop`): **care mistake**, happiness -10, discipline -5, `poopLevel =
  2*poopTimer`, weight `-(rand(4)+poopSize)/4`, `virusBar++` (not for Sukamon), `addTamerLevel(1 %, -1)`,
  `ITEM_SCOLD_FLAG = 1`.
- Toilet (floor trigger 120 → MAPHEAD section 0x4E2, which leads to partner state 6, `handleToilet`): happiness +2,
  discipline +2, `poopLevel = 2*poopTimer`, the same weight loss, no virus. Portable potty item: clears POOPY,
  `poopLevel = poopTimer`, no virus.
- `virusBar >= 16`: `EVOLUTION_TARGET = 0x27` (Sukamon), the stats are copied to `sukaBackup*` and the species to
  pstat 5. Numemon (0x0B) and Sukamon (0x27) eat the piles the tamer steps on (`tickPoopDetection`,
  `handleEatingPoop`): small HP +5 %, MP +2 %, weight +1, 2 % chance of a cure; medium (size 11..13) 10 %/5 %/+3/7 %;
  large 50 %/10 %/+10/20 %.

## Weight

Rises with food (`addWeight`, 1..10 per item; -2/-5 for Black trout and Pricklypear), falls when sleeping
(`defaultWeight/10`), when pooping and with energy 0 (-1 per 200 frames), and never leaves 1..99. It counts towards
evolution (`req.weight ± 5`).

## Happiness, discipline, praise and scolding (`handlePraiseScold`)

| Action | Happiness | Discipline | Other |
|---|---|---|---|
| Praise (state 15) | `+discipline/10 + 2` | -5 | |
| Scold (state 4) | -10 | +2 | clears UNHAPPY, `refusedFavFood = 0` |
| Scold with `ITEM_SCOLD_FLAG == 1` | unassigned (`happinessDelta` is uninitialized in the C) | +8 | the next item is accepted |
| Scold a Rookie with discipline 0 and happiness -100 | | | `NANIMON_TRIGGER = 1` → Nanimon |
| Eat while hungry / not hungry | +5 / -3 | +1 / -2 | |
| Win / flee / lose a battle (`tamer.c:813`) | +2 / -10 / -30 | 0 / -6 / -20 | fleeing +2 tiredness; losing -1 life |
| Toilet / wild poop | +2 / -10 | +2 / -5 | |
| Each hour SLEEPY and awake (Rookie+) | -2 | -4 | |
| Each hour sick | -10 | -5 | +5 tiredness |
| Training session | -1 (-3 more if tiredness >= 70) | -3 if tiredness >= 70 | |
| Each hour on a favoured / hated map | +1 / -1 | | tiredness -2 / +1 |
| New year | | | happiness 100: 5 % chance of +1 tamer level; < 0: 10 % chance of -1 |

**Unhappiness** (`tickUnhappinessMechanics`): with no other condition and happiness < 0, every 200 frames
`rand(100) < |happiness| - discipline` sets UNHAPPY (the butterfly): then happiness +1 every 15 frames and **all base
stats -2 % every 300 frames** (minimum 1) until happiness is back to >= 0 or the partner is scolded.

## Tiredness (`tickTirednessMechanics`)

+5 per battle (`handlePostBattleTiredness`; its factor for MP spent is always 0), +6..10 per training session, +5/h
sick, +1/h on a hated map, +10 when sleeping sick; falls when sleeping, with items and -2/h on a favoured map.
`subTiredness` never rises in US, so tiredness never grows by itself. The Health shoe (0x25) gives +5 HP and +5 MP every
20 frames while the tamer walks. At >= 50 `tirednessHungerTimer++` per frame; at >= 80 TIRED and happiness -2 every 100
frames. At 100 every training gain becomes 1.

## Sickness and injury (`tickSicknessMechanics`)

- Injury: after a battle in which it took damage, `rand(100) < tiredness - HP%` (`handleBattleInjury`).
  `injuryTimer++` per hour; at 12 h it turns into sickness.
- Sickness, three causes: (a) `sicknessCounter >= 10` (10 h awake while sleepy, accumulated until it sleeps): every
  hour `sicknessTries++` and `chance = (sicknessTries-10)*5 + (tiredness-50)`. `chance` is a `uint8_t`, so a negative
  value wraps to >= 156 and `rand(100) < chance` always succeeds: unless tiredness >= 95 it falls sick on the first roll
  (original bug, `[inferred from the type]`); (b) more than 12000 frames (10 h) in a row on a hated map; (c) food with a
  sickness chance (Moldy Meat 100 %, Happymushrm 30 %, Digiseabass and Steak 20 %, Chain melon 5 %). On falling sick:
  `timesBeingSick++`, `sicknessTimer = 1`, happiness -20, an on-screen warning.
- While sick, every hour: happiness -10, discipline -5, tiredness +5, `sicknessTimer++`; **at 12 h it loses a life**:
  `lives--`, pstat 0xFF = 0 and MAPHEAD section 0x4DE. Medicine cures it (`handleMedicineHealing`:
  `rand(3) < injuryChance`, `rand(10) < sicknessChance`), as do eating poop and scripts.

## Lifetime, age and care mistakes

- `remainingLifetime` starts at 360 h (15 days) and drops 1 per game hour, slept or skipped. Every 4 h
  (`CURRENT_FRAME % 4800`, also after training and in `skipHours`) with happiness < 80 it loses an extra
  `(happiness-80)/-50 + 1` (truncating): 1 h with 31..79, 2 with -19..30, 3 with -69..-20, 4 below. It rises +96 h on
  reaching Ultimate naturally, +3 with Digiseabass, +20 with Chain melon, and by script.
- `tickDeathCondition`: lifetime 0, outside the immortal hour, no script running (`IS_SCRIPT_PAUSED == 1`), tamer free
  → `IS_NATURAL_DEATH = 1` and MAPHEAD section 0x4DE.
- `remainingLifetime` is a signed `int16` with no upper clamp (only `< 0 → 0`): at 32 767 it wraps negative and the next
  free tick kills the partner.
- `careMistakes` rises with: hunger passing with low energy, wild poop, missed sleep, a battle or training with
  `starvationTimer` run out and low energy. It resets on evolving and on rebirth. `battles` only counts wins.

## Training gains (`trn_reward.c`, `trn2_reward.c`)

Base gain per session in the File City gym (TRN overlay) and in the Ice Sanctuary and Beetle Land ones (TRN2, screens
99/107/108):

| Training | TRN base gain | TRN2 | tiredness / energy / happiness |
|---|---|---|---|
| HP | HP +80, Off +2 | HP +120 (+Off 2 on the second machine) | +10 / -1 (-2) / -1 |
| MP | MP +80, Def +2 | MP +150 | +7 / -1 / -1 (TRN2 -4) |
| Offense | Off +8, Spd +2 (machine 2: HP +10, Off +8) | Off +12 | +9 / -1 / -1 |
| Defense | Def +8, Brn +2 | Def +12 (+2 on the second) | +9 / -1 / -1 |
| Speed | HP +10, Spd +8 | Spd +12 | +8 / -1 / -1 |
| Brains | MP +10, Brn +8 (machine 2: Brn +15) | | +6 / -1 / -1 |

Each value is multiplied by `v/10` with `v = TRN_calculateTrainingMultiplier`: the `trainingType` affinity (10, 9, 11 or
8 tenths by stat), x0.9 Fresh/In-Training, x1.0 Rookie, x1.1 Champion, x1.2 Ultimate, x1.2 with trigger 0xDB
(HP/Def/Spd) or 0xFB (Off/MP/Brn) of the upgraded gym, x1.2 if that stat's `upgrade*` counter is >= 10. Brains calls the
multiplier in MP mode: it uses the MP affinity, trigger and counter (ten MP sessions as a baby give x1.2 to MP and to
Brains; the Brains counters are never read). x1.1 with the Trn. manual (0x21). With an item's `trainBoostFlag` the
marked stat uses `v*trainBoostValue/100` instead of `v/10`. Then x`c/10` from the slot machine: 10 without it, 5 on a
miss, 20 three of a kind, 40 three of the stat, 100 three sevens. With tiredness 100 everything becomes 1. Each gain is
capped at 999 and the total applied with a 9999/999 cap when the box is confirmed (9999 per gain and 30000/9999 with
the caps patch). The minigame side (slots, timing) is in [minigames.md](minigames.md); the mod's training numbers are
data (patches 0123, 0134).

## Evolution

### When it is evaluated (`tickConditions`, `partner_impl.c:2068-2119`)

Every frame with no day/night fade in progress (`isInDaytimeTransition`, almost always true), outside the immortal hour,
`PARTNER_STATE == 1` and the tamer free:

| Current level | Condition | Function |
|---|---|---|
| 1 Fresh | `evoTimer >= 6` | `getFreshEvolutionTarget`: fixed (Botamon→Koromon, Punimon→Tsunomon, Poyomon→Tokomon, Yuramon→Tanemon) |
| 2 In-Training | `evoTimer >= 24` | `getInTrainingEvolutionTarget`: best score >= 3; ties → first in the `to` list (patch 0111 adds up to 12 extra Rookie targets per In-Training, `getEvolutionExtraTargets`) |
| 3 Rookie | `evoTimer >= 72` | `getRookieEvolutionTarget`; if none reaches 3 and `evoTimer >= 96` → Numemon (11) |
| 4 Champion | `evoTimer >= 144` | `getChampionEvolutionTarget`; nothing if none qualifies |
| 4 Champion | `evoTimer == 360` | `handleSpecialEvolutions(3)` |
| 5 Ultimate (mod) | `evoTimer >= 96` | the Mega patch (0058) evaluates the Ultimate's paths: another Ultimate, or a Mega (level 6) once `evoTimer >= 120`; Megadramon/Gigadramon → Machinedramon from 48 h |

A target other than -1 → `tamerSetState(6)`, `partnerSetState(13)`; state 13 runs the EVL sequence and ends in
`EVL_applyEvolution`. The hours of each level, the specials and the item rules are data in the mod (patches
0117-0119).

### Score (`calculateRequirementScore`)

At most 4 points against `EVOLUTION_REQS[target]`:

1. Care mistakes: `flags & 0x10` → `careMistakes <= care`; otherwise `>= care`.
2. Weight: `req.weight - 5 <= weight <= req.weight + 5`.
3. Stats: for a Rookie target the partner's highest stat (comparing HP/10, MP/10, Off, Def, Spd, Brn; ties go to the
   later index: Brn > Spd > Def > Off > MP > HP) must be marked 1 in the table; at other levels all six must be >= the
   table (-1 does not count; HP and MP compared /10).
4. Bonus, any one of: coming from `req.digimon`; discipline >=; happiness >=; `battles` (`flags & 1` → <=, otherwise
   >=); learned techniques (bits of `learnedMoves`) >= `techs`. For Rookies `battles = -2` or `techs = 0` make it
   always true.

3 points are needed. Against an existing better candidate: a target already raised (trigger `0x200+id`) loses to an
unraised candidate (0 points); a new target over a raised candidate gets +1. For Rookie→Champion and
Champion→Ultimate, among those scoring 3 the one with the highest average of the stats the table requires wins;
`statTotal/statCount` are only reset when a new best is found, so later candidates see a diluted average (original bug,
unverified in play). The mod's score sums the four bits of `evoRequirementsMet`, which the evolution chart also shows.

### Special evolutions (`handleSpecialEvolutions`, one `rand(100)` per call)

- Mode 2 (on waking): < 30 and Birdramon (0x15) or Seadramon (0x0A) with discipline 100, happiness 100 and tiredness 0
  → Airdramon (7); Vegiemon (0x19) with >= 50 battles and discipline 100 → Ninjamon (58); Drimogemon (0x26) with Def >=
  500 and discipline 100 → Monochromon (47); < 50 and Koromon/Tokomon/Tsunomon/Tanemon on screen 1 (Kunemon's Bed) →
  Kunemon (32).
- Mode 3 (after praise/scolding or at 360 h as Champion): Whamon (0x18)/Shellmon (0x23) with `evoTimer == 200` and
  < 30 → Coelamon (49); `NANIMON_TRIGGER` → Nanimon (53); any Champion with `evoTimer >= 240` and < 50 → Vademon (28).
  The exact `evoTimer == 360` may never match because sleep jumps hours (unverified).

### Items (`handleEvoItems`, `item.c:2179`)

Items 0x47..0x72 → `EVOLUTION_ITEM_TARGET[item-0x47]` only if `level(target) - 1 == current level`; Giga Hand (0x7D) →
Gigadramon (0x40), Noble Mane (0x7E, Rookie only) → Panjyamon (0x3F), Metalbanana (0x7F) → MetalEtemon (0x41); 0x7D and
0x7F are only accepted by a Champion. `HAS_USED_EVOITEM = 1`: no stat gains, no +96 h and no tamer level.

### Stats on evolving (`EVL_applyEvolution`, `evl.c:1282`)

With `EVOLUTION_STATS_GAINS[target]`, per stat: if the current value >= the gain → `+gain/10`; otherwise →
`(gain + current)/2`; cap 9999/999 (30000/9999 with the caps patch). Champion gives a 20 % and Ultimate a 100 % chance
of tamer level +1. Numemon (0x0B), Sukamon (0x27), Nanimon (0x35), Devimon (6), any Fresh/In-Training, or coming from
Sukamon use `EVL_scaleBaseStats` instead: `stat * brains/10` (Numemon x0.8, Sukamon x0.5, the rest x1.0); on leaving
Sukamon `backup + (current - backup/2)/2` and `virusBar = 0`. Always: `weight = defaultWeight`, `careMistakes =
battles = 0`, a natural Ultimate gets +96 h of lifetime (a Mega, with patch 0058, tamer level +1 and +120 h), `evoTimer
= 0` if the level changes, trigger `0x200+id` (raised) set.

Techniques on evolving: it learns the one with the **lowest non-zero power** in the new species' main specialty (id
ranges: Fire 0..8, Air 8..16, Nature 16..24, Mech 24..32, Ice 32..40, Battle 40..48, Filth 49..57) and equips it in
`moves[0]`; `moves[1..2] = 0xFF`; `moves[3]` = the last finisher (id 0x3A..0x70) in the species' list. Learned
techniques are kept.

### Evolution rules for the added species

The species added by the mod join the same pickers; the disc's own routes are unchanged.

- **More Rookie targets per In-Training** (patch 0111): each In-Training (Baby II) can take up to 12 extra Rookies past
  the 6 slots of its `EVOLUTION_PATHS.to` list. `getInTrainingEvolutionTarget` and the evolution chart's overview walk
  the extra list after the original one; `EvolutionPath` itself is unchanged. The picker still keeps the best score >= 3
  with ties going to the first listed, so the Rookies of one In-Training need distinct requirements.
- **Parents**: each imported species has 1 or 2 parents, and every parent shares at least one specialty with the child.
- **`requirements.digimon`** names the primary parent: the game reads that field as "the species it evolves from", so
  the bonus point applies to that route only.
- **Rookie weight bands**: the added Rookies ask for weight 26 (overfed) or 4 (underfed; weight drops while energy is
  0), while the disc's Rookies keep 15, so an In-Training raised normally still becomes the disc's Rookie.
- **The disc's routes are kept**: `tools/evo_check.py` models the game's pickers and checks, for every disc route whose
  parent gained new children, that the disc child's own requirements met exactly still choose the disc child; it also
  checks that every link is reachable from some partner state. `tools/evo_graph.py` checks that every partner species has
  a natural route. The special routes (`handleSpecialEvolutions`, items) stay as they are.

Species data, requirements and links are edited as described in [../mods/species.md](../mods/species.md).

### Virus form and reverting

The King of Sukamon (screen 165 GOMI02, NPC slot 0, script 159 section 81) only reverts the virus form: if the partner
is Sukamon (39) he runs `CALL_DIGIMON_ROUTINE 2` (`partner.c:1136`: `EVOLUTION_TARGET = readPStat(5)`, partner state
13), then sets trigger 363, which only changes his dialogue next time. There is no cost, item or limit on repetition.
The result is an ordinary evolution into the old species:

| Field | Into Sukamon (virus bar 16) | Sukamon → old species |
|---|---|---|
| species / level | 39, level 4 | pstat 5 (any level) |
| base stats | x0.5, full copy in `sukaBackup*` | `backup + (current - backup/2)/2` per stat (back to the backup if untrained as Sukamon) |
| `remainingLifetime` | unchanged | +96 if the target is level 5 (no check of the previous level); nothing below |
| `evoTimer` | 0 if the level changes | 0 if the level changes |
| `careMistakes`, `battles`, `virusBar` | 0 | 0 |
| weight | species default | species default |
| lives, happiness, discipline, tamer level | unchanged | unchanged (the tamer-level roll needs `IS_SCRIPT_PAUSED == 1`, false inside a script) |

An Ultimate → Sukamon → Ultimate loop is not a lifetime gain: refilling the bar takes 16 wild poops (the only source),
about 190 game hours with an Ultimate's `poopTimer` of 36 (first poop 6 h, then 12 h each), for +96 h; each wild poop
also costs happiness, which adds the 4-hourly drain. No script writes stat 12 (virus); stat 13 (lifetime) is written
only by script 164 section 8.

The game has no completion percentage. The nearest thing is the evolution chart (61 entries, `hasDigimonRaised` =
trigger `0x200+id`, set at birth and in every `EVL_applyEvolution`, never cleared) and medal 6 (all of 1..61 raised,
+1 tamer level). One partner never leaves its egg line: the four eggs and their In-Training forms can only be raised by
rebirth, so the chart needs several lives.

### Evolution table

`EVOLUTION_PATHS.to`, `EVOLUTION_REQS` and `EVOLUTION_STATS_GAINS` of the original. "-" = no requirement; stat
requirements are HP/MP/Off/Def/Spd/Brn with HP and MP in tenths; for Rookies "1" marks the stat that must be highest;
bonus = previous form / discipline / happiness / battles / techniques; flags 0x10 = maximum mistakes, 0x01 = maximum
battles. Species names and ids are listed in [ids.md](ids.md).

| id | Name | lv | Evolves to | Stat req | Mist | Weight | Bonus | Fl | Gains HP/MP/Off/Def/Spd/Brn |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Botamon | 1 | 2 | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 0/0/0/0/0/10 |
| 2 | Koromon | 2 | 3 17 | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 0/0/0/0/0/10 |
| 3 | Agumon | 3 | 5 9 21 36 47 8 | 1/1/1/-/-/- | 0 | 15 | 2/-/-/-/- | 00 | 1000/500/100/50/50/50 |
| 4 | Betamon | 3 | 10 24 35 49 | 1/1/-/1/-/- | 0 | 15 | 44/-/-/-2/0 | 00 | 1000/500/50/100/50/50 |
| 5 | Greymon | 4 | 12 26 | -/-/100/100/100/100 | 1 | 30 | -/90/-/-/35 | 10 | 2000/1500/200/200/200/200 |
| 6 | Devimon | 4 | 26 54 | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 0/0/0/0/0/10 |
| 7 | Airdramon | 4 | 54 59 | -/100/-/-/100/100 | 1 | 30 | -/90/-/-/35 | 10 | 1500/2000/150/150/200/200 |
| 8 | Tyrannomon | 4 | 12 54 | 100/-/-/100/-/- | 5 | 30 | -/-/-/5/28 | 11 | 2000/1500/150/200/150/150 |
| 9 | Meramon | 4 | 12 40 | -/-/100/-/-/- | 5 | 20 | -/-/-/10/28 | 00 | 1000/1500/250/150/150/150 |
| 10 | Seadramon | 4 | 54 61 | 100/100/-/-/-/- | 3 | 30 | -/-/-/5/28 | 01 | 2000/2000/150/150/100/150 |
| 11 | Numemon | 4 | 14 | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 0/0/0/0/0/8 |
| 12 | MetalGreymon | 5 | - | 400/300/500/500/300/300 | 10 | 65 | -/95/-/30/30 | 10 | 5000/5000/500/500/500/500 |
| 13 | Mamemon | 5 | - | -/-/400/300/300/400 | 15 | 5 | -/-/90/-/25 | 00 | 3000/3000/600/500/500/600 |
| 14 | Monzaemon | 5 | - | 300/300/300/300/300/300 | 0 | 40 | -/-/-/50/49 | 10 | 5000/5000/500/500/500/500 |
| 15 | Punimon | 1 | 16 | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 0/0/0/0/0/10 |
| 16 | Tsunomon | 2 | 18 57 | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 0/0/0/0/0/10 |
| 17 | Gabumon | 3 | 36 47 38 8 34 22 | -/-/-/1/1/1 | 0 | 15 | 2/-/-/-2/0 | 00 | 500/500/50/100/100/50 |
| 18 | Elecmon | 3 | 48 20 37 50 | 1/-/1/-/1/- | 0 | 15 | 16/-/-/-2/0 | 00 | 500/500/100/50/100/50 |
| 19 | Kabuterimon | 4 | 60 27 | 100/100/100/-/100/- | 1 | 30 | 32/-/-/-/35 | 10 | 2000/1500/200/200/200/100 |
| 20 | Angemon | 4 | 40 59 | -/100/-/-/-/100 | 0 | 20 | 31/-/-/-/35 | 10 | 1500/2000/150/150/150/250 |
| 21 | Birdramon | 4 | 59 | -/-/-/-/100/- | 3 | 20 | 45/-/-/-/35 | 00 | 1500/1500/150/100/250/150 |
| 22 | Garurumon | 4 | 26 61 | -/100/-/-/100/- | 1 | 30 | -/90/-/-/28 | 10 | 1500/1500/150/200/150/150 |
| 23 | Frigimon | 4 | 27 13 | -/100/-/-/-/100 | 5 | 30 | -/-/50/-/28 | 10 | 1500/2000/100/150/150/200 |
| 24 | Whamon | 4 | 61 13 | 100/-/-/-/-/100 | 5 | 40 | -/60/-/-/28 | 10 | 2500/1500/100/150/100/200 |
| 25 | Vegiemon | 4 | 55 | -/100/-/-/-/- | 5 | 10 | -/-/50/-/21 | 00 | 1500/2000/100/150/150/100 |
| 26 | SkullGreymon | 5 | - | 400/600/400/400/200/500 | 10 | 30 | -/-/-/40/45 | 00 | 5000/5000/600/600/400/400 |
| 27 | MetalMamemon | 5 | - | -/-/500/400/400/400 | 15 | 10 | -/-/95/-/30 | 10 | 3000/3000/600/600/600/500 |
| 28 | Vademon | 5 | - | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 5000/5000/500/500/500/500 |
| 29 | Poyomon | 1 | 30 | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 0/0/0/0/0/10 |
| 30 | Tokomon | 2 | 31 45 | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 0/0/0/0/0/10 |
| 31 | Patamon | 3 | 38 8 34 48 20 33 | 1/-/1/-/-/1 | 0 | 15 | 30/-/-/-2/0 | 00 | 500/500/100/50/50/100 |
| 32 | Kunemon | 3 | 37 19 51 25 | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 1000/1000/50/50/50/50 |
| 33 | Unimon | 4 | 41 59 | 100/-/-/-/100/- | 3 | 30 | -/-/-/10/35 | 10 | 2000/1500/150/150/200/150 |
| 34 | Ogremon | 4 | 40 41 | 100/-/100/-/-/- | 5 | 30 | -/-/-/15/35 | 00 | 2500/1000/250/150/150/100 |
| 35 | Shellmon | 4 | 60 61 | 100/-/-/100/-/- | 5 | 40 | 4/-/-/-/35 | 00 | 2000/1500/150/250/100/100 |
| 36 | Centarumon | 4 | 40 41 | -/-/-/-/-/100 | 3 | 30 | -/60/-/-/28 | 10 | 1500/1500/150/150/150/250 |
| 37 | Bakemon | 4 | 26 41 | -/100/-/-/-/- | 3 | 20 | -/-/50/-/28 | 00 | 1500/2500/150/100/150/100 |
| 38 | Drimogemon | 4 | 12 | -/-/100/-/-/- | 3 | 40 | -/-/50/-/28 | 00 | 1500/1500/250/150/150/150 |
| 39 | Sukamon | 4 | 42 | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 0/0/0/0/0/5 |
| 40 | Andromon | 5 | - | 200/400/200/400/200/400 | 5 | 40 | -/95/-/30/30 | 10 | 4000/6000/400/600/400/600 |
| 41 | Giromon | 5 | - | -/-/400/-/300/400 | 15 | 5 | -/-/95/100/35 | 00 | 3000/3000/600/600/500/600 |
| 42 | Etemon | 5 | - | 200/300/400/200/400/300 | 0 | 15 | -/-/-/50/49 | 10 | 4000/5000/600/400/600/500 |
| 43 | Yuramon | 1 | 44 | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 0/0/0/0/0/10 |
| 44 | Tanemon | 2 | 46 4 | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 0/0/0/0/0/10 |
| 45 | Biyomon | 3 | 21 7 50 33 19 | -/1/-/1/1/- | 0 | 15 | 30/-/-/-2/0 | 00 | 500/1000/50/50/100/50 |
| 46 | Palmon | 3 | 51 25 58 24 49 | -/1/-/-/1/1 | 0 | 15 | 44/-/-/-2/0 | 00 | 500/1000/50/50/50/100 |
| 47 | Monochromon | 4 | 12 27 | 100/-/-/100/-/100 | 3 | 40 | -/-/-/5/35 | 11 | 2000/1500/150/250/150/200 |
| 48 | Leomon | 4 | 40 13 | -/-/100/-/100/100 | 1 | 20 | -/-/-/10/35 | 10 | 1500/1500/250/150/200/200 |
| 49 | Coelamon | 4 | 61 | -/-/-/100/-/- | 3 | 30 | -/-/-/5/35 | 01 | 1500/1500/150/200/150/150 |
| 50 | Kokatorimon | 4 | 59 55 | 100/-/-/-/-/- | 3 | 30 | 45/-/-/-/28 | 00 | 2500/1500/100/150/150/150 |
| 51 | Kuwagamon | 4 | 60 55 | 100/100/100/-/100/- | 5 | 30 | 32/-/-/-/28 | 00 | 2000/2000/200/150/200/100 |
| 52 | Mojyamon | 4 | 26 13 | 100/-/-/-/-/- | 5 | 20 | -/-/-/5/28 | 01 | 2000/1500/150/150/150/150 |
| 53 | Nanimon | 4 | 56 | -/-/-/-/-/- | - | - | -/-/-/-/- | 00 | 0/0/0/0/0/10 |
| 54 | Megadramon | 5 | - | 300/500/500/300/400/400 | 10 | 55 | -/-/-/30/30 | 10 | 6000/6000/600/500/600/500 |
| 55 | Piximon | 5 | - | -/-/300/300/400/400 | 15 | 5 | -/-/95/-/25 | 00 | 3000/3000/500/500/600/600 |
| 56 | Digitamamon | 5 | - | 300/300/400/400/400/300 | 0 | 10 | -/-/-/100/49 | 10 | 5000/5000/600/600/600/500 |
| 57 | Penguinmon | 3 | 24 35 22 23 52 | -/1/-/1/-/1 | 0 | 15 | 16/-/-/-2/0 | 00 | 500/500/50/100/50/100 |
| 58 | Ninjamon | 4 | 55 27 13 | -/100/100/-/100/- | 1 | 10 | -/-/-/15/35 | 10 | 1500/2000/200/150/200/150 |
| 59 | Phoenixmon | 5 | - | 400/400/-/-/400/600 | 3 | 30 | -/100/-/0/40 | 11 | 6000/6000/400/400/600/600 |
| 60 | H-Kabuterimon | 5 | - | 700/-/400/600/400/- | 5 | 55 | -/-/-/0/40 | 11 | 5000/5000/500/500/500/500 |
| 61 | MegaSeadramon | 5 | - | -/400/500/400/-/400 | 5 | 30 | -/-/-/0/40 | 11 | 3000/6000/600/600/300/600 |
| 62 | WereGarurumon | 0 (sic) | - | 400/-/-/400/400/400 | 3 | 30 | -/-/-/0/49 | 11 | 6000/3000/300/600/600/600 |
| 63 | Panjyamon | 4 | - | (no row) | | | | | 2250/2250/375/225/300/300 |
| 64 | Gigadramon | 5 | - | (no row) | | | | | 9000/9000/900/750/900/750 |
| 65 | MetalEtemon | 5 | - | (no row) | | | | | 6000/7500/900/700/900/750 |

Ids 59..65 appear in no `to` list (except a garbage `{FE,...,00}` row containing 59): the Ultimates 59..62 are only
reachable if they are added to `EVOLUTION_PATHS`, and 63..65 only through items.

## Death and rebirth

- **Losing a life**: 12 h sick, or losing a battle (`script_interp.c:1845`; with `lives == 0` it also sets
  `remainingLifetime = 0`). In both cases, and in a natural death, MAPHEAD section 0x4DE runs and chains the states:
  tamer 17/19 (`tamerTickSicknessLostLife` / `tamerTickBattleLostLife`) → MURD overlay: iris over the partner, box with
  the remaining lives (`MURD_renderLivesBox`), death map (`setDeathMap`: screen 0xCD when trigger 0xDC or 0xD6 is set
  or prosperity >= 50, otherwise 0xDA; see [world.md](world.md)); with 0 lives it loads DOOA. Script routine 3 → state 8
  (`partnerTickDying`): DOOA dissolve, then lifetime = 360, `sicknessTimer = injuryTimer = 0` (this is how losing a
  life cures).
- **Rebirth**: routine 0x1D opens the egg box (`DOO2_openEggBox`) and 29 waits for the choice (left/right among 4);
  then routine 4 → state 14 (`partnerTickDying2`) → `DOOA_getSequenceState`: **if `lives == 0` the egg is replaced by
  `rand() % 4`** (death by battle or sickness with no lives left gives a random egg; a natural death keeps the chosen
  one). `DOOA_tickRebirth` calls `reincarnatePartner` with `REINCARNATE_BABY_TYPE[eggSlot]`.
- `reincarnatePartner`: `DEATH_STATS = stats`, equipped techniques cleared (`moves[0] = 0x2E`), new entity via
  `initializeReincarnatedPartner`: the baby's base stats (Botamon 90/110/10/11/9/10, Punimon 120/100/16/8/8/6, Poyomon
  100/140/12/6/6/8, Yuramon 100/120/8/8/8/8) **plus `tamerLevel` % of `DEATH_STATS` only if `IS_NATURAL_DEATH == 1`**
  (`setReincarnateStats`); 3 lives, lifetime 360, age 0, happiness and discipline 50, `evoTimer = 0`, default weight,
  `raisedCount++` (<= 99), the raised trigger. Kept: `learnedMoves`, `fishCaught`, the `upgrade*` counters, items, money,
  triggers and the name.
- **Tamer level** (`addTamerLevel(chance %, ±1)`): +1 on reaching Champion (20 %) / Ultimate (100 %) without an item, +1
  for raising all 61 (medal 6), 5 % each year with happiness 100; -1 on missing sleep or a wild poop (1 %), 10 % each year
  with happiness < 0. It is the percentage inherited on rebirth. The mod makes these chances data (patch 0121).

## Learning techniques

- **In battle** (`battleMoveLearning`, `battle_ui.c:206`): at the end, for each normal technique (id < 0x3A) that **the
  enemies** used (`usedMoves`, up to 12) and that the partner lacks, whose specialty matches one of the species' three
  (`DigimonPara.special[j]`) and which is in its list of 16 (`DigimonPara.moves`): it qualifies if
  `MOVE_LEARN_CHANCES[id][j] > rand(100)` (j = 0 main, 1 secondary, 2 tertiary; for example Fire Tower 25/16/11 %,
  Spit Fire 30/22/15 %). If several qualify, **one** of them is learned at random.
- **Brains training** (`TRN_awardBrainsTrainingGains`): on crossing 150, 250, 350, 450, 550, 650, 750, 800, 850, 900,
  950 or reaching 999 Brains (exactly 999 in the original; crossing 999 with the caps patch), `TRN_tryLearnMove`: for
  each specialty, the first technique in `TRN_D_8008F14C` (8 per specialty) that the partner lacks and can learn, with
  weight `TRN_D_8008F184[k][i]` (main 25/22/20/18/15/12/10 %..., tertiary 10/8/7/5/2/0); the highest weight is kept and
  learned if `weight > rand(100)`. On crossing 100/200/300/400/500 it teaches battle commands instead.
- **On evolving**: the weakest technique of the main specialty (above). At birth (`initializePartner`): Agumon Spit Fire,
  Gabumon Blaster. Scripts give and take techniques (`LEARN_MOVE`, `unlearnMove`).

## Number limits and the caps patch

Original limits: Offense/Defense/Speed/Brains 999, max HP/MP 9999, one training gain 999, one hit and `hpDamageBuffer`
9999 ([combat.md](combat.md)). The caps patch (0059) raises them to **9999 for the four stats and 30000 for HP, MP and
damage**. Every field stays an `int16_t` (partner, NPC entities, `COMBAT_DATA`, `INITIAL_COMBAT_STATS`, `STATS_GAINS`,
`DIGIMON_DATA`, the save), so saves keep their layout: 30000 leaves room in an int16 for one more sum before the clamp.
Going higher would mean widening the `Stats` struct (every entity and overlay), the battle tables and the save. The
limits live in `include/dw/caps.h` (`STAT_CAP`, `HPMP_CAP`, `DAMAGE_CAP`).

| Place | Original | Caps patch |
|---|---|---|
| `addWithLimit`, script `ADD_STAT`, post-battle/training totals, `EVL_scaleBaseStats` | sum into the int16, then clamp | sum in 32 bits, then clamp (30000 + 9999 would wrap) |
| `STATS_LIMIT_ARRAY` (script `SET_STAT`/`ADD_STAT`), items/chips/food, `EVL_clampBaseStats`, buff disks, battle buffs (`BTL_buffStats`) | 999 / 9999 | 9999 / 30000 |
| Training gain per session | 999 | 9999 |
| Full heals (`HEALING_VALUES[3]`, Restore, food worth 9999) | +9999 | the whole bar when it is longer than 9999 |
| Medal 7 (`tamer.c`) | every stat `==` 999/9999 | `>=` |
| Brains MP discount (`== 999` → 20 %) and the training technique at 999 Brains | exactly 999 | 999 or more / crossing 999 |
| `finisherGoal = 3000 - speed` | >= 2001 | past speed 999 it falls ten times slower (1101 at 9999), never 0 |
| `buffPrioTimer = brains/10 + 5` | <= 104 | Brains counted up to 999 |

Displays: number boxes widen only when a value needs a fifth digit and keep their right edge (status screen, post-battle
and training boxes, enemy HP; the tournament intro's grow to the right); the battle HUD packs a five-digit HP/MP 6 px
apart; stat bars are full at the old limit; a large gain still counts up one by one (✕ skips). Not covered: VS mode
clamps an imported partner to 999/9999, and tournament rivals are generated with the old caps.

## Writing state by hand

Facts that matter when partner RAM is edited from outside (recipes are in [../developing.md](../developing.md)):

- `tickConditionBoundaries` clamps happiness, discipline, tiredness, energy and weight every frame, and
  `EVL_clampBaseStats`/`addWithLimit` clamp stats when the game touches them; a value written out of range stays until
  something recomputes it. Writing with the clock stopped (a menu open) avoids races.
- Condition bits are set and cleared by their ticks: setting `foodLevel = 0`, `poopLevel = 0` or `sleepyHour = HOUR`
  makes the next tick raise the condition properly.
- Do not write the species id at `PARTNER_ENTITY+0`: the loaded model does not change. A forced evolution writes
  `EVOLUTION_TARGET` and puts the partner in state 13 and the tamer in state 6, which is what `handleEvoItems` does;
  `EVOLUTION_STATS_GAINS[id].target` decides the species actually reached.
- The immortal hour after sleeping (`HAS_IMMORTAL_HOUR = 1`) blocks death and life loss for that hour.
- `STATS_LIMIT_ARRAY` only limits scripts; `SET_STAT` id 0x16 (lives) reads past the 22-entry table.
- `PARTNER_PARA` is saved whole, so any write survives a save.

Unverified: what `happinessDelta` holds when scolding with `ITEM_SCOLD_FLAG == 1` (a leftover register); in US
`partnerTickPraiseScold` calls `handlePraiseScold()` with no argument and works because `$a0` still holds the state
`[inferred]`.
