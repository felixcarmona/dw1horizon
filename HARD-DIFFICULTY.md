# HARD difficulty and high Defense

HARD is a saved, opt-in combat setting. Permanent growth, MP, bits, drops and
reward inputs retain their existing rules. EASY and NORMAL retain their
existing damage multipliers; ordinary techniques now have diminishing Defense
returns above 999 in every arena, including two-player VS.

## Rules and compatibility

Owned source: `content/tables/battle-formulas.json`, encoded by `tools/balance.py`.

| HARD rule | Factor |
| --- | ---: |
| Enemy maximum/current HP | 110% |
| Enemy Offense / Brains | 150% |
| Enemy Defense | 105% |
| Enemy Speed | 115% |
| Enemy finisher power | 150% |
| Partner direct technique / finisher damage | 95% |
| Enemy empty move-slot idle weight | 25%, minimum 1 |
| Enemy damage to partner | At least 15% of the same hit against Defense zero |

The factors cover all actual enemies in wild, boss, story and tournament fights.
Friendly scene actors and the partner are excluded. Analogman is a scene actor;
his encounter's fighting Digimon receive the factors. Tournament scaling occurs
after its ordinary encounter generator caps. Higher Brains feeds existing target
and buff priorities; there is no new search or tactical subsystem. Idle scaling
only changes empty technique slots. HP caps at 30000, other stats at 9999.

Field encounters snapshot original stats before scaling; rewards use that
snapshot, and battle teardown restores original maximum HP and other stats.
Difficulty never compounds across repeated fights. Poison and scripted damage
retain their existing rules. VS uses the Defense curve, without HARD scaling.

For ordinary techniques, keep the existing formula until raw Defense exceeds
999 **and effective Defense exceeds max(999, Offense)**. Counter transforms
Defense first. Beyond that boundary, multiply ordinary power at the boundary by
**1000 / (1000 + excess effective Defense)**, truncating before elements and
variance. Thus each additional point has decreasing effect, without artificially
strengthening Defense against an attacker whose Offense still exceeds it.
Missing/nonpositive curve parameters disable the extension. Inside the original
raw Defense range, signed arithmetic, random calls and rounding stay exact.
The positive Offense tail from the earlier attack-curve patch is unchanged.

HARD compares the resulting enemy hit with 15% of a zero-Defense hit using the
same technique, elements and random roll, rounded up to a whole damage point. For blocked melee chip, carry the same zero-Defense comparator through the
actual block roll and round its minimum up again after block truncation. Finishers already ignore Defense, so naturally satisfy this floor;
their power boost still applies. Partner finishers retain their existing linear
Offense formula. The minimum of one and existing damage caps
remain the final bounds. The curve does not remove original one-damage cases
within 999: those already occur when Defense exceeds Offense by at least 500.

A neutral power-586 hit at initial enemy Offense 999, with a 100% roll:

| Partner Defense | NORMAL before | NORMAL now | HARD (Offense 1498) |
| --- | ---: | ---: | ---: |
| Normal late: 800 | 819 | 819 | 1338 |
| Strong: 1500 | 1 | 390 | 584 |
| Maximum: 9999 | 1 | 58 | 235 |

NORMAL's maximum-Defense result is 3.96% of its 1464 zero-Defense hit. These are
controlled arithmetic probes, not entire fights. Buffs, technique elements,
blocking, accuracy, status and finisher readiness affect live results.

The fixed-factor target remains the normal late 800-Offense/800-Defense partner:
with unbuffed opponents, Thunder Justice and an assumed three seconds per landed
hit, final/repeat Machinedramon move from the original 51/72-second NORMAL
budgets to 63/90 seconds on HARD (+24%/+25%). These are controlled hit budgets;
the live trials below include natural AI, buffs, accuracy and animation time.
Training remains beneficial, and no enemy follows the partner's level or stats.

## Save and UI

The existing option byte 10 remains NORMAL=0, EASY=1 and adds HARD=2. Missing or
invalid legacy values default to NORMAL; saved EASY remains EASY. Both the title
header and tagged-save copy use the byte. Explicit title choices keep their
existing precedence over Continue. Record lengths and save allocation do not
grow; an older reader treats HARD as NORMAL.

The existing DIFFICULTY row cycles EASY / NORMAL / HARD. Its third value reuses
unused language-row texture/width storage. All nine languages have an owned
translation. The eight original-hardware languages support new and original
fonts; Chinese retains its existing 8 MB / dedicated-font requirement.

## Verification

Live traces use the interpreter with the debugger enabled; CPU execution
breakpoints require that configuration ([debugging reference](https://pcsx-redux.consoledev.net/Lua/playbook-localizing-bugs/)).

Native tests compile the actual BTL/STD/VS damage functions and helpers with
undefined-behavior sanitization: 5,497,632 damage comparisons plus 630,021
blocked-floor property checks. `tools/test_cheats.py` checks saved values,
legacy lengths, headers and explicit-choice precedence. The numeric audit is
reproducible with `python3 tools/hard_audit.py --out build/hard-audit`.

Live trials use a native MetalEtemon with controlled partner attributes, legal
equipped techniques and its native finisher. Wild fights use Megaton Punch;
boss fights use Buster Dive. Both include Muscle Charge and War Cry. Enemy
stats, accuracy, rolls and outcomes are not forced; AI may buff, miss or block.
Wild trials use Auto without items. Story trials issue five early Muscle Charge
orders, then Buster Dive, allow native finisher input, and consume carried large
recoveries below 75% HP. The item helper enters the native throw path at a safe
battle boundary; item-menu selection time is excluded. It never writes battle HP.
Combat duration comes from the actual 20 Hz battle
counter, rather than interpreter wall time. A defeat is a time to defeat, not a
boss time to kill. Trials are not in RNG lockstep and are not a distribution of
player completion times. Numeric projections remain separate from observations.
No physical PlayStation test is claimed.

The old image is checked against its preserved executable and combat overlays
before using it for the NORMAL-before column. The new and old images use the
same encounter data. Reproduce the live checks with a matching built image and
executable:

```
python3 tools/dev/playtest/hard_battles.py build/stat-softcap.cue --exe build/stat-softcap/exe/SLUS_010.32
python3 tools/dev/playtest/hard_options.py build/stat-softcap.cue --exe build/stat-softcap/exe/SLUS_010.32
python3 tools/hard_evidence.py
python3 tools/hard_charts.py
```

The emulator requires its bundled shared-library directory on `LD_LIBRARY_PATH`
and an X server; headless runs use `xvfb-run -a`. The playtests explicitly choose
the bundled BIOS, interpreter, debugger and 2 MB mode. The language/font tour
also checks EASY → NORMAL → HARD cycling through actual input and a game-written
save followed by a cold boot and Continue.

## Real 2 MB measurements

One trial per primary cell. Every primary trial below ended in victory. Each
cell gives **combat seconds; applied direct damage range (landed hit count)**.
Damage includes enemy finishers and blocks. The three runs have independent
natural rolls. R is the number of large recoveries consumed in the story fight.

| Encounter | Partner | NORMAL before | NORMAL now | HARD |
| --- | --- | --- | --- | --- |
| Guardromon, FACT02 | late | 34.55s; 178–202 (2) | 33.95s; 127–202 (3) | 36.95s; 449–537 (2) |
| Guardromon, FACT02 | strong | 32.20s; 1 (2) | 27.85s; 57 (1) | 39.65s; 195–243 (2) |
| Guardromon, FACT02 | max | 35.75s; 1 (2) | 35.45s; 9–10 (2) | 40.70s; 129–185 (3) |
| Story Machinedramon, MGEN99 | late | 101.80s /4R; 542–2139 (10) | 86.55s /2R; 108–1190 (7) | 133.60s /7R; 875–5055 (12) |
| Story Machinedramon, MGEN99 | strong | 70.40s /0R; 1 (6) | 84.45s /1R; 258–685 (10) | 86.30s /2R; 416–1027 (12) |
| Story Machinedramon, MGEN99 | max | 54.20s /0R; 1 (5) | 113.85s /0R; 38–4047 (14) | 57.40s /0R; 156–413 (7) |
| Repeat Machinedramon, ICSA08 | max | 68.65s; 1 (6) | 113.25s; 87–7402 (7) | 94.20s; 332–443 (4) |

Late = 800 in all four attributes, HP/MP 8005/9520; strong = 1500 and
15000/15000; max = 9999 and 30000/30000. Temporary buffs execute normally.
The primary boss is spawned and configured by the actual ending scene, then
measured from native battle entry. It has a different move set from the repeat
boss. The extra repeat row uses Auto, without items or finisher input.

The late partner won the story fight on HARD with seven recoveries and a minimum
observed 2075 HP; the strong partner used two, and the maximum partner used none.
The 15% floor is retained. Maximum Defense's ordinary story-boss hits now deal
38–102 on NORMAL and 156–413 on HARD; the 4047 NORMAL hit was a finisher.
In the repeat fight, ordinary maximum-Defense damage rose from 1 to 87–122 on
NORMAL and 332–443 on HARD. NORMAL also received a 7402-point finisher; HARD
received none in this trial and won with 28384 HP. Faster HARD times in these
maximum-partner trials do not establish a lower expected TTK: independent AI,
buffs, misses and finisher timing dominate a single observation.

All captured current HARD incoming hits are checked against the **actual native
C zero-Defense comparator**, including the actual blocked-melee roll. Every
applied direct hit meets the rounded-up 15% minimum. Setup also checks scaled
stats, original reward inputs, restoration and absence of compounding. Neither
enemy stats nor damage, accuracy, RNG or outcome is forced during combat.

Earlier exploratory repeat-boss trials exposed a separate post-game risk: the
8005-HP HARD partner can lose to a finisher above 11000 even while using legal
recovery items. The no-item late and strong Auto partners also lost on the old
NORMAL image. In the late HARD trial, ordinary hits were 82.07–97.41% of their
same-roll zero-Defense values, so the 15% floor did not raise them. Reducing that
floor cannot resolve a finisher one-shot, since finishers ignore Defense. These
exploratory losses are retained in local logs; the primary table proves story
boss winnability, not universal first-life post-game winnability.

Portable evidence: [live CSV](docs/data/hard-difficulty/live-fights.csv),
[damage and action traces](docs/data/hard-difficulty/live-fights.json), and
[build/UI/selftest measurements](docs/data/hard-difficulty/verification.json).
There are 18 primary before/current trials and two additional current repeat
trials. No full-life raise or physical-console run is claimed.

## Memory and build

The full nine-language build passed on the original 2 MB target. The complete
selftest passed 130 checks with no failures or skips before the final ceiling
rounding correction; affected C/curve, native link and patch-application checks
were repeated after that correction. The final image repeated all current live
fights and the game-written save/cold-boot/Continue check. Its MENU_REL is byte
identical to the build used for the 24 visually reviewed options screens. All language
executables have `main_BSS_END = 0x801ce1d8`, versus `0x801ce104` before:
+212 resident bytes, or 208 bytes less aligned heap (187888 → 187680 bytes).
All 320 archive-backed screen configurations fit; the tightest is screen 207,
with 2960 bytes remaining. Both heap checks passed without an override.

MENU_REL decreases from 54248 to 53972 bytes; its 27-sector read remains within
55296 bytes. The battle rule table grows from 328 to 350 bytes. There is no new
dynamic allocation, saved state or menu-array growth. BTL and STD each keep
one transient four-byte zero-Defense comparator in their overlay BSS, reset
on every damage calculation. Math and stat setup helpers stay
in combat code; measured resident cost also includes the options/save changes.

Built image SHA-1: `c9a635cbc35ef9aab34a72d3691c9825dccee2a5`.

## HP/MP growth

Growth is unchanged. 8005 HP and 9520 MP normalize to 800.5 and 952 on the other
stats' scale. The constructed no-chip Pukumon witness reproduces these values
with evolution and 54 ordinary training sessions; it is not a replay of the
reported save or a complete first-life care schedule. The source-by-source
finding and proposal to retain growth are in [STAT-SOFTCAP.md](STAT-SOFTCAP.md).
