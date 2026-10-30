# Combat: wild battles, arena and techniques

How battles work in the original engine: the two battle overlays, the fighter state in memory, the technique table,
target and technique choice, hit chance and damage formulas, statuses, finishers, fleeing, rewards, and the
tournament arena. Source: the decompilation; `file.c:line` citations are into `decomp/src/` at the pinned
submodule commit, RAM addresses from `decomp/config/us/symbols*.txt` (original USA executable). A *tick* is one pass of
`BTL_battleTickFrame` (`VSync(3)`, about 20 per second on NTSC).

## Summary

- There are two nearly twin engines: `BTL_REL.BIN` (wild battles, on the
  map) and `STD_REL.BIN` (arena/tournament, on its own stage). They load at the
  same address and share the executable's structures (`CombatData`,
  `MOVE_DATA`, `TYPE_FACTORS`...). The hit, damage, status and finisher logic
  is identical in both; they differ in the start, the commands and the end.
- Combat is real-time: every tick each fighter (partner + up to 3
  enemies) decides, moves, launches techniques; hits arrive as
  `AttackObject`s from the effects engine (EFE) and are resolved in
  `BTL_tickAttackHits`. Damage is not subtracted at once: it goes to
  `hpDamageBuffer` and `damageTick` drains it from the bar drawing code.
- Damage formula: `(P + (Off−Def)·P/500) · elemental_mult · 0.9–1.1`, with
  `Off−Def` clamped to ±500 and `mult` the average of the type table over the
  defender's (up to 3) specialties. Finisher: `(Off + P) · mult`, ×up to
  2 from the player's charge (or ×1–2 random for an enemy).
- The partner obeys by *brains* (number of commands) and *discipline* (disobeys
  when brains < 301). Techniques cost `mpCost×3` MP (the menu already shows
  ×3), with a discount at brains ≥ 700 and a ×1.5 surcharge when sick/injured.
- On victory: bits (sum of `NPC_ENTITIES[].bits`), items (`dropChance`),
  stat gains computed against the strongest enemy, possible learning
  of a technique used by the enemy, possible injury, +20 minutes of clock.
- Tournament: 8 participants, 3 matches against rivals generated from
  `STD_OPPONENT_BASE_STATS[cup]` ±30 % and ×1/×2/×2.5 by level; 99 s
  timer; when it expires whoever has taken less damage wins; draw = defeat.

## Source files

| File | What it contains |
|---|---|
| `src/main/btl.c` | `handleBattleStart` (who joins), `loadBattleData` (overlay load, music, EFE), flee bubbles, `FLEE_CHANCES` table |
| `src/main/battle_tick.c` | player/partner/NPC ticks during combat, `handleCommands` (command menu), `handleFleeing` |
| `src/main/battle_ui.c` | end of battle: `handleBattleEndBox`, `battleStatsGainsAndDrops`, `battleMoveLearning`, `handleBattleInjury`, bits and stats boxes |
| `src/main/tamer.c:795` | `startBattle`: orchestrates everything and applies the consequences (happiness, discipline, tiredness, time) |
| `src/main/script_interp.c:1821` | opcode `START_BATTLE` (0x66): script-predefined battles, defeat → lives, flee → previous map |
| `src/main/tournament.c` | registration (`updateTournamentRegistration`), medals, access to the script's cup data |
| `src/main/utils2.c:566` | `startTournament`: picks the 7 rivals, loads `STD_REL`, tallies the result |
| `src/main/item.c:93` | `TYPE_FACTORS[7][7]` and `MOVE_LEARN_CHANCES[58][3]` (the data lives in the executable) |
| `src/main/utils.c:86` | `damageTick`: drains `hpDamageBuffer` into `currentHP` |
| `src/btl/battle_main.c` | the wild engine: `BTL_battleMain`, AI, distances, hit chance, damage, statuses, finisher |
| `src/btl/battle_setup.c` | `BTL_initializeCombat` (commands by brains, `INITIAL_COMBAT_STATS`), intro, `BTL_isBattleFinished` |
| `src/btl/battle_hud.c` | bars, finisher meter, finisher charge (L1/R1), death countdown, end texts |
| `src/btl/command_menu.c`, `command_shout.c` | command menu and the player's shout |
| `src/btl/battle_effect.c` | EFE engine (technique effects, particles, auras); not detailed here |
| `src/std/std_setup.c` | `STD_tournamentMain`, `STD_initializeOpponent` (rival stats), `STD_OPPONENT_BASE_STATS`, grades |
| `src/std/std_main.c` | arena engine: `STD_combatMain`, `STD_checkEndCondition` (timer/draw), bracket (`STD_setupParticipants`, `STD_WIN_CHANCES`), camera |
| `src/std/std_hud.c`, `std_effect.c` | arena HUD and effects |
| `src/dget/dget.c` | `DGET_REL`: registration screen (calendar, requirements, eligibility) |
| `include/dw/combat.h`, `move.h`, `entity.h`, `btl.h`, `std.h`, `tournament.h`, `attack_object.h` | structs |
| `BTL_REL.BIN`, `STD_REL.BIN` (and `VS_REL.BIN`) | file at `0x80052AE0`, `MWo1` header at `0x80056C68`, code from `0x80056CA8` |
| `DGET_REL.BIN` | `0x80080800` (registration screen) |

Overlays (`config/us/overlay.ld`, `utils2.c:375`): `BTL_REL.BIN`, `STD_REL.BIN`
and `VS_REL.BIN` are read whole at **`0x80052AE0`**; the first 0x4188
bytes are the TIM and TMD of the finisher aura (`0x80052AE0`/`0x80053800`),
the confusion model (`0x80054838`), the stun model (`0x80054D00`) and the
buff model (`0x80055328`) (`btl.c:23-27`); the `MWo1` header ends up at
`0x80056C68` and the code starts at
`0x80056CA8` (`BTL_initializeCombat`). `DGET_REL.BIN` loads at `0x80080800`.
The addresses in `symbols_btl.txt` and `symbols_std.txt` overlap: they are
only valid while that overlay is loaded.

## State in memory

State machine and global variables (all in the executable, bss):

| Symbol | RAM | Type | Meaning |
|---|---|---|---|
| `GAME_STATE` | `0x80134F0A` | i8 | 0 world, 3 loading battle, 1 wild combat in progress, 2 menus/end of battle, 4 arena combat, 5 arena outside combat (`btl.c:379,491`, `battle_setup.c:328`, `std_main.c:3661,3744`) |
| `COMBAT_DATA_PTR` | `0x80134D4C` | ptr | → `COMBAT_DATA`; all code goes through it |
| `COMBAT_DATA` | `0x8013D640` | 0x684 | `CombatData`: `fighter[4]` (0x168 each) + `player` at +0x5A0 (see below) |
| `INITIAL_COMBAT_STATS` | `0x8013D610` | i16[4][6] | hp, mp, off, def, speed, brains of each fighter at the start; [0] = partner |
| `STATS_GAINS` | `0x8013D468` | i16[6] | pending gains after victory (same order) |
| `ENEMY_COUNT` | `0x80134D6C` | i16 | enemies in the battle (1–3) |
| `BATTLE_FRAME_COUNT` | `0x80134D66` | i16 | ticks since the start (starts at 1) |
| `FLEE_TIMER` | `0x80134D68` | i16 | ticks fleeing; ≥ 0x29 ends the battle |
| `DEATH_COUNTDOWN` | `0x80134D6A` | i16 | ticks with the partner down; at 0x14 the countdown appears, at 0xAB defeat |
| `FINISHING_ENTITY` | `0x80134D60` | ptr | entity that is launching a finisher (the rest freeze) |
| `NO_AI_FLAG` | `0x80134D74` | i32 | 1 while a finisher is in progress: AI and timers stop |
| `HAS_TAKEN_DAMAGE` | `0x80134D70` | i32 | the partner has taken damage (condition for injury) |
| `IS_TAMERLESS_BATTLE` | `0x80134D78` | i32 | = trigger 2: no player, no commands (`battle_tick.c:65`) |
| `FLEE_DISABLED[0]` | `0x80134D7C` | i32 | = trigger 1: boss battle, no «Run», everyone on screen joins, enemies spend no MP |
| `FLEE_DISABLED[1]` | `0x80134D80` | i32 | misnamed: global 110-tick lock after an area technique (`battle_main.c:2469,2487`) |
| `IS_PREDEFINED_BATTLE` | `0x80134E84` | u8 | = PStat 0xFA: the enemies are set by the script (PStats 0xFB–0xFD) |
| `BATTLE_TOGGLE_LIFEBAR` | `0x80134D64` | u8 | Select toggles the enemy life bars |
| `BATTLE_ATTACKING_DIGIMON` / `BATTLE_TARGETED_DIGIMON` | `0x80134EF8` / `0x80134EF4` | ptr | who attacks and whom, for the EFE engine |
| `BTL_FINISHER_TIMER` / `BTL_FINISHER_AURA_ID` / `BTL_SAVED_CHARGE_MODE` | `0x80135080` / `0x8013507C` / `0x80135078` | i32, i32, u8 | 0x50-tick aura before releasing the finisher; partner's `chargeMode` on entry (restored on exit) |
| `BATTLES_STARTED` / `BATTLES_FLED` / `BITS_TO_GAIN` / `MONEY` | `0x80134FC8` / `0x80134FCA` / `0x80134E90` / `0x80134EB8` | u16, u16, u16, u32 | counters (cap 9999); bits being counted in the victory box; bits (cap 999 999) |
| `TOURNAMENTS_WON` / `TOURNAMENT_WINS` / `TOURNAMENTS_LOST` | `0x80134FCC` / `CE` / `D0` | i16 | cups won / arena matches won / cups lost |
| `STD_TIMER` | `0x80135110` | u8 | arena timer (99 → 0, −1 every 20 ticks) |
| `STD_STARTING_HP[2]` / `STD_DAMAGE[2]` | `0x801350FC` / `0x80135100` | i16 | starting HP and damage taken, decide the *time-out* |
| `STD_MATCH_RESULT` | `0x801350E4` | i16 | 1 won, −1 lost |
| `STD_PLAYER_SLOT`, `PARTICIPANT_TYPES[8]`, `STD_ROUND1_WINNERS[4]`, `STD_ROUND2_WINNERS[2]` | `0x8013514D`, `0x80135150`, `0x80135158`, `0x8013515C` | u8 | the tournament bracket |
| `DGET_BUFFER`, `TOURNAMENT_SELECTED_COLUMN/ROW` | `0x801353A8`, `0x801353AC/AD` | ptr, u8 | registration screen (5 days × 6 cups; bit 7 = eligible, bit 6 = «overlevel») |
| `SCRIPT_STATE.triggers` | `0x801BDFCD` | u8[100] | bit *n* = byte n/8, bit n%8: 1 boss, 2 no player, 15–36 cup won, 37 registered, 38/39 notices, 40 overlevel, 200+id species recruited |
| `SCRIPT_STATE.pstats` | `0x801BE031` | u8[256] | PStat 2 tournament day (bit 7 = tomorrow), 3 cup, 4 registered species, 0xFA predefined, 0xFB–0xFD entity ids, 0xFF result (1 wins, 0 flees, −1 loses / number of matches won) |
| `ENTITY_TABLE` | `0x8012F344` | ptr[10] | [0] player (`TAMER_ENTITY` `0x8015576C`), [1] partner, [2..9] → `NPC_ENTITIES[0..7]` |

**Fighter block** (`DigimonEntity`, 0x58 bytes; `entity.h`). The
partner is `PARTNER_ENTITY` `0x801557A8`; enemy *i* is
`NPC_ENTITIES[i]` = **`0x80155828 + i·0x68`** (`NPCEntity`, 0x68 because it adds
the flee position and the map data). Offsets within the block:

| Off. | Type | Field | Notes |
|---|---|---|---|
| 0x00 | i32 | `type` | species (index into `DIGIMON_DATA`) |
| 0x04 | ptr | `posData` | → `PositionData` (`entity.h`: matrix, scale, rotation and `location`) |
| 0x08 | ptr | `animPtr` | |
| 0x0C–0x33 | | `anim` | 0x2E `animId` (0x21 idle, 0x22 tired idle, 0x23/0x24 walk, 0x25 block, 0x28/0x29 hit, 0x2A victory, 0x2B down, 0x2C get up, 0x13 disobey, ≥0x2E technique k = 0x2E+k), 0x30 `animFlag` (bit 0 = animation finished) |
| 0x34 | i8 | `isOnMap` | 0x35 `isOnScreen`, 0x36 `flatSprite`, 0x37 `flatTimer` |
| 0x38 | i16 | `base.off` | 0x3A `def`, 0x3C `speed`, 0x3E `brain` |
| 0x40 | u8[4] | `movesPrio` | enemy AI weights per slot (from the map; in the arena 30,30,30,0) |
| 0x44 | u8[4] | `moves` | **animation ids** (0x2E + index into `DIGIMON_DATA[type].moves`), FF empty; [3] = finisher. The technique is `DIGIMON_DATA[type].moves[anim − 0x2E]` (`entityGetTechFromAnim`) |
| 0x48 | i16 | `base.hp` | 0x4A `base.mp` |
| 0x4C | i16 | `currentHP` | 0x4E `currentMP` |
| 0x50 | i16 | `unk1` | technique in progress + 0x100 (−1 none) |
| 0x52 | i8 | `efeSubEffect` | 0x53 `isHit`, 0x54 `vabId` (voice bank 5–7), 0x56 `chargeMode` (0 attack, 1 normal, 2 moderate) |
| 0x58 | SVECTOR | `flee` | (NPC) where it escapes to; partner: `learnedMoves[2]` bits |
| 0x60 | i16 | `bits` | (NPC) bits it drops |
| 0x62 | u8 | `unk1` | (NPC) 1 = always attacks the partner; 0 = if another enemy's area technique hits it, 71 % of the time it turns against that enemy (`battle_main.c:3700`) |
| 0x64–0x67 | u8 | `unk2`, `scriptId`, `autotalk`, `unk5` | from the map (`overworld.c:1015-1037`) |
| 0x68 | char[20] | `name` | (partner only, `0x80155810`); 0x7C `lives` |

`COMBAT_DATA` (`combat.h`): `fighter[i]` at `0x8013D640 + i·0x168`
(0x8013D640, 0x8013D7A8, 0x8013D910, 0x8013DA78). Fields:

| Off. | Type | Field | Notes |
|---|---|---|---|
| 0x04 | i32[4] | `effectSlot` | EFE slot of each technique; 0x14 `activeEffectSlot` |
| 0x18 | i16 | `finisherGoal` | = 3000 − speed |
| 0x1A | i16 | `finisherProgress` | meter; full when = goal |
| 0x1C/1E/20 | i16 | `poisonTimer`, `confusionTimer`, `stunTimer` | remaining ticks |
| 0x22 | i16 | `flatTimer` | flattened: −1 pending, 0x41→0 animation, then 224–304 ticks |
| 0x26 | i16 | `invulnerableTimer` | = `iframes` of the technique received |
| 0x28 | i16 | `cooldown` | 0x28 after attacking, 0x50 without MP |
| 0x2A | i16 | `senileTimer` | disobedience (100) |
| 0x2E | i16 | `hpDamageBuffer` | damage pending subtraction (cap 9999; 30000 with the caps patches) |
| 0x30 | i16 | `mpDamageBuffer` | pending MP (partner only) |
| 0x32 | i16 | `speedBuffer` | «energy»: 100 at the start, −power per technique, min −155, recharges |
| 0x34 | u16 | `flags` | `FIGHTER_FLAG_*`: 1 poison, 2 confusion, 4 stunned, 8 flattened, 0x10 hit, 0x20 attacking, 0x40 transforming/busy, 0x80 blocking, 0x100 protected (anti-status, set by an item, `item.c:2221`), 0x400 target locked, 0x800 charging, 0x1000 cooling down, 0x2000 disobeying, 0x8000 dead |
| 0x36 | i8 | `moveRange` | type of the queued technique (1 melee, 2 ranged, 3 area, 4 buff; −1 out of combat) |
| 0x37 | u8 | `targetId` | target fighter index (FF none) |
| 0x38 | u8 | `queuedAnim` | animation id of the queued technique |
| 0x39 | u8 | `buffsRemaining` | buffs it has left (brains/100 + 1, max 5) |
| 0x3A | u8 | `buffPrioTimer` | extra weight of buffs, decreases every 20 ticks |
| 0x3C | i8[150]×2 | `table1`, `table2` | hits from the same effect already blocked |

`player` at `0x8013DBE0`: `+0xA0` `hitCount` (`0x8013DC80`, attacks
completed by the partner), `+0xA2` `blockedCount`, `+0xA4`
`statusedCount`, `+0xA6` big hits taken (≥ 20 % max HP), `+0xA8`
`startingHP`, `+0xAE` `currentCommand[0]` (`0x8013DC8E`; rewritten every
tick from `bufferedCommand`, `battle_main.c:323`), `+0xB0`
`bufferedCommand[0]` (`0x8013DC90`, the one that counts), `+0xB2` `hoveredCommand[0]`, `+0xB4`
`availableCommands[0][9]`, `+0xC6` `numCommands[0]`, `+0xC8`
`finisherChargeup[0]` (`0x8013DCA8`), `+0xCA` `remainingChargeupTime[0]`,
`+0xCC` `entityIds[4]` (`0x8013DCAC`: `ENTITY_TABLE` index of each
fighter; [0] = 1), `+0xD4` `changeTarget`, `+0xD5` `usedMoves[12]` (techniques
< 0x3A used by the enemies, for learning).

Data in the executable: `MOVE_DATA` `0x8012623C` (122 × 16), `MOVE_NAMES`
`0x80126054`, `MOVE_LEARN_CHANCES` `0x80125FA4` (58 × 3), `TYPE_FACTORS`
`0x80125F70` (7 × 7), `FLEE_CHANCES` `0x8012BB14` (3 × 3),
`ENEMY_MUSIC_MAPPING` `0x8012BAE4`, `CONCAVE_SCREENS` `0x8012BB20`,
`STAT_GAIN_ENEMY_FACTORS` `0x801344D0`, `BRAIN_TO_COMMAND_MAP` `0x801346E0`,
`TARGET_ATTACKER_CHANCE` `0x801346E8`, `BTL_YOUR_CALL_{POWER,MP,WIDE}_PRIO`
`0x801346EC/F0/F4`, `TOURNAMENT_SCHEDULE` `0x80130198` (30 × 6),
`TOURNAMENT_NAMES` `0x801300E0`, `TOURNAMENT_GRADES` `0x8013013C`,
`TOURNAMENT_MEDAL_IDS` `0x8012BACC`, `ARENA_MAPS` `0x801345BC`. In the
STD overlay: `STD_OPPONENT_BASE_STATS` `0x800799B4`, `STD_WIN_CHANCES`
`0x8007A58C`, `STD_GRADES` `0x80079C24`.

## Techniques

`Move` (`move.h`), 16 bytes, 122 entries:

| Off. | Type | Field | Meaning |
|---|---|---|---|
| 0x00 | i32 | `distance` | range **squared** (map units); the technique is launched when `d² ≤ distance + (r_a + r_b)²` ±30 % (`battle_main.c:1348-1363`) |
| 0x04 | i16 | `power` | power; also how much `speedBuffer` drops when using it (`:2580`) |
| 0x06 | u8 | `mpCost` | cost ÷ 3 (the game multiplies by 3 everywhere, `:2346,2527`; the menu too, `game_menu.c:2353`) |
| 0x07 | u8 | `iframes` | invulnerability/stun ticks of the target hit (`:2157`) and duration of the particles |
| 0x08 | u8 | `range` | 1 melee, 2 projectile, 3 area (AI bonus with ≥ 2 enemies), 4 self buff |
| 0x09 | u8 | `special` | element: 0 Fire, 1 Battle, 2 Air, 3 **Nature**, 4 **Ice**, 5 Mech, 6 Filth (255 none) |
| 0x0A | u8 | `status` | 1 poison, 2 confusion, 3 stun, 4 flatten (`:3163-3194`) |
| 0x0B | u8 | `accuracy` | base accuracy (%) |
| 0x0C | u8 | `statusChance` | % chance of applying `status` if the hit lands |
| 0x0D | u8 | `unk3` | bit 0 (T): needs a target (not used without one, `:2342`); bit 1 (L): triggers the global 110-tick lock (`:2469`) |
| 0x0E–0x0F | u8 | `unk4`, `unk5` | always 0 |

Element 3 is Nature and 4 is Ice: Frigimon/Penguinmon/Whamon have specialty 4 and their techniques
Giga Freeze…Tear Drop have `special = 4`; Palmon/Vegiemon/Kunemon have 3
and Poison Powder…Green Trap have `special = 3`.

**Effectiveness** `TYPE_FACTORS[attack element][defender
specialty]` (`item.c:93`), ×0.1. Damage uses the average over the defender's three
specialties (empty ones count as 1.0), so a Digimon with
a single specialty receives `(m + 10 + 10)/30`:

| attack ↓ / defender → | Fire | Battle | Air | Nature | Ice | Mech | Filth |
|---|---|---|---|---|---|---|---|
| Fire | 1.0 | 1.5 | 0.5 | 2.0 | 2.0 | 1.5 | 2.0 |
| Battle | 1.0 | 1.0 | 0.2 | 1.5 | 1.0 | 1.0 | 0.5 |
| Air | 1.5 | 1.5 | 1.5 | 0.5 | 1.5 | 1.5 | 0.5 |
| Nature | 0.5 | 1.5 | 2.0 | 1.0 | 1.0 | 0.5 | 1.5 |
| Ice | 2.0 | 1.5 | 0.5 | 1.5 | 1.0 | 1.5 | 2.0 |
| Mech | 1.0 | 1.0 | 0.5 | 1.0 | 1.0 | 1.0 | 0.5 |
| Filth | 0.5 | 1.5 | 0.5 | 0.2 | 1.0 | 2.0 | 0.2 |

The same table, with each one's first specialty, gives the «element
bonus» the AI uses to weigh its techniques (20→10, 15→7, 10→5, 5→3, 2→1,
`battle_main.c:3570`) and the target score (`:3342`).

Full table, as stored in `SLUS_010.32` at offset `0x9623C`. `MP` is what
is paid (`mpCost×3`; the byte in parentheses). `rng.` = √`distance`. `inv.`
= `iframes`. Id ranges: 0–57 learnable (48 and 57 duplicate 44 and 55; 45
Counter is the counterattack), **58–112 finishers** (`0x3A–0x70`, checked
to be so throughout the code), 113–120 Bubble, 121 the projectile spat by a
flattened Digimon (`0x79`):

| id | name | elem. | type | pow. | MP | acc. | rng. | status (%) | inv. | flags | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Fire Tower | Fire | ranged | 155 | 81 (27) | 55 | 300 | stun 8 | 26 | T |  |
| 1 | Prominence Beam | Fire | ranged | 444 | 183 (61) | 75 | 800 | flat. 3 | 1 | — |  |
| 2 | Spit Fire | Fire | ranged | 66 | 30 (10) | 43 | 400 | — | 1 | — |  |
| 3 | Red Inferno | Fire | area | 210 | 171 (57) | 72 | 600 | — | 1 | — |  |
| 4 | Magma Bomb | Fire | ranged | 279 | 132 (44) | 50 | 800 | confusion 4 | 1 | T |  |
| 5 | Heat Laser | Fire | area | 84 | 105 (35) | 80 | 600 | flat. 32 | 1 | L |  |
| 6 | Inifinity Burn | Fire | area | 488 | 264 (88) | 79 | 400 | stun 11 | 26 | TL |  |
| 7 | Meltdown | Fire | area | 400 | 318 (106) | 86 | 600 | stun 24 | 1 | L |  |
| 8 | Thunder Justice | Air | ranged | 586 | 330 (110) | 85 | 600 | stun 32 | 1 | T |  |
| 9 | Spinning Shot | Air | ranged | 389 | 150 (50) | 77 | 800 | — | 1 | T |  |
| 10 | Electric Cloud | Air | ranged | 120 | 69 (23) | 60 | 900 | stun 9 | 1 | T |  |
| 11 | Megalo Spark | Air | ranged | 382 | 174 (58) | 68 | 400 | stun 23 | 1 | — |  |
| 12 | Static Elect | Air | melee | 85 | 45 (15) | 55 | 0 | stun 15 | 1 | — |  |
| 13 | Wind Cutter | Air | ranged | 178 | 93 (31) | 62 | 800 | — | 1 | T |  |
| 14 | Confused Storm | Air | area | 225 | 216 (72) | 87 | 400 | confusion 60 | 1 | TL |  |
| 15 | Hurricane | Air | area | 366 | 255 (85) | 73 | 400 | confusion 13 | 1 | L |  |
| 16 | Giga Freeze | Ice | ranged | 264 | 120 (40) | 65 | 200 | stun 10 | 5 | — |  |
| 17 | Ice Statue | Ice | ranged | 424 | 186 (62) | 79 | 700 | stun 38 | 17 | — |  |
| 18 | Winter Blast | Ice | area | 120 | 165 (55) | 90 | 600 | stun 15 | 1 | L |  |
| 19 | Ice Needle | Ice | ranged | 126 | 78 (26) | 50 | 800 | stun 5 | 1 | — |  |
| 20 | Water Blit | Ice | ranged | 211 | 102 (34) | 74 | 600 | — | 1 | — |  |
| 21 | Aqua Magic | Ice | buff | 0 | 36 (12) | 100 | 0 | — | 1 | T | Off +7 %, Def +8 %, Spd +7 % |
| 22 | Aurora Freeze | Ice | area | 430 | 258 (86) | 81 | 600 | flat. 24 | 1 | L |  |
| 23 | Tear Drop | Ice | ranged | 60 | 42 (14) | 44 | 400 | flat. 46 | 1 | T |  |
| 24 | Power Crane | Mech | ranged | 226 | 126 (42) | 53 | 700 | — | 1 | T |  |
| 25 | All Range Beam | Mech | area | 573 | 330 (110) | 81 | 600 | — | 1 | L |  |
| 26 | Metal Sprinter | Mech | area | 150 | 165 (55) | 78 | 500 | — | 1 | L |  |
| 27 | Pulse Laser | Mech | ranged | 389 | 168 (56) | 72 | 800 | — | 1 | T |  |
| 28 | Delete Program | Mech | ranged | 430 | 219 (73) | 65 | 800 | flat. 50 | 1 | T |  |
| 29 | DG Dimension | Mech | area | 722 | 420 (140) | 100 | 400 | — | 1 | — |  |
| 30 | Full Potential | Mech | buff | 0 | 99 (33) | 100 | 0 | — | 1 | T | Off +25 %, Def +15 %, Spd +15 % |
| 31 | Reverse Prog | Mech | ranged | 256 | 297 (99) | 100 | 700 | flat. 12 | 1 | T |  |
| 32 | Poison Powder | Nature | area | 117 | 171 (57) | 77 | 600 | poison 62 | 1 | L |  |
| 33 | Bug | Nature | ranged | 500 | 354 (118) | 80 | 800 | flat. 35 | 1 | T |  |
| 34 | Mass Morph | Nature | buff | 0 | 30 (10) | 100 | 0 | — | 1 | T | Def +20 %, Spd +10 % |
| 35 | Insect Plague | Nature | ranged | 58 | 96 (32) | 83 | 800 | poison 90 | 12 | T |  |
| 36 | Charm Perfume | Nature | area | 180 | 210 (70) | 75 | 600 | confusion 57 | 1 | L |  |
| 37 | Poison Claw | Nature | melee | 62 | 51 (17) | 60 | 0 | poison 40 | 1 | — |  |
| 38 | Danger Sting | Nature | melee | 157 | 102 (34) | 70 | 0 | flat. 26 | 1 | — |  |
| 39 | Green Trap | Nature | ranged | 310 | 147 (49) | 82 | 800 | stun 55 | 1 | T |  |
| 40 | Tremar | Battle | area | 178 | 168 (56) | 60 | 600 | — | 1 | L |  |
| 41 | Muscle Charge | Battle | buff | 0 | 66 (22) | 100 | 0 | — | 1 | T | Off +30 % |
| 42 | War Cry | Battle | buff | 0 | 42 (14) | 100 | 0 | — | 1 | T | Off +10 %, Def +5 %, Spd +10 % |
| 43 | Sonic Jab | Battle | melee | 52 | 18 (6) | 53 | 0 | — | 1 | — |  |
| 44 | Dynamite Kick | Battle | melee | 193 | 99 (33) | 62 | 0 | stun 3 | 1 | — |  |
| 45 | Counter | Battle | melee | 285 | 165 (55) | 100 | 0 | confusion 10 | 1 | — | counterattack: rival Def ×0.3; the AI never picks it |
| 46 | Megaton Punch | Battle | melee | 320 | 186 (62) | 70 | 0 | stun 9 | 1 | — |  |
| 47 | Buster Dive | Battle | ranged | 500 | 258 (86) | 80 | 600 | confusion 14 | 1 | — |  |
| 48 | Dynamite Kick | Battle | melee | 255 | 99 (33) | 90 | 0 | — | 1 | — |  |
| 49 | Odor Spray | Filth | ranged | 88 | 75 (25) | 37 | 100 | stun 10 | 1 | — |  |
| 50 | Poop Spd Toss | Filth | ranged | 122 | 96 (32) | 40 | 700 | poison 11 | 1 | — |  |
| 51 | Big Poop Toss | Filth | ranged | 211 | 192 (64) | 49 | 400 | confusion 17 | 1 | T |  |
| 52 | Big Rnd Toss | Filth | area | 211 | 282 (94) | 47 | 400 | confusion 20 | 1 | L |  |
| 53 | Poop Rnd Toss | Filth | area | 75 | 120 (40) | 33 | 400 | poison 9 | 1 | L |  |
| 54 | Rnd Spd Toss | Filth | area | 122 | 216 (72) | 50 | 500 | poison 10 | 1 | L |  |
| 55 | Horizontal Kick | Filth | melee | 53 | 24 (8) | 41 | 0 | — | 1 | — |  |
| 56 | Ult Poop Hell | Filth | area | 333 | 333 (111) | 100 | 600 | flat. 83 | 1 | L |  |
| 57 | Horizontal Kick | Filth | melee | 53 | 24 (8) | 41 | 0 | — | 1 | — |  |
| 58 | Blaze Blast | Fire | ranged | 174 | 120 (40) | 100 | 300 | — | 15 | — | finisher |
| 59 | Pepper Breath | Fire | ranged | 89 | 120 (40) | 100 | 400 | — | 1 | — | finisher |
| 60 | Lovely Attack | Battle | ranged | 230 | 120 (40) | 100 | 600 | — | 1 | T | finisher |
| 61 | Fireball | Fire | ranged | 155 | 120 (40) | 100 | 600 | — | 1 | — | finisher |
| 62 | Death Claw | Battle | melee | 180 | 120 (40) | 100 | 0 | — | 1 | — | finisher |
| 63 | Mega Flame | Fire | ranged | 196 | 120 (40) | 100 | 300 | — | 15 | — | finisher |
| 64 | Howling Blaster | Fire | ranged | 183 | 120 (40) | 100 | 300 | — | 15 | T | finisher |
| 65 | Party time | Filth | ranged | 100 | 120 (40) | 100 | 1000 | — | 1 | T | finisher |
| 66 | Electric Shock | Air | ranged | 92 | 120 (40) | 100 | 100 | — | 20 | T | finisher |
| 67 | Abduction Beam | Mech | ranged | 222 | 120 (40) | 100 | 600 | — | 1 | T | finisher |
| 68 | Smiley Bomb | Mech | ranged | 225 | 120 (40) | 100 | 600 | — | 1 | T | finisher |
| 69 | Spnning Needle | Air | ranged | 152 | 120 (40) | 100 | 600 | — | 1 | T | finisher |
| 70 | Spiral Twister | Fire | ranged | 91 | 120 (40) | 100 | 300 | — | 1 | T | finisher |
| 71 | Boom Bubble | Air | ranged | 85 | 120 (40) | 100 | 300 | — | 1 | T | finisher |
| 72 | Sweet Breath | Nature | ranged | 130 | 120 (40) | 100 | 600 | — | 1 | T | finisher |
| 73 | Bit Bomb | Nature | ranged | 232 | 120 (40) | 100 | 700 | — | 1 | — | finisher |
| 74 | Deadly Bomb | Mech | ranged | 260 | 120 (40) | 100 | 600 | — | 1 | T | finisher |
| 75 | Drill Spin | Battle | ranged | 150 | 120 (40) | 100 | 400 | — | 1 | T | finisher |
| 76 | Electric Thread | Air | ranged | 94 | 120 (40) | 100 | 200 | — | 1 | T | finisher |
| 77 | Energy Bomb | Mech | ranged | 214 | 120 (40) | 100 | 600 | — | 1 | — | finisher |
| 78 | Genoside Attack | Mech | ranged | 215 | 120 (40) | 100 | 800 | — | 1 | — | finisher |
| 79 | Giga Scissor Claw | Mech | ranged | 215 | 120 (40) | 100 | 800 | — | 1 | T | finisher |
| 80 | Dark Shot | Mech | ranged | 200 | 120 (40) | 100 | 800 | — | 1 | T | finisher |
| 81 | Pummel Whack | Battle | ranged | 170 | 120 (40) | 100 | 300 | — | 1 | — | finisher |
| 82 | Hand of Fate | Air | ranged | 166 | 120 (40) | 100 | 600 | — | 1 | T | finisher |
| 83 | Dark Claw | Air | melee | 143 | 120 (40) | 100 | 0 | — | 1 | — | finisher |
| 84 | Aerial Attack | Air | ranged | 153 | 120 (40) | 100 | 600 | — | 1 | T | finisher |
| 85 | Bone Boomerang | Ice | ranged | 148 | 120 (40) | 100 | 800 | — | 1 | T | finisher |
| 86 | Solar Ray | Air | ranged | 167 | 120 (40) | 100 | 600 | — | 1 | — | finisher |
| 87 | Hydro Pressure | Ice | ranged | 155 | 120 (40) | 100 | 800 | — | 1 | T | finisher |
| 88 | Ice Blast | Ice | ranged | 162 | 120 (40) | 100 | 700 | — | 1 | — | finisher |
| 89 | Iga School Knife Throw | Battle | ranged | 150 | 120 (40) | 100 | 600 | — | 1 | T | finisher |
| 90 | Blasting Spout | Ice | ranged | 150 | 120 (40) | 100 | 800 | — | 1 | — | finisher |
| 91 | Fist of the Beast King | Battle | ranged | 170 | 120 (40) | 100 | 300 | — | 1 | — | finisher |
| 92 | Dark Network & Concert Crush | Battle | area | 202 | 120 (40) | 100 | 400 | — | 1 | T | finisher |
| 93 | Electro Shocker | Fire | ranged | 170 | 120 (40) | 100 | 600 | — | 1 | T | finisher |
| 94 | Meteor Wing | Fire | ranged | 158 | 120 (40) | 100 | 600 | — | 1 | T | finisher |
| 95 | Super Slap | Ice | ranged | 91 | 120 (40) | 100 | 100 | — | 1 | — | finisher |
| 96 | Nightmare Syndromer | Fire | ranged | 222 | 120 (40) | 100 | 600 | — | 1 | — | finisher |
| 97 | Frozen Fire Shot | Fire | ranged | 159 | 120 (40) | 100 | 400 | — | 20 | T | finisher |
| 98 | Poison Ivy | Nature | melee | 101 | 120 (40) | 100 | 0 | — | 4 | — | finisher |
| 99 | Blue Blaster | Fire | ranged | 90 | 120 (40) | 100 | 600 | — | 1 | — | finisher |
| 100 | Scissor Claw | Battle | ranged | 172 | 120 (40) | 100 | 400 | — | 1 | T | finisher |
| 101 | Super Thunder Strike | Air | ranged | 100 | 120 (40) | 100 | 100 | — | 20 | — | finisher |
| 102 | Spiral Sword | Mech | ranged | 210 | 120 (40) | 100 | 300 | — | 1 | — | finisher |
| 103 | Variable Darts | Ice | melee | 153 | 120 (40) | 100 | 0 | — | 1 | — | finisher |
| 104 | Volcanic Strike | Fire | ranged | 160 | 120 (40) | 100 | 600 | — | 1 | — | finisher |
| 105 | Subzero Ice Punch | Ice | melee | 157 | 120 (40) | 100 | 0 | — | 1 | — | finisher |
| 106 | Infinity Cannon | Mech | ranged | 777 | 120 (40) | 100 | 1000 | — | 38 | T | finisher |
| 107 | Party time | Filth | ranged | 100 | 120 (40) | 100 | 1000 | — | 1 | T | finisher |
| 108 | Party time | Filth | ranged | 100 | 120 (40) | 100 | 1000 | — | 1 | T | finisher |
| 109 | Crimson Flare | Fire | ranged | 213 | 120 (40) | 100 | 600 | — | 1 | T | finisher |
| 110 | Glacial Blast | — | — | 0 | 0 (0) | 0 | 0 | — | 1 | — | finisher; empty entry |
| 111 | Mail Strome | Ice | ranged | 211 | 120 (40) | 100 | 600 | — | 1 | — | finisher |
| 112 | High Electro Shocker | Fire | ranged | 218 | 120 (40) | 100 | 600 | — | 1 | T | finisher |
| 113 | Bubble | Ice | ranged | 6 | 0 (0) | 2 | 400 | — | 1 | — | Bubble (Fresh/In-Training) |
| 114 | Bubble | Ice | ranged | 6 | 0 (0) | 2 | 400 | — | 1 | — | Bubble (Fresh/In-Training) |
| 115 | Bubble | Ice | ranged | 5 | 0 (0) | 2 | 400 | — | 1 | — | Bubble (Fresh/In-Training) |
| 116 | Bubble | Ice | ranged | 5 | 0 (0) | 2 | 400 | — | 1 | — | Bubble (Fresh/In-Training) |
| 117 | Bubble | Ice | ranged | 10 | 0 (0) | 2 | 400 | — | 1 | — | Bubble (Fresh/In-Training) |
| 118 | Bubble | Ice | ranged | 11 | 0 (0) | 2 | 400 | — | 1 | — | Bubble (Fresh/In-Training) |
| 119 | Bubble | Ice | ranged | 10 | 0 (0) | 2 | 400 | — | 1 | — | Bubble (Fresh/In-Training) |
| 120 | Bubble | Ice | ranged | 10 | 0 (0) | 2 | 400 | — | 1 | — | Bubble (Fresh/In-Training) |
| 121 | (unnamed; flattened projectile) | Ice | ranged | 10 | 0 (0) | 70 | 800 | — | 1 | — | id 0x79: spit while flattened |

## How it works

### Start of a wild battle

1. `startBattle(id)` (`tamer.c:795`): `GAME_STATE = 1`, saves the player's
   position, stops the clock (`stopGameTime`) and calls
   `handleBattleStart`, `loadBattleData` and `BTL_battleMain`. It is invoked by the
   script opcode `START_BATTLE` (`script_interp.c:1821`) with the entity
   that was talked to/bumped into (`TALKED_TO_ENTITY`); the world decides
   *when* ([world.md](world.md)); this section starts there.
2. **Who joins** (`handleBattleStart`, `btl.c:198`): enemy `id`
   always. If PStat 0xFA = 1 (predefined battle), the enemies are
   PStats 0xFB–0xFD (entity ids) and nobody else. Otherwise, every other Digimon on
   screen (`ENTITY_TABLE[2..9]`, `isOnMap && isOnScreen`) joins with
   probability `FLEE_CHANCES[partner type − 1][enemy type − 1]`
   (`btl.c:99`; misnamed, it is the *join* chance), up to 3 enemies:

   | partner ↓ / enemy → | Data | Vaccine | Virus |
   |---|---|---|---|
   | Data | 60 % | 70 % | 100 % |
   | Vaccine | 80 % | 60 % | 100 % |
   | Virus | 90 % | 100 % | 30 % |

   The roll (0–99) gets +20 if you carry *Enemy repel* (item 35) or
   −50 if you carry *Enemy bell* (36) (`btl.c:296-310`); it joins if roll <
   table. Trigger 1 (boss) forces roll = 0: everyone joins. On the 18
   «concave» screens (`CONCAVE_SCREENS`) line of sight from the
   player and the partner is also required. Those that don't join flee (flee bubble type 1).
3. **Loading** (`loadBattleData`, `btl.c:334`): music `playMusic(0x21, v)` with
   `v` = 0 predefined, 3 if the first enemy is Machinedramon (0x73), otherwise
   `ENEMY_MUSIC_MAPPING[type − 0x43]` (1 or 2) or 1; `loadDynamicLibrary(BTL_REL)`
   while frames keep being drawn; voice banks (`readVBALLSection`,
   enemy *i* → bank `i+4`); aura/confusion/stun/buff models;
   EFE engine and the effects of each equipped technique (`BTL_loadMoveEFE`); the
   techniques the model lacks are emptied (FF).
4. **Setup** (`BTL_initializeCombat`, `battle_setup.c:43`):
   `IS_TAMERLESS_BATTLE = trigger 2`; per fighter: `targetId = FF`,
   `speedBuffer = 100`, `buffsRemaining = brains/100 + 1` (4 if 400–599, 5 if
   ≥ 600), `buffPrioTimer = brains/10 + 5`, **`finisherGoal = 3000 − speed`**.
   Commands available by the partner's brains (`:124-181`):

   | brains | commands (in menu order) |
   |---|---|
   | < 100 | Finisher, Run, Your Call |
   | 100–199 | + Attack |
   | 200–299 | + Moderate |
   | 300–399 | + Change (target), Distance |
   | 400–499 | + Defensive |
   | ≥ 500 | Finisher, Run, Change, Defensive, Distance, technique 3, 2, 1, Your Call (Attack/Moderate disappear) |

   Everyone's stats are copied to `INITIAL_COMBAT_STATS` and, if the partner
   is injured or sick (`condition & 0x60`), it loses 20 % of Off, Def,
   Speed and Brains for the battle (`:195-201`).
5. **Intro** (`BTL_handleBattleIntro`): the player walks back along their
   *waypoints* to their origin tile or until ≥ 200 ticks, the Digimon
   that are not fighting leave the screen, «BATTLE» text and `GAME_STATE = 1`.

### The loop (`BTL_battleMain`, `battle_main.c:1832`)

Each tick, while `BTL_isBattleFinished() == 0`: `BTL_tickPartnerAI` →
`BTL_tickEnemyAI` → `BTL_tickFighterStates` → `BTL_tickPartnerWaypointTrail`
→ `BTL_battleTickFrame` (objects, render, `VSync(3)`) → `handlePause` →
`BATTLE_FRAME_COUNT++`. Inside `tickFighterStates` (`:648`): per fighter
+1 to the finisher meter, then **one** state according to its flags: attacking →
`tickAttackState`; hit/blocking → `tickHitState` (counts down
`invulnerableTimer`); if not out of combat: flattened, stunned,
confused, disobeying, charging (`tickChargeState`), cooling down
(`tickCooldownState`) or executing the queued technique (`tickQueuedMove`).
Then `BTL_tickAttackHits` (hit resolution) and `BTL_tickStatusEffects`.

**Commands** (`handleCommands`, `battle_tick.c:53`; ids in
`BTL_COMMAND_NAMES[cmd−1]`): 1 Run, 2 Attack, 3 Your Call, 4 Moderate, 5
Distance, 6 Defensive, 7 Change, 8–10 technique 1–3, 11 Finisher. Left /
right cycle through the menu (skipping Run if trigger 1), Cross confirms (no
effect if no enemies remain), Square launches the finisher if
`finisherProgress == finisherGoal`, Select toggles the bars, Triangle opens
the inventory (`battle_tick.c:249`). `commandDelay` is computed from
discipline and set to 0 right afterwards (`:135-141`): dead code, the
commands are immediate. Effect (`BTL_tickPartnerAI` `:372-513`,
`BTL_handlePartnerMoveCommand` `:1206`):

- *Attack*: most powerful technique (`selectMoveByPower`: power → effectiveness
  → random) and `chargeMode = 0` (attacks as soon as `speedBuffer > 0`).
- *Moderate*: the cheapest in MP and `chargeMode = 2` (waits for `speedBuffer
  = 100` while moving away).
- *Your Call* (and any other): the partner's own `chargeMode`
  (`BTL_SAVED_CHARGE_MODE`) and `selectPartnerMove` (`:3415`): weights per
  slot; mode 0 sorts by power with weights 50/20/5, mode 2 by MP
  50/20/10, mode 1 20 to each usable one; + element bonus against the target;
  buffs (`range 4`) weigh `buffPrioTimer` + bonus; area ones add
  `10·enemies` (mode 0) or `15·enemies` (1, 2) if brains ≥ 200 and there are ≥ 2
  enemies; with HP < 31 % in mode 2 it prefers the longest-range ones
  (`BTL_YOUR_CALL_WIDE_PRIO`). Weighted draw.
- *Distance*: moves away while `d² < enemy's maximum range + 640 000`
  (`:1231`). *Defensive*: stays still facing the target (`:1225`).
- *Change*: switches to the other enemy (or rotates among three without repeating, `:389`).
- 8–10: forces that technique if usable (`BTL_isMoveUsable`); 11: queues
  slot 3 (finisher).
- *Run*: see «Fleeing».

**Disobedience** (`:329-339`): if brains < 301, every `(brains/2 + 1)·20`
ticks the partner ignores everything for 100 ticks (anim 0x13) with probability
`(70 − discipline) %`. An enemy with brains < 301 does it with
`(300 − brains)/4 %` (`:546-552`).

**Partner's target** (`BTL_selectFighterTarget`, `:3686`): brains ≥ 300
→ an enemy with a status ailment; otherwise, the «weakest» by
`HP% + inverted_type_mult·Def/999·10` (`:3342`; 20↔2, 15↔5, lower = weaker),
switching only if it improves by ≥ 40;
brains ≥ 150 → the weakest, and keeps it; less → the nearest. On
taking a hit it switches to the aggressor with probability `TARGET_ATTACKER_CHANCE
[chargeMode] − discipline` (70/40/30 %) or if its target has fallen (`:1976`).

**Enemy AI** (`BTL_tickEnemyAI`, `:515`; `BTL_selectEnemyMove`, `:3804`):
on each decision `chargeMode` = 2 if it is off screen, otherwise 0 or 1 at
random; if its slot 3 is a finisher and the meter is full it launches it at the
partner (`:617-626`); otherwise, a draw with the map's `movesPrio[]` weights (+20 to
area ones if another enemy is alive and `unk1 == 0`; buffs +
`buffPrioTimer`); target is the partner unless it is «locked» (bit 0x400)
after being hit by another enemy (area): with `unk1 == 0` 71 % of the
time it turns against that enemy and 29 % it goes back to the partner (`:3700`,
`rand ≥ 71` → partner). No MP for anything: `chargeMode = 2` and 80 ticks
of cooldown.

**Distances** (`:1250-1376`, `:1601-1637`): positions in map units;
everything is compared squared. Melee: attacks when `d² ≤ (r_a +
r_b)²` (`radius` from `DIGIMON_DATA`), otherwise walks towards the target with
collision (`entityCheckCollision(…, 0x118, 0xC8)`). Ranged: ideal zone
`D = distance + (r_a + r_b)²`; if `d² > 1.3·D` it approaches, if `d² < 0.7·D` it
backs away (`backAwayFromTarget` looks for a free rotation), otherwise it fires; after
80 ticks approaching without arriving it fires anyway (`unk15`, `:1337`).
While charging/cooling down, mode 0/1 keeps `d²` between contact + 0 and contact
+ 480 000 (walking: between +160 000 and +320 000), mode 2 moves away.

**Executing a technique** (`BTL_setupQueuedMove` `:2386`,
`BTL_applyChargeRequirement` `:2400`, `BTL_startQueuedMove` `:2421`,
`BTL_setupMoveExecution` `:2494`): `queuedAnim` and `moveRange` are queued;
it enters charging if `speedBuffer ≤ 0` (mode 0), `< power` and ≠ 100 (mode 1) or
`< 100` (mode 2). `speedBuffer` rises `speed/100 + 1` every 2 ticks up to 100
(`:1639`) and drops by `power` on firing (min −155). On firing: cost
`mpCost·3`; the partner pays ×1.5 if injured/sick and with brains ≥ 700
gets a discount of 5 % (700–799), 10 % (800–899), 15 % (900–998) or 20 % (999); an
enemy pays `mpCost·3` except in boss battles (trigger 1, spends nothing) and its
technique (< 0x3A) is recorded in `usedMoves` for learning; a buff
spends one `buffsRemaining`; area ones lock out any other area one
for 110 ticks. If the target is in a hit animation (0x28/0x29) it
waits. After completing the attack: `cooldown = 40` ticks, `hitCount++`
(partner) and +4 % of meter (`:1551-1559`). `Counter` (0x2D) is never
chosen: it only fires as a counterattack (below).

**Hit chance** (`BTL_calculateHitChance`, `:1922`; `fighter` is the *defender*):
100 % if the defender is Fresh/In-Training (`level < 3`), is stunned,
flattened or disobeying, if the **partner is sick** (`condition &
0x40`, applies to every hit in the battle), if the defender has
`speedBuffer ≤ 0` or is in the middle of a technique (`animId ≥ 0x2E`); finishers
always hit and break blocking. 0 % if it is blocking. Otherwise:

    x = acc/2 · (Speed_def − Speed_att/10) / 999   (×1.2 if the defender is standing still)
    (with the mod, patch 0110: the difference Speed_def − Speed_att/10 is limited to ±999 first, so stats past 999 under
    the caps cannot saturate the hit chance; for the disc's stats the result is the same)
    hit = clamp(acc − x, 0, 100)

**Damage** (`BTL_calculateDamage`, `:1988`), with `m` = sum of
`TYPE_FACTORS[elem][spec_i]` over the defender's 3 specialties (10 for the
empty ones):

    normal:   dmg = m · (P + clamp(Off − Def, −500, 500) · P / 500) / 30 · rand(90..110) / 100
    counter:  same, with Def · 0.3
    finisher: dmg = (Off + P) · m / 30            (no Def term)
              × chargeup/40 if it is the partner and chargeup ≥ 41 (up to ×2)
              × rand(100..200)/100 if it is an enemy
              × rand(90..110)/100
    always:   1 ≤ dmg ≤ 9999   (30000 with the caps patches)

The damage goes to `hpDamageBuffer` (cap 9999), which `damageTick` (`utils.c:86`)
subtracts from `currentHP` at 900+80+6+1 per frame from the bar drawing code
(the caps patches add a 9000 step while it holds more than 9999);
`BTL_isFighterDefeated` already counts `currentHP − hpDamageBuffer ≤ 0`. A hit
that lands: `HAS_TAKEN_DAMAGE = 1`, recoils/turns towards the impact (0x28
from the front, 0x29 from behind, `:3093`), `invulnerableTimer = iframes`, floating
text, and `BTL_applyMoveStatus` (`:3149`): with `statusChance %` it applies
poison (1–3 % of max HP every 100 ticks; it does not expire: only an item
or fainting removes it, `BTL_clearPoison` `:2745`), confusion
(200–300 ticks: 70 % no target, random technique and turning), stun
(200–240 ticks without acting) or flattening (65 ticks of animation and 224–304
ticks as a pancake: it only spits projectile 0x79 every 40 ticks); bit
0x100 (`PROTECTED`, item) prevents it. A missed hit against someone who
is not blocking (`:2162-2224`): if the technique was melee and the defender
has `Counter` equipped and ≥ 165 MP, it counterattacks with probability
`speed/level %`; otherwise it blocks (anim 0x25, 3 ticks invulnerable): a blocked
melee hit still deals `dmg · rand(10..30) %`, the defender gains
+6 % of meter, the attacker +8 % and `blockedCount++` if it is the partner.

**With the caps patches** (the `caps` series merged as patch 0059: stats 9999, HP/MP and
damage 30000; [partner.md](partner.md)): the `±500` clamp on `Off − Def`
stays, so a normal hit is still at most `m·2P/30` (a few hundred) whatever
the stats; damage past 9999 comes from finishers, `(Off + P)·m/30` ×2 at full
charge (Off 9999: ~11 000–22 000 against Native Forest's ModokiBetamon). The
hit-chance `/999` is unchanged too: a defender with Speed far above 999 is
almost never hit (`hit` clamps to 0), and the target choice still weighs
`Def·100/999`. Overflows were the real limit: `hpDamageBuffer += dmg` is now
summed in 32 bits before the clamp, as are the post-battle stat totals, and a
stat gain is capped at the stat's limit.

**Finisher**: meter `finisherProgress/finisherGoal` (goal = 3000 − speed;
+1 per tick, +4 % per own attack completed, +6 % for blocking, +8 % if you
get blocked), only if slot 3 is a finisher (`:2614`). Full: the player
presses Square (`:176-185`) or the enemy uses it on its own. On launching it
(`:1279-1292`, `:2435-2449`): `NO_AI_FLAG = 1`, `FINISHING_ENTITY`, an aura of
0x50 ticks during which nobody else acts and the status timers don't
run, and for the partner the **charge**: 0x50 ticks in which each
press of L1 or R1 adds 2 to `finisherChargeup` (max 80, `battle_hud.c:312`);
it counts in the damage if ≥ 41 (×1.025 … ×2). The launcher's meter goes back to 0.

**Buffs** (`BTL_applyBuffMove`, `:1887`, by technique id): Muscle Charge
Off +30 %; War Cry Off +10 %, Def +5 %, Speed +10 %; Mass Morph Def +20 %,
Speed +10 %; Aqua Magic Off +7 %, Def +8 %, Speed +7 %; Full Potential Off
+25 %, Def +15 %, Speed +15 % (cap 999; 9999 with the caps patches). Disks/chips thrown by the
player (`handleBuffDisks`, `main.c:4231`) add +20/+50 up to 130 % of the
initial stat. Everything is lost when the battle ends (`resetStatsAfterCombat`).
**Items**: the thrown item flies for 24 frames and calls
`ITEM_FUNCTIONS[type]` (`main.c:4217`); with an item in the air the death
countdown stops (`battle_setup.c:366`). Details in [items-and-menus.md](items-and-menus.md#using-an-item).

### Fleeing and the end

- **Run** (`battle_tick.c:143-166`, `:188`): `currentCommand = 1`; the
  player walks back along their waypoints to the origin tile and faces the exit
  (`MAP_WARPS[CURRENT_EXIT]`); the partner runs towards the player
  (`:1216-1224`). `FLEE_TIMER` counts; at 0x14 it fades to black, from 0x13
  on no more hits are taken (`:2111`) and at **0x29 (41 ticks)** the battle
  ends if the partner is still alive (`battle_setup.c:338`). Result 0.
- **Defeat**: with `currentHP == 0` the partner falls (anim 0x2B,
  `BTL_faintDigimon`); `DEATH_COUNTDOWN` rises every tick with no item in the
  air, at 0x14 the clock appears and at **0xAB (171 ticks)** it ends
  (`battle_setup.c:365-376`). Result −1. A revive item in time
  sets anim 0x2C and clears the death (`:342-363`).
- **Victory**: all enemies in 0x2B with the animation finished and the
  partner alive (`:378-389`). Result 1.
- `BTL_deinitializeCombat` (`battle_main.c:739`): restores `chargeMode`, removes
  effects and items, gives each **enemy** back its initial HP/MP and stats
  (they heal fully, also after a flee), and if it was neither a flee nor a
  defeat runs `BTL_handleVictorySequence` (`:868`): sound, victory
  pose, `handleBattleEndBox`, the enemies get up (0x2C) and flee off
  screen (in a boss battle they stay).
- `handleBattleEndBox` (`battle_ui.c:280`): `BITS_TO_GAIN` = Σ
  `NPC_ENTITIES[].bits`; `battleStatsGainsAndDrops`; injury; new
  commands/MP texts; `battleMoveLearning`; stats and bits boxes (Cross or
  Triangle skips the count); `spawnDroppedItems`; `resetStatsAfterCombat`.

**Stat gains** (`battleStatsGainsAndDrops`, `battle_ui.c:110`), per
stat (hp, mp, off, def, speed, brains), with `E` = the highest value among the
enemies at the start, `P` the partner's, `F = {10, 12, 16}[enemies − 1]`:

    if E ≥ P:  gains ⌈E·F / (P·10)⌉        (P = 0 counts as 1)
    if E < P:  gains 1 with probability E·F·100 / (P·10) %

Stats left at 0 get a second chance of +1: HP with
`% of HP lost`, MP and Off with `hitCount·10 %`, Def with `big hits·10
%`, Speed with `blockedCount·10 + HP lost/2 %`, Brains with `(hitCount +
big hits)·5 %`. They are added to `INITIAL_COMBAT_STATS[0]` (caps 9999 / 999)
and from there to the real stats (30000 / 9999 with the caps patches). **Items**: per enemy, `dropChance >
rand(100)` drops `dropItem` (`DIGIMON_DATA`), never on screen 0x8F.
**Injury** (`handleBattleInjury`): if it took damage and was not injured, with
probability `tiredness − HP% %` it sets `condition |= 0x20`. **Techniques**
(`battleMoveLearning`, `:206`): of each technique an enemy used
(`usedMoves`) that the partner doesn't know, if its element matches the
partner's specialty *j* and it is in `DIGIMON_DATA[partner].moves[16]`,
it is a candidate with `MOVE_LEARN_CHANCES[technique][j] %`; **one** of the
candidates is learned at random. The probability table is `MOVE_LEARN_CHANCES` ([partner.md](partner.md)).

Consequences (`tamer.c:811-833`, `script_interp.c:1841-1866`): win →
happiness +2, tiredness +5 (+10 for every 10 % of max MP spent, formula broken
in vanilla: `partner_impl.c:2020`), food −15, `battles++`; flee →
happiness −10, discipline −6, tiredness +2 and the above, `BATTLES_FLED++`,
returns to the previous screen; lose → happiness −30, discipline −20, loses
items (`handleItemLoss`), `lives − 1` (at 0, `remainingLifetime = 0`) and jumps
to section 0x4DE of script 0. In all cases the clock advances 20
minutes (`advanceBattleTime`, `tamer.c:848`) and PStat 0xFF stores the result.

### Tournaments (arena)

**Registration** (`DGET_REL`, `dget.c`; opcode `CALL_ROUTINE 18`): the
calendar is `TOURNAMENT_SCHEDULE[day % 30][6]` (`script_common.c:564`, cup
FF = gap); 5 days from today are shown, but you can only register in
today's column (until 10:00) or tomorrow's (`dget.c:113-132`).
Each cup is filtered with `isTournamentEnabled` (`:326`): section 10
of the map script (`getCupDataJumpTable(10, cup)`, five entries per
cup: 0 text, 1 requirements `{minimum recruited species, minimum cups,
type}`, 2 «overlevel» list, 3 eligible list, 4 rivals list);
«recruited» = trigger 200 + id. Bit 7 (eligible) if the partner's species
is in list 3, bit 6 («fair»/overlevel, `TRIGGER_40`) if it is in list 2.
Confirming writes PStat 3 (cup), PStat 2 (day; `| 0x80` if it is for tomorrow),
PStat 4 (species) and triggers 37, 38, 39. `updateTournamentRegistration`
(`tournament.c:42`): it is cancelled if the partner changes species; from
12:00 and again from 20:00 it calls section 0x4D9 of script 0
(triggers 38/39, once each); if the day changes or it passes 23:01 it calls
0x4DA and clears the registration; with bit 7 (for tomorrow) it does nothing
until something clears that bit (not seen here). Cups: 0–5 Grade D, C, B, A,
S, R; 6–10 Version 1–4 and 0; 11–17 Fire, Grapple, Thunder Wind, Cool, Nature,
Metalic, Filth; 18–22 Dino, Wing, Animal, Human, Beetle (`TOURNAMENT_NAMES`).

**Startup** (`startTournament`, `utils2.c:566`; opcode `CALL_ROUTINE 6`):
rivals = the cup's list 4 filtered by recruited ones (the Beetle Cup, 22, uses
the whole list; an empty list → all species 0–111 recruited). Exactly 7
are used as is; fewer, it is filled with random repeats; more, the
partner's species is removed and 7 distinct ones are drawn. `STD_tournamentMain`
(`std_setup.c:504`) remaps 64→54, 63→48, 65→42 (Gigadramon→Megadramon,
Panjyamon→Leomon, MetalEtemon→Etemon: no arena model `[inferred]`),
picks arena 1 (`B_TOGI`, Beetle Land) if `CURRENT_SCREEN == 0x6A`, otherwise
arena 0 (`T_TOGI`; the `DGET` registration is loaded on the `ARENA_MAPS` maps
208/223, Arena Lobby), loads the grade TIM (`STD_GRADES[cup]`) and builds the
bracket (`STD_setupParticipants`, `std_main.c:3173`): 8 slots, the player in
a random one, the rest of the bracket is **simulated** with `STD_WIN_CHANCES[level A −
3][level B − 3]` (A wins: Rookie 50/20/5 %, Champion 80/50/15 %, Ultimate
95/85/50 %). 3 matches are played (`STD_runMatch`) against the rival in your
pairing, the winner of the neighbouring pairing and the one from the other half; the tournament
stops on a loss. It returns the number of matches won (3 = champion);
`startTournament` counts `TOURNAMENTS_WON++` and sets trigger `15 + cup` if
it is 3 (2 for cup 5), otherwise `TOURNAMENTS_LOST++`; `TOURNAMENT_WINS +=
won`; PStat 0xFF = won.

**Rivals** (`STD_initializeOpponent`, `std_setup.c:266`): base `B =
STD_OPPONENT_BASE_STATS[cup]` = D 100, C 150, B 200, A 250, S 300, R 0,
Version 200, element cups (11–21) 250, Beetle 350. Each stat = `B ·
(1 ± 0–30 %)`, HP and MP = `10·B · (1 ± 0–30 %)`, and everything × 1 (Rookie), × 2
(Champion) or × 2.5 (Ultimate); caps 999 / 9999; HP and MP full. Techniques:
3 at random among the species' ones whose cost (`mpCost·3`) ≤ MP/10, no
finishers; slot 3 = the species' first finisher (the 10 % draw
at `:370` is overwritten at `:374`, dead code). `movesPrio` fixed 30/30/30/0
(`std_main.c:4036`); `chargeMode` 2 with 10 %, otherwise 0/1 (`:4131`).

**Combat** (`STD_combatMain`, `std_main.c:5291`): same loop and same
formulas (`STD_calculateDamage`, `:5676`, is byte for byte the BTL one;
`STD_applyPartnerStatsToFighter`, `:5622`, is the hit chance). Differences:
`FLEE_DISABLED[0] = 1` (no Run), menu by brains with
`STD_BRAIN_TO_COMMAND_MAP = {2,3,4,5,6}` (Finisher, Your Call, +Attack,
+Moderate, +Distance, +Defensive; ≥ 500: Finisher, Defensive, Distance,
techniques, Your Call), a single enemy, dynamic camera, and the **timer**:
`STD_TIMER = 99`, −1 every 20 ticks while nobody is down (`:2662`). End
(`STD_checkEndCondition`, `:3747`): rival down → 1; partner down → −1
(both → 2); timer at 0 → whoever has **taken less damage** wins
(`STD_DAMAGE = starting HP − HP`), equal → 2. `STD_deinitializeCombat`
(`:4233`): 2 (draw) returns −1, that is, **draw = defeat**; after each
match the partner recovers 20 % of HP and MP (`:4296`) and its initial
stats. There are no bits, items, stat gains or learning in the arena
(no `handleBattleEndBox`): the prize is given by the map script on return
(PStat 0xFF, cup triggers).

**Medals** (`checkTournamentMedalConditions`, `tournament.c:168`; opcode
`CALL_ROUTINE 22`): the 6 grade cups → medal 0; the 5 Version cups → 1; the
7 element cups → 2; Dino/Wing/Animal/Human → 3; `TOURNAMENT_WINS ≥ 100` → 4;
the 66 cards and having finished the game → medal 12.

## Useful writes

Readings of the code for driving a battle from a debugger or an emulator's memory writes (how to do that:
[../developing.md](../developing.md)). Inside a battle `GAME_STATE` (`0x80134F0A`) is 1. The battle copies its data at
the start (`INITIAL_COMBAT_STATS`) and restores it at the end.

| Goal | Write | Notes |
|---|---|---|
| set an enemy's HP | enemy *j* (1–3) is `ENTITY_TABLE[entityIds[j]]` (`entityIds` at `0x8013DCAC`); its block is `0x80155828 + (id − 2)·0x68`; `currentHP` at `+0x4C`, max at `+0x48` | also clear `fighter[j].hpDamageBuffer` (`0x8013D640 + j·0x168 + 0x2E`) or the pending damage still kills it |
| win | `currentHP = 0` on every enemy | `BTL_tickEnemyAI` knocks each down and the victory sequence with rewards follows. `FLEE_TIMER` (`0x80134D68`) = 0x29 without having chosen Run should also end the battle as a victory, since `bufferedCommand ≠ 1` |
| flee, even from a boss | `bufferedCommand[0]` (`0x8013DC90`) = 1 | writing `currentCommand` (`0x8013DC8E`) does not last: it is copied from `bufferedCommand` every tick. Ends after about 2 s with result 0 |
| lose | partner HP (`0x801557F4`) = 0 | then 171 ticks with no item thrown |
| a partner that takes no damage | no flag exists (`PROTECTED` only blocks statuses); write 0 to `fighter[0].hpDamageBuffer` (`0x8013D66E`) every frame, or make `BTL_calculateDamage` (`0x8005BEB8`, with BTL loaded) return 1 | Def 999 keeps normal hits at 1 but finishers ignore Def and poison continues. Making the partner sick (condition bit 0x40) makes every hit land in both directions |
| finisher ready | `finisherProgress` (`0x8013D65A`) = `finisherGoal` (i16 at `0x8013D658`); `finisherChargeup` (`0x8013DCA8`) = 80 during the charge for ×2 | only if slot 3 (`0x801557EF`) holds a finisher; id 0xFF indexes garbage |
| fight a chosen Digimon | PStat 0xFA (`0x801BE12B`) = 1 and PStats 0xFB–0xFD (`0x801BE12C–2E`) = entity ids (2–9) before `START_BATTLE`, or edit the NPC's stats in the map | the species must be loaded on the map (model and animations); changing `type` at `+0x00` changes stats/techniques/element but not the model. Outside battle, an NPC's block (`+0x38..+0x4F`) can be changed before bumping into it |
| tournament state (outside battle) | cup PStat 3 (`0x801BE034`), day PStat 2 (`0x801BE033`), species PStat 4 (`0x801BE035`); triggers 37–39 = bits 5–7 of `0x801BDFD1` | the same byte holds triggers 32–36. Cup won: trigger `15 + cup` → byte `0x801BDFCD + (15+cup)/8`, bit `(15+cup) % 8`. `TOURNAMENTS_WON` `0x80134FCC`, `TOURNAMENT_WINS` `0x80134FCE` (≥ 100 for medal 4) |
| end an arena match | `STD_TIMER` (`0x80135110`) = 1 leaves one second | the less-damage rule decides; `STD_DAMAGE` is recomputed on expiry, so writing it has no effect. The rival's HP at 0 (`NPC_ENTITIES[i]`, `i` = match number, `+0x4C`) wins the match |

## Notes

- Grade R (cup 5): `STD_OPPONENT_BASE_STATS[5] = 0` (rivals would have 0 HP) and `startTournament` counts it won
  with 2 wins. It looks unused.
- Winning the Beetle Cup (22) sets trigger 15 + 22 = 37, which is also `TRIGGER_TOURNAMENT_REGISTERED`
  (`utils2.c:653-663` clears it just before).
- The per-cup lists (text, requirements, eligible, overlevel, rivals) live in section 10 of the arena script in
  `DG.SCN`, not in the executable; so does the meaning of each `TOURNAMENT_SCHEDULE` day.
- The ×1.2 in the hit chance against a standing defender (anim 0x21/0x22) is applied to `x`, so it **reduces** the
  chance of hitting someone who stands still (`battle_main.c:1960`); counter-intuitive, but that is the code.
- The EFE effect interpreter (`battle_effect.c`) is outlined in [engine.md](engine.md#effects-efedatefe).
